"""ArchPat's proposal IR. These are NOT copies of upstream URT/urievents contracts."""
from __future__ import annotations

from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,79}$")]
InternalIdentifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")]
Nonempty = Annotated[str, Field(min_length=1, max_length=8000)]
Interface = Literal["rest", "mcp", "shell"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class TemporalRequirement(Model):
    text: Nonempty
    timezone: str = "Europe/Warsaw"
    resolution_status: Literal["unresolved"] = "unresolved"
    owner: Literal["uritime"] = "uritime"

    @field_validator("timezone")
    @classmethod
    def check_zone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class OperationSpec(Model):
    id: Identifier
    name: Nonempty
    kind: Literal["command", "query"]
    capability: Identifier
    aggregate: Identifier
    input_urns: list[str] = Field(default_factory=list, max_length=100)
    output_urns: list[str] = Field(default_factory=list, max_length=100)
    consistency: Literal["eventual", "read_your_writes"] = "eventual"
    temporal: TemporalRequirement | None = None

    @field_validator("input_urns", "output_urns")
    @classmethod
    def check_refs(cls, values: list[str]) -> list[str]:
        import re
        for value in values:
            if not re.fullmatch(r"urn:[a-zA-Z0-9][a-zA-Z0-9-]*:[^\s]+", value):
                raise ValueError("data references must be URNs; version/digest are bound upstream")
        return values


class Constraints(Model):
    ram_budget_mb: int = Field(default=4096, ge=1, le=1048576)
    reserved_ram_mb: int = Field(default=0, ge=0, le=1048576)
    max_processes: int = Field(default=3, ge=1, le=1024)
    isolate_projection: bool = False
    independent_command_query_scaling: bool = False
    offline: bool = True
    interfaces: list[Interface] = Field(default_factory=lambda: ["rest", "mcp", "shell"], min_length=1)
    artifact_formats: list[Literal["json", "protobuf"]] = Field(default_factory=lambda: ["json", "protobuf"], min_length=1)
    required_patterns: list[Literal["cqrs", "event_sourcing", "outbox", "ports_adapters"]] = Field(
        default_factory=lambda: ["cqrs", "event_sourcing", "outbox", "ports_adapters"]
    )

    @field_validator("interfaces", "artifact_formats", "required_patterns")
    @classmethod
    def no_duplicates(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate values are not permitted")
        return values


class Weights(Model):
    ram: float = Field(default=0.35, ge=0, le=1)
    processes: float = Field(default=0.25, ge=0, le=1)
    coupling: float = Field(default=0.20, ge=0, le=1)
    change_surface: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def positive_sum(self) -> Weights:
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("at least one optimization weight must be positive")
        return self


class StorySpec(Model):
    schema_version: Literal["archpat.story/v1"] = "archpat.story/v1"
    id: Identifier
    title: Nonempty
    actor: Nonempty
    goal: Nonempty
    acceptance_criteria: list[Nonempty] = Field(min_length=1, max_length=100)
    operations: list[OperationSpec] = Field(min_length=1, max_length=50)
    constraints: Constraints = Field(default_factory=Constraints)
    weights: Weights = Field(default_factory=Weights)
    assumptions: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def distinct_ops(self) -> StorySpec:
        ids = [operation.id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("operation IDs must be unique")
        return self


class ReuseEvidence(Model):
    project: str
    path: str
    symbols: list[str] = Field(default_factory=list)
    source_sha256: str | None = None
    status: Literal["indexed_only", "source_seen", "contract_verified"] = "indexed_only"
    note: str = "Candidate only; the source API and behavioral contract require verification."


Role = Literal["actor", "adapter", "command_handler", "query_handler", "aggregate",
               "event_store", "outbox", "relay", "projector", "read_model", "temporal_service"]


class Node(Model):
    id: InternalIdentifier
    label: str
    role: Role
    capability: str
    owner: str
    process_group: str
    story_ids: list[str]
    operation_id: str | None = None
    aggregate_id: str | None = None
    deployment: Literal["local", "remote", "external"] = "local"
    interface: Interface | None = None
    service_url: str | None = None
    process_uri: str | None = None
    binding_status: Literal["unbound", "proposed", "verified"] = "unbound"
    reuse: list[ReuseEvidence] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


EdgeKind = Literal["invoke", "command", "query", "event", "read", "write", "return",
                   "depends_on", "temporal", "propose"]


class Edge(Model):
    id: InternalIdentifier
    source: str
    target: str
    kind: EdgeKind
    operation_id: str | None = None
    data_urns: list[str] = Field(default_factory=list)
    effect: Literal["none", "read", "write"] = "none"
    interface: str = "in_process"
    encoding: Literal["json", "protobuf", "object"] = "object"
    delivery: Literal["local", "at_least_once"] = "local"
    idempotent: bool = True
    transaction_group: str | None = None


class ArchitectureGraph(Model):
    schema_version: Literal["archpat.graph/v1"] = "archpat.graph/v1"
    id: InternalIdentifier
    variant: Literal["modular_monolith", "worker_split", "service_split"]
    story: StorySpec
    patterns: list[str]
    nodes: list[Node] = Field(max_length=300)
    edges: list[Edge] = Field(max_length=2500)
    provenance: dict[str, Any] = Field(default_factory=dict)


class Finding(Model):
    severity: Literal["error", "warning"]
    code: str
    subject: str
    message: str


class ValidationReport(Model):
    findings: list[Finding] = Field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [item for item in self.findings if item.severity == "error"]

    @property
    def valid(self) -> bool:
        return not self.errors


class Metrics(Model):
    ram_mb_estimate: int
    reserved_ram_mb: int
    total_ram_mb_estimate: int
    process_count: int
    cross_process_edges: int
    change_surface_prior: int
    evidence: Literal["heuristic_unmeasured"] = "heuristic_unmeasured"


class Candidate(Model):
    id: str
    graph: ArchitectureGraph
    metrics: Metrics
    validation: ValidationReport
    rejection_reasons: list[str]
    score: float | None
    score_terms: dict[str, float]
    feasible: bool


class SynthesisResult(Model):
    schema_version: Literal["archpat.synthesis/v1"] = "archpat.synthesis/v1"
    status: Literal["best_in_catalog", "no_feasible_catalog_candidate"]
    selected_id: str | None
    pareto_ids: list[str]
    input_sha256: str
    search_scope: Literal["three_explicit_cqrs_es_templates"] = "three_explicit_cqrs_es_templates"
    objective_definition: str = "weighted_normalized_priors_v1; smaller is better"
    execution_ready: Literal[False] = False
    assumptions: list[str]
    candidates: list[Candidate]


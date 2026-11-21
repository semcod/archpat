"""ARP-004: Versioned Architecture IR v2 with ecosystem profile bindings, provenance, migration, and semantic hashing.

Design rules:
- Strictly additive over ``archpat.graph/v1`` (lossless migration from v1 and explicit downgrade reporting).
- Separates user input, LLM inference, deterministic rules, and runtime observations via ``ProvenanceRecord``.
- Enforces upstream URI grammar boundaries discovered in ARP-002/ARP-003 without overwriting upstream contracts.
- Preserves unknown upstream fields in ``extensions`` rather than silently dropping them.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import Field, field_validator

from .models import (
    ArchitectureGraph,
    Edge,
    Finding,
    InternalIdentifier,
    Model,
    Node,
    StorySpec,
    ValidationReport,
)

EvidenceLevel = Literal[
    "proposed",
    "indexed_only",
    "source_verified",
    "contract_verified",
    "integration_verified",
]
ProvenanceSourceKind = Literal[
    "user_input",
    "llm_inference",
    "deterministic_rule",
    "source_index",
    "runtime_observation",
]
PolycellEffect = Literal[
    "pure",
    "read_data",
    "write_data",
    "local_write",
    "external",
    "credential_use",
]

# Verified upstream regexes from ARP-002 & ARP-003 (evidence/source-lock.json)
URIEVENTS_POA_URI_RE = re.compile(r"^(poa|urn:poa):[a-z0-9][a-z0-9._:/-]*#(v[0-9]+|[0-9]+)$")
SERVICE_HTTP_URL_RE = re.compile(r"^https?://[^\s]+$")
URT_TEMPORAL_REF_RE = re.compile(r"^(urt:v1:|urn:uuid:)[A-Za-z0-9._:/?=&%-]+$")
POLYCELL_CELL_URN_RE = re.compile(r"^urn:wm:cell:[a-z0-9_-]+:[a-z0-9_.]+:v[0-9]+$")
POLYCELL_PROCESS_REF_RE = re.compile(r"^poa://[^\s]+$")
FORGE_OPERATION_URI_RE = re.compile(r"^(?:urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[a-z][a-z0-9+.-]*://[^\s?#]+)$")
UUID_URN_RE = re.compile(r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
NL_RFC3986_URI_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:[^\s]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceRecord(Model):
    source_kind: ProvenanceSourceKind
    producer: str = Field(min_length=1, max_length=256)
    evidence_level: EvidenceLevel = "proposed"
    revision: str | None = None
    content_sha256: str | None = None
    note: str = ""

    @field_validator("content_sha256")
    @classmethod
    def check_sha256(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("content_sha256 must be a 64-character lowercase hex digest")
        return value


class UritimeBinding(Model):
    poa_uri: str
    service_url: str | None = None
    temporal_ref: str | None = None
    owner: Literal["uritime", "autodo"] = "uritime"
    contract_schema: Literal["ur.command-envelope/v1", "ur.timeline-query/v1", "ur.operation-descriptor/v1"] = (
        "ur.command-envelope/v1"
    )

    @field_validator("poa_uri")
    @classmethod
    def check_poa_uri(cls, value: str) -> str:
        if not URIEVENTS_POA_URI_RE.fullmatch(value):
            raise ValueError("uritime.poa_uri must match upstream ur-cqrs-v1 poaUri grammar (urn:poa:...#vN)")
        return value

    @field_validator("service_url")
    @classmethod
    def check_service_url(cls, value: str | None) -> str | None:
        if value is not None and not SERVICE_HTTP_URL_RE.fullmatch(value):
            raise ValueError("uritime.service_url must be an http(s) URL")
        return value

    @field_validator("temporal_ref")
    @classmethod
    def check_temporal_ref(cls, value: str | None) -> str | None:
        if value is not None and not URT_TEMPORAL_REF_RE.fullmatch(value):
            raise ValueError("uritime.temporal_ref must start with urt:v1: or urn:uuid:")
        return value


class PolycellBinding(Model):
    cell_urn: str
    process_ref: str | None = None
    cell_schema: Literal["wellmanifest.polycell.cell/v1"] = "wellmanifest.polycell.cell/v1"
    owner_lang: Literal["python", "ts", "rust"] = "python"
    effects: list[PolycellEffect] = Field(default_factory=lambda: ["pure"])

    @field_validator("cell_urn")
    @classmethod
    def check_cell_urn(cls, value: str) -> str:
        if not POLYCELL_CELL_URN_RE.fullmatch(value):
            raise ValueError("polycell.cell_urn must match ^urn:wm:cell:<ns>:<name>:v<major>$")
        return value

    @field_validator("process_ref")
    @classmethod
    def check_process_ref(cls, value: str | None) -> str | None:
        if value is not None and not POLYCELL_PROCESS_REF_RE.fullmatch(value):
            raise ValueError("polycell.process_ref must start with poa://")
        return value


class ForgeBinding(Model):
    process_uri: str
    project_urn: str | None = None
    snapshot_id: str | None = None
    qualification_authority: Literal["decision_only"] = "decision_only"

    @field_validator("process_uri")
    @classmethod
    def check_process_uri(cls, value: str) -> str:
        if not FORGE_OPERATION_URI_RE.fullmatch(value):
            raise ValueError("forge.process_uri must be a urn:uuid:... or scheme://host/path URI")
        return value

    @field_validator("project_urn")
    @classmethod
    def check_project_urn(cls, value: str | None) -> str | None:
        if value is not None and not UUID_URN_RE.fullmatch(value):
            raise ValueError("forge.project_urn must be a urn:uuid:... identifier")
        return value

    @field_validator("snapshot_id")
    @classmethod
    def check_snapshot_id(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("forge.snapshot_id must be a 64-character lowercase hex digest")
        return value


class NlUriBinding(Model):
    action_uri: str
    provenance_source: Literal["nl_deterministic", "llm_gbnf", "direct_dsl"] = "direct_dsl"

    @field_validator("action_uri")
    @classmethod
    def check_action_uri(cls, value: str) -> str:
        if not NL_RFC3986_URI_RE.fullmatch(value):
            raise ValueError("nl_uri.action_uri must be a valid RFC 3986 URI or URN")
        return value


class ProfileBindings(Model):
    uritime: UritimeBinding | None = None
    polycell: PolycellBinding | None = None
    forge: ForgeBinding | None = None
    nl_uri: NlUriBinding | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class NodeV2(Model):
    node: Node
    evidence_level: EvidenceLevel = "proposed"
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    profiles: ProfileBindings = Field(default_factory=ProfileBindings)


class EdgeV2(Model):
    edge: Edge
    evidence_level: EvidenceLevel = "proposed"
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)


class CriterionLink(Model):
    criterion_index: int = Field(ge=0)
    criterion_text: str = Field(min_length=1, max_length=8000)
    operation_ids: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel = "proposed"


class ArchitectureIRv2(Model):
    schema_version: Literal["archpat.ir/v2"] = "archpat.ir/v2"
    migrated_from: Literal["archpat.graph/v1", "native_v2"] = "archpat.graph/v1"
    id: InternalIdentifier
    variant: Literal["modular_monolith", "worker_split", "service_split"]
    story: StorySpec
    patterns: list[str]
    nodes: list[NodeV2] = Field(max_length=300)
    edges: list[EdgeV2] = Field(max_length=2500)
    criteria_links: list[CriterionLink] = Field(default_factory=list)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    legacy_provenance: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)
    execution_ready: Literal[False] = False

    def to_v1_graph(self) -> ArchitectureGraph:
        return ArchitectureGraph(
            id=self.id,
            variant=self.variant,
            story=self.story,
            patterns=list(self.patterns),
            nodes=[item.node for item in self.nodes],
            edges=[item.edge for item in self.edges],
            provenance=dict(self.legacy_provenance),
        )


def semantic_hash(ir: ArchitectureIRv2) -> str:
    """Deterministic SHA-256 over semantic IR content, invariant to node/edge/link ordering."""
    payload = {
        "schema_version": ir.schema_version,
        "id": ir.id,
        "variant": ir.variant,
        "story": ir.story.model_dump(mode="json"),
        "patterns": sorted(ir.patterns),
        "nodes": sorted(
            [item.model_dump(mode="json") for item in ir.nodes],
            key=lambda x: x["node"]["id"],
        ),
        "edges": sorted(
            [item.model_dump(mode="json") for item in ir.edges],
            key=lambda x: x["edge"]["id"],
        ),
        "criteria_links": sorted(
            [item.model_dump(mode="json") for item in ir.criteria_links],
            key=lambda x: x["criterion_index"],
        ),
        "extensions": ir.extensions,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def migrate_v1_to_v2(
    graph: ArchitectureGraph,
    *,
    profile_bindings: dict[str, ProfileBindings] | None = None,
    evidence_level: EvidenceLevel = "proposed",
    extra_provenance: list[ProvenanceRecord] | None = None,
) -> ArchitectureIRv2:
    """Losslessly migrate an ``archpat.graph/v1`` proposal into ``archpat.ir/v2``."""
    bindings = profile_bindings or {}
    unknown_binding_targets = set(bindings) - {n.id for n in graph.nodes}
    if unknown_binding_targets:
        raise ValueError(f"Profile bindings reference unknown nodes: {sorted(unknown_binding_targets)}")

    story_sha = graph.provenance.get("story_sha256")
    base_prov = [
        ProvenanceRecord(
            source_kind="user_input",
            producer="archpat.story/v1",
            evidence_level="proposed",
            content_sha256=story_sha if isinstance(story_sha, str) and SHA256_RE.fullmatch(story_sha) else None,
            note=f"Story {graph.story.id}",
        ),
        ProvenanceRecord(
            source_kind="deterministic_rule",
            producer=str(graph.provenance.get("generator", "archpat/0.1.0")),
            evidence_level=evidence_level,
            note=f"Migrated from archpat.graph/v1 variant={graph.variant}",
        ),
    ]
    if extra_provenance:
        base_prov.extend(extra_provenance)

    nodes_v2: list[NodeV2] = []
    for n in graph.nodes:
        node_level: EvidenceLevel = evidence_level
        if n.binding_status == "verified":
            node_level = "contract_verified"
        elif n.reuse:
            statuses = {r.status for r in n.reuse}
            if "contract_verified" in statuses:
                node_level = "contract_verified"
            elif "source_seen" in statuses:
                node_level = "source_verified"
            else:
                node_level = "indexed_only"
        node_prov = [
            ProvenanceRecord(
                source_kind="deterministic_rule",
                producer="archpat.synthesis",
                evidence_level=node_level,
                note=f"Role={n.role} owner={n.owner}",
            )
        ]
        nodes_v2.append(
            NodeV2(
                node=n.model_copy(deep=True),
                evidence_level=node_level,
                provenance=node_prov,
                profiles=bindings.get(n.id, ProfileBindings()).model_copy(deep=True),
            )
        )

    edges_v2 = [
        EdgeV2(
            edge=e.model_copy(deep=True),
            evidence_level=evidence_level,
            provenance=[
                ProvenanceRecord(
                    source_kind="deterministic_rule",
                    producer="archpat.synthesis",
                    evidence_level=evidence_level,
                    note=f"Edge kind={e.kind}",
                )
            ],
        )
        for e in graph.edges
    ]

    criteria_links = _auto_link_criteria(graph)
    return ArchitectureIRv2(
        migrated_from="archpat.graph/v1",
        id=graph.id,
        variant=graph.variant,
        story=graph.story.model_copy(deep=True),
        patterns=list(graph.patterns),
        nodes=nodes_v2,
        edges=edges_v2,
        criteria_links=criteria_links,
        provenance=base_prov,
        legacy_provenance=dict(graph.provenance),
    )


def _auto_link_criteria(graph: ArchitectureGraph) -> list[CriterionLink]:
    """Attach structural candidate links for each acceptance criterion without claiming verification."""
    links: list[CriterionLink] = []
    commands = [op.id for op in graph.story.operations if op.kind == "command"]
    queries = [op.id for op in graph.story.operations if op.kind == "query"]
    temporal_ops = [op.id for op in graph.story.operations if op.temporal is not None]
    node_ids_by_role: dict[str, list[str]] = {}
    for n in graph.nodes:
        node_ids_by_role.setdefault(n.role, []).append(n.id)

    for idx, text in enumerate(graph.story.acceptance_criteria):
        low = text.casefold()
        op_ids: list[str] = []
        n_ids: list[str] = []
        if any(k in low for k in ("czas", "time", "urt", "uritime", "deadline", "przed", "po ")):
            op_ids.extend(temporal_ops or commands)
            n_ids.extend(node_ids_by_role.get("temporal_service", []))
        if any(k in low for k in ("replay", "odbudow", "histori", "event", "zdarze", "projekcj")):
            n_ids.extend(node_ids_by_role.get("event_store", []))
            n_ids.extend(node_ids_by_role.get("projector", []))
            n_ids.extend(node_ids_by_role.get("read_model", []))
        if any(k in low for k in ("zapytan", "query", "odczyt", "wynik", "feedback", "retriev", "inspect")):
            op_ids.extend(queries)
            n_ids.extend(node_ids_by_role.get("query_handler", []))
            n_ids.extend(node_ids_by_role.get("read_model", []))
        if any(k in low for k in ("komend", "command", "idempoten", "ponowien", "artefakt", "urn", "wersj", "submit")):
            op_ids.extend(commands)
            n_ids.extend(node_ids_by_role.get("command_handler", []))
            n_ids.extend(node_ids_by_role.get("aggregate", []))
            n_ids.extend(node_ids_by_role.get("event_store", []))
        if not op_ids and not n_ids:
            op_ids = [op.id for op in graph.story.operations]
            n_ids = [n.id for n in graph.nodes if n.role in {"command_handler", "query_handler"}]
        links.append(
            CriterionLink(
                criterion_index=idx,
                criterion_text=text,
                operation_ids=sorted(set(op_ids)),
                node_ids=sorted(set(n_ids)),
                evidence_level="proposed",
            )
        )
    return links


def downgrade_v2_to_v1_with_report(ir: ArchitectureIRv2) -> tuple[ArchitectureGraph, dict[str, Any]]:
    """Convert IR v2 back to v1 and explicitly report any v2-only fields that cannot fit in v1."""
    dropped_profiles = [
        item.node.id
        for item in ir.nodes
        if any(
            [
                item.profiles.uritime is not None,
                item.profiles.polycell is not None,
                item.profiles.forge is not None,
                item.profiles.nl_uri is not None,
                bool(item.profiles.extensions),
            ]
        )
    ]
    report = {
        "lossless_for_v1_fields": True,
        "v2_only_profiles_omitted_in_v1": sorted(dropped_profiles),
        "v2_criteria_links_omitted_in_v1": len(ir.criteria_links),
        "v2_extensions_omitted_in_v1": sorted(ir.extensions.keys()),
    }
    return ir.to_v1_graph(), report


def validate_ir_v2(ir: ArchitectureIRv2) -> ValidationReport:
    """Validate both underlying v1 structural invariants and v2 IDs, references, and provenance."""
    from .validation import validate_graph

    v1_report = validate_graph(ir.to_v1_graph())
    findings: list[Finding] = list(v1_report.findings)

    def add(code: str, subject: str, message: str, severity: Literal["error", "warning"] = "error") -> None:
        findings.append(Finding(code=code, subject=subject, message=message, severity=severity))

    node_ids = [item.node.id for item in ir.nodes]
    node_set = set(node_ids)
    op_set = {op.id for op in ir.story.operations}

    if len(node_ids) != len(node_set):
        add("ir_v2_duplicate_node", ir.id, "Duplicate node IDs in ArchitectureIRv2.")

    edge_ids = [item.edge.id for item in ir.edges]
    if len(edge_ids) != len(set(edge_ids)):
        add("ir_v2_duplicate_edge", ir.id, "Duplicate edge IDs in ArchitectureIRv2.")

    for link in ir.criteria_links:
        if link.criterion_index >= len(ir.story.acceptance_criteria):
            add(
                "dangling_criterion_index",
                f"criterion:{link.criterion_index}",
                "CriterionLink index exceeds story.acceptance_criteria length.",
            )
        for oid in link.operation_ids:
            if oid not in op_set:
                add(
                    "dangling_criterion_operation",
                    f"criterion:{link.criterion_index}",
                    f"CriterionLink references unknown operation '{oid}'.",
                )
        for nid in link.node_ids:
            if nid not in node_set:
                add(
                    "dangling_criterion_node",
                    f"criterion:{link.criterion_index}",
                    f"CriterionLink references unknown node '{nid}'.",
                )

    for item in ir.nodes:
        # Honest boundary: claiming integration_verified without provenance record is an error
        if item.evidence_level in {"contract_verified", "integration_verified"} and not item.provenance:
            add(
                "unsubstantiated_evidence_level",
                item.node.id,
                f"Node declares evidence_level='{item.evidence_level}' without provenance records.",
            )
        # Polycell pure cell cannot claim write_data or external effects simultaneously with pure-only regeneration
        if item.profiles.polycell and "pure" in item.profiles.polycell.effects and len(item.profiles.polycell.effects) > 1:
            add(
                "polycell_mixed_pure_effects",
                item.node.id,
                "Polycell contract mixes 'pure' with side-effect flags; separate pure logic from I/O.",
                severity="warning",
            )

    return ValidationReport(findings=findings)

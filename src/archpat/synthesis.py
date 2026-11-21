"""Finite, explainable pattern catalog. No claim of globally optimal architecture."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from .models import (ArchitectureGraph, Candidate, Edge, Metrics, Node, ReuseEvidence,
                     StorySpec, SynthesisResult)
from .validation import validate_graph

TEMPLATES = {
    "modular_monolith": {"base_ram": 160, "processes": 1, "change_prior": 2},
    "worker_split": {"base_ram": 288, "processes": 2, "change_prior": 6},
    "service_split": {"base_ram": 544, "processes": 4, "change_prior": 12},
}


def fingerprint(value: Any) -> str:
    """Local serialization fingerprint; not URT canonicalization or RFC 8785."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def build_graph(story: StorySpec, variant: str, inventories: list[dict] | None = None) -> ArchitectureGraph:
    if variant not in TEMPLATES:
        raise ValueError(f"Unknown catalog variant: {variant}")
    nodes: list[Node] = []
    edges: list[Edge] = []

    def group(role: str) -> str:
        if variant == "modular_monolith":
            return "application"
        if role in {"relay", "projector"}:
            return "projection_worker"
        if variant == "service_split":
            if role == "adapter":
                return "gateway"
            if role in {"query_handler", "read_model"}:
                return "query_service"
            return "command_service"
        return "application"

    def node(id: str, label: str, role: str, capability: str, **kwargs: Any) -> None:
        reuse = []
        if inventories:
            from .indexing import match_reuse
            for inventory in inventories:
                for match in match_reuse(inventory, capability)[:3]:
                    reuse.append(ReuseEvidence(project=match.get("project", inventory.get("project", "unknown")),
                                               path=match["path"], symbols=match.get("symbols", []),
                                               source_sha256=inventory.get("sha256") or inventory.get("source_sha256")))
        nodes.append(Node(id=id, label=label, role=role, capability=capability,
                          owner="story_application", process_group=group(role),
                          story_ids=[story.id], reuse=reuse[:6], **kwargs))

    def edge(source: str, target: str, kind: str, **kwargs: Any) -> None:
        identity = [source, target, kind, kwargs.get("operation_id"), kwargs.get("interface", "in_process")]
        edges.append(Edge(id="e." + fingerprint(identity)[:24], source=source, target=target, kind=kind, **kwargs))

    node("actor", story.actor, "actor", "user", deployment="external")
    for interface in story.constraints.interfaces:
        node(f"adapter.{interface}", interface.upper(), "adapter", "operation_descriptor", interface=interface)
        edge("actor", f"adapter.{interface}", "invoke", interface=interface, encoding="json")
        edge(f"adapter.{interface}", "actor", "return", interface=interface, encoding="json")
    node("event_store", "Append-only domain event log", "event_store", "event_store",
         properties={"append_only": True, "optimistic_concurrency": True, "replayable": True,
                     "logical_store": "domain_database"})
    node("outbox", "Transactional outbox", "outbox", "outbox", properties={"logical_store": "domain_database"})
    node("relay", "Outbox relay", "relay", "outbox")
    node("projector", "Replayable projector", "projector", "projection",
         properties={"replay_side_effect_free": True, "checkpoint_and_dedup": True})
    node("read_model", "Query projection + checkpoints", "read_model", "projection")
    edge("outbox", "relay", "event", delivery="at_least_once", encoding="json")
    edge("relay", "projector", "event", delivery="at_least_once", encoding="json")
    edge("projector", "event_store", "read", effect="read")
    edge("projector", "read_model", "write", effect="write", transaction_group="projection_checkpoint")
    edge("projector", "event_store", "depends_on")
    aggregates = sorted({op.aggregate for op in story.operations if op.kind == "command"})
    for aggregate in aggregates:
        node(f"aggregate.{aggregate}", aggregate, "aggregate", "aggregate_ownership", aggregate_id=aggregate)
        edge(f"aggregate.{aggregate}", "event_store", "write", effect="write", transaction_group=f"domain.{aggregate}")
        edge(f"aggregate.{aggregate}", "outbox", "write", effect="write", transaction_group=f"domain.{aggregate}")
    if any(op.temporal for op in story.operations):
        node("uritime", "URTime + URT (unbound)", "temporal_service", "temporal",
             properties={"role": "existing temporal owner", "resolution_status": "unresolved"})
        nodes[-1].owner = "uritime"
        nodes[-1].process_group = "existing_uritime"
    for operation in story.operations:
        id = f"operation.{operation.id}"
        role = "command_handler" if operation.kind == "command" else "query_handler"
        properties = ({"idempotency_key": True, "expected_version": True} if operation.kind == "command"
                      else {"min_checkpoint_wait": operation.consistency == "read_your_writes", "read_only": True})
        properties["input_urns"] = operation.input_urns
        properties["output_urns"] = operation.output_urns
        node(id, operation.name, role, operation.capability, operation_id=operation.id,
             aggregate_id=operation.aggregate, properties=properties)
        for interface in story.constraints.interfaces:
            edge(f"adapter.{interface}", id, operation.kind, operation_id=operation.id,
                 data_urns=operation.input_urns, interface=interface, encoding="json")
            edge(f"adapter.{interface}", id, "depends_on")
            edge(id, f"adapter.{interface}", "return", operation_id=operation.id,
                 data_urns=operation.output_urns, interface=interface, encoding="json")
        if operation.kind == "command":
            edge(id, f"aggregate.{operation.aggregate}", "command", operation_id=operation.id,
                 data_urns=operation.input_urns)
            edge(id, f"aggregate.{operation.aggregate}", "depends_on")
        else:
            edge(id, "read_model", "read", operation_id=operation.id, effect="read", data_urns=operation.output_urns)
            edge(id, "read_model", "depends_on")
        if operation.temporal:
            edge("actor", "uritime", "propose", operation_id=operation.id, encoding="json")
            # A temporal trigger is a prospective control edge, not a Python import dependency.
            edge("uritime", id, "temporal", operation_id=operation.id, encoding="json")
    for item in edges:
        source = next(n for n in nodes if n.id == item.source)
        target = next(n for n in nodes if n.id == item.target)
        if item.kind in {"read", "write"} and target.role in {"event_store", "outbox", "read_model"}:
            item.interface = "sql"
        elif (source.process_group != target.process_group and item.interface == "in_process"
              and item.kind != "depends_on"):
            item.interface = "unbound_ipc"
            item.encoding = "json"
    return ArchitectureGraph(id=f"g.{story.id}", variant=variant, story=story,
                             patterns=["cqrs", "event_sourcing", "outbox", "ports_adapters"],
                             nodes=nodes, edges=edges, provenance={
                                 "story_sha256": fingerprint(story.model_dump(mode="json")),
                                 "hash_format": "archpat-json-v1",
                                 "generator": "archpat/0.1.0",
                                 "catalog": "cqrs-es-three-templates/v1",
                                 "metric_basis": "heuristic priors, not benchmark measurements",
                                 "source_indexes": [{"project": x.get("project"), "sha256": x.get("sha256")} for x in (inventories or [])],
                             })


def estimate(graph: ArchitectureGraph) -> Metrics:
    template = TEMPLATES[graph.variant]
    nodes = {node.id: node for node in graph.nodes}
    crossings = sum(1 for e in graph.edges if e.kind != "depends_on"
                    and nodes[e.source].role != "actor"
                    and nodes[e.target].role != "actor"
                    and nodes[e.source].process_group != nodes[e.target].process_group)
    ram = template["base_ram"] + 16 * len(graph.story.operations)
    reserved = graph.story.constraints.reserved_ram_mb
    return Metrics(ram_mb_estimate=ram, reserved_ram_mb=reserved,
                   total_ram_mb_estimate=ram + reserved, process_count=template["processes"],
                   cross_process_edges=crossings, change_surface_prior=template["change_prior"])


def synthesize(story: StorySpec | dict, inventories: list[dict] | None = None) -> SynthesisResult:
    story = StorySpec.model_validate(story)
    candidates = []
    for variant in TEMPLATES:
        graph = build_graph(story, variant, inventories)
        report = validate_graph(graph)
        metrics = estimate(graph)
        constraints = story.constraints
        rejected = [f"{f.code}: {f.message}" for f in report.errors]
        if metrics.total_ram_mb_estimate > constraints.ram_budget_mb:
            rejected.append("ram_budget_mb: estimated target + reserved RAM exceeds the budget")
        if metrics.process_count > constraints.max_processes:
            rejected.append("max_processes: application process count exceeds the limit")
        if constraints.isolate_projection and variant == "modular_monolith":
            rejected.append("isolate_projection: requires a separate projection worker")
        if constraints.independent_command_query_scaling and variant != "service_split":
            rejected.append("independent_command_query_scaling: requires separately deployed command/query services")
        raw_terms = {"ram": metrics.total_ram_mb_estimate / 4096,
                     "processes": metrics.process_count / 8,
                     "coupling": metrics.cross_process_edges / 40,
                     "change_surface": metrics.change_surface_prior / 20}
        weights = story.weights.model_dump()
        total_weight = sum(weights.values())
        score_terms = {k: round(raw_terms[k] * weights[k] / total_weight, 8) for k in weights}
        score = round(sum(score_terms.values()), 8) if not rejected else None
        candidates.append(Candidate(id=variant, graph=graph, metrics=metrics, validation=report,
                                    rejection_reasons=rejected, score=score, score_terms=score_terms,
                                    feasible=not rejected))
    feasible = sorted([c for c in candidates if c.feasible], key=lambda c: (c.score, c.id))

    def vector(candidate: Candidate) -> tuple[int, ...]:
        m = candidate.metrics
        return m.total_ram_mb_estimate, m.process_count, m.cross_process_edges, m.change_surface_prior

    def dominates(left: Candidate, right: Candidate) -> bool:
        a, b = vector(left), vector(right)
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    pareto = [c.id for c in feasible if not any(dominates(other, c) for other in feasible if other.id != c.id)]
    return SynthesisResult(status="best_in_catalog" if feasible else "no_feasible_catalog_candidate",
                           selected_id=feasible[0].id if feasible else None, pareto_ids=pareto,
                           input_sha256=fingerprint(story.model_dump(mode="json")), candidates=candidates,
                           assumptions=[
                               "Only three CQRS+ES deployment templates are enumerated; this is not a global solver.",
                               "RAM and change-surface values are editable, unmeasured priors; no latency guarantee is inferred.",
                               "Existing URTime/Autodo/LLM/database processes are excluded from the new-process count; reserve their RAM explicitly.",
                               "Architecture feasibility is structural and conditional on priors, not a production readiness attestation.",
                               "URL/URI/URN/URT runtime contracts and Polycell/Forge adapters need local source verification.",
                           ] + story.assumptions)


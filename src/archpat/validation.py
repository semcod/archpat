"""Architecture fitness checks: structural evidence, never an execution attestation."""
from __future__ import annotations

import networkx as nx
from .models import ArchitectureGraph, Finding, ValidationReport


def validate_graph(graph: ArchitectureGraph) -> ValidationReport:
    findings: list[Finding] = []

    def add(code: str, subject: str, message: str, severity: str = "error") -> None:
        findings.append(Finding(code=code, subject=subject, message=message, severity=severity))

    ids = [node.id for node in graph.nodes]
    if len(ids) != len(set(ids)):
        add("duplicate_node", graph.id, "Node IDs must be unique.")
    edge_ids = [edge.id for edge in graph.edges]
    if len(edge_ids) != len(set(edge_ids)):
        add("duplicate_edge", graph.id, "Edge IDs must be unique.")
    nodes = {node.id: node for node in graph.nodes}
    operation_ids = {op.id for op in graph.story.operations}
    dependency_graph = nx.DiGraph()
    dependency_graph.add_nodes_from(nodes)
    flow_graph = nx.MultiDiGraph()
    flow_graph.add_nodes_from(nodes)
    call_graph = nx.DiGraph()
    call_graph.add_nodes_from(nodes)
    for edge in graph.edges:
        if edge.operation_id is not None and edge.operation_id not in operation_ids:
            add("unknown_operation", edge.id, "The edge refers to an operation not declared by its user story.")
        if edge.source not in nodes or edge.target not in nodes:
            add("unknown_endpoint", edge.id, "Both edge endpoints must exist.")
            continue
        source, target = nodes[edge.source], nodes[edge.target]
        if edge.kind == "depends_on":
            dependency_graph.add_edge(edge.source, edge.target)
        else:
            flow_graph.add_edge(edge.source, edge.target, key=edge.id)
        if edge.kind not in {"depends_on", "return", "temporal", "propose"}:
            call_graph.add_edge(edge.source, edge.target)
        if source.role == "query_handler" and (edge.effect == "write" or edge.kind in {"write", "command"}):
            add("query_writes", edge.id, "A query path cannot issue a command or mutate domain state.")
        if edge.effect == "write" and target.role == "event_store" and source.role != "aggregate":
            add("event_authority", edge.id, "Only the owning aggregate appends domain events.")
        if edge.effect == "write" and target.role == "read_model" and source.role != "projector":
            add("projection_authority", edge.id, "Read models are written by their projector.")
        if source.role == "adapter" and target.role in {"event_store", "read_model", "aggregate"}:
            add("adapter_bypass", edge.id, "Adapters must enter through application handlers.")
        if edge.delivery == "at_least_once" and not edge.idempotent:
            add("missing_idempotency", edge.id, "At-least-once consumers need a deduplication/idempotency design.")
    if not nx.is_directed_acyclic_graph(dependency_graph):
        add("dependency_cycle", graph.id, "A depends_on cycle was found; business event cycles are checked separately.")
    declared = set(graph.patterns)
    missing = set(graph.story.constraints.required_patterns) - declared
    if missing:
        add("required_pattern_missing", graph.id, f"Missing requested patterns: {sorted(missing)}")
    roles = {node.role for node in graph.nodes}
    if "event_sourcing" in declared and "event_store" not in roles:
        add("missing_event_store", graph.id, "Event sourcing needs a durable event store and replay design.")
    if "cqrs" in declared and not {"projector", "read_model"}.issubset(roles):
        add("missing_projection", graph.id, "This CQRS+ES template needs a projector and read model.")
    aggregate_groups: dict[str, list] = {}
    for node in graph.nodes:
        if node.operation_id is not None and node.operation_id not in operation_ids:
            add("unknown_operation", node.id, "The node refers to an operation not declared by its user story.")
        if node.role == "aggregate":
            aggregate_groups.setdefault(node.aggregate_id or "", []).append(node)
        if node.role == "event_store" and node.properties.get("append_only") is not True:
            add("event_mutability", node.id, "The event store must be append-only in the proposed model.")
        if node.role == "projector" and node.properties.get("replay_side_effect_free") is not True:
            add("replay_effects", node.id, "Projector replay must not execute external effects.")
        if node.role == "projector" and node.properties.get("checkpoint_and_dedup") is not True:
            add("projection_checkpoint", node.id, "Projectors need durable checkpoint and event deduplication.")
        if graph.story.constraints.offline and node.deployment == "remote":
            add("offline_remote", node.id, "Offline architecture cannot require a remote node.")
    for aggregate_id, owners in aggregate_groups.items():
        if not aggregate_id or len(owners) != 1:
            add("aggregate_ownership", aggregate_id, "Each aggregate boundary must have exactly one logical writer.")
        for owner in owners:
            writes = [e for e in graph.edges if e.source == owner.id and e.kind == "write"]
            event_tx = {e.transaction_group for e in writes if nodes.get(e.target) and nodes[e.target].role == "event_store"}
            outbox_tx = {e.transaction_group for e in writes if nodes.get(e.target) and nodes[e.target].role == "outbox"}
            event_stores = {nodes[e.target].properties.get("logical_store") for e in writes
                            if nodes.get(e.target) and nodes[e.target].role == "event_store"}
            outbox_stores = {nodes[e.target].properties.get("logical_store") for e in writes
                             if nodes.get(e.target) and nodes[e.target].role == "outbox"}
            if "outbox" in declared and (len(event_tx) != 1 or None in event_tx or event_tx != outbox_tx
                                          or len(event_stores) != 1 or None in event_stores or event_stores != outbox_stores):
                add("non_atomic_outbox", owner.id, "Event append and outbox enqueue must share one local transaction.")
    if "outbox" in declared:
        event_graph = nx.DiGraph((e.source, e.target) for e in graph.edges
                                if e.kind == "event" and e.source in nodes and e.target in nodes)
        projectors = [n.id for n in graph.nodes if n.role == "projector"]
        for outbox in [n for n in graph.nodes if n.role == "outbox"]:
            if outbox.id not in event_graph or not any(p in event_graph and nx.has_path(event_graph, outbox.id, p)
                                                      for p in projectors):
                add("event_delivery_gap", outbox.id, "The outbox must deliver events to a projector.")
        for projector in projectors:
            if not any(e.source == projector and e.kind == "write" and nodes.get(e.target)
                       and nodes[e.target].role == "read_model" for e in graph.edges):
                add("projection_write_gap", projector, "A projector must update a read model.")
    for operation in graph.story.operations:
        handlers = [node for node in graph.nodes if node.operation_id == operation.id
                    and node.role in {"command_handler", "query_handler"}]
        expected_role = "command_handler" if operation.kind == "command" else "query_handler"
        if len(handlers) != 1 or handlers[0].role != expected_role:
            add("operation_coverage", operation.id, "Every operation needs exactly one handler of the declared kind.")
            continue
        handler = handlers[0]
        if graph.story.id not in handler.story_ids:
            add("story_trace", handler.id, "Handler must trace back to its user story.")
        for interface in graph.story.constraints.interfaces:
            adapters = [n for n in graph.nodes if n.role == "adapter" and n.interface == interface]
            if not adapters or not any(flow_graph.has_edge(n.id, handler.id) for n in adapters):
                add("interface_coverage", operation.id, f"No {interface} adapter reaches this operation.")
        if operation.kind == "command":
            if handler.properties.get("idempotency_key") is not True or handler.properties.get("expected_version") is not True:
                add("command_concurrency", handler.id, "Commands require idempotency and expected stream version.")
            if not any(e.source == handler.id and e.kind == "command" and nodes.get(e.target)
                       and nodes[e.target].role == "aggregate" and nodes[e.target].aggregate_id == operation.aggregate
                       for e in graph.edges):
                add("command_path_gap", handler.id, "Command must reach the declared aggregate.")
        if operation.kind == "query":
            # Trace indirect calls as well; a direct-edge-only check misses a query -> helper -> writer.
            reachable = nx.descendants(call_graph, handler.id)
            if (any(nodes[n].role in {"command_handler", "aggregate", "outbox", "projector"} for n in reachable)
                    or any(e.source in reachable | {handler.id} and e.effect == "write" for e in graph.edges)):
                add("query_reaches_writer", handler.id, "A query transitively reaches a domain write path.")
            if not any(e.source == handler.id and e.kind == "read" and nodes.get(e.target)
                       and nodes[e.target].role == "read_model" for e in graph.edges):
                add("query_path_gap", handler.id, "Query must read a projection.")
            if operation.consistency == "read_your_writes" and handler.properties.get("min_checkpoint_wait") is not True:
                add("freshness_missing", handler.id, "Read-your-writes requires a bounded wait for the requested checkpoint.")
        if operation.temporal:
            add("temporal_unresolved", operation.id, "Natural-language time awaits uritime/URT interpretation and binding.", "warning")
    if any(node.binding_status != "verified" for node in graph.nodes if node.role != "actor"):
        add("unbound_implementations", graph.id, "This is an architecture proposal; runtime bindings remain unverified.", "warning")
    if any(item.status != "contract_verified" for node in graph.nodes for item in node.reuse):
        add("reuse_not_verified", graph.id, "Index/source presence is not proof of contract compatibility.", "warning")
    return ValidationReport(findings=findings)


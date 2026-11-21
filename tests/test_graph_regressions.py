"""Regressions found by reviewing the generated CQRS/ES graphs.

These checks break meaningful graph guarantees while leaving the surrounding
nodes and dependency declarations intact. They also distinguish temporal and
response edges from execution paths, and exercise accepted identifier limits.
"""
from __future__ import annotations

import unittest

from archpat.models import (
    ArchitectureGraph,
    Constraints,
    Edge,
    OperationSpec,
    StorySpec,
    TemporalRequirement,
)
from archpat.synthesis import build_graph, synthesize
from archpat.validation import validate_graph


def write_read_story() -> StorySpec:
    return StorySpec(
        id="job-review",
        title="Submit a job and inspect its outcome",
        actor="Operator",
        goal="Keep the submitted job and make its result available",
        acceptance_criteria=["A submitted job can subsequently be retrieved."],
        operations=[
            OperationSpec(
                id="submit",
                name="Submit job",
                kind="command",
                capability="job_submission",
                aggregate="job",
                input_urns=["urn:job:request:v1"],
                output_urns=["urn:job:receipt:v1"],
            ),
            OperationSpec(
                id="inspect",
                name="Inspect job",
                kind="query",
                capability="job_query",
                aggregate="job",
                output_urns=["urn:job:result:v1"],
            ),
        ],
        constraints=Constraints(max_processes=4),
    )


class GraphRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.story = write_read_story()
        self.graph = build_graph(self.story, "modular_monolith")

    def assert_diagnostic(self, code: str, graph: ArchitectureGraph | None = None):
        report = validate_graph(self.graph if graph is None else graph)
        self.assertFalse(report.valid, report.model_dump())
        self.assertIn(code, {item.code for item in report.errors}, report.model_dump())
        return report

    def test_dependency_declaration_does_not_replace_command_flow(self):
        self.graph.edges = [
            edge for edge in self.graph.edges
            if not (edge.source == "operation.submit" and edge.kind == "command")
        ]
        self.assert_diagnostic("command_path_gap")

    def test_dependency_declaration_does_not_replace_projection_read(self):
        self.graph.edges = [
            edge for edge in self.graph.edges
            if not (edge.source == "operation.inspect" and edge.kind == "read")
        ]
        self.assert_diagnostic("query_path_gap")

    def test_each_cut_in_event_delivery_is_detected(self):
        for source, target in (("outbox", "relay"), ("relay", "projector")):
            with self.subTest(source=source, target=target):
                graph = self.graph.model_copy(deep=True)
                graph.edges = [
                    edge for edge in graph.edges
                    if not (edge.source == source and edge.target == target and edge.kind == "event")
                ]
                self.assert_diagnostic("event_delivery_gap", graph)

    def test_query_cannot_trigger_a_mutating_projector(self):
        self.graph.edges.append(
            Edge(
                id="query-projector",
                source="operation.inspect",
                target="projector",
                kind="query",
                operation_id="inspect",
            )
        )
        report = self.assert_diagnostic("query_reaches_writer")
        self.assertNotIn("query_writes", {item.code for item in report.errors})

    def test_shared_temporal_owner_does_not_turn_query_into_command(self):
        for operation in self.story.operations:
            operation.temporal = TemporalRequirement(text="Po następnym zakończonym zadaniu")
        result = synthesize(self.story)
        self.assertEqual(result.status, "best_in_catalog")
        for candidate in result.candidates:
            with self.subTest(variant=candidate.id):
                self.assertTrue(candidate.feasible, candidate.rejection_reasons)
                self.assertTrue(candidate.validation.valid, candidate.validation.model_dump())
                temporal = [
                    finding for finding in candidate.validation.findings
                    if finding.code == "temporal_unresolved"
                ]
                self.assertEqual({finding.subject for finding in temporal}, {"submit", "inspect"})
                self.assertTrue(all(finding.severity == "warning" for finding in temporal))

    def test_response_edge_does_not_follow_adapter_to_other_commands(self):
        self.graph.edges.append(
            Edge(
                id="query-response",
                source="operation.inspect",
                target="adapter.rest",
                kind="return",
                operation_id="inspect",
                data_urns=["urn:job:result:v1"],
            )
        )
        report = validate_graph(self.graph)
        self.assertTrue(report.valid, report.model_dump())

    def test_accepted_eighty_character_ids_survive_prefixes_and_round_trip(self):
        payload = self.story.model_dump(mode="json")
        command_id, query_id = "a" * 79 + "b", "a" * 79 + "c"
        aggregate_id = "j" * 80
        payload["id"] = "s" * 80
        payload["operations"][0]["id"] = command_id
        payload["operations"][1]["id"] = query_id
        for operation in payload["operations"]:
            operation["aggregate"] = aggregate_id
        story = StorySpec.model_validate(payload)
        graph = build_graph(story, "modular_monolith")
        restored = ArchitectureGraph.model_validate_json(graph.model_dump_json())
        report = validate_graph(restored)
        self.assertTrue(report.valid, report.model_dump())
        self.assertEqual(restored.id, "g." + story.id)
        self.assertEqual(
            {node.operation_id for node in restored.nodes if node.operation_id is not None},
            {command_id, query_id},
        )
        self.assertEqual(len(restored.nodes), len({node.id for node in restored.nodes}))

    def test_command_must_reach_its_own_aggregate_not_another_valid_owner(self):
        self.story.operations.append(
            OperationSpec(
                id="invoice",
                name="Create invoice",
                kind="command",
                capability="invoice_creation",
                aggregate="invoice",
            )
        )
        graph = build_graph(self.story, "modular_monolith")
        for edge in graph.edges:
            if edge.source == "operation.submit" and edge.kind == "command":
                edge.target = "aggregate.invoice"
        report = self.assert_diagnostic("command_path_gap", graph)
        self.assertTrue(any(
            finding.code == "command_path_gap" and finding.subject == "operation.submit"
            for finding in report.errors
        ))

    def test_text_false_cannot_satisfy_required_boolean_guarantees(self):
        cases = (
            ("event_store", "append_only", "event_mutability"),
            ("projector", "checkpoint_and_dedup", "projection_checkpoint"),
            ("projector", "replay_side_effect_free", "replay_effects"),
            ("operation.submit", "idempotency_key", "command_concurrency"),
            ("operation.submit", "expected_version", "command_concurrency"),
        )
        for node_id, property_name, code in cases:
            with self.subTest(node=node_id, property=property_name):
                graph = self.graph.model_copy(deep=True)
                node = next(node for node in graph.nodes if node.id == node_id)
                node.properties[property_name] = "false"
                self.assert_diagnostic(code, graph)

    def test_text_false_cannot_claim_read_your_writes_checkpoint_wait(self):
        self.story.operations[1].consistency = "read_your_writes"
        graph = build_graph(self.story, "modular_monolith")
        query = next(node for node in graph.nodes if node.id == "operation.inspect")
        query.properties["min_checkpoint_wait"] = "false"
        self.assert_diagnostic("freshness_missing", graph)


if __name__ == "__main__":
    unittest.main()

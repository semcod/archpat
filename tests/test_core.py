"""Behavioral checks for architecture invariants and constrained selection.

The fixtures describe a small write/read use case. Negative tests deliberately
break one architectural guarantee and require an explicit diagnostic; they do
not assert the internal edge ordering or duplicate the scoring formula.
"""
from __future__ import annotations

import unittest

from pydantic import ValidationError

from archpat.models import (
    Constraints,
    Edge,
    OperationSpec,
    StorySpec,
    TemporalRequirement,
    Weights,
)
from archpat.synthesis import build_graph, fingerprint, synthesize
from archpat.validation import validate_graph


def make_story(**constraint_overrides) -> StorySpec:
    """A domain command and its query, with all requested access interfaces."""
    constraints = {"max_processes": 4, **constraint_overrides}
    return StorySpec(
        id="exercise-review",
        title="Submit and inspect an exercise review",
        actor="Lecturer",
        goal="Keep a durable review and read its result",
        acceptance_criteria=[
            "A submitted review is recorded durably.",
            "The lecturer can retrieve the current review.",
        ],
        operations=[
            OperationSpec(
                id="submit",
                name="Submit review",
                kind="command",
                capability="review_submission",
                aggregate="review",
                input_urns=["urn:artifact:exercise:v1"],
                output_urns=["urn:artifact:review:v1"],
            ),
            OperationSpec(
                id="result",
                name="Read review",
                kind="query",
                capability="review_retrieval",
                aggregate="review",
                output_urns=["urn:artifact:review:v1"],
            ),
        ],
        constraints=Constraints(**constraints),
    )


class StoryContractTests(unittest.TestCase):
    def test_operation_identifiers_must_be_unique(self):
        payload = make_story().model_dump(mode="json")
        payload["operations"][1]["id"] = "submit"
        with self.assertRaises(ValidationError):
            StorySpec.model_validate(payload)

    def test_data_reference_is_not_a_service_url(self):
        payload = make_story().model_dump(mode="json")
        payload["operations"][0]["input_urns"] = ["https://service.example/items/1"]
        with self.assertRaises(ValidationError):
            StorySpec.model_validate(payload)

    def test_time_zone_must_be_resolvable(self):
        with self.assertRaises(ValidationError):
            TemporalRequirement(text="Tomorrow after the review", timezone="Europe/Invented")

    def test_optimization_needs_at_least_one_positive_weight(self):
        with self.assertRaises(ValidationError):
            Weights(ram=0, processes=0, coupling=0, change_surface=0)


class ArchitectureInvariantTests(unittest.TestCase):
    def setUp(self):
        self.story = make_story()
        self.graph = build_graph(self.story, "modular_monolith")

    def node(self, identifier):
        return next(node for node in self.graph.nodes if node.id == identifier)

    def edge(self, source, target, kind=None):
        return next(
            edge
            for edge in self.graph.edges
            if edge.source == source
            and edge.target == target
            and (kind is None or edge.kind == kind)
        )

    def assertError(self, code):
        report = validate_graph(self.graph)
        self.assertFalse(report.valid, report.model_dump())
        self.assertIn(code, {finding.code for finding in report.errors}, report.model_dump())
        return report

    def remove_node_and_edges(self, identifier):
        self.graph.nodes = [node for node in self.graph.nodes if node.id != identifier]
        self.graph.edges = [
            edge
            for edge in self.graph.edges
            if edge.source != identifier and edge.target != identifier
        ]

    def test_catalog_graphs_obey_their_declared_structural_rules(self):
        for variant in ("modular_monolith", "worker_split", "service_split"):
            with self.subTest(variant=variant):
                report = validate_graph(build_graph(self.story, variant))
                self.assertTrue(report.valid, report.model_dump())

    def test_query_cannot_write_directly(self):
        self.graph.edges.append(
            Edge(
                id="query-write",
                source="operation.result",
                target="event_store",
                kind="write",
                effect="write",
                operation_id="result",
            )
        )
        self.assertError("query_writes")

    def test_query_cannot_reach_a_writer_through_a_helper(self):
        self.graph.edges.extend(
            [
                Edge(id="query-helper", source="operation.result", target="relay", kind="query"),
                Edge(id="helper-write", source="relay", target="aggregate.review", kind="command"),
            ]
        )
        report = self.assertError("query_reaches_writer")
        self.assertNotIn("query_writes", {finding.code for finding in report.errors})

    def test_one_aggregate_cannot_have_two_logical_write_owners(self):
        owner = self.node("aggregate.review").model_copy(deep=True)
        owner.id = "aggregate.review-second-owner"
        self.graph.nodes.append(owner)
        self.assertError("aggregate_ownership")

    def test_outbox_and_event_append_must_share_a_transaction(self):
        self.edge("aggregate.review", "outbox", "write").transaction_group = "separate-transaction"
        self.assertError("non_atomic_outbox")

    def test_missing_outbox_enqueue_breaks_the_declared_outbox_pattern(self):
        self.graph.edges = [
            edge
            for edge in self.graph.edges
            if not (edge.source == "aggregate.review" and edge.target == "outbox" and edge.kind == "write")
        ]
        self.assertError("non_atomic_outbox")

    def test_transaction_label_cannot_make_two_databases_atomic(self):
        self.node("outbox").properties["logical_store"] = "separate-outbox-database"
        self.assertError("non_atomic_outbox")

    def test_dependency_cycles_are_rejected(self):
        self.graph.edges.extend(
            [
                Edge(id="dep-forward", source="relay", target="projector", kind="depends_on"),
                Edge(id="dep-backward", source="projector", target="relay", kind="depends_on"),
            ]
        )
        self.assertError("dependency_cycle")

    def test_a_business_event_cycle_is_not_an_import_dependency_cycle(self):
        self.graph.edges.append(
            Edge(
                id="feedback-event",
                source="projector",
                target="relay",
                kind="event",
                delivery="at_least_once",
                idempotent=True,
            )
        )
        report = validate_graph(self.graph)
        self.assertTrue(report.valid, report.model_dump())
        self.assertNotIn("dependency_cycle", {finding.code for finding in report.findings})

    def test_retried_delivery_requires_an_idempotent_consumer(self):
        self.edge("relay", "projector", "event").idempotent = False
        self.assertError("missing_idempotency")

    def test_each_requested_interface_must_reach_every_operation(self):
        self.remove_node_and_edges("adapter.mcp")
        report = self.assertError("interface_coverage")
        missing = [finding for finding in report.errors if finding.code == "interface_coverage"]
        self.assertEqual({finding.subject for finding in missing}, {"submit", "result"})
        self.assertTrue(all("mcp" in finding.message for finding in missing))

    def test_handler_must_trace_back_to_the_story(self):
        self.node("operation.submit").story_ids = []
        self.assertError("story_trace")

    def test_each_operation_requires_a_handler(self):
        self.remove_node_and_edges("operation.result")
        self.assertError("operation_coverage")

    def test_handler_kind_must_match_the_operation_contract(self):
        self.node("operation.result").role = "command_handler"
        self.assertError("operation_coverage")

    def test_operation_edge_cannot_claim_an_undeclared_operation(self):
        self.edge("adapter.rest", "operation.submit", "command").operation_id = "undeclared-operation"
        self.assertError("unknown_operation")

    def test_read_your_writes_requires_a_checkpoint_strategy(self):
        self.graph.story.operations[1].consistency = "read_your_writes"
        self.node("operation.result").properties["min_checkpoint_wait"] = False
        self.assertError("freshness_missing")

    def test_replay_must_not_produce_external_effects(self):
        self.node("projector").properties["replay_side_effect_free"] = False
        self.assertError("replay_effects")

    def test_event_sourcing_cannot_use_a_mutable_event_log(self):
        self.node("event_store").properties["append_only"] = False
        self.assertError("event_mutability")

    def test_temporal_intent_stays_an_unresolved_warning(self):
        story = make_story()
        story.operations[0].temporal = TemporalRequirement(text="Po zakończeniu ćwiczenia, przed następną lekcją")
        graph = build_graph(story, "modular_monolith")
        report = validate_graph(graph)
        self.assertTrue(report.valid, report.model_dump())
        findings = [finding for finding in report.findings if finding.code == "temporal_unresolved"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject, "submit")
        self.assertEqual(findings[0].severity, "warning")
        self.assertEqual(graph.story.operations[0].temporal.resolution_status, "unresolved")


class ConstrainedSelectionTests(unittest.TestCase):
    def test_small_local_use_case_prefers_modular_monolith(self):
        result = synthesize(make_story())
        self.assertEqual(result.status, "best_in_catalog")
        self.assertEqual(result.selected_id, "modular_monolith")

    def test_isolated_projection_selects_worker_variant(self):
        result = synthesize(make_story(isolate_projection=True))
        self.assertEqual(result.selected_id, "worker_split")
        monolith = next(candidate for candidate in result.candidates if candidate.id == "modular_monolith")
        self.assertFalse(monolith.feasible)
        self.assertIsNone(monolith.score)
        self.assertTrue(any(reason.startswith("isolate_projection:") for reason in monolith.rejection_reasons))

    def test_independent_command_query_scaling_selects_services(self):
        result = synthesize(make_story(independent_command_query_scaling=True))
        self.assertEqual(result.selected_id, "service_split")
        self.assertEqual([candidate.id for candidate in result.candidates if candidate.feasible], ["service_split"])

    def test_hard_process_limit_cannot_be_overridden_by_a_good_score(self):
        result = synthesize(make_story(independent_command_query_scaling=True, max_processes=2))
        self.assertEqual(result.status, "no_feasible_catalog_candidate")
        self.assertIsNone(result.selected_id)
        self.assertEqual(result.pareto_ids, [])
        self.assertTrue(all(not candidate.feasible and candidate.score is None for candidate in result.candidates))

    def test_impossible_ram_budget_returns_no_candidate(self):
        result = synthesize(make_story(ram_budget_mb=1))
        self.assertEqual(result.status, "no_feasible_catalog_candidate")
        self.assertIsNone(result.selected_id)
        self.assertEqual(result.pareto_ids, [])
        for candidate in result.candidates:
            with self.subTest(candidate=candidate.id):
                self.assertFalse(candidate.feasible)
                self.assertIsNone(candidate.score)
                self.assertTrue(any(reason.startswith("ram_budget_mb:") for reason in candidate.rejection_reasons))

    def test_reserved_runtime_ram_is_included_in_feasibility(self):
        result = synthesize(make_story(ram_budget_mb=512, reserved_ram_mb=511))
        self.assertIsNone(result.selected_id)
        self.assertTrue(all(not candidate.feasible for candidate in result.candidates))

    def test_a_selected_proposal_is_not_a_runtime_attestation(self):
        result = synthesize(make_story())
        self.assertFalse(result.execution_ready)
        self.assertTrue(all(candidate.metrics.evidence == "heuristic_unmeasured" for candidate in result.candidates))

    def test_same_input_produces_identical_candidates_and_fingerprints(self):
        first = synthesize(make_story())
        second = synthesize(make_story())
        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))

    def test_fingerprint_ignores_mapping_insertion_order(self):
        first = {"story": {"a": 1, "b": 2}, "operations": ["submit", "result"]}
        second = {"operations": ["submit", "result"], "story": {"b": 2, "a": 1}}
        self.assertEqual(fingerprint(first), fingerprint(second))

    def test_changed_requirement_changes_input_fingerprint(self):
        story = make_story()
        before = synthesize(story).input_sha256
        story.acceptance_criteria.append("Read results must include a revision identifier.")
        self.assertNotEqual(before, synthesize(story).input_sha256)


if __name__ == "__main__":
    unittest.main()

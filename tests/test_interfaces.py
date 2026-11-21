"""Cross-format and user-facing boundary tests for architecture proposals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import networkx as nx
from pydantic import ValidationError

from archpat.analysis import diff_graphs, impact
from archpat.exporters import write_bundle
from archpat.models import ArchitectureGraph, Edge
from archpat.operations import synthesize_operation, validate_operation
from archpat.synthesis import build_graph, synthesize

from test_core import make_story

try:
    import httpx  # noqa: F401: TestClient requires this optional dependency.
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


class ExportBundleTests(unittest.TestCase):
    def test_json_and_graphml_preserve_the_proposal_and_parallel_edges(self):
        result = synthesize(make_story())
        selected = next(candidate.graph for candidate in result.candidates if candidate.id == result.selected_id)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            written = {Path(path).name for path in write_bundle(result, output)}
            self.assertTrue(
                {"architecture.json", "architecture.graphml", "synthesis.json", "decision.md"}.issubset(written)
            )
            restored = ArchitectureGraph.model_validate_json((output / "architecture.json").read_text())
            self.assertEqual(restored.model_dump(mode="json"), selected.model_dump(mode="json"))

            exchange = nx.read_graphml(output / "architecture.graphml", force_multigraph=True)
            self.assertTrue(exchange.is_directed())
            self.assertTrue(exchange.is_multigraph())
            self.assertEqual(set(exchange.nodes), {node.id for node in selected.nodes})
            self.assertEqual(exchange.number_of_edges(), len(selected.edges))

            exported_nodes = {identifier: json.loads(data["data"]) for identifier, data in exchange.nodes(data=True)}
            self.assertEqual(exported_nodes, {node.id: node.model_dump(mode="json") for node in selected.nodes})
            exported_edges = {
                identifier: json.loads(data["data"])
                for _, _, identifier, data in exchange.edges(keys=True, data=True)
            }
            self.assertEqual(exported_edges, {edge.id: edge.model_dump(mode="json") for edge in selected.edges})

            # The operational call and import dependency share endpoints. A
            # DiGraph export would collapse them and silently lose semantics.
            parallel = exchange.get_edge_data("adapter.rest", "operation.submit")
            self.assertIsNotNone(parallel)
            self.assertEqual({attributes["kind"] for attributes in parallel.values()}, {"command", "depends_on"})

    def test_nonempty_output_requires_explicit_overwrite_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            output.mkdir()
            sentinel = output / "notes.txt"
            sentinel.write_text("User-owned note", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_bundle(synthesize(make_story()), output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "User-owned note")
            self.assertFalse((output / "architecture.json").exists())

    def test_handoff_is_an_unsubmitted_proposal(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            write_bundle(synthesize(make_story()), output)
            handoff = json.loads((output / "handoff-proposal.json").read_text())
            self.assertEqual(handoff["status"], "unbound_proposal")
            self.assertFalse(handoff["submitted"])
            self.assertFalse(handoff["upstream_schema_verified"])
            self.assertIsNone(handoff["runtime_process_uri"])


class ComparisonAndImpactTests(unittest.TestCase):
    def test_json_roundtrip_is_an_unchanged_diff(self):
        before = build_graph(make_story(), "modular_monolith")
        after = ArchitectureGraph.model_validate_json(before.model_dump_json())
        difference = diff_graphs(before, after)
        self.assertEqual(difference["baseline_sha256"], difference["target_sha256"])
        for section in ("nodes", "edges"):
            with self.subTest(section=section):
                self.assertEqual(difference[section]["added"], [])
                self.assertEqual(difference[section]["removed"], [])
                self.assertEqual(difference[section]["changed"], [])
                self.assertTrue(difference[section]["unchanged"])
        self.assertFalse(difference["potentially_breaking"])
        self.assertFalse(difference["applied"])

    def test_split_variant_reports_changed_deployment_boundaries(self):
        story = make_story()
        difference = diff_graphs(build_graph(story, "modular_monolith"), build_graph(story, "worker_split"))
        self.assertNotEqual(difference["baseline_sha256"], difference["target_sha256"])
        changed = {item["id"]: set(item["changed_fields"]) for item in difference["nodes"]["changed"]}
        self.assertIn("process_group", changed["projector"])
        self.assertIn("process_group", changed["relay"])
        self.assertTrue(difference["potentially_breaking"])
        self.assertFalse(difference["applied"])

    def test_dependency_impact_runs_from_dependency_to_its_consumers(self):
        graph = build_graph(make_story(), "modular_monolith")
        # Isolate the relation semantics from the template's other edges.
        graph.edges = [
            Edge(id="handler-dep", source="operation.submit", target="aggregate.review", kind="depends_on"),
            Edge(id="adapter-dep", source="adapter.rest", target="operation.submit", kind="depends_on"),
            Edge(id="business-event", source="aggregate.review", target="projector", kind="event"),
        ]
        affected = impact(graph, "aggregate.review")
        self.assertEqual(set(affected["dependent_nodes"]), {"operation.submit", "adapter.rest"})
        self.assertEqual(affected["downstream_flow_nodes"], ["projector"])
        self.assertFalse(affected["source_code_impact_verified"])
        self.assertEqual(impact(graph, "adapter.rest")["dependent_nodes"], [])

    def test_impact_rejects_unknown_nodes(self):
        with self.assertRaises(ValueError):
            impact(build_graph(make_story(), "modular_monolith"), "not-a-node")


class ApplicationBoundaryTests(unittest.TestCase):
    def test_synthesis_rejects_unknown_story_fields(self):
        payload = make_story().model_dump(mode="json")
        payload["silently_ignored_option"] = True
        with self.assertRaises(ValidationError):
            synthesize_operation(payload)

    def test_validation_rejects_unknown_node_fields(self):
        graph = build_graph(make_story(), "modular_monolith").model_dump(mode="json")
        graph["nodes"][0]["invented_schema_field"] = "unrecognized"
        with self.assertRaises(ValidationError):
            validate_operation(graph)


class CliBoundaryTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "archpat", *map(str, arguments)],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_cli_exports_a_bundle_that_its_validator_accepts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            story_path = root / "story.json"
            story_path.write_text(make_story().model_dump_json(), encoding="utf-8")
            output = root / "bundle"
            completed = self.run_cli("synthesize", story_path, "--out", output)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["selected"], "modular_monolith")
            self.assertFalse(receipt["execution_ready"])
            self.assertTrue((output / "architecture.json").is_file())
            self.assertTrue(all(Path(path).is_file() for path in receipt["files"]))

            checked = self.run_cli("validate", output / "architecture.json")
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertTrue(json.loads(checked.stdout)["valid"])

    def test_infeasible_overwrite_removes_the_previous_selected_architecture(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            story_path = root / "story.json"
            story_path.write_text(make_story().model_dump_json(), encoding="utf-8")
            output = root / "bundle"
            first = self.run_cli("synthesize", story_path, "--out", output)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((output / "architecture.json").is_file())
            sentinel = output / "notes.txt"
            sentinel.write_text("Keep my note", encoding="utf-8")

            story_path.write_text(make_story(ram_budget_mb=1).model_dump_json(), encoding="utf-8")
            second = self.run_cli("synthesize", story_path, "--out", output, "--overwrite")
            self.assertEqual(second.returncode, 2, second.stderr)
            receipt = json.loads(second.stdout)
            self.assertEqual(receipt["status"], "no_feasible_catalog_candidate")
            self.assertIsNone(receipt["selected"])
            for stale in (
                "architecture.json", "architecture.graphml", "architecture.proto",
                "flow.mmd", "dependencies.mmd", "handoff-proposal.json",
            ):
                with self.subTest(stale=stale):
                    self.assertFalse((output / stale).exists(), f"Stale selected artifact: {stale}")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep my note")
            saved = json.loads((output / "synthesis.json").read_text())
            self.assertEqual(saved["status"], "no_feasible_catalog_candidate")
            self.assertIsNone(saved["selected_id"])

    def test_cli_rejects_unknown_fields_without_writing_a_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = make_story().model_dump(mode="json")
            payload["made_up_option"] = "must not disappear"
            story_path = root / "story.json"
            story_path.write_text(json.dumps(payload), encoding="utf-8")
            output = root / "bundle"
            completed = self.run_cli("synthesize", story_path, "--out", output)
            self.assertEqual(completed.returncode, 2)
            error = json.loads(completed.stderr)
            self.assertIn("made_up_option", error["message"])
            self.assertFalse((output / "synthesis.json").exists())


@unittest.skipIf(TestClient is None, "REST tests require optional fastapi and httpx")
class RestBoundaryTests(unittest.TestCase):
    def setUp(self):
        from archpat.api import create_app

        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_synthesis_and_validation_share_the_application_contract(self):
        payload = make_story().model_dump(mode="json")
        response = self.client.post("/v1/synthesize", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        proposal = response.json()
        self.assertEqual(proposal, synthesize_operation(payload))
        graph = next(candidate["graph"] for candidate in proposal["candidates"] if candidate["id"] == proposal["selected_id"])

        checked = self.client.post("/v1/validate", json=graph)
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertEqual(checked.json(), validate_operation(graph))
        self.assertTrue(checked.json()["valid"])
        self.assertFalse(checked.json()["execution_ready"])

    def test_invalid_architecture_returns_structural_diagnostics(self):
        graph = build_graph(make_story(), "modular_monolith").model_dump(mode="json")
        projector = next(node for node in graph["nodes"] if node["role"] == "projector")
        projector["properties"]["replay_side_effect_free"] = False
        checked = self.client.post("/v1/validate", json=graph)
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertFalse(checked.json()["valid"])
        self.assertIn("replay_effects", {finding["code"] for finding in checked.json()["findings"]})

    def test_unknown_story_field_is_a_validation_error(self):
        payload = make_story().model_dump(mode="json")
        payload["unexpected_field"] = True
        response = self.client.post("/v1/synthesize", json=payload)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(any("unexpected_field" in entry["loc"] for entry in response.json()["detail"]))

    def test_unknown_graph_field_is_a_validation_error(self):
        graph = build_graph(make_story(), "modular_monolith").model_dump(mode="json")
        graph["nodes"][0]["unexpected_field"] = True
        response = self.client.post("/v1/validate", json=graph)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(any("unexpected_field" in entry["loc"] for entry in response.json()["detail"]))


if __name__ == "__main__":
    unittest.main()

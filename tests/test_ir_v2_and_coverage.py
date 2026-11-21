"""Tests for Etap 2: ARP-004 (ArchitectureIRv2, profiles, migration, semantic hash) and ARP-005 (views, coverage, delta)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pydantic import ValidationError

from archpat.indexing import parse_toon
from archpat.ir_v2 import (
    ArchitectureIRv2,
    ForgeBinding,
    NlUriBinding,
    PolycellBinding,
    ProfileBindings,
    ProvenanceRecord,
    UritimeBinding,
    downgrade_v2_to_v1_with_report,
    migrate_v1_to_v2,
    semantic_hash,
    validate_ir_v2,
)
from archpat.models import StorySpec
from archpat.synthesis import build_graph
from archpat.views_coverage import as_is_to_be_delta, extract_view, story_coverage_report

ROOT = Path(__file__).resolve().parents[1]


def _load_example_story() -> StorySpec:
    return StorySpec.model_validate(json.loads((ROOT / "examples" / "story-local.json").read_text(encoding="utf-8")))


class TestArp004IrV2(unittest.TestCase):
    def test_migration_roundtrip_and_order_independent_semantic_hash(self) -> None:
        story = _load_example_story()
        v1 = build_graph(story, "modular_monolith")
        profiles = {
            "operation.request-review": ProfileBindings(
                uritime=UritimeBinding(
                    poa_uri="urn:poa:exercise.review#v1",
                    service_url="http://127.0.0.1:8765/v1/exercise/review",
                    temporal_ref="urt:v1:interval:2026-11-21T09:15:00Z/2026-11-21T09:55:00Z",
                ),
                polycell=PolycellBinding(
                    cell_urn="urn:wm:cell:exercise:review.evaluate:v1",
                    process_ref="poa://exercise.local/process/review/v1",
                    owner_lang="python",
                    effects=["pure"],
                ),
                forge=ForgeBinding(
                    process_uri="urn:uuid:2f65cf6c-f10a-4d82-895b-923779aee001",
                    project_urn="urn:uuid:66dfbf7c-bf9b-56f0-acfe-fd586c15bff8",
                ),
                nl_uri=NlUriBinding(action_uri="proc://heyasa.forge/project/impact/v1", provenance_source="direct_dsl"),
                extensions={"upstream_custom_flag": "preserved"},
            )
        }
        v2 = migrate_v1_to_v2(v1, profile_bindings=profiles)
        restored = ArchitectureIRv2.model_validate_json(v2.model_dump_json())
        self.assertEqual(restored.model_dump(mode="json"), v2.model_dump(mode="json"))

        # Semantic hash must ignore node/edge insertion order
        reordered = restored.model_copy(deep=True)
        reordered.nodes = list(reversed(reordered.nodes))
        reordered.edges = list(reversed(reordered.edges))
        self.assertEqual(semantic_hash(v2), semantic_hash(reordered))

        # Validation passes and preserves v1 lossless downgrade with explicit v2-omission report
        report = validate_ir_v2(v2)
        self.assertTrue(report.valid, report.model_dump())
        back_v1, downgrade_report = downgrade_v2_to_v1_with_report(v2)
        self.assertEqual(back_v1.model_dump(mode="json"), v1.model_dump(mode="json"))
        self.assertEqual(downgrade_report["v2_only_profiles_omitted_in_v1"], ["operation.request-review"])

    def test_profile_uri_grammars_reject_invalid_upstream_identifiers(self) -> None:
        with self.assertRaises(ValidationError):
            UritimeBinding(poa_uri="https://example.com/not-poa")
        with self.assertRaises(ValidationError):
            PolycellBinding(cell_urn="https://not-a-cell-urn.example/bad")
        with self.assertRaises(ValidationError):
            ForgeBinding(process_uri="not a valid uri", project_urn="urn:uuid:invalid")

    def test_dangling_criterion_and_unsubstantiated_evidence_are_rejected(self) -> None:
        v2 = migrate_v1_to_v2(build_graph(_load_example_story(), "modular_monolith"))
        v2.criteria_links[0].node_ids.append("nonexistent.node")
        v2.nodes[0].evidence_level = "integration_verified"
        v2.nodes[0].provenance = []
        report = validate_ir_v2(v2)
        codes = {f.code for f in report.errors}
        self.assertIn("dangling_criterion_node", codes)
        self.assertIn("unsubstantiated_evidence_level", codes)

    def test_substantiated_provenance_accepted(self) -> None:
        v2 = migrate_v1_to_v2(build_graph(_load_example_story(), "modular_monolith"))
        v2.nodes[0].evidence_level = "contract_verified"
        v2.nodes[0].provenance = [
            ProvenanceRecord(source_kind="runtime_observation", producer="pilot", evidence_level="contract_verified")
        ]
        report = validate_ir_v2(v2)
        self.assertNotIn("unsubstantiated_evidence_level", {f.code for f in report.errors})


class TestArp005ViewsCoverageDelta(unittest.TestCase):
    def test_all_five_layers_project_cleanly(self) -> None:
        graph = build_graph(_load_example_story(), "worker_split")
        for layer in ("domain", "data_flow", "deployment", "temporal", "implementation"):
            with self.subTest(layer=layer):
                view = extract_view(graph, layer)  # type: ignore[arg-type]
                self.assertEqual(view["layer"], layer)
                self.assertEqual(view["graph_id"], graph.id)
                self.assertEqual(len(view["semantic_hash"]), 64)
        deploy = extract_view(graph, "deployment")
        self.assertIn("projection_worker", deploy["process_groups"])
        self.assertTrue(deploy["cross_process_edges"])
        temporal = extract_view(graph, "temporal")
        self.assertEqual(len(temporal["temporal_requirements"]), 1)

    def test_story_coverage_detects_removed_required_node_and_never_fakes_runtime_proof(self) -> None:
        graph = build_graph(_load_example_story(), "modular_monolith")
        baseline = story_coverage_report(graph)
        self.assertTrue(baseline["structurally_complete"], baseline)
        # Honest boundary: structural completeness is NOT runtime verification
        self.assertFalse(baseline["runtime_verified"])
        self.assertTrue(all(c["status"] == "structurally_supported_unverified" for c in baseline["acceptance_criteria"]))

        # Removing projector must trigger concrete gap_detected on replay/projection criteria
        broken = graph.model_copy(deep=True)
        broken.nodes = [n for n in broken.nodes if n.id != "projector"]
        broken.edges = [e for e in broken.edges if e.source != "projector" and e.target != "projector"]
        broken_report = story_coverage_report(broken)
        self.assertFalse(broken_report["structurally_complete"])
        gapped = [c for c in broken_report["acceptance_criteria"] if c["status"] == "gap_detected"]
        self.assertTrue(gapped, broken_report)
        all_diags = " ".join(d for c in gapped for d in c["diagnostics"])
        self.assertIn("missing_side_effect_free_projector", all_diags)

    def test_as_is_to_be_delta_uses_real_indexes_and_never_claims_unused_proof(self) -> None:
        story = _load_example_story()
        inventories = [
            parse_toon(ROOT / "examples" / "indexes" / "uritime.toon.yaml"),
            parse_toon(ROOT / "examples" / "indexes" / "forge.toon.yaml"),
        ]
        target = build_graph(story, "modular_monolith", inventories)
        delta = as_is_to_be_delta(target, inventories)
        self.assertEqual(delta["schema_version"], "archpat.as-is-to-be-delta/v1")
        self.assertFalse(delta["applied"])
        self.assertFalse(delta["as_is_summary"]["unused_proof"])
        self.assertGreater(delta["as_is_summary"]["total_observed_modules"], 1000)
        self.assertTrue(delta["matched_target_nodes"])
        self.assertTrue(all(
            cand["evidence"] == "indexed_only" and cand["api_verified"] is False
            for m in delta["matched_target_nodes"]
            for cand in m["candidates"]
        ))

    def test_cli_migrate_view_coverage_delta_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "graph.json"
            graph_path.write_text(build_graph(_load_example_story(), "modular_monolith").model_dump_json(), encoding="utf-8")

            for args in (
                ("migrate", str(graph_path)),
                ("view", str(graph_path), "--layer", "temporal"),
                ("coverage", str(graph_path)),
                ("delta", str(graph_path), "--index", str(ROOT / "examples" / "indexes" / "uritime.toon.yaml")),
                ("schema", "ir-v2"),
            ):
                with self.subTest(args=args):
                    proc = subprocess.run(
                        [sys.executable, "-m", "archpat", *args],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    parsed = json.loads(proc.stdout)
                    self.assertIsInstance(parsed, dict)


if __name__ == "__main__":
    unittest.main()

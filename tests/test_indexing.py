from pathlib import Path
import hashlib
import tempfile
import unittest

from archpat.indexing import match_reuse, parse_toon, probe_workspace


FIXTURE = """# demo | 3f 80L | python:2,md:1 | 2026-11-21
# producer: code2llm | artifact: map.toon.yaml | schema: 1
# stats: 4 func | 1 cls | 3 mod | CC̄=2.5 | critical:1 | cycles:unknown
M[3]:
  src/service.py,60
  src/temporal.py,12
  README.md,8
D:
  src/service.py:
    i: json,os
    e: ServiceBinding,create_server
    ServiceBinding: to_dict(0),normalize(1)  # A binding, not execution.
    create_server(store;host)
  src/temporal.py:
    e: resolve_temporal_intent
    resolve_temporal_intent(intent)
  README.md:
"""


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.index_path = self.root / "index.toon.yaml"
        self.index_path.write_text(FIXTURE, encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_parse_reports_provenance_and_explicit_symbol_evidence(self):
        result = parse_toon(self.index_path)
        self.assertEqual("demo", result["project"])
        self.assertEqual(hashlib.sha256(FIXTURE.encode()).hexdigest(), result["sha256"])
        self.assertEqual("code2llm", result["header"]["producer"])
        self.assertEqual(3, result["stats"]["parsed_module_count"])
        self.assertEqual(2.5, result["stats"]["reported_mean_cc"])
        self.assertEqual("indexed_only", result["evidence"])
        self.assertFalse(result["api_verified"])
        self.assertEqual(
            ["ServiceBinding", "create_server", "ServiceBinding.to_dict", "ServiceBinding.normalize"],
            result["modules"][0]["symbols"],
        )
        self.assertNotIn("json", result["modules"][0]["symbols"])

    def test_detail_only_modules_have_unknown_loc(self):
        self.index_path.write_text(FIXTURE + "  src/extra.py:\n    e: extra\n", encoding="utf-8")
        result = parse_toon(self.index_path)
        self.assertEqual(3, result["stats"]["declared_module_count"])
        self.assertEqual(4, result["stats"]["parsed_module_count"])
        self.assertIsNone(result["modules"][-1]["loc"])

    def test_arbitrary_yaml_is_not_misrepresented_as_an_index(self):
        self.index_path.write_text("project: demo\nmodules: []\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            parse_toon(self.index_path)

    def test_duplicate_module_is_rejected(self):
        self.index_path.write_text(FIXTURE.replace("  README.md,8", "  src/service.py,8"), encoding="utf-8")
        with self.assertRaises(ValueError):
            parse_toon(self.index_path)

    def test_lexical_matches_are_deterministic_and_do_not_verify_api(self):
        inventory = parse_toon(self.index_path)
        matches = match_reuse(inventory, "temporal")
        self.assertEqual("src/temporal.py", matches[0]["path"])
        self.assertEqual("indexed_only", matches[0]["evidence"])
        self.assertFalse(matches[0]["api_verified"])
        self.assertEqual(matches, match_reuse(inventory, "temporal"))
        self.assertEqual([], match_reuse(inventory, ""))
        self.assertEqual([], match_reuse(inventory, "protobuf"))

    def test_probe_uses_ast_without_executing_module(self):
        source = self.root / "src"
        source.mkdir()
        marker = self.root / "must-not-exist"
        code = (
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
            "class ServiceBinding:\n    def to_dict(self):\n        return {}\n"
            "async def create_server():\n    return None\n"
        )
        (source / "service.py").write_text(code, encoding="utf-8")
        (self.root / "README.md").write_text("# docs", encoding="utf-8")
        result = probe_workspace(parse_toon(self.index_path), self.root)
        observation = result["modules"][0]
        self.assertFalse(marker.exists())
        self.assertEqual("source_ast_only", observation["evidence"])
        self.assertEqual(hashlib.sha256(code.encode()).hexdigest(), observation["sha256"])
        self.assertIn("ServiceBinding.to_dict", observation["symbols"])
        self.assertIn("create_server", observation["symbols"])
        self.assertEqual(["ServiceBinding.normalize"], observation["unobserved_index_symbols"])
        self.assertFalse(observation["api_verified"])
        self.assertEqual("missing", result["modules"][1]["status"])
        self.assertEqual("present_non_python", result["modules"][2]["status"])

    def test_probe_rejects_absolute_traversal_and_symlink_paths(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "secret.py"
            outside.write_text("def secret(): pass\n", encoding="utf-8")
            (self.root / "link.py").symlink_to(outside)
            inventory = {"modules": [
                {"path": str(outside)},
                {"path": "../secret.py"},
                {"path": "link.py"},
                {"path": "C:\\secret.py"},
            ]}
            result = probe_workspace(inventory, self.root)
            self.assertEqual({"unsafe_path": 4}, result["summary"])
            self.assertTrue(all("sha256" not in m for m in result["modules"]))

    def test_probe_reports_syntax_error_with_source_hash(self):
        broken = self.root / "broken.py"
        broken.write_text("def broken(:\n", encoding="utf-8")
        result = probe_workspace({"modules": [{"path": "broken.py"}]}, self.root)
        observation = result["modules"][0]
        self.assertEqual("parse_error", observation["status"])
        self.assertIn("sha256", observation)
        self.assertFalse(observation["api_verified"])


if __name__ == "__main__":
    unittest.main()

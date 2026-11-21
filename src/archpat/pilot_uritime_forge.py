"""Vertical PC integration pilot binding ArchPat proposals to real uritime, URT, Forge, and Polycell contracts.

Design boundaries (honest by construction):
- ArchPat remains the owner of the proposed ArchitectureGraph (``execution_ready=False``).
- ``uritime_urt`` owns temporal AST validation and deterministic resolution.
- ``urievents`` + ``uritime`` own CQRS command/query envelopes, PlanLedger CAS, and pure event replay.
- ``forge_base`` owns immutable Git-commit snapshots, bounded check execution, and CAS publication preconditions.
- ``wellmanifest/polycell`` owns the ``wellmanifest.polycell.cell/v1`` contract schema.

All runtime checks execute against isolated temporary directories and never mutate sibling checkouts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .indexing import parse_toon
from .io import read_json
from .models import StorySpec
from .synthesis import synthesize

ARCHPAT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EcosystemRoots:
    uritime_root: Path = Path("/home/tom/github/uritime")
    forge_root: Path = Path("/home/tom/github/paxlet-com/forge")
    polycell_root: Path = Path("/home/tom/github/wellmanifest/polycell")
    nl_uri_root: Path = Path("/home/tom/github/wellmanifest/nl-uri-dsl-llm")

    @property
    def python_paths(self) -> tuple[Path, ...]:
        return (
            self.uritime_root / "uritime" / "src",
            self.uritime_root / "urt" / "src",
            self.uritime_root / "autodo" / "src",
            self.forge_root / "packages" / "forge_base",
        )

    def missing_paths(self) -> list[str]:
        required = [
            *self.python_paths,
            self.polycell_root / "standard" / "polycell-cell.schema.v1.json",
            self.nl_uri_root / "schemas" / "process-uri.schema.json",
        ]
        return [str(p) for p in required if not p.exists()]


def _ensure_ecosystem_imports(roots: EcosystemRoots) -> None:
    missing = roots.missing_paths()
    if missing:
        raise FileNotFoundError(f"Missing local ecosystem paths: {missing}")
    for path in roots.python_paths:
        text = str(path.resolve())
        if text not in sys.path:
            sys.path.insert(0, text)


def verify_contract_corpus(roots: EcosystemRoots = EcosystemRoots()) -> dict[str, Any]:
    """ARP-002 + ARP-003: Run positive and negative contract examples against real upstream validators."""
    _ensure_ecosystem_imports(roots)

    from forge_base.contracts import IMPACT_URI, validate_input as forge_validate_input
    from subactor_autonomy.operation_descriptor import (
        canonical_operation_uri,
        parse_operation_uri,
    )
    from subactor_autonomy.ownership import Conflict
    from urievents.contracts import (
        CommandEnvelope,
        DataRef,
        ProcessRef,
        ServiceBinding,
        validate_command_envelope,
        validate_query_envelope,
    )
    from uritime_urt.errors import URTError
    from uritime_urt.intents import validate_temporal_intent
    from uritime_urt.resolution import resolve_temporal_intent

    checks: list[dict[str, Any]] = []

    def record(name: str, contract: str, expected: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "contract": contract,
                "expected": expected,
                "passed": passed,
                "detail": detail,
            }
        )

    # 1. nl-uri-dsl-llm process-uri.schema.json (upstream vs Forge copy)
    nl_schema_path = roots.nl_uri_root / "schemas" / "process-uri.schema.json"
    forge_schema_path = (
        roots.forge_root / "examples" / "wellman" / "standards" / "nl-uri-dsl-llm" / "process-uri.schema.json"
    )
    nl_schema = json.loads(nl_schema_path.read_text(encoding="utf-8"))
    nl_validator = Draft202012Validator(nl_schema, format_checker=FormatChecker())
    identical = nl_schema_path.read_bytes() == forge_schema_path.read_bytes()
    record(
        "nl_uri_schema_matches_forge_copy",
        "wellmanifest/nl-uri-dsl-llm/process-uri.schema.json",
        "identical_bytes",
        identical,
        f"sha256={hashlib.sha256(nl_schema_path.read_bytes()).hexdigest()[:16]}",
    )

    valid_process_uri_doc = {
        "uri": "proc://heyasa.forge/project/impact/v1",
        "payload": {"symbol": "request_review"},
        "provenance": {"source": "direct_dsl", "confidence": 1.0},
    }
    nl_validator.validate(valid_process_uri_doc)
    record("nl_uri_valid_action_uri", "nl-uri-dsl-llm/process-uri", "accept", True, valid_process_uri_doc["uri"])

    bad_process_uri_doc = {"payload": {"symbol": "missing_uri"}}
    try:
        nl_validator.validate(bad_process_uri_doc)
        record("nl_uri_missing_required_uri", "nl-uri-dsl-llm/process-uri", "reject", False, "unexpectedly accepted")
    except ValidationError as exc:
        record("nl_uri_missing_required_uri", "nl-uri-dsl-llm/process-uri", "reject", True, exc.message)

    # 2. urievents ur-cqrs-v1: CommandEnvelope positive + negative (unpinned input, URL-shaped process URI)
    artifact_bytes = b"exercise-submission-v1-screenshot-artifact"
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
    good_cmd = CommandEnvelope(
        command_id="cmd-exercise-review-001",
        ticket_id="exercise-feedback-001",
        process=ProcessRef(
            uri=canonical_operation_uri("exercise.review", 1),
            operation_id="exercise.review",
            version=1,
            effect="pure",
        ),
        inputs=[
            DataRef(
                name="submission",
                urn=f"urn:sha256:{artifact_sha}",
                logical_urn="urn:uritime:exercise:submission:ex-001",
                content_sha256=artifact_sha,
                media_type="application/octet-stream",
                size_bytes=len(artifact_bytes),
            )
        ],
        expected_output_schema={"type": "object", "required": ["status", "submission_urn"]},
        temporal_ref="urt:v1:interval:2026-11-21T10:00:00Z/2026-11-21T12:00:00Z",
        idempotency_key=f"review:ex-001:{artifact_sha[:16]}",
        service=ServiceBinding(
            url="http://127.0.0.1:8765/v1/exercise/review",
            connector_id="local-exercise-reviewer",
            remote_operation="exercise.review",
            readback_mode="sync",
        ),
        decision_mode="accepted",
        expected_version=0,
    )
    validate_command_envelope(good_cmd)
    record("urievents_command_valid", "ur.command-envelope/v1", "accept", True, good_cmd.process.uri)

    # Negative: accepted command with unpinned logical URN must fail
    unpinned_doc = good_cmd.to_dict()
    unpinned_doc["inputs"] = [
        {
            "name": "submission",
            "urn": "urn:uritime:exercise:submission:unpinned",
            "media_type": "application/octet-stream",
            "size_bytes": 10,
        }
    ]
    try:
        validate_command_envelope(unpinned_doc)
        record("urievents_command_unpinned_input", "ur.command-envelope/v1", "reject", False, "unexpectedly accepted")
    except ValueError as exc:
        record("urievents_command_unpinned_input", "ur.command-envelope/v1", "reject", True, str(exc))

    # Negative: query masquerading as command must fail
    try:
        validate_query_envelope({"schema": "ur.timeline-query/v1", "message_kind": "command"})
        record("urievents_query_masquerade", "ur.timeline-query/v1", "reject", False, "unexpectedly accepted")
    except ValueError as exc:
        record("urievents_query_masquerade", "ur.timeline-query/v1", "reject", True, str(exc))

    # 3. Autodo operation_descriptor fail-closed URL dereferencing boundary
    op_id, op_ver = parse_operation_uri("urn:poa:exercise.review#v1")
    record("autodo_parse_poa_uri", "ur.operation-descriptor/v1", "accept", (op_id, op_ver) == ("exercise.review", 1), f"{op_id}@{op_ver}")
    try:
        parse_operation_uri("https://example.com/exercise/review")
        record("autodo_reject_http_url", "ur.operation-descriptor/v1", "reject", False, "unexpectedly accepted")
    except Conflict as exc:
        record("autodo_reject_http_url", "ur.operation-descriptor/v1", "reject", True, str(exc))

    # 4. URT temporal intent validation & resolution (positive + negative unpinned alias)
    intent_valid = {
        "schema": "urt.temporal-intent/v1",
        "intent_id": "urn:uuid:7e9a1b04-5f5f-5c6c-9c7b-3b4d2a1f0001",
        "revision": 1,
        "source": {
            "text": "po dostarczeniu zrzutu ekranu, przed rozpoczęciem następnego ćwiczenia",
            "locale": "pl-PL",
        },
        "context": {
            "reference_now": "2026-11-21T09:00:00Z",
            "timezone": "Europe/Warsaw",
            "policy_ref": "policy://exercise-review/v1",
        },
        "ast": {
            "op": "all",
            "operands": [
                {
                    "op": "after",
                    "anchor": {
                        "op": "next",
                        "selector_id": "screenshot_delivered",
                        "selector": {
                            "domain": "observed_event",
                            "source": "urn:uritime:urievents",
                            "stream": "exercise_events",
                            "event_type": "artifact.submitted",
                            "scope": {"artifact_kind": "screenshot"},
                            "order": "stream_sequence",
                            "late_policy": "exclude_events_before_reference",
                            "tie_breaker": "sequence_then_id",
                            "on_missing": "wait",
                            "start_cursor": {
                                "store_id": "store-local-1",
                                "generation": 1,
                                "sequence": 0,
                            },
                        },
                    },
                    "offset": "PT0S",
                },
                {
                    "op": "before",
                    "anchor": {
                        "domain": "accepted_plan_occurrence",
                        "plan_id": "plan:course:next-exercise",
                        "revision": 1,
                        "occurrence_id": "occ-next-class",
                    },
                    "target": "completion",
                    "margin": "PT5M",
                },
            ],
        },
        "ambiguities": [],
        "provenance": {"producer": "archpat-pilot", "mode": "deterministic"},
    }
    validate_temporal_intent(intent_valid)
    res_valid = resolve_temporal_intent(
        intent_valid,
        observed_events=[
            {
                "id": "evt-screenshot-001",
                "source": "urn:uritime:urievents",
                "stream_id": "exercise_events",
                "store_id": "store-local-1",
                "generation": 1,
                "sequence": 1,
                "event_type": "artifact.submitted",
                "occurred_at": "2026-11-21T09:15:00Z",
                "data": {"artifact_kind": "screenshot"},
            }
        ],
        accepted_plans={("plan:course:next-exercise", 1): {"occ-next-class": "2026-11-21T10:00:00Z"}},
        resolved_at="2026-11-21T09:20:00Z",
    )
    record(
        "urt_temporal_intent_resolved",
        "urt.resolution/v1",
        "accept",
        res_valid["status"] == "resolved" and res_valid["dispatch_allowed"] is True,
        str(res_valid.get("resolved_urt")),
    )

    # Negative: missing explicit timezone must be rejected by validate_temporal_intent
    intent_bad_tz = json.loads(json.dumps(intent_valid))
    intent_bad_tz["context"]["timezone"] = ""
    try:
        validate_temporal_intent(intent_bad_tz)
        record("urt_missing_timezone_rejected", "urt.temporal-intent/v1", "reject", False, "unexpectedly accepted")
    except URTError as exc:
        record("urt_missing_timezone_rejected", "urt.temporal-intent/v1", "reject", True, f"{exc.code}: {exc}")

    # 5. Forge process contract validation (positive + negative undeclared node)
    forge_spec = forge_validate_input(
        IMPACT_URI,
        {
            "nodes": ["cmd.request_review", "aggregate.exercise", "projector.exercise"],
            "edges": [
                ["cmd.request_review", "aggregate.exercise"],
                ["aggregate.exercise", "projector.exercise"],
            ],
            "changed": ["aggregate.exercise"],
            "backend": "python",
        },
    )
    record("forge_impact_input_valid", IMPACT_URI, "accept", forge_spec["name"] == "analyze.impact", forge_spec["uri"])
    try:
        forge_validate_input(
            IMPACT_URI,
            {
                "nodes": ["aggregate.exercise"],
                "edges": [],
                "changed": ["undeclared.node"],
            },
        )
        record("forge_impact_undeclared_node", IMPACT_URI, "reject", False, "unexpectedly accepted")
    except ValueError as exc:
        record("forge_impact_undeclared_node", IMPACT_URI, "reject", True, str(exc))

    # 6. Polycell cell contract validation (pricing.quote + autonomy-pilot backlog.reconciliation + negative)
    cell_schema_path = roots.polycell_root / "standard" / "polycell-cell.schema.v1.json"
    cell_validator = Draft202012Validator(json.loads(cell_schema_path.read_text(encoding="utf-8")))
    for label, yaml_path in (
        ("polycell_pricing_quote_cell", roots.polycell_root / "contracts" / "cells" / "pricing.quote.cell.yaml"),
        (
            "uritime_pilot_backlog_cell",
            roots.uritime_root / "planning" / "autonomy-pilot" / "contracts" / "cells" / "backlog.reconciliation.cell.yaml",
        ),
    ):
        doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        cell_validator.validate(doc)
        record(label, "wellmanifest.polycell.cell/v1", "accept", True, doc["urn"])

    bad_cell = {
        "schema": "wellmanifest.polycell.cell/v1",
        "urn": "https://not-a-cell-urn.example/bad",
        "name": "bad.cell",
        "version": "0.1.0",
        "owner": "python",
        "input": {},
        "output": {},
    }
    try:
        cell_validator.validate(bad_cell)
        record("polycell_invalid_urn_rejected", "wellmanifest.polycell.cell/v1", "reject", False, "unexpectedly accepted")
    except ValidationError as exc:
        record("polycell_invalid_urn_rejected", "wellmanifest.polycell.cell/v1", "reject", True, exc.message)

    # Execute all 14 pure examples of autonomy-pilot's backlog_reconciliation.py
    pilot_cell_yaml = yaml.safe_load(
        (roots.uritime_root / "planning" / "autonomy-pilot" / "contracts" / "cells" / "backlog.reconciliation.cell.yaml")
        .read_text(encoding="utf-8")
    )
    pilot_cell_py = roots.uritime_root / "planning" / "autonomy-pilot" / "cells" / "python" / "backlog_reconciliation.py"
    examples_passed = _run_backlog_cell_examples(pilot_cell_py, pilot_cell_yaml["examples"])
    record(
        "polycell_backlog_reconciliation_examples",
        "urn:wm:cell:autonomy:backlog.reconciliation:v1",
        "all_pass",
        examples_passed["passed"] == examples_passed["total"] and examples_passed["total"] > 0,
        f"{examples_passed['passed']}/{examples_passed['total']} examples passed",
    )

    all_passed = all(c["passed"] for c in checks)
    return {
        "schema": "archpat.contract-corpus/v1",
        "evidence_level": "contract_verified" if all_passed else "source_verified",
        "all_passed": all_passed,
        "total": len(checks),
        "passed": sum(1 for c in checks if c["passed"]),
        "checks": checks,
    }


def _run_backlog_cell_examples(cell_py: Path, examples: list[dict[str, Any]]) -> dict[str, int]:
    """Load the pure backlog_reconciliation cell in isolation and verify every YAML example."""
    stub = types.ModuleType("polycell_types")
    stub.BacklogReconciliationInput = dict  # type: ignore[attr-defined]
    stub.BacklogReconciliationOutput = dict  # type: ignore[attr-defined]
    previous = sys.modules.get("polycell_types")
    sys.modules["polycell_types"] = stub
    try:
        spec = importlib.util.spec_from_file_location("_archpat_pilot_backlog_cell", cell_py)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if previous is None:
            sys.modules.pop("polycell_types", None)
        else:
            sys.modules["polycell_types"] = previous

    passed = 0
    for ex in examples:
        actual = mod.run(ex["input"])
        if actual == ex["output"]:
            passed += 1
    return {"passed": passed, "total": len(examples)}


def _run_forge_qualification_point(roots: EcosystemRoots, work_dir: Path) -> dict[str, Any]:
    """Bind 1 real Forge qualification point (SnapshotStore + project_jobs prepare/run_checks/publish_precondition)."""
    _ensure_ecosystem_imports(roots)
    from forge_base.project_jobs import prepare, publish_precondition, run_checks
    from forge_base.snapshots import SnapshotStore

    repo = work_dir / "exercise_review_target"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "review.py").write_text(
        '"""Minimal target module for exercise-feedback vertical pilot."""\n'
        "def review_submission(submission_urn: str) -> dict[str, str]:\n"
        '    return {"status": "pending", "submission_urn": submission_urn}\n',
        encoding="utf-8",
    )
    (repo / "test_review.py").write_text(
        "import unittest\n"
        "from review import review_submission\n\n"
        "class TestReview(unittest.TestCase):\n"
        "    def test_status(self):\n"
        '        out = review_submission("urn:sha256:" + "a" * 64)\n'
        '        self.assertEqual(out["status"], "pending")\n',
        encoding="utf-8",
    )

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "GIT_AUTHOR_NAME": "ArchPat Pilot",
                "GIT_AUTHOR_EMAIL": "pilot@local.invalid",
                "GIT_COMMITTER_NAME": "ArchPat Pilot",
                "GIT_COMMITTER_EMAIL": "pilot@local.invalid",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        )

    git("init", "-q")
    git("add", "review.py", "test_review.py")
    git("commit", "-q", "-m", "initial clean target")

    project_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, 'archpat.pilot.exercise-review')}"
    store = SnapshotStore(work_dir / "forge-snapshots")
    captured = store.capture(repo, project_urn)
    snapshot_id = captured["snapshot_id"]

    # Unified diff upgrading review_submission to require pinned sha256 URN and return qualified feedback
    import difflib

    old_review = (repo / "review.py").read_text(encoding="utf-8")
    new_review = (
        '"""Minimal target module for exercise-feedback vertical pilot."""\n'
        "def review_submission(submission_urn: str) -> dict[str, str]:\n"
        '    if not submission_urn.startswith("urn:sha256:"):\n'
        '        raise ValueError("submission_urn must be content-pinned")\n'
        '    return {"status": "reviewed", "submission_urn": submission_urn}\n'
    )
    old_test = (repo / "test_review.py").read_text(encoding="utf-8")
    new_test = (
        "import unittest\n"
        "from review import review_submission\n\n"
        "class TestReview(unittest.TestCase):\n"
        "    def test_status(self):\n"
        '        out = review_submission("urn:sha256:" + "a" * 64)\n'
        '        self.assertEqual(out["status"], "reviewed")\n\n'
        "    def test_rejects_unpinned(self):\n"
        "        with self.assertRaises(ValueError):\n"
        '            review_submission("urn:example:unpinned")\n'
    )
    patch_text = "".join(
        difflib.unified_diff(old_review.splitlines(True), new_review.splitlines(True), fromfile="a/review.py", tofile="b/review.py")
    ) + "".join(
        difflib.unified_diff(old_test.splitlines(True), new_test.splitlines(True), fromfile="a/test_review.py", tofile="b/test_review.py")
    )
    patch = patch_text.encode("utf-8")

    job = prepare(store, snapshot_id, work_dir / "forge-workspaces", "exercise-review-job", patch)
    checked = run_checks(job, [[sys.executable, "-B", "-m", "unittest", "-q", "test_review.py"]], timeout=60)
    fresh_decision = publish_precondition(store, repo, checked)

    # Simulate concurrent upstream commit to prove Forge rejects stale snapshots fail-closed
    (repo / "README.md").write_text("concurrent change\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "concurrent commit advancing base snapshot")
    stale_decision = publish_precondition(store, repo, checked)

    return {
        "project_urn": project_urn,
        "snapshot_id": snapshot_id,
        "changed_paths": checked["changed_paths"],
        "patch_sha256": checked["patch_sha256"],
        "checks_status": checked["status"],
        "result_digest": checked["result_digest"],
        "fresh_publish_precondition": fresh_decision,
        "stale_publish_precondition": stale_decision,
    }


def run_vertical_pilot(
    roots: EcosystemRoots = EcosystemRoots(),
    story_path: Path = ARCHPAT_ROOT / "examples" / "story-local.json",
) -> dict[str, Any]:
    """Execute Section 12 vertical pilot:
    ArchPat synthesis -> URT temporal resolution -> 1 Command (PlanLedger) + 1 Query (PlanQueries)
    -> pure replay -> Forge SnapshotStore/project_jobs qualification -> Polycell/URI corpus verification.
    """
    _ensure_ecosystem_imports(roots)

    from subactor_autonomy.operation_descriptor import canonical_operation_uri
    from urievents.contracts import (
        CommandEnvelope,
        DataRef,
        ProcessRef,
        ServiceBinding,
        export_store_to_urt_records,
        validate_command_envelope,
        validate_query_envelope,
    )
    from urievents.store import UriEventStore
    from uritime.plan_commands import OwnershipViolationError, PlanConflictError, PlanLedger
    from uritime.plan_queries import PlanQueries
    from uritime_urt.resolution import resolve_temporal_intent

    # 1. ArchPat synthesis (proposal stage remains execution_ready=False)
    story = StorySpec.model_validate(read_json(story_path))
    indexes = [
        parse_toon(ARCHPAT_ROOT / "examples" / "indexes" / "uritime.toon.yaml"),
        parse_toon(ARCHPAT_ROOT / "examples" / "indexes" / "forge.toon.yaml"),
    ]
    synthesis = synthesize(story, indexes)
    selected = next(c for c in synthesis.candidates if c.id == synthesis.selected_id)

    # 2. Temporal resolution via real uritime_urt
    cmd_op = next(op for op in story.operations if op.kind == "command")
    qry_op = next(op for op in story.operations if op.kind == "query")
    assert cmd_op.temporal is not None

    temporal_intent = {
        "schema": "urt.temporal-intent/v1",
        "intent_id": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'{story.id}:{cmd_op.id}')}",
        "revision": 1,
        "source": {"text": cmd_op.temporal.text, "locale": "pl-PL"},
        "context": {
            "reference_now": "2026-11-21T09:00:00Z",
            "timezone": cmd_op.temporal.timezone,
            "policy_ref": "policy://archpat-pilot/exercise-review/v1",
        },
        "ast": {
            "op": "all",
            "operands": [
                {
                    "op": "after",
                    "anchor": {
                        "op": "next",
                        "selector_id": "screenshot_delivered",
                        "selector": {
                            "domain": "observed_event",
                            "source": "urn:uritime:urievents",
                            "stream": "exercise_events",
                            "event_type": "artifact.submitted",
                            "scope": {"exercise_id": "ex-001"},
                            "order": "stream_sequence",
                            "late_policy": "exclude_events_before_reference",
                            "tie_breaker": "sequence_then_id",
                            "on_missing": "wait",
                            "start_cursor": {
                                "store_id": "store-pilot-01",
                                "generation": 1,
                                "sequence": 0,
                            },
                        },
                    },
                    "offset": "PT0S",
                },
                {
                    "op": "before",
                    "anchor": {
                        "domain": "accepted_plan_occurrence",
                        "plan_id": "plan:course:next-exercise",
                        "revision": 1,
                        "occurrence_id": "occ-next-exercise",
                    },
                    "target": "completion",
                    "margin": "PT5M",
                },
            ],
        },
        "ambiguities": [],
        "provenance": {"producer": "archpat-pilot", "story_id": story.id},
    }
    resolution = resolve_temporal_intent(
        temporal_intent,
        observed_events=[
            {
                "id": "evt-screenshot-ex-001",
                "source": "urn:uritime:urievents",
                "stream_id": "exercise_events",
                "store_id": "store-pilot-01",
                "generation": 1,
                "sequence": 1,
                "event_type": "artifact.submitted",
                "occurred_at": "2026-11-21T09:15:00Z",
                "data": {"exercise_id": "ex-001"},
            }
        ],
        accepted_plans={("plan:course:next-exercise", 1): {"occ-next-exercise": "2026-11-21T10:00:00Z"}},
        resolved_at="2026-11-21T09:20:00Z",
    )
    assert resolution["status"] == "resolved" and resolution["dispatch_allowed"] is True

    # 3. Bind 1 Command + 1 Query against real UriEventStore, PlanLedger, PlanQueries
    artifact_payload = json.dumps(
        {"exercise": "ex-001", "student": "student-01", "artifact": "screenshot.png"},
        sort_keys=True,
    ).encode("utf-8")
    artifact_sha = hashlib.sha256(artifact_payload).hexdigest()
    pinned_urn = f"urn:sha256:{artifact_sha}"
    plan_id = f"urn:uritime:plan:{story.id}:ex-001"
    idempotency_key = f"{cmd_op.id}:ex-001:{artifact_sha[:16]}"

    command_envelope = CommandEnvelope(
        command_id=f"cmd-{story.id}-001",
        ticket_id=plan_id,
        process=ProcessRef(
            uri=canonical_operation_uri(cmd_op.capability, 1),
            operation_id=cmd_op.capability,
            version=1,
            effect="pure",
        ),
        inputs=[
            DataRef(
                name="submission",
                urn=pinned_urn,
                logical_urn="urn:uritime:exercise:submission:ex-001",
                content_sha256=artifact_sha,
                media_type="application/json",
                size_bytes=len(artifact_payload),
            )
        ],
        expected_output_schema={"type": "object", "required": ["status", "submission_urn"]},
        temporal_ref=str(resolution["resolved_urt"]),
        idempotency_key=idempotency_key,
        service=ServiceBinding(
            url="http://127.0.0.1:8765/v1/exercise/review",
            connector_id="local-exercise-reviewer",
            remote_operation=cmd_op.capability,
            readback_mode="sync",
        ),
        decision_mode="accepted",
        intent_digest=str(resolution["intent_digest"]),
        expected_version=0,
    )
    validated_cmd = validate_command_envelope(command_envelope)

    query_envelope = validate_query_envelope(
        {
            "schema": "ur.timeline-query/v1",
            "message_kind": "query",
            "ticket_id": plan_id,
            "recorded_at": 1795167600.0,
        }
    )

    pilot_tmp_base = ARCHPAT_ROOT / "build" / ".pilot-tmp"
    pilot_tmp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="archpat-vertical-pilot-", dir=pilot_tmp_base) as tmp:
        work_dir = Path(tmp)
        store = UriEventStore(work_dir / "urievents-state")
        ledger = PlanLedger(store)
        queries = PlanQueries(store)

        # Command step A: ArchPat proposes non-dispatchable plan
        proposal_ev = ledger.propose_plan(
            plan_id,
            proposer="archpat",
            occurrences=[
                {
                    "occurrence_id": "occ-review-001",
                    "process_uri": validated_cmd["process"]["uri"],
                    "submission_urn": pinned_urn,
                    "idempotency_key": idempotency_key,
                    "window_urt": resolution["resolved_urt"],
                    "planned_ts": 1795166100.0,
                }
            ],
            reason=f"ArchPat selected {selected.graph.variant} for {story.id}",
            recorded_at=1795166400.0,
        )

        # Negative ownership check: archpat cannot self-accept a Plan (owner=uritime)
        archpat_accept_rejected = False
        try:
            ledger.accept_plan(
                plan_id,
                expected_version=0,
                proposal_event_urn=proposal_ev.event_urn,
                actor="archpat",
                recorded_at=1795166410.0,
            )
        except OwnershipViolationError:
            archpat_accept_rejected = True

        # Command step B: uritime authority accepts proposal under CAS expected_version=0
        accepted_ev = ledger.accept_plan(
            plan_id,
            expected_version=0,
            proposal_event_urn=proposal_ev.event_urn,
            actor="uritime",
            recorded_at=1795166420.0,
        )

        # Idempotency / CAS check: re-accepting same proposal with expected_version=0 fails without duplicating state
        events_before_dup = len(store.list_events(after_seq=0, limit=100))
        duplicate_rejected = False
        try:
            ledger.accept_plan(
                plan_id,
                expected_version=0,
                proposal_event_urn=proposal_ev.event_urn,
                actor="uritime",
                recorded_at=1795166430.0,
            )
        except PlanConflictError:
            duplicate_rejected = True
        events_after_dup = len(store.list_events(after_seq=0, limit=100))

        # Export CloudEvents URT Record v1 from live store
        urt_records = export_store_to_urt_records(store)

        # Query step: strictly read-only get_plan + query_knowledge_at + pure replay
        seq_before_query = store.stream_identity()["sequence"]
        plan_view = queries.get_plan(plan_id, recorded_at=query_envelope["recorded_at"])
        knowledge_view = queries.query_knowledge_at(
            recorded_cutoff=float(query_envelope["recorded_at"]),
            ticket_id=plan_id,
        )
        seq_after_query = store.stream_identity()["sequence"]

        all_events = store.list_events(after_seq=0, limit=100)
        replayed_view = PlanQueries.rebuild_from_events(all_events, plan_id)
        replay_matches_live = (
            replayed_view["active_revision"] == plan_view["active_revision"]
            and replayed_view["status"] == plan_view["status"]
            and replayed_view["dispatchable_occurrences"] == plan_view["dispatchable_occurrences"]
        )

        # 4. Forge qualification point
        forge_result = _run_forge_qualification_point(roots, work_dir)

    # 5. ARP-002 + ARP-003 contract corpus
    corpus = verify_contract_corpus(roots)

    acceptance = {
        "criterion_1_idempotent_command": duplicate_rejected and events_before_dup == events_after_dup,
        "criterion_2_readonly_query_zero_mutations": (
            seq_before_query == seq_after_query and plan_view["active_revision"] == 1
        ),
        "criterion_3_pure_replay_matches_live": replay_matches_live,
        "criterion_4_pinned_artifact_urn": (
            validated_cmd["inputs"][0]["urn"] == pinned_urn
            and plan_view["dispatchable_occurrences"][0]["submission_urn"] == pinned_urn
        ),
        "criterion_5_urt_temporal_resolution": (
            resolution["status"] == "resolved"
            and str(resolution["resolved_urt"]).startswith("urt:v1:interval:")
        ),
        "ownership_enforced_uritime_only": archpat_accept_rejected,
        "forge_fresh_publishable": forge_result["fresh_publish_precondition"]["publishable"] is True,
        "forge_stale_snapshot_rejected": (
            forge_result["stale_publish_precondition"]["publishable"] is False
            and "base_snapshot_changed" in forge_result["stale_publish_precondition"]["reasons"]
        ),
        "contract_corpus_all_passed": corpus["all_passed"] is True,
    }
    all_ok = all(acceptance.values())

    graph_sha256 = hashlib.sha256(
        json.dumps(selected.graph.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "archpat.vertical-pilot-result/v1",
        "story_id": story.id,
        "archpat_proposal": {
            "selected_variant": selected.graph.variant,
            "graph_sha256": graph_sha256,
            "execution_ready": synthesis.execution_ready,
        },
        "evidence_level": "integration_verified" if all_ok else "contract_verified",
        "all_acceptance_passed": all_ok,
        "acceptance": acceptance,
        "temporal_resolution": {
            "status": resolution["status"],
            "resolved_urt": resolution["resolved_urt"],
            "intent_digest": resolution["intent_digest"],
            "eligibility": resolution["eligibility"],
        },
        "command_binding": {
            "operation_id": cmd_op.id,
            "process_uri": validated_cmd["process"]["uri"],
            "plan_id": plan_id,
            "proposal_event_urn": proposal_ev.event_urn,
            "accepted_event_urn": accepted_ev.event_urn,
            "accepted_version": plan_view["active_revision"],
            "pinned_input_urn": pinned_urn,
            "exported_urt_records": len(urt_records),
        },
        "query_binding": {
            "operation_id": qry_op.id,
            "plan_status": plan_view["status"],
            "plan_version": plan_view["active_revision"],
            "events_before_query": seq_before_query,
            "events_after_query": seq_after_query,
            "audit_trail_entries": len(knowledge_view["audit_trail"]),
            "replay_matches_live": replay_matches_live,
        },
        "forge_qualification": forge_result,
        "contract_corpus_summary": {
            "total": corpus["total"],
            "passed": corpus["passed"],
            "all_passed": corpus["all_passed"],
        },
    }

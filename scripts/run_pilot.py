#!/usr/bin/env python3
"""Run ARP-001 source-lock, ARP-002/003 contract corpus, and Section 12 vertical PC pilot."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_source_lock import build_source_lock  # noqa: E402
from archpat.pilot_uritime_forge import run_vertical_pilot, verify_contract_corpus  # noqa: E402


def main() -> int:
    evidence_dir = ROOT / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    source_lock = build_source_lock()
    (evidence_dir / "source-lock.json").write_text(
        json.dumps(source_lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    corpus = verify_contract_corpus()
    (evidence_dir / "contract-corpus.json").write_text(
        json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    pilot = run_vertical_pilot()
    (evidence_dir / "pilot-result.json").write_text(
        json.dumps(pilot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    summary = {
        "source_lock_present": sum(1 for s in source_lock["sources"] if s["status"] == "source_verified"),
        "source_lock_missing": [s["id"] for s in source_lock["sources"] if s["status"] != "source_verified"],
        "contract_corpus": f"{corpus['passed']}/{corpus['total']}",
        "pilot_evidence_level": pilot["evidence_level"],
        "pilot_all_acceptance_passed": pilot["all_acceptance_passed"],
        "forge_checks_status": pilot["forge_qualification"]["checks_status"],
        "forge_fresh_publishable": pilot["forge_qualification"]["fresh_publish_precondition"]["publishable"],
        "forge_stale_reasons": pilot["forge_qualification"]["stale_publish_precondition"]["reasons"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if (corpus["all_passed"] and pilot["all_acceptance_passed"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

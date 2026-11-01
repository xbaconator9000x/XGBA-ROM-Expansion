#!/usr/bin/env python3
"""Read-only evaluator for the proposed Copilot-qualified Phase 1 v2 lane."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import phase1_copilot_receipts_v4_adapter as adapter

SCHEMA = "xgba.phase1.semantic_review_policy.v2"
PASSED = "COPILOT_REVIEWED/PASSED"
NEEDS_REVIEW = "NEEDS_REVIEW"
BLOCKED = "BLOCKED"
LEGACY_APPROVALS = 0
LEGACY_P0_CANDIDATES = 338
INVENTORY_SIZE = 14834
NEEDS_REVIEW_BLOCKERS = (
    "Receipt has no semantic approval decision",
    "Receipt lacks substantive semantic rationale",
    "Receipt lacks source-grounded semantic findings",
    "Receipt contains an unsupported or empty finding",
    "Finding lacks valid whole-file source line anchors",
    "Receipt does not bind complete source-file coverage",
    "Whole-file line coverage has gaps or invalid ranges",
    "Dependency closure is incomplete",
    "Dependency closure lacks review rationale",
    "Dependency closure inventory is missing",
    "Licensing is unresolved or lacks rationale",
    "Licensing clearance lacks pinned evidence",
    "Evidence distinctions are incomplete",
    "Evidence distinction has an unsupported status:",
    "Claimed evidence lacks hashed artifacts:",
    "Non-source VERIFIED artifacts require independent byte verification:",
    "Unrun or unclaimed evidence lacks an explicit reason:",
    "Objection disposition is missing",
    "Unresolved substantive objection",
)


def _source_label(key):
    return f"{key[0]}:{key[1]}"


def _classify_result(result):
    if result is None:
        return BLOCKED, "Pinned v4 adapter omitted this receipt"
    if result.get("status") == "COPILOT_RECEIPT_VALIDATED":
        if any(type(result.get(field)) is not int or result[field] < 1
               for field in ("pr_jobs", "push_jobs")):
            return BLOCKED, "Pinned v4 adapter omitted successful executed PR/push job counts"
        return PASSED, "Pinned v4 receipt, source/dossier evidence, provenance, and exact-head CI validated"
    blocker = str(result.get("blocker") or "Receipt provenance or infrastructure validation failed")
    # Only errors emitted for substantive review gaps by the hash-pinned v4 validator
    # map to NEEDS_REVIEW; provenance and infrastructure errors remain BLOCKED.
    if result.get("status") == "BLOCKED" and any(
        marker in blocker for marker in NEEDS_REVIEW_BLOCKERS
    ):
        return NEEDS_REVIEW, blocker
    return BLOCKED, blocker


def _validate_legacy_gate(gate):
    if not isinstance(gate, dict):
        raise ValueError("Legacy mapping gate snapshot is not an object")
    if gate.get("decision") != "FAIL_INCOMPLETE":
        raise ValueError("Legacy mapping gate changed; v2 proposal must remain non-authoritative")
    if (
        gate.get("verified_source_manifest_entries") != INVENTORY_SIZE
        or gate.get("machine_generated_dossiers") != INVENTORY_SIZE
        or gate.get("p0_review_candidates") != LEGACY_P0_CANDIDATES
        or gate.get("approved_semantic_dispositions") != LEGACY_APPROVALS
    ):
        raise ValueError("Historical legacy gate counts changed from the pinned proposal baseline")
    return gate["approved_semantic_dispositions"]


def build_report(receipts, adapter_results, legacy_gate):
    """Project only pinned adapter outcomes into v2 labels; never alter legacy gate data."""
    legacy_count = _validate_legacy_gate(legacy_gate)
    adapter.validate_receipt_inventory(receipts)
    expected_keys = set(adapter.EXPECTED_RECEIPTS)

    results_by_key = {}
    global_error = None
    if not isinstance(adapter_results, list):
        global_error = "Pinned v4 adapter returned an invalid result collection"
    else:
        for result in adapter_results:
            if not isinstance(result, dict) or not isinstance(result.get("source"), str):
                global_error = "Pinned v4 adapter returned a malformed per-file result"
                break
            parts = result["source"].split(":", 1)
            key = tuple(parts) if len(parts) == 2 else ()
            if key not in expected_keys or key in results_by_key:
                global_error = "Pinned v4 adapter returned an unknown or duplicate source"
                break
            results_by_key[key] = result

    dispositions = []
    for key in sorted(expected_keys):
        result = results_by_key.get(key)
        if global_error:
            status, reason = BLOCKED, global_error
        else:
            status, reason = _classify_result(result)
        item = {"source": _source_label(key), "disposition": status, "reason": reason}
        for field in ("pr_jobs", "push_jobs"):
            if field in (result or {}):
                item[field] = result[field]
        dispositions.append(item)

    qualified = {
        item["source"]
        for item in dispositions
        if item["disposition"] == PASSED
    }
    return {
        "schema": SCHEMA,
        "policy_status": "PROPOSAL_NOT_ACTIVATED",
        "legacy_external_independent_approved": legacy_count,
        "legacy_p0_external_independent_approved": LEGACY_APPROVALS,
        "legacy_p0_review_candidates": LEGACY_P0_CANDIDATES,
        "legacy_inventory_total": INVENTORY_SIZE,
        "v2_qualified_semantic_review_count": len(qualified),
        "v2_completion_gate": "FAIL_INCOMPLETE",
        "dispositions": dispositions,
    }


def evaluate(pr8_root, source_root, legacy_gate_path, token=None):
    pinned_root = adapter.verify_pinned_worktree(pr8_root)
    receipt_path = pinned_root / adapter.RECEIPT_PATH
    receipts, problems = adapter._load_pinned_validator(pinned_root)[1].load_receipts(receipt_path)
    if problems:
        raise ValueError("; ".join(problems))
    adapter.validate_receipt_inventory(receipts)
    legacy_gate = json.loads(Path(legacy_gate_path).read_text(encoding="utf-8"))
    _validate_legacy_gate(legacy_gate)
    adapter_results = adapter.run_live(pr8_root, source_root, token=token)
    return build_report(receipts, adapter_results, legacy_gate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr8-root", type=Path, required=True,
                        help="full-history worktree at the exact pinned PR #8 head")
    parser.add_argument("--source-root", type=Path, required=True,
                        help="read-only upstream checkouts at their pinned revisions")
    parser.add_argument(
        "--legacy-gate",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "semantic-snapshots/current/phase1_mapping_gate.json",
        help="read-only historical Ed25519 gate snapshot",
    )
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.pr8_root, args.source_root, args.legacy_gate)
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "policy_status": "PROPOSAL_NOT_ACTIVATED",
            "legacy_external_independent_approved": None,
            "legacy_p0_external_independent_approved": None,
            "v2_qualified_semantic_review_count": 0,
            "v2_completion_gate": "FAIL_INCOMPLETE",
            "dispositions": [
                {"source": _source_label(key), "disposition": BLOCKED, "reason": str(exc)}
                for key in sorted(adapter.EXPECTED_RECEIPTS)
            ],
        }
        print(json.dumps(report, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if all(item["disposition"] == PASSED for item in report["dispositions"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

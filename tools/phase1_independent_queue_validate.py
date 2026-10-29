#!/usr/bin/env python3
"""Fail-closed bootstrap validation for the Phase 1 independent review queue.

This is queue schema/integrity verification, NEVER an independent source approval.
"""
import argparse
import json
import re
from pathlib import Path

EXPECTED_PINS = {
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "pret/agbcc": "da598c1d918402c42c0c0d7128ba14567f3175e9",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
    "huderlem/porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
}
GROUPS = (("curated_p0", 29), ("remaining_p0", 309), ("other_inventory", 14496))
SHA = re.compile(r"^[0-9a-f]{40}$")


def validate(root):
    root = Path(root)
    issues = []
    try:
        gate = json.loads((root / "semantic-snapshots/current/phase1_mapping_gate.json").read_text())
        queue = json.loads((root / "semantic-snapshots/independent-reviews/queue.json").read_text())
        curated = json.loads((root / "semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json").read_text())
    except (OSError, ValueError) as exc:
        return ["missing or malformed authoritative JSON: " + str(exc)]

    if gate.get("decision") != "FAIL_INCOMPLETE":
        issues.append("authoritative gate must remain FAIL_INCOMPLETE")
    if gate.get("approved_semantic_dispositions") != 0 or gate.get("remaining_dispositions") != 14834:
        issues.append("bootstrap gate cannot claim independent approvals")
    if gate.get("verified_source_manifest_entries") != 14834 or gate.get("p0_review_candidates") != 338:
        issues.append("authoritative inventory/P0 count mismatch")
    if queue.get("schema_version") != 1 or queue.get("source") != "semantic-snapshots/current/phase1_mapping_gate.json":
        issues.append("queue schema or gate provenance mismatch")
    if queue.get("status") != "READY_FOR_INDEPENDENT_REVIEW" or queue.get("phase1_gate") != "FAIL_INCOMPLETE":
        issues.append("queue status/gate mismatch")
    if queue.get("total_target") != 14834 or queue.get("total_approved") != 0:
        issues.append("queue target or independent approval count mismatch")
    if "distinct independent" not in queue.get("review_policy", ""):
        issues.append("distinct independent reviewer requirement absent")
    if not isinstance(queue.get("priority"), list) or [
        (x.get("group"), x.get("target"), x.get("approved")) for x in queue.get("priority", [])
        if isinstance(x, dict)
    ] != [(name, target, 0) for name, target in GROUPS]:
        issues.append("queue group order, counts, or approval totals invalid")
    if curated.get("candidate_file_count") != 29 or curated.get("independent_review_approvals") != 0 or curated.get("phase1_mapping_complete") is not False:
        issues.append("curated candidate count or approval status invalid")
    if curated.get("repository_pins") != EXPECTED_PINS:
        issues.append("immutable source pins mismatch")
    files = curated.get("candidate_files", [])
    if not isinstance(files, list) or len(files) != 29:
        issues.append("curated candidate array must have 29 entries")
        files = []
    seen = set()
    for i, entry in enumerate(files):
        if not isinstance(entry, dict):
            issues.append("curated entry is not an object: " + str(i))
            continue
        key = (entry.get("repository"), entry.get("source_path"), entry.get("revision"))
        if key in seen:
            issues.append("duplicate curated source identity: " + str(i))
        seen.add(key)
        if entry.get("revision") != EXPECTED_PINS.get(entry.get("repository")):
            issues.append("source revision not pinned: " + str(i))
        if not SHA.fullmatch(str(entry.get("expected_git_blob_sha1", ""))):
            issues.append("invalid source blob SHA: " + str(i))
        if not entry.get("interpreted_semantic_roles"):
            issues.append("missing interpreted role: " + str(i))
        if entry.get("independent_whole_file_signoff") is not False or entry.get("status") != "CANDIDATE_AWAITING_INDEPENDENT_WHOLE_FILE_REVIEW":
            issues.append("unsupported independent approval: " + str(i))
        if entry.get("upstream_blob_url") != (
            "https://github.com/" + str(entry.get("repository")) + "/blob/"
            + str(entry.get("revision")) + "/" + str(entry.get("source_path"))
        ):
            issues.append("source URL does not match pinned identity: " + str(i))
    docs = curated.get("source_documentation", [])
    doc_hashes = curated.get("source_documentation_git_blob_sha1", {})
    if len(docs) != 5 or len(set(docs)) != 5 or set(docs) != set(doc_hashes):
        issues.append("curated source evidence documents incomplete")
    if any(not SHA.fullmatch(str(h)) for h in doc_hashes.values()):
        issues.append("invalid evidence document blob pin")
    if (root / "semantic-snapshots/independent-reviews/approved.json").exists():
        issues.append("unverified approval receipt file found")
    intake_path = root / "semantic-snapshots/independent-reviews/curated-p0-intake-20261029.json"
    try:
        intake = json.loads(intake_path.read_text())
    except (OSError, ValueError) as exc:
        issues.append("missing or malformed curated intake: " + str(exc))
        return issues
    if intake.get("schema") != "xgba.phase1.curated_p0_independent_review_intake.v1":
        issues.append("intake schema mismatch")
    if intake.get("source_registry_blob_sha1") != "b6269c9a4ddf164643e3202ffb0497e27160bcca":
        issues.append("intake registry pin mismatch")
    if intake.get("record_count") != 29 or intake.get("partial_source_inspected_count") != 5 or intake.get("registry_only_count") != 24:
        issues.append("intake count mismatch")
    if intake.get("independent_approved_count") != 0 or intake.get("gate") != "FAIL_INCOMPLETE":
        issues.append("intake cannot claim approvals or completed gate")
    records = intake.get("records", [])
    if not isinstance(records, list) or len(records) != 29:
        issues.append("intake must have 29 per-file records")
        records = []
    inspected = 0
    for i, record in enumerate(records):
        if not isinstance(record, dict) or i >= len(files):
            issues.append("invalid intake record index " + str(i))
            continue
        f = files[i]
        expected_identity = {
            "repository": f.get("repository"), "revision": f.get("revision"),
            "path": f.get("source_path"), "git_blob_sha1": f.get("expected_git_blob_sha1"),
        }
        if record.get("identity") != expected_identity or record.get("ordinal") != i + 1:
            issues.append("intake source identity mismatch: " + str(i))
        if (record.get("independent_reviewer") is not None
                or record.get("independent_review_receipt") is not None
                or record.get("independent_review_verdict") != "NEEDS_REVIEW"
                or record.get("whole_file_semantic_coverage") is not False
                or record.get("machine_dossier_sha1") is not None):
            issues.append("intake invented reviewer, whole-file coverage or dossier: " + str(i))
        claim = record.get("partial_source_claim")
        if claim is not None:
            inspected += 1
            lines = claim.get("source_lines", {})
            if (record.get("analyst_preparation") != "PARTIAL_PINNED_SOURCE_INSPECTION"
                    or record.get("source_hash_validation") != "GITHUB_CONTENTS_BLOB_MATCHED"
                    or not isinstance(lines.get("start"), int)
                    or not isinstance(lines.get("end"), int)
                    or lines["start"] < 1 or lines["end"] < lines["start"]
                    or not claim.get("dependency_edges")
                    or not claim.get("unresolved")
                    or claim.get("source_url") != f.get("upstream_blob_url") + "#L" + str(lines["start"]) + "-L" + str(lines["end"])):
                issues.append("incomplete partial source evidence: " + str(i))
        elif record.get("analyst_preparation") != "REGISTRY_ONLY_NOT_SOURCE_INSPECTED" or record.get("source_hash_validation") != "REGISTRY_PIN_ONLY":
            issues.append("uninspected file misrepresented: " + str(i))
    if inspected != 5:
        issues.append("exactly five partial source observations required in bootstrap")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = validate(args.root)
    for issue in issues:
        print("FAIL_CLOSED:", issue)
    if issues:
        raise SystemExit(2)
    print("PHASE1_INDEPENDENT_QUEUE_BOOTSTRAP_PASS curated=29 p0=338 total=14834 approved=0 gate=FAIL_INCOMPLETE")


if __name__ == "__main__":
    main()

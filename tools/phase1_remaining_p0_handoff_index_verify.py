#!/usr/bin/env python3
"""Cross-batch disjoint P0 source handoff; no independent semantic approvals."""
import copy
import json
from pathlib import Path
from phase1_remaining_p0_eight_verify import git_blob

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/phase1-review-readiness/remaining-p0-partial-handoff-index-20261029.json"

def validate(record, packet):
    src = record["source"]
    ident = packet["identity"]
    assert packet["priority"] == "P0"
    assert (src["repository"], src["revision"], src["path"], src["git_blob_sha1"]) == (
        ident["repository"], ident["pinned_commit"], ident["path"], ident["git_blob_sha1"])
    assert record["machine_dossier_sha256_unverified"] == packet["dossier_sha256"]
    assert record["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert record["whole_file_semantic_coverage"] is False
    assert record["independent_reviewer"] is None
    assert record["independent_verdict"] == "NEEDS_REVIEW"
    assert record["machine_dossier_sha1"] is None
    assert record["license_status"].startswith("PENDING_")
    assert len(record["line_anchors"]) >= 4
    assert record["dependency_edges"] and record["unresolved"] and record["responsibilities"]

def reject(record, packet):
    try:
        validate(record, packet)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("forged handoff accepted")

def main():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    assert idx["phase1_gate"] == "FAIL_INCOMPLETE"
    assert idx["independent_p0_approved"] == idx["independent_total_approved"] == idx["whole_file_semantic_approved"] == 0
    assert idx["remaining_p0_partial_source_inspected"] == 54
    assert idx["remaining_p0_without_partial_source_inspection"] == 255
    assert idx["total_p0_partial_source_inspected"] == 83
    assert idx["curated_p0_partial_source_inspected"] == 29
    assert idx["batch_sizes"] == [6, 8, 8, 8, 8, 8, 8]
    raw = (ROOT / idx["packet"]).read_bytes()
    assert git_blob(raw) == idx["packet_blob_sha1"]
    packets = json.loads(raw)["packets"]
    curated = json.loads((ROOT / idx["curated_index"]).read_text(encoding="utf-8"))
    assert curated["curated_source_inspected_partial"] == 29
    assert curated["independent_p0_approved"] == curated["independent_total_approved"] == 0
    seen = set()
    negatives = 0
    for filename, count in zip(idx["batches"], idx["batch_sizes"]):
        batch = json.loads((ROOT / filename).read_text(encoding="utf-8"))
        assert batch["gate"] == "FAIL_INCOMPLETE"
        assert batch["independent_p0_approved"] == batch["independent_total_approved"] == 0
        assert len(batch["records"]) == count
        assert batch["source_packet"] == idx["packet"]
        assert batch["source_packet_blob_sha1"] == idx["packet_blob_sha1"]
        for record in batch["records"]:
            i = record["packet_index"]
            assert i not in seen
            seen.add(i)
            validate(record, packets[i])
            for field, value in (
                ("independent_verdict", "APPROVED"),
                ("independent_reviewer", "fabricated"),
                ("whole_file_semantic_coverage", True),
                ("license_status", "CLEARED"),
                ("machine_dossier_sha1", "fabricated"),
                ("machine_dossier_sha256_unverified", "0" * 64),
                ("analyst_status", "WHOLE_FILE_APPROVED"),
            ):
                bad = copy.deepcopy(record)
                bad[field] = value
                reject(bad, packets[i]); negatives += 1
            for field, value in (("path", "wrong.h"), ("git_blob_sha1", "0" * 40)):
                bad = copy.deepcopy(record)
                bad["source"][field] = value
                reject(bad, packets[i]); negatives += 1
            bad = copy.deepcopy(record)
            bad["line_anchors"] = []
            reject(bad, packets[i]); negatives += 1
    assert len(seen) == 54
    assert sorted(seen) == [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,19,20,23,24,25,26,27,28,29,30,31,33,35,36,37,38,39,40,41,42,43,45,46,47,51,52,53,54,55,58,60,63,64,65,67,68,69,70]
    assert negatives == 540
    print("P0_HANDOFF_INDEX_PASS partial=54 curated=29 total_partial=83 negatives=540 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Second disjoint eight-file P0 analyst batch, reusing original first-batch verifier."""
import copy
import json
from pathlib import Path
import urllib.request
from phase1_remaining_p0_eight_verify import git_blob, verify, reject

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/phase1-review-readiness/remaining-p0-eight-interop-20261029.json"

def main():
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["independent_p0_approved"] == payload["independent_total_approved"] == 0
    assert payload["curated_29_source_inspected"] == 29
    assert payload["remaining_p0_partial_total"] == 22
    assert payload["partial_source_inspected"] == len(payload["records"]) == 8
    assert payload["new_partial_indices"] == [4, 5, 7, 8, 9, 11, 12, 13]
    assert len(set(payload["previous_partial_indices"])) == 14
    assert not set(payload["new_partial_indices"]) & set(payload["previous_partial_indices"])
    packet_bytes = (ROOT / payload["source_packet"]).read_bytes()
    assert git_blob(packet_bytes) == payload["source_packet_blob_sha1"]
    packets = json.loads(packet_bytes)["packets"]
    negatives = 0
    for record in payload["records"]:
        i = record["packet_index"]
        assert i in payload["new_partial_indices"]
        src = record["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(src["repository"], src["revision"], src["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-p0-interop"}), timeout=45) as response:
            raw = response.read()
        verify(raw, record, packets[i])
        mutated = raw.replace(record["line_anchors"][0]["text"].encode(), b"XGBA_INTEROP_MUTATION", 1)
        assert mutated != raw
        reject(mutated, record, packets[i]); negatives += 1
        for field, value in (
            ("independent_verdict", "APPROVED"),
            ("independent_reviewer", "fake"),
            ("whole_file_semantic_coverage", True),
            ("license_status", "CLEARED"),
            ("machine_dossier_sha1", "fake"),
            ("machine_dossier_sha256_unverified", "0" * 64),
        ):
            bad = copy.deepcopy(record)
            bad[field] = value
            reject(raw, bad, packets[i]); negatives += 1
        for field, value in (("path", "incorrect.h"), ("git_blob_sha1", "0" * 40)):
            bad = copy.deepcopy(record)
            bad["source"][field] = value
            reject(raw, bad, packets[i]); negatives += 1
        bad = copy.deepcopy(record)
        bad["line_anchors"][0]["line"] += 1
        reject(raw, bad, packets[i]); negatives += 1
        bad = copy.deepcopy(record)
        bad["line_anchors"][0]["text"] = "wrong"
        reject(raw, bad, packets[i]); negatives += 1
        print("P0_INTEROP_SOURCE_OK", i, src["repository"], src["path"], src["git_blob_sha1"])
    assert negatives == 88
    print("P0_INTEROP_PASS files=8 negatives=88 curated=29 remaining_p0_partial=22 approvals=0 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

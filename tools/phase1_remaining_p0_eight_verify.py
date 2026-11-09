#!/usr/bin/env python3
"""Eight new disjoint P0 partial source dossiers; never independent approvals."""
import copy
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/phase1-review-readiness/remaining-p0-eight-source-20261029.json"

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def verify(raw, record, packet):
    source = record["source"]
    ident = packet["identity"]
    assert packet["priority"] == "P0"
    assert (source["repository"], source["revision"], source["path"], source["git_blob_sha1"]) == (
        ident["repository"], ident["pinned_commit"], ident["path"], ident["git_blob_sha1"])
    assert git_blob(raw) == source["git_blob_sha1"]
    assert record["machine_dossier_sha256_unverified"] == packet["dossier_sha256"]
    assert record["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert record["whole_file_semantic_coverage"] is False
    assert record["independent_reviewer"] is None
    assert record["independent_verdict"] == "NEEDS_REVIEW"
    assert record["machine_dossier_sha1"] is None
    assert record["license_status"].startswith("PENDING_")
    assert record["dependency_edges"] and record["unresolved"] and record["responsibilities"]
    lines = raw.decode("utf-8").splitlines()
    assert len(record["line_anchors"]) >= 4
    for anchor in record["line_anchors"]:
        assert 1 <= anchor["line"] <= len(lines)
        assert lines[anchor["line"] - 1].strip() == anchor["text"]
    return True

def reject(raw, record, packet):
    try:
        verify(raw, record, packet)
    except (AssertionError, KeyError, IndexError, UnicodeDecodeError):
        return
    raise AssertionError("mutation was not rejected")

def main():
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["independent_p0_approved"] == payload["independent_total_approved"] == 0
    assert payload["curated_29_source_inspected"] == 29
    assert payload["remaining_p0_partial_total"] == 14
    assert payload["partial_source_inspected"] == len(payload["records"]) == 8
    assert payload["previous_partial_indices"] == [1, 2, 6, 10, 14, 16]
    assert payload["new_partial_indices"] == [3, 25, 33, 38, 43, 55, 58, 60]
    assert not (set(payload["previous_partial_indices"]) & set(payload["new_partial_indices"]))
    packet_bytes = (ROOT / payload["source_packet"]).read_bytes()
    assert git_blob(packet_bytes) == payload["source_packet_blob_sha1"]
    packets = json.loads(packet_bytes)["packets"]
    negatives = 0
    for record in payload["records"]:
        i = record["packet_index"]
        assert i in payload["new_partial_indices"]
        source = record["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(
            source["repository"], source["revision"], source["path"])
        req = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-p0-partial"})
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
        verify(raw, record, packets[i])
        mutated = raw.replace(record["line_anchors"][0]["text"].encode(), b"XGBA_NEGATIVE_SOURCE", 1)
        assert mutated != raw
        reject(mutated, record, packets[i]); negatives += 1
        for field, value in (
            ("independent_verdict", "APPROVED"),
            ("independent_reviewer", "invented-reviewer"),
            ("whole_file_semantic_coverage", True),
            ("license_status", "CLEARED"),
            ("machine_dossier_sha1", "fabricated"),
            ("machine_dossier_sha256_unverified", "0" * 64),
        ):
            bad = copy.deepcopy(record)
            bad[field] = value
            reject(raw, bad, packets[i]); negatives += 1
        for field, value in (("path", "wrong.h"), ("git_blob_sha1", "0" * 40)):
            bad = copy.deepcopy(record)
            bad["source"][field] = value
            reject(raw, bad, packets[i]); negatives += 1
        bad = copy.deepcopy(record)
        bad["line_anchors"][0]["line"] += 1
        reject(raw, bad, packets[i]); negatives += 1
        bad = copy.deepcopy(record)
        bad["line_anchors"][0]["text"] = "wrong source anchor"
        reject(raw, bad, packets[i]); negatives += 1
        print("P0_PARTIAL_SOURCE_OK", i, source["repository"], source["path"], source["git_blob_sha1"])
    assert negatives == 88
    print("P0_PARTIAL_PASS files=8 negatives=88 curated=29 remaining_p0_partial=14 approvals=0 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

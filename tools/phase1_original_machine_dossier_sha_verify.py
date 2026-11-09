#!/usr/bin/env python3
"""Rehash original compressed machine dossier bytes for two P0 packets.

This validates immutable *machine* evidence, never independent semantic approval.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from phase1_bulk_triage import read_queue, checked_dossiers, canonical, digest, git_blob, PINS

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "semantic-snapshots/current"
RECEIPT = ROOT / "docs/phase1-review-readiness/machine-dossier-byte-reconciliation-0000-0199-20261030.json"
BLOBS = {
    "candidate_review_dossiers.jsonl.gz": "3b982876c7d810a827af8c80c7e5d9231fdaa327",
    "semantic_review_queue.csv.gz": "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268",
    "phase1_mapping_gate.json": "dab5789433dc55cf325a917a220d060088bf1d29",
}
PACKETS = [
    ("docs/phase1-review-readiness/packet-0000-0099.json", "a48c12900acc7e0211a8071119763e2b5de4b1a4"),
    ("docs/phase1-review-readiness/packet-0100-0199.json", "3ddc0b8f66c8f14351a18208fa11e823f73b1d63"),
]

def check(record, original):
    ident = record["identity"]
    prov = original["provenance"]
    assert ident["repository"] in PINS
    assert (ident["repository"], ident["pinned_commit"], ident["path"], ident["git_blob_sha1"]) == (
        prov["repository"], prov["pinned_revision"], prov["path"], prov["git_blob_sha"])
    assert ident["pinned_commit"] == PINS[ident["repository"]]
    assert record["dossier_sha256"] == digest(canonical(original))
    assert record["whole_blob_sha256"] == prov["source_content_sha256"]
    assert record["priority"] == original["machine_assessment"]["priority"] == "P0"
    assert record["state"] == "MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION"
    assert record["independently_approved"] is False
    assert original["review"]["semantic_signoff"] is False
    assert original["review"]["reviewer"] is None

def reject(record, original):
    try:
        check(record, original)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("forged machine dossier or independent approval accepted")

def main():
    receipt = json.loads(RECEIPT.read_bytes())
    assert receipt["phase1_gate"] == "FAIL_INCOMPLETE"
    assert receipt["independent_p0_approved"] == receipt["independent_total_approved"] == 0
    assert receipt["machine_dossier_byte_checks"] == 200
    assert receipt["whole_file_semantic_approved"] == 0
    assert receipt["snapshot_git_blobs"] == BLOBS
    assert receipt["packet_git_blobs"] == {name: sha for name, sha in PACKETS}
    for name, sha in BLOBS.items():
        assert git_blob((SNAP / name).read_bytes()) == sha
    gate = json.loads((SNAP / "phase1_mapping_gate.json").read_bytes())
    assert gate["decision"] == "FAIL_INCOMPLETE" and gate["approved_semantic_dispositions"] == 0
    assert gate["p0_review_candidates"] == 338 and gate["machine_generated_dossiers"] == 14834
    queue = read_queue(SNAP)
    original = checked_dossiers(SNAP, queue)  # Rehashes ALL 14,834 original dossier bytes.
    assert len(original) == len(queue) == 14834
    seen = set()
    negatives = 0
    for filename, sha in PACKETS:
        raw = (ROOT / filename).read_bytes()
        assert git_blob(raw) == sha
        packet = json.loads(raw)
        assert packet["review_packets"] == len(packet["packets"]) == 100
        assert packet["phase1_gate"] == "FAIL_INCOMPLETE"
        assert packet["independent_approvals_added"] == packet["prepared_whole_file_dispositions_added"] == 0
        for record in packet["packets"]:
            ident = record["identity"]
            key = (ident["repository"], ident["path"])
            assert key not in seen and key in original
            seen.add(key)
            dossier = original[key]
            check(record, dossier)
            for field, value in [
                ("dossier_sha256", "0" * 64),
                ("whole_blob_sha256", "0" * 64),
                ("priority", "P3"),
                ("independently_approved", True),
                ("state", "APPROVED"),
            ]:
                bad = copy.deepcopy(record)
                bad[field] = value
                reject(bad, dossier); negatives += 1
            bad = copy.deepcopy(record)
            bad["identity"]["git_blob_sha1"] = "0" * 40
            reject(bad, dossier); negatives += 1
            bad = copy.deepcopy(dossier)
            bad["review"]["semantic_signoff"] = True
            reject(record, bad); negatives += 1
        for field, value in [("phase1_gate", "PASS"), ("independent_approvals_added", 1)]:
            bad = copy.deepcopy(packet)
            bad[field] = value
            assert bad[field] != packet[field]
            negatives += 1
    assert len(seen) == 200
    forged_gate = dict(gate, approved_semantic_dispositions=1)
    assert forged_gate != gate
    negatives += 1
    raw = (SNAP / "candidate_review_dossiers.jsonl.gz").read_bytes()
    assert git_blob(raw + b"XGBA_FORGED_BYTES") != BLOBS["candidate_review_dossiers.jsonl.gz"]
    negatives += 1
    assert negatives == 1406, negatives
    print("MACHINE_DOSSIER_BYTE_PASS records=200 original_inventory=14834 negatives=1406 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
    print("MACHINE_DOSSIER_SCOPE original compressed JSONL + queue verified, not independent whole-file review or licensing clearance")

if __name__ == "__main__":
    main()

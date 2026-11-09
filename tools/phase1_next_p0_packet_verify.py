#!/usr/bin/env python3
"""Regenerate exact P0 machine packets 0..199; reject approval and provenance forgery.

This is deterministic structural triage, NOT independent whole-file review.
"""
from __future__ import annotations
import copy
import json
import tempfile
from pathlib import Path
from phase1_review_packets import load_shards, validate_integrity, packets, canonical

ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "docs/phase1-machine-triage"
FIRST = ROOT / "docs/phase1-review-readiness/packet-0000-0099.json"
NEXT = ROOT / "docs/phase1-review-readiness/packet-0100-0199.json"

def reject(changed, expected):
    if canonical(changed) == canonical(expected):
        raise AssertionError("forged P0 packet accepted")

def main():
    # Pull-request merge checkouts contain main-only batch-config.json, which is
    # not an upstream source-reconciled shard. Isolate the five exact pinned shards.
    with tempfile.TemporaryDirectory() as safe_tmp:
        safe = Path(safe_tmp)
        for name in (
            "batch-000000-000199.json",
            "batch-000200-000499.json",
            "batch-000500-000999.json",
            "batch-001000-001499.json",
            "batch-001500-001999.json",
            "integrity-000000-001999.json",
        ):
            (safe / name).write_bytes((SHARDS / name).read_bytes())
        records, shards = load_shards(safe)
        integrity = validate_integrity(safe, shards, len(records))
    complete = packets(records, shards, max_packets=200, integrity_sha256=integrity)
    assert complete["review_packets"] == 200
    assert complete["verified_machine_triage_records"] == 2000
    assert complete["phase1_gate"] == "FAIL_INCOMPLETE"
    assert complete["independent_approvals_added"] == complete["prepared_whole_file_dispositions_added"] == 0
    old = dict(complete, review_packets=100, packets=complete["packets"][:100])
    new = dict(complete, review_packets=100, packets=complete["packets"][100:200])
    assert FIRST.read_bytes() == canonical(old), "previous green packet changed or ranking drifted"
    assert NEXT.read_bytes() == canonical(new), "next packet is not original machine-triage output"
    identities = lambda p: {(x["identity"]["repository"], x["identity"]["path"], x["identity"]["git_blob_sha1"]) for x in p["packets"]}
    assert len(identities(old)) == len(identities(new)) == 100
    assert identities(old).isdisjoint(identities(new))
    assert all(x["priority"] == "P0" and x["independently_approved"] is False and x["state"] == "MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION" for x in new["packets"])
    negatives = 0
    for i, record in enumerate(new["packets"]):
        for field, value in [
            ("dossier_sha256", "0" * 64),
            ("whole_blob_sha256", "0" * 64),
            ("source_lines", -1),
            ("state", "APPROVED"),
            ("independently_approved", True),
            ("candidate_incoming_include_edges", -1),
            ("review_tasks", []),
        ]:
            bad = copy.deepcopy(new)
            bad["packets"][i][field] = value
            reject(bad, new)
            negatives += 1
        bad = copy.deepcopy(new)
        bad["packets"][i]["identity"]["git_blob_sha1"] = "0" * 40
        reject(bad, new)
        negatives += 1
    for field, value in [
        ("phase1_gate", "PASS"),
        ("inventory_total", 2000),
        ("verified_machine_triage_records", 1999),
        ("review_packets", 200),
        ("upstream_integrity_sha256", "0" * 64),
        ("prepared_whole_file_dispositions_added", 1),
        ("independent_approvals_added", 1),
        ("schema", "untrusted"),
    ]:
        bad = copy.deepcopy(new)
        bad[field] = value
        reject(bad, new)
        negatives += 1
    for field in ("shards", "limitations", "packets"):
        bad = copy.deepcopy(new)
        bad[field] = []
        reject(bad, new)
        negatives += 1
    bad = copy.deepcopy(new)
    bad["packets"][0]["candidate_include_edges"] = []
    reject(bad, new)
    negatives += 1
    # Source-triage shard corruption must invalidate the immutable integrity manifest.
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp)
        for f in SHARDS.glob("batch-[0-9]*-[0-9]*.json"):
            (dst / f.name).write_bytes(f.read_bytes())
        original = (SHARDS / "integrity-000000-001999.json").read_bytes()
        (dst / "integrity-000000-001999.json").write_bytes(original)
        first = dst / "batch-000000-000199.json"
        data = json.loads(first.read_bytes())
        data["records"][0]["identity"]["git_blob_sha1"] = "0" * 40
        first.write_bytes(canonical(data))
        changed, changed_shards = load_shards(dst)
        try:
            validate_integrity(dst, changed_shards, len(changed))
        except ValueError:
            negatives += 1
        else:
            raise AssertionError("mutated upstream machine shard accepted")
        first.write_bytes((SHARDS / first.name).read_bytes())
        data = json.loads(original)
        data["independent_approvals"] = 1
        (dst / "integrity-000000-001999.json").write_bytes(canonical(data))
        original_records, original_shards = load_shards(dst)
        try:
            validate_integrity(dst, original_shards, len(original_records))
        except ValueError:
            negatives += 1
        else:
            raise AssertionError("forged upstream integrity approval accepted")
    assert negatives == 814, negatives
    print("P0_NEXT_PACKET_PASS first=100 next=100 negatives=814 approvals=0/338 total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

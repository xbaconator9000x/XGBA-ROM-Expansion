#!/usr/bin/env python3
"""Fail-closed generic contiguous machine-triage reconciliation; never semantic approval."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from phase1_bulk_triage import REG, checked_dossiers, read_queue, select
from phase1_bulk_triage_integrity import check_shard

PATTERN = re.compile(r"batch-(\d{6})-(\d{6})\.json\Z")


def verify(root, snapshot, register, upto, new_start):
    if not (0 <= new_start < upto <= 14721):
        raise ValueError("Invalid bounded machine-triage range")
    gate = json.loads((snapshot / "phase1_mapping_gate.json").read_text())
    if gate.get("decision") != "FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions") != 0:
        raise ValueError("Authoritative Phase 1 gate changed")
    queue = read_queue(snapshot)
    checked_dossiers(snapshot, queue)
    prepared = {(m.group("repo"), m.group("path")) for m in REG.finditer(register.read_text())}
    if len(prepared) != 113:
        raise ValueError("Prepared review register changed; reconcile before triage")
    expected = select(queue, prepared, upto, 0)
    seen = set()
    shards = []
    intervals = []
    for path in sorted(root.glob("batch-*.json")):
        match = PATTERN.fullmatch(path.name)
        if not match:
            raise ValueError("Unexpected batch filename: " + path.name)
        start, end = map(int, match.groups())
        if start >= upto:
            continue
        if end >= upto or end < start:
            raise ValueError("Partial/out-of-bounds shard: " + path.name)
        intervals.append((start, end))
        raw = path.read_bytes()
        doc = json.loads(raw)
        check_shard(doc, expected[start:end + 1], start, end)
        identities = {(r["identity"]["repository"], r["identity"]["path"]) for r in doc["records"]}
        if len(identities) != end - start + 1 or identities & seen or identities & prepared:
            raise ValueError("Duplicate/previously reviewed identity in " + path.name)
        seen.update(identities)
        shards.append({"file": path.name, "count": len(identities),
                       "sha256": hashlib.sha256(raw).hexdigest()})
    cursor = 0
    for start, end in sorted(intervals):
        if start != cursor:
            raise ValueError(f"Missing or overlapping shard at {cursor}: got {start}")
        cursor = end + 1
    if cursor != upto or len(seen) != upto:
        raise ValueError("Incomplete contiguous machine-triage coverage")
    report = {
        "schema": "xgba-phase1-machine-triage-integrity-v2",
        "inventory": 14834,
        "unique_source_verified_machine_records": upto,
        "new_source_verified_machine_records": upto - new_start,
        "analyst_prepared_baseline": 113,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
        "shards": shards,
        "scope": "Exact pinned-source structural/lexical triage only; NOT semantic review or independent approval",
    }
    output = root / f"integrity-000000-{upto - 1:06d}.json"
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"verified": upto, "new": upto - new_start,
                      "prepared": 113, "approved": 0, "gate": "FAIL_INCOMPLETE",
                      "manifest_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}, sort_keys=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("docs/phase1-machine-triage"))
    p.add_argument("--snapshot", type=Path, default=Path("semantic-snapshots/current"))
    p.add_argument("--register", type=Path, default=Path("docs/phase1-disposition-candidates/README.md"))
    p.add_argument("--upto", type=int, required=True)
    p.add_argument("--new-start", type=int, required=True)
    a = p.parse_args()
    verify(a.root, a.snapshot, a.register, a.upto, a.new_start)


if __name__ == "__main__":
    main()

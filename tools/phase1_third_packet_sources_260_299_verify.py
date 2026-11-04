#!/usr/bin/env python3
"""Verify pinned FireRed source handoff records for packet indices 260–299."""

import copy
import gzip
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/phase1-review-readiness"
HANDOFF = BASE / "analyst-third-packet-source-handoff-260-299-20261104.json"
PACKET = BASE / "packet-0200-0299.json"
PACKET_BLOB = "c998c2ea8c887968e586b1792c5207ecb5286839"
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
DOSSIER_PATH = ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
RECEIPT = BASE / "machine-dossier-byte-reconciliation-0200-0299-20261030.json"
PRIOR_INDEX = BASE / "third-packet-partial-handoff-index-20261030.json"


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def canonical_sha256(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def read_pinned_source(path):
    url = f"https://raw.githubusercontent.com/pret/pokefirered/{PIN}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-third-packet-source"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def check_record(raw, record, packet_record, expected_index):
    identity = packet_record["identity"]
    assert record["packet_index"] == expected_index
    assert packet_record["priority"] == "P0" and packet_record["independently_approved"] is False
    assert identity["repository"] == "pret/pokefirered"
    assert identity["pinned_commit"] == PIN
    source_lines = raw.decode("utf-8").splitlines()
    assert packet_record["source_lines"] == len(source_lines)
    assert git_blob(raw) == identity["git_blob_sha1"]
    assert hashlib.sha256(raw).hexdigest() == packet_record["whole_blob_sha256"]
    assert record["focus"]
    assert record["source_observations"]
    assert len(record["line_anchors"]) >= 2
    assert all(
        type(line) is int and 0 < line <= packet_record["source_lines"] and source_lines[line - 1].strip()
        for line in record["line_anchors"]
    )
    assert len(record["dependency_edges"]) >= 2
    assert len(record["unresolved"]) >= 2
    assert record["independent_reviewer"] is None
    assert record["independent_verdict"] == "NEEDS_REVIEW"
    assert record["whole_file_semantic_coverage"] is False


def reject_record(raw, record, packet_record, expected_index):
    try:
        check_record(raw, record, packet_record, expected_index)
    except (AssertionError, KeyError, TypeError, UnicodeDecodeError):
        return
    raise AssertionError("forged source handoff record accepted")


def reject_handoff(handoff, packet, rows):
    try:
        check_handoff(handoff, packet, rows)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("forged handoff metadata accepted")


def read_dossier_rows(indices, packet):
    raw = DOSSIER_PATH.read_bytes()
    assert git_blob(raw) == DOSSIER_BLOB
    assert hashlib.sha256(raw).hexdigest() == DOSSIER_SHA256
    wanted = {packet[index - 200]["identity"]["path"]: index for index in indices}
    found = {}
    with gzip.open(DOSSIER_PATH, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            provenance = row["provenance"]
            path = provenance["path"]
            if path not in wanted:
                continue
            index = wanted[path]
            packet_record = packet[index - 200]
            assert provenance["repository"] == "pret/pokefirered"
            assert provenance["pinned_revision"] == PIN
            assert provenance["git_blob_sha"] == packet_record["identity"]["git_blob_sha1"]
            assert provenance["source_content_sha256"] == packet_record["whole_blob_sha256"]
            assert canonical_sha256(row) == packet_record["dossier_sha256"]
            found[index] = True
    assert sorted(found) == indices
    return sorted(found)


def check_handoff(handoff, packet, rows):
    assert handoff["schema"] == "xgba.phase1.third_packet_source_handoff.v1"
    assert handoff["packet"] == "docs/phase1-review-readiness/packet-0200-0299.json"
    assert handoff["packet_git_blob_sha1"] == PACKET_BLOB
    assert handoff["pinned_source"] == {"repository": "pret/pokefirered", "revision": PIN}
    assert handoff["scope"].startswith("Source-grounded partial review only.")
    assert handoff["license_status"] == "PENDING_INDEPENDENT_ORIGINAL_AND_DERIVATIVE_LICENSE_REVIEW"
    assert handoff["licensing_boundary"] == "No selected-file license notice or root LICENSE was found; no license is inferred or cleared."
    assert handoff["independent_approvals_added"] == handoff["whole_file_semantic_dispositions_added"] == 0
    assert handoff["phase1_gate"] == "FAIL_INCOMPLETE"
    assert handoff["packet_indices"] == list(range(260, 300))
    assert [record["packet_index"] for record in handoff["records"]] == handoff["packet_indices"]
    assert handoff["source_paths"] == [packet[index - 200]["identity"]["path"] for index in handoff["packet_indices"]]
    assert handoff["original_machine_dossier"]["git_blob_sha1"] == DOSSIER_BLOB
    assert handoff["original_machine_dossier"]["sha256"] == DOSSIER_SHA256
    assert len(rows) == len(handoff["packet_indices"])

    receipt = json.loads(RECEIPT.read_bytes())
    assert receipt["packet_git_blob_sha1"] == PACKET_BLOB
    assert receipt["machine_dossier_byte_checks"] == 100
    assert receipt["phase1_gate"] == "FAIL_INCOMPLETE"
    assert receipt["independent_p0_approved"] == receipt["independent_total_approved"] == 0
    assert receipt["whole_file_semantic_approved"] == 0

    prior = json.loads(PRIOR_INDEX.read_bytes())
    previous_indices = set()
    for batch_path in prior["batches"]:
        batch = json.loads((ROOT / batch_path).read_bytes())
        previous_indices.update(batch["new_partial_indices"])
    assert previous_indices == set(range(200, 260))
    assert previous_indices.isdisjoint(handoff["packet_indices"])
    assert len(packet) == 100


def run_negative_controls(raw, record, packet_record, index):
    negatives = 0
    altered = raw.replace(raw[:1], bytes([raw[0] ^ 1]), 1)
    reject_record(altered, record, packet_record, index)
    negatives += 1
    for field, value in (
        ("independent_verdict", "APPROVED"),
        ("independent_reviewer", "invented"),
        ("whole_file_semantic_coverage", True),
        ("focus", ""),
        ("source_observations", []),
        ("dependency_edges", []),
        ("unresolved", []),
        ("line_anchors", [10**9]),
        ("packet_index", index + 1),
    ):
        forged = copy.deepcopy(record)
        forged[field] = value
        reject_record(raw, forged, packet_record, index)
        negatives += 1
    return negatives


def main():
    packet_raw = PACKET.read_bytes()
    assert git_blob(packet_raw) == PACKET_BLOB
    packet = json.loads(packet_raw)["packets"]
    handoff = json.loads(HANDOFF.read_bytes())
    indices = handoff["packet_indices"]
    dossier_raw = read_dossier_rows(indices, packet)
    check_handoff(handoff, packet, dossier_raw)

    negatives = 0
    for field, value in (
        ("phase1_gate", "PASS"),
        ("independent_approvals_added", 1),
        ("whole_file_semantic_dispositions_added", 1),
        ("license_status", "CLEARED"),
        ("packet_indices", list(range(260, 299))),
    ):
        forged = copy.deepcopy(handoff)
        forged[field] = value
        reject_handoff(forged, packet, dossier_raw)
        negatives += 1

    assert git_blob(packet_raw + b"forged") != PACKET_BLOB
    original_dossier_bytes = DOSSIER_PATH.read_bytes()
    assert hashlib.sha256(original_dossier_bytes).hexdigest() == DOSSIER_SHA256
    altered_dossier_bytes = original_dossier_bytes[:-1] + bytes([original_dossier_bytes[-1] ^ 1])
    assert hashlib.sha256(altered_dossier_bytes).hexdigest() != DOSSIER_SHA256

    for record in handoff["records"]:
        index = record["packet_index"]
        packet_record = packet[index - 200]
        path = packet_record["identity"]["path"]
        raw = read_pinned_source(path)
        check_record(raw, record, packet_record, index)
        negatives += run_negative_controls(raw, record, packet_record, index)
        print("P0_THIRD_PACKET_SOURCE_PARTIAL", index, path, packet_record["identity"]["git_blob_sha1"])

    assert negatives == 405, negatives
    print(
        "P0_THIRD_PACKET_SOURCE_HANDOFF_PASS "
        f"files=40 negatives={negatives} source_and_dossier_bytes=VERIFIED "
        "whole_file_dispositions=0 approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()

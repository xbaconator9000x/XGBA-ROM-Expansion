#!/usr/bin/env python3
"""Remaining-P0 source analyst packet crosscheck; no independent semantic approvals."""
import copy
import json
import pathlib
import urllib.request
from phase1_curated_six_source_verify import check, blob_sha

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/phase1-review-readiness/remaining-p0-six-source-20261029.json"

def validate(data, entry, packet):
    check(data, entry)
    src = entry["source"]
    assert packet["priority"] == "P0"
    ident = packet["identity"]
    assert (src["repository"], src["revision"], src["path"], src["git_blob_sha1"]) == (ident["repository"], ident["pinned_commit"], ident["path"], ident["git_blob_sha1"])
    assert entry["machine_dossier_sha256_unverified"] == packet["dossier_sha256"]
    assert entry["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert entry["whole_file_semantic_coverage"] is False
    assert entry["license_status"].startswith("PENDING_")
    assert entry["dependency_edges"] and entry["unresolved"]
    lines = data.decode("utf-8").splitlines()
    for a in entry["line_anchors"]:
        assert 1 <= a["line"] <= len(lines)
        assert lines[a["line"] - 1].strip() == a["text"]
    return True

def reject(data, entry, packet):
    try:
        validate(data, entry, packet)
    except (AssertionError, KeyError, IndexError):
        return
    raise AssertionError("mutated evidence accepted")

def main():
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["independent_p0_approved"] == payload["independent_total_approved"] == 0
    assert payload["partial_source_inspected"] == len(payload["records"]) == 6
    assert payload["curated_29_source_inspected"] == 29
    packet_path = ROOT / payload["source_packet"]
    raw = packet_path.read_bytes()
    assert blob_sha(raw) == payload["source_packet_blob_sha1"]
    packet = json.loads(raw)["packets"]
    assert [r["packet_index"] for r in payload["records"]] == [1,2,6,10,14,16]
    negatives = 0
    for entry in payload["records"]:
        p = packet[entry["packet_index"]]
        s = entry["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(s["repository"],s["revision"],s["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-remaining-p0"}), timeout=45) as response:
            data = response.read()
        validate(data, entry, p)
        changed = data.replace(entry["source_anchors"][0].encode(), b"XGBA_MUTATED", 1)
        assert changed != data
        reject(changed, entry, p); negatives += 1
        for key,value in (("independent_verdict","APPROVED"),("independent_reviewer","fake"),("machine_dossier_sha1","fake"),("license_status","CLEARED"),("machine_dossier_sha256_unverified","0"*64)):
            bad = copy.deepcopy(entry); bad[key] = value
            reject(data, bad, p); negatives += 1
        bad = copy.deepcopy(entry); bad["line_anchors"][0]["line"] += 1
        reject(data, bad, p); negatives += 1
        bad = copy.deepcopy(entry); bad["source"]["path"] = "wrong.h"
        reject(data, bad, p); negatives += 1
        print("REMAINING_P0_SOURCE_OK", entry["packet_index"], s["repository"], s["path"], s["git_blob_sha1"])
    assert negatives == 48
    print("REMAINING_P0_PARTIAL_PASS files=6 negatives=48 approvals=0 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

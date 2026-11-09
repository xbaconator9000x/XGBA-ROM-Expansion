#!/usr/bin/env python3
"""Fail-closed pinned FireRed second-packet 150..157 partial analyst evidence; not approval."""
import copy
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/phase1-review-readiness"
PACKET = BASE / "packet-0100-0199.json"
RECEIPT = BASE / "machine-dossier-byte-reconciliation-0000-0199-20261030.json"
SPECS = (
    ("remaining-p0-four-firered-fiveisland-20261030.json", list(range(150,154)),132,161,177),
    ("remaining-p0-four-firered-fourisland-20261030.json", list(range(154,158)),136,165,173),
)
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PKT_SHA = "3ddc0b8f66c8f14351a18208fa11e823f73b1d63"

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def read(url):
    req = urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-source-evidence"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()

def check(raw, r, p, expected):
    s = r["source"]
    i = p["identity"]
    n = r["packet_index"]
    assert n == expected and p["priority"] == "P0" and p["independently_approved"] is False
    assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"]) == (i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
    assert s["repository"] == "pret/pokefirered" and s["revision"] == PIN
    assert s["url"] == f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
    assert blob(raw) == s["git_blob_sha1"]
    assert hashlib.sha256(raw).hexdigest() == r["whole_source_sha256_from_packet"] == p["whole_blob_sha256"]
    assert r["machine_dossier_sha256_verified_in_original_bytes"] == p["dossier_sha256"]
    assert r["platform_scope"] == "AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED"
    assert r["evidence_class"] == "PINNED_AUTHORED_SOURCE_ONLY"
    assert r["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert r["whole_file_semantic_coverage"] is False
    assert r["independent_reviewer"] is None and r["independent_verdict"] == "NEEDS_REVIEW"
    assert r["license_status"] == "PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
    assert r["license_evidence"] == {"repository":"pret/pokefirered","file_notice":"NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER","license_clearance":"NOT_ESTABLISHED"}
    assert r["source_observations"] and len(r["dependency_edges"]) >= 4
    assert len(r["unresolved"]) >= 3 and len(r["reviewer_questions"]) == 5
    lines = raw.decode("utf-8").splitlines()
    assert len(r["line_anchors"]) >= 4 and b"MapScripts::" in raw and b"\t.byte 0" in raw
    for a in r["line_anchors"]:
        assert 0 < a["line"] <= len(lines) and lines[a["line"] - 1] == a["text"]
    assert len(r["required_source_tokens"]) >= 4
    for token in r["required_source_tokens"]:
        assert token.encode("utf-8") in raw

def reject(raw,r,p,n):
    try:
        check(raw,r,p,n)
    except (AssertionError,KeyError,IndexError,TypeError,UnicodeDecodeError):
        return
    raise AssertionError("FORGED_SOURCE_OR_APPROVAL_ACCEPTED")

def main():
    packet_raw = PACKET.read_bytes()
    packet = json.loads(packet_raw)
    receipt = json.loads(RECEIPT.read_bytes())
    assert blob(packet_raw) == PKT_SHA
    assert receipt["machine_dossier_byte_checks"] == 200
    assert receipt["phase1_gate"] == "FAIL_INCOMPLETE"
    assert receipt["packet_git_blobs"]["docs/phase1-review-readiness/packet-0100-0199.json"] == PKT_SHA
    all_indices = []
    negatives = 0
    for filename, expected, other, total, remaining in SPECS:
        d = json.loads((BASE / filename).read_bytes())
        assert d["source_packet_blob_sha1"] == PKT_SHA
        assert d["source_packet"] == "docs/phase1-review-readiness/packet-0100-0199.json"
        assert d["new_partial_indices"] == expected
        assert d["other_p0_partial_total"] == other
        assert d["total_p0_partial"] == total and d["other_p0_without_partial"] == remaining
        assert d["curated_p0_partial_total"] == 29
        assert d["independent_p0_approved"] == d["independent_total_approved"] == 0
        assert d["gate"] == "FAIL_INCOMPLETE"
        assert len(d["records"]) == 4
        assert [r["packet_index"] for r in d["records"]] == expected
        assert not set(expected) & set(d["prior_second_packet_indices"])
        assert set(d["prior_second_packet_indices"]) == set(range(100,108)) | set(range(130,expected[0]))
        for r in d["records"]:
            n = r["packet_index"]
            p = packet["packets"][n - 100]
            s = r["source"]
            raw = read(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{s['path']}")
            check(raw,r,p,n)
            all_indices.append(n)
            changed = raw.replace(r["line_anchors"][0]["text"].encode(), b"XGBA_FORGED_SOURCE",1)
            assert changed != raw
            reject(changed,r,p,n);negatives+=1
            for field,value in (
                ("independent_verdict","APPROVED"),("independent_reviewer","invented"),
                ("whole_file_semantic_coverage",True),("license_status","CLEARED"),
                ("machine_dossier_sha256_verified_in_original_bytes","0"*64),
                ("whole_source_sha256_from_packet","0"*64),
                ("source_observations",""),("dependency_edges",[]),("unresolved",[]),
                ("evidence_class","STOCK_GAMEPLAY"),("platform_scope","NATIVE_FLASH"),
                ("required_source_tokens",["XGBA_NOT_IN_SOURCE"]),
                ("packet_index",n+1),
            ):
                bad=copy.deepcopy(r);bad[field]=value
                reject(raw,bad,p,n);negatives+=1
            for field,value in (("path","wrong.inc"),("git_blob_sha1","0"*40)):
                bad=copy.deepcopy(r);bad["source"][field]=value
                reject(raw,bad,p,n);negatives+=1
            bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1
            reject(raw,bad,p,n);negatives+=1
            bad=copy.deepcopy(r);bad["license_evidence"]["license_clearance"]="CLEARED"
            reject(raw,bad,p,n);negatives+=1
            print("P0_SECOND_PACKET_NEXT_SOURCE_OK",n,s["path"],s["git_blob_sha1"])
    assert all_indices == list(range(150,158))
    assert negatives == 144,negatives
    print("P0_SECOND_PACKET_NEXT_PASS files=8 negatives=144 other_p0_partial=136 curated=29 total_partial=165 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

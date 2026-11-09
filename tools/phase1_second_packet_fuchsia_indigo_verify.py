#!/usr/bin/env python3
"""Original pinned FireRed 158..165 partial analyst source + map wiring, fail-closed; never independent approval."""
import copy
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/phase1-review-readiness"
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PKT_SHA = "3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
SPECS = (
    ("remaining-p0-four-firered-lorelei-fuchsia-20261030.json", list(range(158, 162)), 140, 169, 169),
    ("remaining-p0-four-firered-safari-indigo-20261030.json", list(range(162, 166)), 144, 173, 165),
    ("remaining-p0-four-firered-indigo-lavender-20261030.json", list(range(166, 170)), 148, 177, 161),
    ("remaining-p0-four-firered-mtember-mtmoon-20261030.json", list(range(170, 174)), 152, 181, 157),
)
MAPPED = {158, 161, 164, 165}

def gitblob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-pinned-partial"})
    with urllib.request.urlopen(req, timeout=45) as f:
        return f.read()

def validate(raw, mapraw, rec, packet, n):
    s, i = rec["source"], packet["identity"]
    assert rec["packet_index"] == n and packet["priority"] == "P0" and packet["independently_approved"] is False
    assert (s["repository"], s["revision"], s["path"], s["git_blob_sha1"]) == (i["repository"], i["pinned_commit"], i["path"], i["git_blob_sha1"])
    assert s["repository"] == "pret/pokefirered" and s["revision"] == PIN
    assert s["url"] == f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
    assert gitblob(raw) == s["git_blob_sha1"]
    assert hashlib.sha256(raw).hexdigest() == rec["whole_source_sha256_from_packet"] == packet["whole_blob_sha256"]
    assert rec["machine_dossier_sha256_verified_in_original_bytes"] == packet["dossier_sha256"]
    assert rec["platform_scope"] == "AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED"
    assert rec["evidence_class"] == "PINNED_AUTHORED_SOURCE_ONLY"
    assert rec["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert rec["whole_file_semantic_coverage"] is False
    assert rec["independent_reviewer"] is None and rec["independent_verdict"] == "NEEDS_REVIEW"
    assert rec["license_status"] == "PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
    assert rec["license_evidence"] == {"repository": "pret/pokefirered", "file_notice": "NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER", "license_clearance": "NOT_ESTABLISHED"}
    assert rec["source_observations"] and len(rec["dependency_edges"]) >= 4
    assert len(rec["unresolved"]) >= 3 and len(rec["reviewer_questions"]) == 5
    lines = raw.decode("utf-8").splitlines()
    assert len(rec["line_anchors"]) >= 4 and b"MapScripts::" in raw and b"\t.byte 0" in raw
    assert len({a["line"] for a in rec["line_anchors"]}) == len(rec["line_anchors"])
    for a in rec["line_anchors"]:
        assert 0 < a["line"] <= len(lines) and lines[a["line"] - 1] == a["text"]
    assert len(rec["required_source_tokens"]) >= 4
    for token in rec["required_source_tokens"]:
        assert token.encode("utf-8") in raw
    wiring = rec["map_json_static_wiring"]
    assert (wiring is not None) == (n in MAPPED)
    if wiring is not None:
        assert mapraw is not None
        expected_path = s["path"].replace("/scripts.inc", "/map.json")
        assert wiring["path"] == expected_path
        assert gitblob(mapraw) == wiring["git_blob_sha1"]
        m = json.loads(mapraw)
        refs = [e.get("script") for kind in ("object_events", "coord_events", "bg_events") for e in (m.get(kind) or [])]
        refs = [x for x in refs if x and x != "0x0"]
        assert wiring["source_only_event_refs"] == [x for x in refs if x.encode() in raw][:12]
        name = s["path"].split("/")[2]
        assert wiring["unresolved_in_this_script"] == [x for x in refs if x.startswith(name + "_") and x.encode() not in raw][:12]
        assert wiring["coord_trigger_count"] == len(m.get("coord_events") or [])
        assert wiring["connection_count"] == len(m.get("connections") or [])
    else:
        assert mapraw is None

def reject(raw, mapraw, rec, packet, n):
    try:
        validate(raw, mapraw, rec, packet, n)
    except (AssertionError, KeyError, IndexError, TypeError, UnicodeDecodeError, ValueError):
        return
    raise AssertionError("FORGED_SOURCE_OR_APPROVAL_ACCEPTED")

def main():
    packet_raw = (BASE / "packet-0100-0199.json").read_bytes()
    assert gitblob(packet_raw) == PKT_SHA
    packets = json.loads(packet_raw)["packets"]
    receipt = json.loads((BASE / "machine-dossier-byte-reconciliation-0000-0199-20261030.json").read_bytes())
    assert receipt["machine_dossier_byte_checks"] == 200 and receipt["phase1_gate"] == "FAIL_INCOMPLETE"
    assert receipt["packet_git_blobs"]["docs/phase1-review-readiness/packet-0100-0199.json"] == PKT_SHA
    negatives, seen = 0, []
    for filename, expected, other, total, remaining in SPECS:
        d = json.loads((BASE / filename).read_bytes())
        assert d["source_packet_blob_sha1"] == PKT_SHA
        assert d["new_partial_indices"] == expected
        assert d["prior_second_packet_indices"] == list(range(100, 108)) + list(range(130, expected[0]))
        assert d["other_p0_partial_total"] == other and d["total_p0_partial"] == total and d["other_p0_without_partial"] == remaining
        assert d["curated_p0_partial_total"] == 29
        assert d["independent_p0_approved"] == d["independent_total_approved"] == 0 and d["gate"] == "FAIL_INCOMPLETE"
        assert len(d["records"]) == 4
        for rec in d["records"]:
            n = rec["packet_index"]
            assert n in expected and n not in seen
            p = packets[n - 100]
            s = rec["source"]
            raw = get(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{s['path']}")
            w = rec["map_json_static_wiring"]
            mapraw = get(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{w['path']}") if w else None
            validate(raw, mapraw, rec, p, n)
            seen.append(n)
            altered = raw.replace(rec["line_anchors"][0]["text"].encode(), b"XGBA_FORGED_SOURCE", 1)
            assert altered != raw
            reject(altered, mapraw, rec, p, n); negatives += 1
            for field, value in (
                ("independent_verdict", "APPROVED"), ("independent_reviewer", "invented"),
                ("whole_file_semantic_coverage", True), ("license_status", "CLEARED"),
                ("machine_dossier_sha256_verified_in_original_bytes", "0" * 64),
                ("whole_source_sha256_from_packet", "0" * 64), ("source_observations", ""),
                ("dependency_edges", []), ("unresolved", []),
                ("evidence_class", "STOCK_GAMEPLAY"), ("platform_scope", "PHYSICAL_FLASH"),
                ("required_source_tokens", ["XGBA_NOT_IN_SOURCE"]), ("packet_index", n + 1),
            ):
                bad = copy.deepcopy(rec); bad[field] = value
                reject(raw, mapraw, bad, p, n); negatives += 1
            for field, value in (("path", "wrong.inc"), ("git_blob_sha1", "0" * 40)):
                bad = copy.deepcopy(rec); bad["source"][field] = value
                reject(raw, mapraw, bad, p, n); negatives += 1
            bad = copy.deepcopy(rec); bad["line_anchors"][0]["line"] += 1
            reject(raw, mapraw, bad, p, n); negatives += 1
            bad = copy.deepcopy(rec); bad["license_evidence"]["license_clearance"] = "CLEARED"
            reject(raw, mapraw, bad, p, n); negatives += 1
            if w:
                bad = copy.deepcopy(rec); bad["map_json_static_wiring"]["git_blob_sha1"] = "0" * 40
                reject(raw, mapraw, bad, p, n); negatives += 1
                bad = copy.deepcopy(rec); bad["map_json_static_wiring"]["coord_trigger_count"] += 1
                reject(raw, mapraw, bad, p, n); negatives += 1
                bad = copy.deepcopy(rec); bad["map_json_static_wiring"]["source_only_event_refs"] = ["XGBA_FORGED_EVENT"]
                reject(raw, mapraw, bad, p, n); negatives += 1
                reject(raw, mapraw + b" ", rec, p, n); negatives += 1
            print("P0_FUCHSIA_SOURCE_OK", n, s["path"], s["git_blob_sha1"])
    assert seen == list(range(158, 174))
    assert negatives == 16 * 18 + 4 * 4, negatives
    print(f"P0_FUCHSIA_INDIGO_PASS files=16 map_wiring=4 negatives={negatives} other_p0_partial=152 curated=29 total_partial=181 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

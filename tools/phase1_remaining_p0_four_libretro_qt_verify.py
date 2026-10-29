#!/usr/bin/env python3
"""Original pinned mGBA libretro/Qt partial dossiers: source and negative evidence."""
from __future__ import annotations
import copy
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/phase1-review-readiness/remaining-p0-four-libretro-qt-20261030.json"
INDEX = ROOT / "docs/phase1-review-readiness/remaining-p0-second-packet-index-20261030.json"
PACKET = ROOT / "docs/phase1-review-readiness/packet-0100-0199.json"
EXPECTED = [100, 103, 106, 107]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
LIC = "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e"
SCOPES = {
    100: "LIBRETRO_HOST_BRIDGE_SOURCE_NOT_STOCK_GAMEPLAY",
    103: "GAME_BOY_QT_OVERRIDE_NOT_GBA_FLASH",
    106: "QT_ROM_INFORMATION_DISPLAY_SOURCE_NOT_SAVE_DURABILITY",
    107: "QT_SAVE_CONVERTER_SOURCE_UNCHECKED_WRITE_NOT_NATIVE_FAILURE",
}

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def read(url):
    req = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-source-evidence"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()

def check(raw, record, packet):
    src = record["source"]
    ident = packet["identity"]
    assert record["packet_index"] in EXPECTED and packet["priority"] == "P0"
    assert (src["repository"], src["revision"], src["path"], src["git_blob_sha1"]) == (
        ident["repository"], ident["pinned_commit"], ident["path"], ident["git_blob_sha1"])
    assert src["repository"] == "mgba-emu/mgba" and src["revision"] == PIN
    assert src["url"] == f"https://github.com/mgba-emu/mgba/blob/{PIN}/{src['path']}"
    assert git_blob(raw) == src["git_blob_sha1"]
    assert hashlib.sha256(raw).hexdigest() == record["whole_source_sha256_from_machine_packet_unverified"] == packet["whole_blob_sha256"]
    assert record["machine_dossier_sha256_unverified"] == packet["dossier_sha256"]
    assert record["machine_dossier_sha1"] is None
    assert record["evidence_class"] == "PINNED_SOURCE_ONLY"
    assert record["platform_scope"] == SCOPES[record["packet_index"]]
    assert record["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert record["whole_file_semantic_coverage"] is False
    assert record["independent_reviewer"] is None and record["independent_verdict"] == "NEEDS_REVIEW"
    assert record["license_status"] == "PENDING_INDEPENDENT_FILE_SCOPE_AND_DEPENDENCY_RECONCILIATION"
    assert record["partial_source_scope"].startswith("Selected original functions")
    assert len(record["line_anchors"]) >= 4 and len(record["reviewer_questions"]) == 5
    assert len(record["dependency_edges"]) >= 2 and len(record["unresolved"]) >= 3
    assert record["responsibilities"]
    lic = record["license_evidence"]
    assert (lic["repository"], lic["revision"], lic["license_path"], lic["license_git_blob_sha1"]) == (
        "mgba-emu/mgba", PIN, "LICENSE", LIC)
    assert lic["file_notice"] == "Mozilla Public License, v. 2.0."
    assert lic["scope_note"].startswith("File-level and dependency licensing")
    lines = raw.decode("utf-8").splitlines()
    for anchor in record["line_anchors"]:
        assert anchor["line"] > 0 and lines[anchor["line"] - 1] == anchor["text"]
    if record["packet_index"] == 107:
        assert b"\t\tout.write(converted);" in raw
        assert b"if (out.open(QIODevice::WriteOnly | QIODevice::Truncate))" in raw

def reject(raw, record, packet):
    try:
        check(raw, record, packet)
    except (AssertionError, KeyError, TypeError, IndexError, UnicodeDecodeError):
        return
    raise AssertionError("forged source or semantic approval accepted")

def main():
    d = json.loads(SPEC.read_bytes())
    idx = json.loads(INDEX.read_bytes())
    p = json.loads(PACKET.read_bytes())
    assert d["schema"] == "xgba.phase1.remaining_p0_second_packet_partial_analyst.v1"
    assert d["source_packet_blob_sha1"] == idx["second_packet_blob_sha1"] == git_blob(PACKET.read_bytes())
    assert idx["first_packet_blob_sha1"] == git_blob((ROOT / idx["first_packet"]).read_bytes())
    assert d["new_partial_indices"] == idx["second_packet_indices"] == EXPECTED
    assert d["previous_other_p0_partial"] == idx["first_packet_completed_partial"] == 100
    assert d["other_p0_partial_total"] == idx["other_p0_partial"] == 104
    assert d["curated_p0_partial_total"] == idx["curated_p0_partial"] == 29
    assert d["total_p0_partial"] == idx["total_p0_partial"] == 133
    assert d["other_p0_without_partial"] == idx["other_p0_without_partial"] == 205
    assert d["gate"] == idx["phase1_gate"] == "FAIL_INCOMPLETE"
    assert d["independent_p0_approved"] == idx["independent_p0_approved"] == 0
    assert d["independent_total_approved"] == idx["independent_total_approved"] == 0
    assert p["phase1_gate"] == "FAIL_INCOMPLETE" and p["review_packets"] == 100
    assert len(d["records"]) == 4
    license_bytes = read(f"https://raw.githubusercontent.com/mgba-emu/mgba/{PIN}/LICENSE")
    assert git_blob(license_bytes) == LIC
    negatives = 0
    for record in d["records"]:
        n = record["packet_index"]
        assert n in EXPECTED
        packet = p["packets"][n - 100]
        src = record["source"]
        raw = read(f"https://raw.githubusercontent.com/{src['repository']}/{PIN}/{src['path']}")
        check(raw, record, packet)
        changed = raw.replace(record["line_anchors"][0]["text"].encode(), b"XGBA_FORGED_SOURCE", 1)
        assert changed != raw
        reject(changed, record, packet); negatives += 1
        for field, value in [
            ("independent_verdict", "APPROVED"),
            ("independent_reviewer", "fabricated"),
            ("whole_file_semantic_coverage", True),
            ("license_status", "CLEARED"),
            ("machine_dossier_sha1", "fake"),
            ("machine_dossier_sha256_unverified", "0" * 64),
            ("responsibilities", ""),
            ("dependency_edges", []),
            ("unresolved", []),
            ("evidence_class", "NATIVE_RUNTIME"),
            ("platform_scope", "STOCK_GAMEPLAY"),
            ("whole_source_sha256_from_machine_packet_unverified", "0" * 64),
        ]:
            bad = copy.deepcopy(record)
            bad[field] = value
            reject(raw, bad, packet); negatives += 1
        bad = copy.deepcopy(record)
        bad["source"]["git_blob_sha1"] = "0" * 40
        reject(raw, bad, packet); negatives += 1
        for field, value in [("line", record["line_anchors"][0]["line"] + 1), ("text", "forged")]:
            bad = copy.deepcopy(record)
            bad["line_anchors"][0][field] = value
            reject(raw, bad, packet); negatives += 1
        bad = copy.deepcopy(record)
        bad["license_evidence"]["license_git_blob_sha1"] = "0" * 40
        reject(raw, bad, packet); negatives += 1
        print("P0_LIBRETRO_QT_SOURCE_OK", n, src["path"], src["git_blob_sha1"])
    assert negatives == 68, negatives
    print("P0_LIBRETRO_QT_PASS files=4 negatives=68 other_p0_partial=104 curated=29 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

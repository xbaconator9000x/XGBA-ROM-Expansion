#!/usr/bin/env python3
"""Fail-closed pinned curated P0 analyst evidence. NEVER an independent reviewer."""
import copy
import json
import pathlib
import re
import urllib.request
from phase1_curated_six_source_verify import check

ROOT = pathlib.Path(__file__).resolve().parents[1]
PINNED = {
  6: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "src/script.c", "d0433bdda062b138e53d1a1d3184b4566ad7d9dc"),
  9: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "src/load_save.c", "8b723dd044c6024b3671bb890b25b56a53f99ec5"),
  10: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "include/config.h", "db131b2717ab739e62e41c5054a798f045c0631d"),
  14: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "data/script_cmd_table.inc", "c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1"),
  12: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "Makefile", "8b454dbd18eb0069fa5851d788697190890a5b37"),
  13: ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", "ld_script.ld", "9a4b45031e93c1e1da8186d8c697332710526048"),
  22: ("huderlem/poryscript", "c32481161c767b25a3425fa9f1f8729927ff3d55", "main.go", "10db05ef1518460da78b0bd41f22bb091917a385"),
  28: ("mgba-emu/mgba", "fd9dc5c2cbf234365068855851107e762fc6211b", "src/arm/arm.c", "0b92d7f55f1fb853d4b1b9c9163ee086126066e2"),
}

def opcode_table_check(content):
    table = re.findall(r"^\s*\.4byte\s+(ScrCmd_\w+)\s+@\s+0x([0-9a-fA-F]+)\s*$", content, re.M)
    assert len(table) == 213, "expected exactly 0x00..0xD4 annotated opcodes"
    assert [int(code, 16) for _, code in table] == list(range(213)), "opcode numbering not contiguous"
    assert table[4][0] == "ScrCmd_call" and table[0x25][0] == "ScrCmd_special"
    assert table[0xa2][0] == "ScrCmd_setmetatile"
    return True

def validate(data, entry):
    check(data, entry)
    src = entry["source"]
    assert (src["repository"], src["revision"], src["path"], src["git_blob_sha1"]) == PINNED[entry["ordinal"]], "registry identity mismatch"
    assert entry["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
    assert entry["whole_file_semantic_coverage"] is False
    expected_license = "PENDING_MPL_2_0_NOTICE_AND_FILE_SCOPE_RECONCILIATION" if entry["ordinal"] == 28 else "PENDING_UPSTREAM_LICENSE_RECONCILIATION"
    assert entry["license_status"] == expected_license
    assert entry["dependency_edges"] and entry["unresolved"]
    lines = data.decode("utf-8").splitlines()
    assert len(entry["line_anchors"]) >= 4
    for anchor in entry["line_anchors"]:
        assert 1 <= anchor["line"] <= len(lines)
        assert lines[anchor["line"] - 1].strip() == anchor["text"], "line evidence mismatch"
    if entry["ordinal"] == 14:
        opcode_table_check(data.decode("utf-8"))
    return True

def expect_reject(data, entry):
    try:
        validate(data, entry)
    except (AssertionError, KeyError, IndexError):
        return
    raise AssertionError("negative mutation was accepted")

def run(spec_path, expected_ordinals):
    payload = json.loads((ROOT / spec_path).read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["p0_independent_approved"] == payload["total_independent_approved"] == 0
    assert [x["ordinal"] for x in payload["records"]] == expected_ordinals
    negatives = 0
    for entry in payload["records"]:
        src = entry["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(src["repository"], src["revision"], src["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-curated-source"}), timeout=45) as response:
            data = response.read()
        validate(data, entry)
        altered = data.replace(entry["source_anchors"][0].encode(), b"XGBA_MUTATED_SOURCE", 1)
        assert altered != data
        expect_reject(altered, entry); negatives += 1
        for key, value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("machine_dossier_sha1","fabricated"),("license_status","CLEARED")):
            bad = copy.deepcopy(entry); bad[key] = value
            expect_reject(data, bad); negatives += 1
        bad = copy.deepcopy(entry); bad["line_anchors"][0]["line"] += 1
        expect_reject(data, bad); negatives += 1
        bad = copy.deepcopy(entry); bad["source"]["path"] = "wrong.c"
        expect_reject(data, bad); negatives += 1
        print("PINNED_PARTIAL_OK", entry["ordinal"], src["path"], src["git_blob_sha1"])
    assert negatives == len(expected_ordinals) * 7
    print("CURATED_SOURCE_PASS files={} negatives={} approvals=0 gate=FAIL_INCOMPLETE".format(len(expected_ordinals), negatives))

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1 or sys.argv[1] == "core":
        run("docs/phase1-review-readiness/curated-firered-core-four-20261029.json", [6,9,10,14])
    elif sys.argv[1] == "interop":
        run("docs/phase1-review-readiness/curated-toolchain-interop-four-20261029.json", [12,13,22,28])
    else:
        raise SystemExit("unknown batch")

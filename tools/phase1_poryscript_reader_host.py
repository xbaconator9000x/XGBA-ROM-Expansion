#!/usr/bin/env python3
"""Execute exact pinned FireRed map-script reader function bodies on host.

Extraction preserves original C bodies. Test-only 32-bit ROM-pointer translation
and VarGet shims are NOT FireRed memory-safety checks or emulator execution.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOB = "d0433bdda062b138e53d1a1d3184b4566ad7d9dc"
NAMES = ("MapHeaderGetScriptTable", "MapHeaderCheckScriptTable")
ANCHORS = (
    ("if (*mapScripts == 0)", "mapScripts += 5;", "return T2_READ_PTR(mapScripts);"),
    ("varIndex1 = T1_READ_16(ptr);", "if (!varIndex1)", "ptr += 2;",
     "if (VarGet(varIndex1) == VarGet(varIndex2))", "ptr += 4;"),
)
EXPECTED = "HOST_EXTRACTED_FIRERED_MAP_SCRIPT_READER PASS cases=9 gate=FAIL_INCOMPLETE approvals=0"

def require(ok, why):
    if not ok:
        raise ValueError(why)

def extract_one(source, name, anchors):
    pat = r"static\s+u8\s*\*\s*" + re.escape(name) + r"\s*\(\s*u8\s+tag\s*\)\s*\{"
    matches = list(re.finditer(pat, source))
    require(len(matches) == 1, "missing/duplicate pinned function " + name)
    match = matches[0]
    depth = 0
    end = None
    for i in range(match.end()-1, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i+1
                break
    require(end is not None, "unterminated function " + name)
    body = source[match.start():end]
    for anchor in anchors:
        require(anchor in body, "source semantic anchor missing: " + anchor)
    return body

def extract_pair(source):
    return "\n\n".join(extract_one(source, n, a) for n, a in zip(NAMES, ANCHORS)) + "\n"

def negative_source_controls(source):
    first = extract_one(source, NAMES[0], ANCHORS[0])
    variants = [
        source.replace("static u8 *MapHeaderGetScriptTable", "static u8 *ChangedFunction", 1),
        source + "\n" + first,
        source.replace("static u8 *MapHeaderGetScriptTable(u8 tag)",
                       "static u8 *MapHeaderGetScriptTable(u16 tag)", 1),
        source.replace("mapScripts += 5;", "mapScripts += 6;", 1),
        source.replace("ptr += 4;", "ptr += 8;", 1),
        source.replace("if (!varIndex1)", "if (varIndex1)", 1),
    ]
    for i, changed in enumerate(variants):
        require(changed != source, "source negative mutation ineffective")
        try:
            extract_pair(changed)
        except ValueError:
            continue
        raise ValueError("source mutation escaped: " + str(i))
    return len(variants)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--test", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    head = subprocess.check_output(["git", "-C", str(a.firered), "rev-parse", "HEAD"],
                                   text=True).strip()
    require(head == PIN, "pinned FireRed commit mismatch")
    blob = subprocess.check_output(["git", "-C", str(a.firered),
                                    "hash-object", "src/script.c"], text=True).strip()
    require(blob == BLOB, "pinned FireRed script.c blob mismatch")
    source = (a.firered / "src/script.c").read_text()
    pair = extract_pair(source)
    source_controls = negative_source_controls(source)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "phase1_reader_functions.inc").write_text(pair)
        binary = root / "host-map-script-reader"
        subprocess.run(["cc", "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                        "-I", str(root), str(a.test), "-o", str(binary)], check=True)
        stdout = subprocess.check_output([str(binary)], text=True).strip()
    require(stdout == EXPECTED, "actual host C reader results changed")
    mutations = [
        stdout.replace("cases=9", "cases=8"),
        stdout.replace("gate=FAIL_INCOMPLETE", "gate=PASS"),
        stdout.replace("approvals=0", "approvals=1"),
        stdout.replace("PASS", "FAIL"),
    ]
    require(len(mutations) == 4 and all(x != EXPECTED for x in mutations),
            "output negative mutation escaped")
    result = {
        "class": "SOURCE_EXTRACTED_PINNED_FIRERED_HOST_C_MAP_SCRIPT_READER",
        "source_commit": PIN, "script_c_blob": blob,
        "extracted_function_names": list(NAMES),
        "extracted_c_sha256": hashlib.sha256(pair.encode()).hexdigest(),
        "host_c_cases_passed": 9,
        "source_mutations_rejected": source_controls,
        "output_mutations_rejected": len(mutations),
        "actual_pinned_function_bodies_executed_on_host": True,
        "original_agbcc_or_mgba_execution": False,
        "native_malformed_table_safety_verified": False,
        "host_pointer_guard_is_test_only": True,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bounded POSIX guard-page evidence for exact pinned FireRed map-script C readers.

Missing sentinels fault in host guarded memory. This is NOT mGBA/ARM behavior,
native ROM safety, or proof of a natural stock-gameplay malformed table.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from phase1_poryscript_reader_host import PIN, BLOB, extract_pair, require

EXPECTED = [
    "OUTER_TERMINATED returns_null=1",
    "CONDITIONAL_TERMINATED returns_null=1",
    "OUTER_MISSING_SENTINEL guarded_fault=1",
    "CONDITIONAL_MISSING_SENTINEL guarded_fault=1",
    "HOST_PINNED_READER_GUARD_PAGE PASS cases=4 guarded_faults=2 gate=FAIL_INCOMPLETE approvals=0",
]
ANCHORS = ("while (1)", "if (*mapScripts == 0)", "mapScripts += 5;",
           "if (!varIndex1)", "ptr += 4;")

def check_semantics(pair):
    require(pair.count("while (1)") == 2, "both loops must be unbounded")
    for anchor in ANCHORS[1:]:
        require(pair.count(anchor) == 1, "missing/duplicate sentinel or stride: " + anchor)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--test", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    head = subprocess.check_output(["git", "-C", str(args.firered), "rev-parse", "HEAD"], text=True).strip()
    blob = subprocess.check_output(["git", "-C", str(args.firered), "hash-object", "src/script.c"], text=True).strip()
    require(head == PIN and blob == BLOB, "immutable pinned source mismatch")
    pair = extract_pair((args.firered / "src/script.c").read_text())
    check_semantics(pair)
    variants = [
        pair.replace("while (1)", "while (0)", 1),
        pair.replace("if (*mapScripts == 0)", "if (*mapScripts != 0)", 1),
        pair.replace("if (!varIndex1)", "if (varIndex1)", 1),
        pair.replace("ptr += 4;", "ptr += 8;", 1),
    ]
    for i, altered in enumerate(variants):
        require(altered != pair, "ineffective source mutation")
        try:
            check_semantics(altered)
        except ValueError:
            continue
        raise ValueError("source mutation escaped: " + str(i))
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "phase1_reader_functions.inc").write_text(pair)
        exe = root / "reader-guard"
        subprocess.run(["cc", "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                        "-I", str(root), str(args.test), "-o", str(exe)], check=True)
        actual = subprocess.check_output([str(exe)], text=True).splitlines()
    require(actual == EXPECTED, "guard-page executable result differs")
    mutations = [
        actual[:-1],
        actual[:2] + actual[3:],
        actual[:2] + [actual[3], actual[2]] + actual[4:],
        [s.replace("guarded_fault=1", "guarded_fault=0") for s in actual],
        [s.replace("returns_null=1", "returns_null=0") for s in actual],
        [s.replace("guarded_faults=2", "guarded_faults=1") for s in actual],
        [s.replace("gate=FAIL_INCOMPLETE", "gate=PASS") for s in actual],
        [s.replace("approvals=0", "approvals=1") for s in actual],
    ]
    require(len(mutations) == 8 and all(m != EXPECTED for m in mutations),
            "output mutation escaped")
    result = {
        "class": "PINNED_FIRERED_SOURCE_EXTRACTED_HOST_C_GUARD_PAGE",
        "firered_commit": PIN, "script_c_blob": blob,
        "extracted_function_sha256": hashlib.sha256(pair.encode()).hexdigest(),
        "valid_terminated_cases": 2, "missing_sentinel_guard_fault_cases": 2,
        "guard_fault_address_verified_inside_protected_page": True,
        "source_semantic_mutations_rejected": len(variants),
        "output_mutations_rejected": len(mutations),
        "unmodified_source_extracted_c_functions": True,
        "test_only_posix_memory_guard": True,
        "original_agbcc_or_mgba_execution": False,
        "native_malformed_table_safety_verified": False,
        "gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
        "stdout": actual,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()

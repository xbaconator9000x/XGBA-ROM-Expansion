#!/usr/bin/env python3
"""Phase 1 native mGBA special-sector transaction evidence, fail-closed.
The emulator is unchanged; commands are host-driven, not FireRed ARM code.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

MGBA_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
MGBA_BLOB = "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb"
FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
FIRERED_BLOB = "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c"
REQUIRED = (
    "synthetic_rom_allocated", "native_mgba_core_initialized",
    "synthetic_rom_loaded", "native_flash1m_initialized",
    "fresh_special_sectors_erased", "physical_bank1_selected",
    "old_generation_both_sectors", "adjacent_and_bank0_isolation",
    "interrupted_two_sector_mixed_generation_visible",
    "retry_restores_matching_generation",
    "unlocked_bus_write_does_not_program", "invalid_bank_rejected",
    "bank0_reselected", "bank_switch_does_not_alias_special_sector",
)
SOURCE_ANCHORS = (
    "SECTOR_30_OFFSET = 0x1E000",
    "SECTOR_31_OFFSET = 0x1F000",
    "SECTOR_29_OFFSET = 0x1D000",
    "BANK0_SECTOR_30_OFFSET = 0xE000",
    "core->busWrite8(core, 0x0E000000U + address, value);",
    "GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH1M);",
    "flash(core, 0x5555, 0xAA);",
    "flash(core, 0x2AAA, 0x55);",
    "flash(core, 0x5555, 0xB0);",
    "flash(core, 0x5555, 0x80);",
    "flash(core, address, 0x30);",
    "flash(core, 0x5555, 0xA0);",
    "write_sector(core, 0xE000, 0x60);",
    "write_sector(core, 0xF000, 0x60);",
    "original_firered_arm_executed=false",
    "synthetic_rom=true physical_hardware=false persistent_sav=false",
    "phase1_gate=FAIL_INCOMPLETE approvals=0",
)
def require(condition, message):
    if not condition:
        raise ValueError(message)
def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
def check_source(src):
    for token in SOURCE_ANCHORS:
        require(src.count(token) == 1, "source contract changed: " + token)
    require("0x9D, 0xB3, 0x00, 0x00" in src,
            "original sentinel fixture changed")
    require("value_for(generation, i)" in src, "generation payload changed")
    require("matches(physical, SECTOR_30_OFFSET, 0x60) &&" in src,
            "sector30 mixed generation not checked")
    require("matches(physical, SECTOR_31_OFFSET, 0x20)" in src,
            "sector31 old generation not checked")
def check_output(stdout):
    require("FAIL " not in stdout, "native assertion failure")
    lines = stdout.splitlines()
    passed = [line[5:] for line in lines if line.startswith("PASS ")]
    require(tuple(passed) == REQUIRED, "native assertions missing, duplicated or reordered")
    summaries = [line for line in lines if line.startswith("SUMMARY ")]
    require(len(summaries) == 1, "missing/duplicate native summary")
    require(summaries[0] == (
        "SUMMARY native_mgba=true original_firered_arm_executed=false "
        "synthetic_rom=true physical_hardware=false persistent_sav=false "
        "phase1_gate=FAIL_INCOMPLETE approvals=0 checks=14"),
        "scope or assertion count changed")
    require(len(lines) == len(REQUIRED) + 1, "unexpected runtime transcript")
    return len(passed)
def negatives(src, stdout):
    source_count = 0
    for token in SOURCE_ANCHORS:
        changed = src.replace(token, "PHASE1_MUTATED", 1)
        require(changed != src, "missing source mutation anchor")
        try:
            check_source(changed)
        except ValueError:
            source_count += 1
        else:
            raise AssertionError("source mutation escaped: " + token)
    require(source_count == len(SOURCE_ANCHORS), "source negative count changed")
    mutations = [
        stdout.replace("PASS " + REQUIRED[0] + "\n", "", 1),
        stdout.replace("PASS " + REQUIRED[7], "FAIL " + REQUIRED[7], 1),
        stdout.replace("PASS " + REQUIRED[8], "PASS wrong_sector", 1),
        stdout.replace("PASS " + REQUIRED[9], "PASS " + REQUIRED[8], 1),
        stdout.replace("native_mgba=true", "native_mgba=false", 1),
        stdout.replace("original_firered_arm_executed=false", "original_firered_arm_executed=true", 1),
        stdout.replace("synthetic_rom=true", "synthetic_rom=false", 1),
        stdout.replace("physical_hardware=false", "physical_hardware=true", 1),
        stdout.replace("persistent_sav=false", "persistent_sav=true", 1),
        stdout.replace("phase1_gate=FAIL_INCOMPLETE", "phase1_gate=PASS", 1),
        stdout.replace("approvals=0", "approvals=1", 1),
        stdout.replace("checks=14", "checks=13", 1),
        stdout + "PASS " + REQUIRED[0] + "\n",
    ]
    count = 0
    for modified in mutations:
        require(modified != stdout, "ineffective transcript mutation")
        try:
            check_output(modified)
        except ValueError:
            count += 1
        else:
            raise AssertionError("transcript mutation escaped " + str(count))
    return source_count, count
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mgba", type=Path, required=True)
    p.add_argument("--firered", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--executable", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    a = p.parse_args()
    require(git(a.mgba, "rev-parse", "HEAD") == MGBA_PIN, "mGBA pin mismatch")
    require(git(a.mgba, "hash-object", "src/gba/savedata.c") == MGBA_BLOB,
            "mGBA savedata.c blob mismatch")
    require(git(a.firered, "rev-parse", "HEAD") == FIRERED_PIN,
            "FireRed pin mismatch")
    require(git(a.firered, "hash-object", "src/save.c") == FIRERED_BLOB,
            "FireRed save.c blob mismatch")
    src = a.source.read_text()
    check_source(src)
    completed = subprocess.run([str(a.executable.resolve())],
                               text=True, capture_output=True)
    a.log.parent.mkdir(parents=True, exist_ok=True)
    a.log.write_text(completed.stdout + completed.stderr)
    require(completed.returncode == 0,
            "native executable failed: " + completed.stderr[-3000:])
    count = check_output(completed.stdout)
    source_neg, output_neg = negatives(src, completed.stdout)
    record = {
        "evidence_class": "NATIVE_PINNED_MGBA_FLASH_BUS_SYNTHETIC_ROM",
        "source_pins": {"mgba": MGBA_PIN, "firered": FIRERED_PIN},
        "source_blobs": {"mgba_savedata_c": MGBA_BLOB, "firered_save_c": FIRERED_BLOB},
        "fixture_sha256": hashlib.sha256(a.source.read_bytes()).hexdigest(),
        "runtime_stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "checks": count, "source_mutations_rejected": source_neg,
        "transcript_mutations_rejected": output_neg,
        "native_mgba_flash_bus_executed": True,
        "original_firered_agbcc_arm_executed": False,
        "synthetic_rom": True, "persistent_save_file_tested": False,
        "physical_flash_tested": False, "stock_gameplay_reachability_proven": False,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
        "unresolved": [
            "Original agbcc Trainer Tower ARM call execution in mGBA",
            "Real source-built FireRed gameplay reachability",
            "Persistent .sav restart and hardware power-cut semantics",
            "Independent whole-file semantic review",
        ],
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
if __name__ == "__main__":
    main()

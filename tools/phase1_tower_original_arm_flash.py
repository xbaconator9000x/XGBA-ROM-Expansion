#!/usr/bin/env python3
"""Fail-closed verifier for experimental original-agbcc Flash initialization
and sector30/31 ARM execution in unchanged pinned mGBA. No success claim
until exact-head CI emits and validates the native transcript.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

FR = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
AG = "da598c1d918402c42c0c0d7128ba14567f3175e9"
MG = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOBS = {"src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
         "src/load_save.c": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
         "src/agb_flash_1m.c": "e249fab9a350f3263e7df5f20ff301a6d008e3db"}
SYMBOLS = ("CheckForFlashMemory", "TryWriteSpecialSaveSector",
           "TryReadSpecialSaveSector", "gFlashMemoryPresent", "gFlash")
EXPECTED = ("original_flash_detection_and_callbacks",
            "original_arm_sector30_write", "original_arm_sector31_write",
            "original_arm_sector30_readback", "original_arm_sector31_readback",
            "invalid_sector_no_flash_mutation")
SUMMARY = ("SUMMARY native_mgba=true original_agbcc_arm=true "
           "original_flash_init=true host_flash_commands=false "
           "synthetic_direct_entry=true stock_gameplay=false "
           "physical_hardware=false persistent_sav=false "
           "phase1_gate=FAIL_INCOMPLETE approvals=0")

def need(ok, why):
    if not ok:
        raise ValueError(why)

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def verify(log):
    need("FAIL " not in log, "native failure")
    arm = re.findall(r"^ARM (\w+) steps=(\d+) result=0x([0-9a-f]{8})$", log, re.M)
    names = ("CheckForFlashMemory", "WriteSector30", "WriteSector31",
             "ReadSector30", "ReadSector31", "RejectSector29")
    need(tuple(x[0] for x in arm) == names, "native ARM calls/order")
    need(all(0 < int(x[1]) <= 12000000 for x in arm), "bounded return")
    need(tuple(int(x[2], 16) for x in arm[1:]) == (1, 1, 1, 1, 255),
         "original return values")
    passed = tuple(x[5:] for x in log.splitlines() if x.startswith("PASS "))
    need(passed == EXPECTED, "native assertions")
    need(log.count(SUMMARY) == 1, "native scope")
    return len(arm), len(passed)

def negatives(log):
    changes = [
        log.replace("native_mgba=true", "native_mgba=false", 1),
        log.replace("original_agbcc_arm=true", "original_agbcc_arm=false", 1),
        log.replace("original_flash_init=true", "original_flash_init=false", 1),
        log.replace("host_flash_commands=false", "host_flash_commands=true", 1),
        log.replace("synthetic_direct_entry=true", "synthetic_direct_entry=false", 1),
        log.replace("stock_gameplay=false", "stock_gameplay=true", 1),
        log.replace("physical_hardware=false", "physical_hardware=true", 1),
        log.replace("persistent_sav=false", "persistent_sav=true", 1),
        log.replace("phase1_gate=FAIL_INCOMPLETE", "phase1_gate=PASS", 1),
        log.replace("approvals=0", "approvals=1", 1),
        log.replace("PASS original_arm_sector30_write", "FAIL original_arm_sector30_write", 1),
        log.replace("PASS original_arm_sector31_readback", "PASS wrong_readback", 1),
        log.replace("ARM WriteSector31", "ARM WrongFunction", 1),
        log.replace("steps=", "steps=999999999", 1),
        log.replace("result=0x00000001", "result=0x000000ff", 1),
        log.replace("ARM RejectSector29", "ARM RejectSector30", 1),
    ]
    for i, changed in enumerate(changes):
        need(changed != log, "ineffective negative %d" % i)
        try:
            verify(changed)
        except ValueError:
            continue
        raise AssertionError("negative escaped %d" % i)
    return len(changes)

def main():
    ap = argparse.ArgumentParser()
    for name in ("firered", "agbcc", "mgba", "elf", "rom", "executable", "output", "log"):
        ap.add_argument("--" + name, required=True, type=Path)
    a = ap.parse_args()
    for root, pin in ((a.firered, FR), (a.agbcc, AG), (a.mgba, MG)):
        need(git(root, "rev-parse", "HEAD") == pin, "pin drift")
    for path, blob in BLOBS.items():
        need(git(a.firered, "hash-object", path) == blob, "source blob drift " + path)
    nm = subprocess.check_output(["arm-none-eabi-nm", str(a.elf)], text=True)
    addresses = []
    for name in SYMBOLS:
        matches = re.findall(r"(?m)^([0-9a-fA-F]+)\s+[a-zA-Z]\s+" +
                             re.escape(name) + r"$", nm)
        need(len(matches) == 1, "missing/duplicate ELF symbol " + name)
        addresses.append(int(matches[0], 16))
    for address in addresses[:3]:
        need(0x08000000 <= address < 0x0A000000, "ARM function not in ROM")
    for address in addresses[3:]:
        need(0x02000000 <= address < 0x04000000, "Flash global not in RAM")
    cmd = [str(a.executable.resolve()), str(a.rom.resolve())] + [
        hex(x) for x in addresses]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    a.log.parent.mkdir(parents=True, exist_ok=True)
    a.log.write_text(proc.stdout + proc.stderr)
    need(proc.returncode == 0, "native execution failed: " + proc.stderr[-1200:])
    calls, checks = verify(proc.stdout)
    rejected = negatives(proc.stdout)
    out = {"evidence_class": "EXPERIMENTAL_ORIGINAL_AGBCC_ARM_MGBA_SPECIAL_SECTORS",
           "pins": {"firered": FR, "agbcc": AG, "mgba": MG},
           "source_blobs": BLOBS, "symbols": dict(zip(SYMBOLS, map(hex, addresses))),
           "rom_sha256": hashlib.sha256(a.rom.read_bytes()).hexdigest(),
           "native_transcript_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
           "original_arm_calls": calls, "native_assertions": checks,
           "transcript_negatives_rejected": rejected,
           "stock_gameplay": False, "physical_flash": False,
           "persistent_sav": False, "phase1_gate": "FAIL_INCOMPLETE",
           "independent_approvals": 0}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("ORIGINAL_ARM_SPECIAL_SECTORS_NATIVE_PASS calls=%d checks=%d negatives=%d gate=FAIL_INCOMPLETE approvals=0" % (calls, checks, rejected))

if __name__ == "__main__":
    main()

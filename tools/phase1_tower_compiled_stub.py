#!/usr/bin/env python3
"""Phase 1: source-built original-agbcc FireRed Trainer Tower stub ABI witness.

Checks actual linked Thumb instructions; does not execute the game or prove
external Trainer Tower data reachability in a different ROM.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e",
    "src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
}
SYMBOL = "ReadTrainerTowerAndValidate"
HEADER = re.compile(r"(?m)^([0-9a-fA-F]+)\s+<ReadTrainerTowerAndValidate>:\s*$")
INSN = re.compile(
    r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{4,8}\s+)+"
    r"(?P<opcode>[a-z][a-z0-9.]*)\s*(?P<operands>.*)$"
)

def require(ok, message):
    if not ok:
        raise ValueError(message)

def parse_stub(disassembly):
    matches = list(HEADER.finditer(disassembly))
    require(len(matches) == 1, "expected one exact linked Trainer Tower stub symbol")
    body = disassembly[matches[0].end():].split("\n\n", 1)[0]
    insns = []
    for line in body.splitlines():
        match = INSN.match(line)
        if match:
            insns.append((match.group("opcode").lower(),
                          match.group("operands").split(";", 1)[0].strip().lower()))
    require(len(insns) == 2, f"stub instruction count changed: {insns}")
    first, second = insns
    require(first[0] in ("mov", "movs", "mov.w", "movs.w")
            and re.fullmatch(r"r0\s*,\s*#(?:0|0x0+)", first[1]),
            f"linked stub does not set R0 to FALSE: {first}")
    require(second[0] in ("bx", "bx.w") and second[1] in ("lr", "r14"),
            f"linked stub does not return directly: {second}")
    return {"linked_symbol_address": matches[0].group(1),
            "instructions": [list(i) for i in insns],
            "compiled_stub_returns_false": True}

def rejected(text):
    try:
        parse_stub(text)
    except ValueError:
        return True
    raise AssertionError("tampered linked stub escaped verification")

def controls():
    good = ("08012340 <ReadTrainerTowerAndValidate>:\n"
            " 8012340: 2000  movs r0, #0\n"
            " 8012342: 4770  bx lr\n")
    require(parse_stub(good)["compiled_stub_returns_false"], "positive disassembly failed")
    mutations = (
        good.replace("#0", "#1"),
        good.replace("r0, #0", "r1, #0"),
        good.replace("bx lr", "bx r3"),
        good.replace("ReadTrainerTowerAndValidate", "OtherFunction"),
        good.replace("4770  bx lr", "f000  bl 0x8001000"),
        good.replace(" 8012342: 4770  bx lr\n", ""),
        good.replace(" 8012342: 4770  bx lr\n", " 8012342: 46c0  nop\n 8012344: 4770  bx lr\n"),
    )
    for i, mutation in enumerate(mutations):
        require(rejected(mutation), f"negative disassembly #{i+1} escaped")
    return len(mutations)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--elf", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    head = subprocess.check_output(["git", "-C", str(a.source), "rev-parse", "HEAD"],
                                   text=True).strip()
    require(head == PIN, "FireRed source revision mismatch")
    identities = {}
    for path, blob in BLOBS.items():
        actual = subprocess.check_output(["git", "-C", str(a.source),
                                          "hash-object", path], text=True).strip()
        require(actual == blob, f"source blob mismatch: {path}")
        identities[path] = actual
    nm = subprocess.check_output(["arm-none-eabi-nm", str(a.elf)], text=True)
    symbols = re.findall(r"(?m)^[0-9a-fA-F]+\s+[Tt]\s+ReadTrainerTowerAndValidate$", nm)
    require(len(symbols) == 1, "expected one linked text symbol in original-agbcc ELF")
    disasm = subprocess.check_output(
        ["arm-none-eabi-objdump", "-d", "--disassemble=" + SYMBOL, str(a.elf)],
        text=True)
    compiled = parse_stub(disasm)
    count = controls()
    result = {
        "source_revision": PIN, "source_blobs": identities,
        "original_agbcc_revision": "da598c1d918402c42c0c0d7128ba14567f3175e9",
        "linked_elf_sha256": hashlib.sha256(a.elf.read_bytes()).hexdigest(),
        "compiled": compiled, "negative_controls_rejected": count,
        "evidence_scope": "linked source-built FireRed stub; not emulator execution",
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
        "remaining": ["native callsite reachability", "e-Reader writer execution",
                      "cross-engine ABI", "hardware Flash recovery"]
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Phase 1: original-agbcc linked FireRed map-script reader symbol witness.

This is a compiled function-boundary check, not emulator execution or proof of
malformed-table memory safety. The prior host-C reader test is independent.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOB = "d0433bdda062b138e53d1a1d3184b4566ad7d9dc"
FUNCTIONS = ("MapHeaderGetScriptTable", "MapHeaderCheckScriptTable")
HEADER = re.compile(r"(?m)^([0-9a-fA-F]+)\s+<(?P<name>\w+)>:\s*$")
INSN = re.compile(r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{4,8}\s+)+"
                  r"(?P<opcode>[a-z][a-z0-9.]*)\s*(?P<operands>.*)$")

def require(value, message):
    if not value:
        raise ValueError(message)

def parse(disassembly, name, address):
    hits = [m for m in HEADER.finditer(disassembly) if m.group("name") == name]
    require(len(hits) == 1, "missing/duplicate original-agbcc reader symbol " + name)
    require(int(hits[0].group(1), 16) == address, "ELF symbol/disassembly mismatch")
    body = disassembly[hits[0].end():].split("\n\n", 1)[0]
    instructions = [m.group("opcode").lower() for line in body.splitlines()
                    if (m := INSN.match(line))]
    require(len(instructions) >= 4, "empty/truncated compiled reader " + name)
    require(any(op.startswith("ldr") for op in instructions),
            "no compiled reader load instruction " + name)
    require(any(op.startswith("b") for op in instructions),
            "no compiled reader branch instruction " + name)
    return {"name": name, "address": f"0x{address:08x}",
            "instruction_count": len(instructions),
            "load_opcodes": sorted(set(x for x in instructions if x.startswith("ldr"))),
            "branch_opcodes": sorted(set(x for x in instructions if x.startswith("b"))),
            "disassembly_sha256": hashlib.sha256(body.encode()).hexdigest()}

def controls():
    good = ("08123400 <MapHeaderGetScriptTable>:\n"
            " 8123400: 7800 ldrb r0, [r0]\n"
            " 8123402: 2800 cmp r0, #0\n"
            " 8123404: d001 beq 812340a <MapHeaderGetScriptTable+0xa>\n"
            " 8123406: 4770 bx lr\n")
    require(parse(good, FUNCTIONS[0], 0x08123400)["instruction_count"] == 4,
            "positive compiled reader fixture invalid")
    edits = (
        good.replace("MapHeaderGetScriptTable>:", "OtherReader>:"),
        good.replace("08123400 <", "08123402 <"),
        good.replace("ldrb", "movs"),
        good.replace("beq", "nop").replace("bx", "movs"),
        good.replace(" 8123406: 4770 bx lr\n", ""),
        good.replace(" 8123402: 2800 cmp r0, #0\n", ""),
        good + good,
    )
    for i, changed in enumerate(edits):
        try:
            parse(changed, FUNCTIONS[0], 0x08123400)
        except ValueError:
            continue
        raise AssertionError(f"compiled reader mutation escaped: {i}")
    return len(edits)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--elf", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    def run(*cmd):
        return subprocess.check_output(cmd, text=True).strip()
    require(run("git", "-C", str(a.source), "rev-parse", "HEAD") == PIN,
            "wrong FireRed revision")
    require(run("git", "-C", str(a.source), "hash-object", "src/script.c") == BLOB,
            "wrong script.c blob")
    nm = run("arm-none-eabi-nm", str(a.elf))
    witnesses = []
    for name in FUNCTIONS:
        matches = re.findall(r"(?m)^([0-9a-fA-F]+)\s+[Tt]\s+"+name+r"$", nm)
        require(len(matches) == 1, "linked reader symbol missing/duplicate: "+name)
        address = int(matches[0], 16) & ~1
        require(0x08000000 <= address < 0x0A000000, "reader outside GBA ROM address window")
        disassembly = run("arm-none-eabi-objdump", "-d",
                          "--disassemble="+name, str(a.elf))
        witnesses.append(parse(disassembly, name, address))
    negatives = controls()
    result = {
        "source_pin": PIN, "script_c_blob": BLOB,
        "original_agbcc_pin": "da598c1d918402c42c0c0d7128ba14567f3175e9",
        "elf_sha256": hashlib.sha256(a.elf.read_bytes()).hexdigest(),
        "linked_reader_functions": witnesses,
        "compiled_trace_mutations_rejected": negatives,
        "scope": "original-agbcc compiled linked symbols; no reader instruction execution",
        "unresolved": ["mGBA runtime reader table consumption",
                       "malformed-table native safety", "pointer bounds in GBA address space",
                       "independent complete-file review"],
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()

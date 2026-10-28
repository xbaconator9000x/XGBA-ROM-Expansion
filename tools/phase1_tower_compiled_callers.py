#!/usr/bin/env python3
"""Phase 1: original-agbcc Trainer Tower linked callsite contract, not runtime reachability."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from phase1_tower_compiled_stub import parse_stub

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {"src/trainer_tower.c": "732b3f2ed31ed95d6476b9e111d53f759c448d81",
         "src/cereader_tool.c": "395be0bcbed8454e645a9f5670cde3024eda508e"}
STUB = "ReadTrainerTowerAndValidate"
CALLERS = ("SetUpTrainerTowerDataStruct", "StartTrainerTowerChallenge")
HEADER = re.compile(r"(?m)^[0-9a-fA-F]+\s+<(?P<name>\w+)>:\s*$")
BRANCH = re.compile(r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{4,8}\s+)+"
                    r"(?P<op>[a-z][a-z0-9.]*)\s+(?P<address>(?:0x)?[0-9a-fA-F]+)"
                    r"\s+<(?P<target>[^>]+)>", re.M)

def require(value, reason):
    if not value:
        raise ValueError(reason)

def body(source, name):
    m = re.search(r"\bstatic\s+void\s+" + name + r"\s*\(\s*void\s*\)\s*\{", source)
    require(m is not None, "source function absent: " + name)
    depth = 0
    for i in range(m.end()-1, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[m.start():i+1]
    raise ValueError("source function unterminated: " + name)

def source_contract(source):
    setup, start = (body(source, n) for n in CALLERS)
    a = "ReadTrainerTowerAndValidate() == TRUE"
    b = "CEReaderTool_LoadTrainerTower(&sTrainerTowerState->data)"
    c = "gTrainerTowerFloors[challengeType]"
    require(setup.count(a) == 1 and setup.count(b) == 1
            and setup.index(a) < setup.index(b) < setup.index(c),
            "external-load setup guard/order changed")
    a, b, c = ("if (!ReadTrainerTowerAndValidate())",
               "TRAINER_TOWER.validated = TRUE;", "TRAINER_TOWER.validated = FALSE;")
    require(start.count(a) == 1 and start.index(a) < start.index(b) < start.index(c),
            "challenge validation guard/order changed")
    return {"setup_external_loader_guarded_by_stub_true": True,
            "challenge_validated_true_when_stub_false": True,
            "setup_ignores_external_loader_return": True}

def source_controls(source):
    edits = (("ReadTrainerTowerAndValidate() == TRUE", "ReadTrainerTowerAndValidate() == FALSE"),
             ("CEReaderTool_LoadTrainerTower(&sTrainerTowerState->data)", "CEReaderTool_LoadTrainerTower(NULL)"),
             ("if (!ReadTrainerTowerAndValidate())", "if (ReadTrainerTowerAndValidate())"),
             ("TRAINER_TOWER.validated = TRUE;", "TRAINER_TOWER.validated = FALSE;"))
    for a, b in edits:
        require(a in source, "negative source anchor missing")
        try:
            source_contract(source.replace(a, b, 1))
        except ValueError:
            continue
        raise AssertionError("source mutation escaped: " + a)
    return len(edits)

def parse_caller(disassembly, name, address):
    matches = [m for m in HEADER.finditer(disassembly) if m.group("name") == name]
    require(len(matches) == 1, "linked caller symbol absent/duplicate: " + name)
    instructions = list(BRANCH.finditer(disassembly[matches[0].end():].split("\n\n", 1)[0]))
    calls = [m for m in instructions if m.group("target") == STUB]
    require(len(calls) == 1, "expected one direct linked stub call: " + name)
    require(calls[0].group("op").lower() in ("bl", "bl.w"), "not Thumb BL")
    require(int(calls[0].group("address"), 16) == address,
            "linked stub target address mismatch")
    return {"caller": name, "stub_target": f"0x{address:08x}",
            "direct_bl_count": 1, "other_symbolic_branches": len(instructions)-1}

def compiled_controls():
    good = ("08100000 <SetUpTrainerTowerDataStruct>:\n"
            " 8100000: f000 f800  bl 815d834 <ReadTrainerTowerAndValidate>\n"
            " 8100004: 4770       bx lr\n")
    require(parse_caller(good, CALLERS[0], 0x0815d834)["direct_bl_count"] == 1,
            "positive disassembly fixture invalid")
    edits = (good.replace("815d834", "815d836"),
             good.replace("  bl ", "  b "),
             good.replace("<ReadTrainerTowerAndValidate>", "<OtherFunction>"),
             good.replace("SetUpTrainerTowerDataStruct", "OtherCaller"),
             good.replace(" 8100004:", " 8100004: f000 f800 bl 815d834 <ReadTrainerTowerAndValidate>\n 8100006:"),
             good.replace("f000 f800  bl", "f000 f800  nop"),
             good.replace("ReadTrainerTowerAndValidate", "ReadTrainerTowerAndValidateExtra"))
    for i, mutated in enumerate(edits):
        try:
            parse_caller(mutated, CALLERS[0], 0x0815d834)
        except ValueError:
            continue
        raise AssertionError(f"compiled mutation escaped: {i}")
    return len(edits)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--elf", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    def run(*cmd):
        return subprocess.check_output(cmd, text=True).strip()
    require(run("git", "-C", str(args.source), "rev-parse", "HEAD") == PIN,
            "wrong source revision")
    for path, blob in BLOBS.items():
        require(run("git", "-C", str(args.source), "hash-object", path) == blob,
                "source blob mismatch " + path)
    source = (args.source/"src/trainer_tower.c").read_text()
    contract = source_contract(source)
    source_negative = source_controls(source)
    nm = run("arm-none-eabi-nm", str(args.elf))
    def address(name):
        hits = re.findall(r"(?m)^([0-9a-fA-F]+)\s+[Tt]\s+" + re.escape(name) + r"$", nm)
        require(len(hits) == 1, "missing/duplicate ELF symbol " + name)
        return int(hits[0], 16) & ~1
    target = address(STUB)
    require(target != 0, "null stub address")
    require(parse_stub(run("arm-none-eabi-objdump", "-d", "--disassemble="+STUB,
                           str(args.elf)))["compiled_stub_returns_false"],
            "linked stub no longer FALSE")
    observations = []
    for name in CALLERS:
        address(name)
        observations.append(parse_caller(
            run("arm-none-eabi-objdump", "-d", "--disassemble="+name, str(args.elf)),
            name, target))
    negative = compiled_controls()
    result = {"source_pin": PIN, "blobs": BLOBS,
              "original_agbcc_pin": "da598c1d918402c42c0c0d7128ba14567f3175e9",
              "elf_sha256": hashlib.sha256(args.elf.read_bytes()).hexdigest(),
              "source_contract": contract, "linked_stub_returns_false": True,
              "linked_callsites": observations,
              "source_mutations_rejected": source_negative,
              "compiled_mutations_rejected": negative,
              "not_verified": ["runtime execution", "complete gameplay reachability",
                               "external two-sector Flash transaction", "independent whole-file approval"],
              "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()

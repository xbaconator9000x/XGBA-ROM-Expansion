#!/usr/bin/env python3
"""Phase 1: compiled pinned FireRed bank-switch commands to mGBA Flash writes.

The actual upstream function bodies are injected without rewriting their C.
Stubbed save bus/timing/VFile means this is not full emulator or ROM execution.
"""
import argparse
import hashlib
import json
import re
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path

PINS = {
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
}
BLOBS = {
    ("pret/pokefirered", "src/agb_flash.c"): "08aeed1638e214a3cad8b28d103964ab24342fba",
    ("mgba-emu/mgba", "src/gba/savedata.c"): "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
}
F = "pret/pokefirered"
M = "mgba-emu/mgba"
FUNCTIONS = [
    (F, "src/agb_flash.c", "void SwitchFlashBank(u8 bankNum)"),
    (M, "src/gba/savedata.c", "void GBASavedataWriteFlash(struct GBASavedata* savedata, uint16_t address, uint8_t value)"),
    (M, "src/gba/savedata.c", "void _flashSwitchBank(struct GBASavedata* savedata, int bank)"),
    (M, "src/gba/savedata.c", "void _flashErase(struct GBASavedata* savedata)"),
    (M, "src/gba/savedata.c", "void _flashEraseSector(struct GBASavedata* savedata, uint16_t sectorStart)"),
]
ANCHORS = {
    "SwitchFlashBank": ["FLASH_WRITE(0x5555, 0xAA);", "FLASH_WRITE(0x2AAA, 0x55);",
                        "FLASH_WRITE(0x5555, 0xB0);", "FLASH_WRITE(0x0000, bankNum);"],
    "GBASavedataWriteFlash": ["savedata->currentBank[address] = value;",
                              "if (address == 0 && value < 2)",
                              "_flashSwitchBank(savedata, value);",
                              "_flashEraseSector(savedata, address);",
                              "_flashErase(savedata);"],
    "_flashSwitchBank": ["savedata->type = GBA_SAVEDATA_FLASH1M;",
                         "savedata->currentBank = &savedata->data[bank << 16];"],
    "_flashErase": ["memset(savedata->data, 0xFF, size);"],
    "_flashEraseSector": ["size_t size = 0x1000;",
                          "mTimingSchedule(&savedata->p->timing, &savedata->dust, FLASH_ERASE_CYCLES);",
                          "memset(&savedata->currentBank[sectorStart & ~(size - 1)], 0xFF, size);"],
}

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def fetch(repo, path):
    url = "https://raw.githubusercontent.com/" + repo + "/" + PINS[repo] + "/" + path
    request = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-flash-bank-sector"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()

def extract(source, signature):
    brace = -1
    pos = -1
    for match in re.finditer(re.escape(signature), source):
        candidate = match.end()
        while candidate < len(source) and source[candidate].isspace():
            candidate += 1
        if candidate < len(source) and source[candidate] == "{":
            pos, brace = match.start(), candidate
            break
    require(pos >= 0, "missing pinned function definition: " + signature)
    depth = 1
    for i in range(brace + 1, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[pos:i + 1]
    raise RuntimeError("unclosed function: " + signature)

def contract(raw):
    parts = {}
    for repo, path, signature in FUNCTIONS:
        name = signature.split("(")[0].split()[-1]
        part = extract(raw[(repo, path)].decode("utf-8"), signature)
        for anchor in ANCHORS[name]:
            require(anchor in part, "pinned Flash contract drift: " + name + ": " + anchor)
        parts[name] = part
    return parts

def negative_controls(raw):
    cases = [
        ("SwitchFlashBank", "FLASH_WRITE(0x5555, 0xB0);", "FLASH_WRITE(0x5555, 0xB1);"),
        ("GBASavedataWriteFlash", "if (address == 0 && value < 2)", "if (address == 0 && value < 3)"),
        ("GBASavedataWriteFlash", "savedata->currentBank[address] = value;", "savedata->currentBank[address+1] = value;"),
        ("_flashSwitchBank", "savedata->currentBank = &savedata->data[bank << 16];", "savedata->currentBank = &savedata->data[bank << 15];"),
        ("_flashErase", "memset(savedata->data, 0xFF, size);", "memset(savedata->data, 0x00, size);"),
        ("_flashEraseSector", "size_t size = 0x1000;", "size_t size = 0x2000;"),
        ("_flashEraseSector", "FLASH_ERASE_CYCLES);", "FLASH_PROGRAM_CYCLES);"),
    ]
    passed = []
    for name, before, after in cases:
        repo, path, signature = next(row for row in FUNCTIONS if row[2].split("(")[0].split()[-1] == name)
        key = (repo, path)
        src = raw[key].decode("utf-8")
        require(before in extract(src, signature), "missing mutation anchor: " + name)
        modified = dict(raw)
        modified[key] = src.replace(before, after, 1).encode()
        try:
            contract(modified)
        except RuntimeError:
            passed.append(name + ": " + before)
        else:
            raise RuntimeError("negative mutation escaped: " + name)
    return passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=Path("tests/phase1_firered_mgba_flash_bank_sector.c"))
    args = parser.parse_args()
    raw = {key: fetch(*key) for key in BLOBS}
    for key, expected in BLOBS.items():
        require(sha(raw[key]) == expected, "pinned Git blob mismatch: " + str(key))
    parts = contract(raw)
    negatives = negative_controls(raw)
    harness = args.harness.read_text()
    require(harness.count("/* PINNED_FUNCTIONS_INSERT */") == 1, "missing injection marker")
    compiled = harness.replace("/* PINNED_FUNCTIONS_INSERT */", "\n\n".join(parts.values()))
    with tempfile.TemporaryDirectory(prefix="xgba-flash-bank-") as d:
        cfile = Path(d) / "witness.c"
        binary = Path(d) / "witness"
        cfile.write_text(compiled)
        subprocess.run(["cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        str(cfile), "-o", str(binary)], check=True)
        output = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
        result = json.loads(output.stdout)
    require(result["compiled_pinned_functions"] == 5, "unexpected compiled function count")
    require(result["sector_programs"] == 32, "missing 32-sector coverage")
    result.update({
        "pins": PINS,
        "verified_git_blobs": {repo + "/" + path: value for (repo, path), value in BLOBS.items()},
        "negative_controls": negatives,
        "negative_control_count": len(negatives),
        "machine_processed_new_unique_files": 0,
        "target_shortfall": 1000,
        "new_complete_file_reviews": 0,
        "independent_approvals": 0,
        "evidence_scope": "five exact upstream C function bodies in stubbed host Flash bus; no native ROM/emulator",
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()

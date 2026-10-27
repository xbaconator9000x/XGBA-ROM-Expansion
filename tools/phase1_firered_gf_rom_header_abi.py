#!/usr/bin/env python3
"""Source-pinned Phase 1 whole-file review preparation: FireRed's GF ROM header.

This verifies source identity and structural contracts, NOT runtime compatibility,
a compiled ELF location, or independent semantic approval.
"""
import argparse
import hashlib
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

UPSTREAM = "pret/pokefirered"
REV = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/rom_header_gf.c": "60696d810a8154c350fa293104477638061bc5c9",
    "src/rom_header.s": "c98c89992a128b82ef3bc8f75c791cd1c6cbdcb9",
    "Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
    "ld_script.ld": "9a4b45031e93c1e1da8186d8c697332710526048",
    "ld_script_modern.ld": "e930243522bd21da40cc1a05de9a42b8ad409b46",
}
EXPECTED_OFFSETS = {
    "flagsOffset": ("SaveBlock1", "flags"),
    "varsOffset": ("SaveBlock1", "vars"),
    "pokedexOffset": ("SaveBlock2", "pokedex"),
    "seen1Offset": ("SaveBlock1", "seen1"),
    "seen2Offset": ("SaveBlock1", "seen2"),
    "partyCountOffset": ("SaveBlock1", "playerPartyCount"),
    "partyOffset": ("SaveBlock1", "playerParty"),
    "warpFlagsOffset": ("SaveBlock2", "specialSaveWarpFlags"),
    "trainerIdOffset": ("SaveBlock2", "playerTrainerId"),
    "playerNameOffset": ("SaveBlock2", "playerName"),
    "playerGenderOffset": ("SaveBlock2", "playerGender"),
    "unkFlagOffset": ("SaveBlock2", "unkFlag2"),
    "unkFlagOffset2": ("SaveBlock2", "unkFlag2"),
    "externalEventFlagsOffset": ("SaveBlock1", "externalEventFlags"),
    "externalEventDataOffset": ("SaveBlock1", "externalEventData"),
    "gcnLinkFlagsOffset": ("SaveBlock2", "gcnLinkFlags"),
    "pcItemsOffset": ("SaveBlock1", "pcItems"),
    "giftRibbonsOffset": ("SaveBlock1", "giftRibbons"),
    "enigmaBerryOffset": ("SaveBlock1", "enigmaBerry"),
}
EXPECTED_SIZES = {
    "saveBlock2Size": "SaveBlock2",
    "saveBlock1Size": "SaveBlock1",
    "enigmaBerrySize": "EnigmaBerry",
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def fetch(path):
    url = "https://raw.githubusercontent.com/" + UPSTREAM + "/" + REV + "/" + path
    request = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-gf-header-audit"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()

def verify_sources(raw):
    require(set(raw) == set(BLOBS), "missing or extra pinned inputs")
    for path, expected in BLOBS.items():
        require(git_blob_sha(raw[path]) == expected, "source Git blob mismatch: " + path)

def contract(raw):
    gf = raw["src/rom_header_gf.c"].decode("utf-8")
    rom = raw["src/rom_header.s"].decode("utf-8")
    make = raw["Makefile"].decode("utf-8")
    old = raw["ld_script.ld"].decode("utf-8")
    modern = raw["ld_script_modern.ld"].decode("utf-8")
    struct = re.search(r"struct GFRomHeader\s*\{(.*?)\};", gf, re.S)
    init = re.search(r"static const struct GFRomHeader sGFRomHeader\s*=\s*\{(.*?)\};", gf, re.S)
    require(struct is not None and init is not None, "missing complete GF header declarations")
    members = []
    for declaration in struct.group(1).split(";"):
        declaration = declaration.strip()
        if not declaration:
            continue
        pointer = re.search(r"\(\*\s*(\w+)\s*\)", declaration)
        match = pointer or re.search(r"(\w+)\s*(?:\[\s*\d*\s*\])?\s*$", declaration)
        require(match is not None, "unparsed GF header member")
        members.append(match.group(1))
    require(len(members) == 74 and len(set(members)) == 74, "GF header 74-member ABI changed")
    assignments = re.findall(r"^\s*\.(\w+)\s*=", init.group(1), re.M)
    counts = Counter(assignments)
    require(set(counts) == set(members), "GF header initializer coverage mismatch")
    require(len(assignments) == 75 and all(n == (2 if name == "gameName" else 1)
                                            for name, n in counts.items()),
            "unexpected duplicate or missing designated initializer")
    require(re.search(r"#ifdef FIRERED\s*\.gameName\s*=\s*\"pokemon red version\",\s*#else\s*\.gameName\s*=\s*\"pokemon green version\",\s*#endif",
                      init.group(1)) is not None, "conditional game name variants changed")
    require('__attribute__((section(".text.consts")))' in gf,
            "GF header no longer explicitly placed in .text.consts")
    offsets = dict((member, (kind, field)) for member, kind, field in
                   re.findall(r"^\s*\.(\w+)\s*=\s*offsetof\(struct\s+(\w+),\s*(\w+)\)",
                              init.group(1), re.M))
    require(offsets == EXPECTED_OFFSETS, "save layout offsetof contract changed")
    sizes = dict(re.findall(r"^\s*\.(\w+)\s*=\s*sizeof\(struct\s+(\w+)\)",
                            init.group(1), re.M))
    require(sizes == EXPECTED_SIZES, "save layout sizeof contract changed")
    require("RomHeaderNintendoLogo:" in rom and ".space 156" in rom
            and "RomHeaderGameCode:" in rom and "RomHeaderChecksum:" in rom,
            "distinct cartridge header assembly changed")
    require("src/rom_header_gf.o(.text*);" in old,
            "legacy linker no longer places GF header's text input")
    require("*(.text*);" in modern, "modern linker no longer accepts text.consts")
    require("LD_SCRIPT := ld_script.ld" in make and
            "LD_SCRIPT := ld_script_modern.ld" in make and
            "$(FIX) $@" in make and "$(OBJCOPY) -O binary" in make,
            "build/linker/header-fix producer chain changed")
    return {
        "complete_file": "src/rom_header_gf.c",
        "member_count": len(members),
        "unique_initializer_members": len(counts),
        "conditional_initializer_occurrences": counts["gameName"],
        "save_offset_fields": len(offsets),
        "save_size_fields": len(sizes),
        "aliased_offset_fields": ["unkFlagOffset", "unkFlagOffset2"],
        "linker_variants_source_checked": ["ld_script.ld", "ld_script_modern.ld"],
        "compiled_elf_verified": False,
        "external_consumer_abi_verified": False,
        "independent_semantic_approval": False,
    }

def negative_controls(raw):
    mutations = [
        ("src/rom_header_gf.c", "u32 unk20;", "u32 renamed20;"),
        ("src/rom_header_gf.c", ".unk20 = 0xFFFFFFFF", ".renamed20 = 0xFFFFFFFF"),
        ("src/rom_header_gf.c", 'section(".text.consts")', 'section(".rodata")'),
        ("src/rom_header_gf.c", ".flagsOffset = offsetof(struct SaveBlock1, flags)",
         ".flagsOffset = offsetof(struct SaveBlock2, flags)"),
        ("src/rom_header_gf.c", ".unkFlagOffset2 = offsetof(struct SaveBlock2, unkFlag2)",
         ".unkFlagOffset2 = offsetof(struct SaveBlock2, unkFlag1)"),
        ("src/rom_header_gf.c", ".saveBlock1Size = sizeof(struct SaveBlock1)",
         ".saveBlock1Size = sizeof(struct SaveBlock2)"),
        ("src/rom_header.s", ".space 156", ".space 155"),
        ("ld_script.ld", "src/rom_header_gf.o(.text*);", "src/rom_header_gf.o(.rodata);"),
        ("ld_script_modern.ld", "*(.text*);", "*(.text);"),
        ("Makefile", "LD_SCRIPT := ld_script_modern.ld", "LD_SCRIPT := ld_script.ld"),
    ]
    passed = []
    for path, before, after in mutations:
        source = raw[path].decode("utf-8")
        require(source.count(before) == 1, "mutation anchor absent or ambiguous: " + path + ":" + before)
        altered = dict(raw)
        altered[path] = source.replace(before, after, 1).encode()
        try:
            contract(altered)
        except ValueError:
            passed.append(path + ": " + before)
        else:
            raise RuntimeError("negative control escaped: " + path + ": " + before)
    return passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = {path: fetch(path) for path in BLOBS}
    verify_sources(raw)
    summary = contract(raw)
    negatives = negative_controls(raw)
    result = {
        "schema": "xgba.phase1.gf_rom_header_abi_review.v1",
        "phase1_gate": "FAIL_INCOMPLETE",
        "source_revision": REV,
        "source_blobs": BLOBS,
        "source_sha256": {p: hashlib.sha256(v).hexdigest() for p, v in raw.items()},
        "source_lines": {p: len(v.splitlines()) for p, v in raw.items()},
        "whole_file_review": summary,
        "negative_controls": negatives,
        "negative_control_count": len(negatives),
        "historical_machine_triage": 14721,
        "registered_substantive_candidates_unchanged": 113,
        "independent_approvals_unchanged": 0,
        "new_registered_dispositions": 0,
        "limitations": [
            "Source-structural preparation only, not a compiled ELF placement proof",
            "No external GF ROM header consumer or save migration tested",
            "No independent reviewer has signed any file disposition",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pinned_sources": len(raw), "members": summary["member_count"],
                      "negative_controls": len(negatives), "gate": "FAIL_INCOMPLETE"}))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pinned FireRed compiler/linker variant and ROM-image contract.

Source interpretation only: not a linked ELF inspection, emulator test, or
independent whole-file semantic disposition.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
    "config.mk": "c07d31fc083fa341cca29c340e560ed107d5364a",
    "ld_script.ld": "9a4b45031e93c1e1da8186d8c697332710526048",
    "ld_script_rev10.ld": "4eb3bc2eec749437be5797202442188972ac0693",
    "ld_script_modern.ld": "e930243522bd21da40cc1a05de9a42b8ad409b46",
}
LEGACY = ("ld_script.ld", "ld_script_rev10.ld")
ALL_SCRIPTS = (*LEGACY, "ld_script_modern.ld")


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def contract(files):
    config, make = files["config.mk"], files["Makefile"]
    for expr in ("GAME_VERSION  ?= FIRERED", "GAME_REVISION ?= 0",
                 "MODERN        ?= 0"):
        require(expr in config, "default build variant drift: " + expr)
    require("ifeq (modern,$(MAKECMDGOALS))\n  MODERN := 1\nendif" in config,
            "modern goal selection drift")
    require("ifeq ($(MODERN),0)\n  CPPFLAGS += -I tools/agbcc/include"
            in make and "CC1 := tools/agbcc/bin/agbcc$(EXE)" in make,
            "original agbcc compiler branch drift")
    require("else\n  # Note: The makefile must be set up to not call these if modern == 0\n"
            "  MODERNCC := $(PREFIX)gcc" in make,
            "modern compiler branch drift")

    # Require the *complete* selector: both legacy revisions and modern mode.
    selector = ("ifeq ($(MODERN),0)\n"
                "ifeq ($(GAME_REVISION),10)\n"
                "LD_SCRIPT := ld_script_rev10.ld\n"
                "LD_SCRIPT_DEPS := $(OBJ_DIR)/sym_bss_rev10.ld "
                "$(OBJ_DIR)/sym_common_rev10.ld $(OBJ_DIR)/sym_ewram_rev10.ld\n"
                "else\n"
                "LD_SCRIPT := ld_script.ld\n"
                "LD_SCRIPT_DEPS := $(OBJ_DIR)/sym_bss.ld "
                "$(OBJ_DIR)/sym_common.ld $(OBJ_DIR)/sym_ewram.ld\n"
                "endif\n"
                "else\n"
                "LD_SCRIPT := ld_script_modern.ld\n"
                "LD_SCRIPT_DEPS :=\n"
                "endif")
    require(selector in make, "linker script / build variant dispatch drift")
    require("$(ELF): $(LD_SCRIPT) $(LD_SCRIPT_DEPS) $(OBJS)" in make
            and "$(LD) $(LDFLAGS) -T ../../$< --print-memory-usage"
            in make, "ELF linker invocation drift")
    require("$(ROM): $(ELF)\n"
            "\t$(OBJCOPY) -O binary --gap-fill 0xFF --pad-to 0x9000000 $< $@"
            in make, "ROM binary conversion or minimum padding drift")
    require('$(FIX) $@ -t"$(TITLE)" -c$(GAME_CODE) '
            '-m$(MAKER_CODE) -r$(GAME_REVISION) --silent' in make,
            "ELF header-fix stage drift")

    memory = re.compile(
        r"(?m)^\s*ROM\s+\(rx\)\s*:\s*ORIGIN\s*=\s*0x8000000,\s*"
        r"LENGTH\s*=\s*32M\s*$")
    for path in ALL_SCRIPTS:
        script = files[path]
        require(len(memory.findall(script)) == 1,
                "32 MiB native ROM region drift: " + path)
        require(". = 0x8000000;" in script,
                "native ROM start drift: " + path)
        require(re.search(r"\.text\s*:\s*ALIGN\(4\)\s*\{", script)
                and re.search(r"\}\s*>\s*ROM\s*=0", script),
                "ROM output section linkage drift: " + path)

    fixed = re.compile(r"(?m)^\s*gfx_data\s+0x08D00000\s*:\s*$")
    for path in LEGACY:
        require(len(fixed.findall(files[path])) == 1,
                "legacy fixed graphics address drift: " + path)
        require(re.search(
            r"gfx_data\s+0x08D00000\s*:\s*ALIGN\(4\)\s*"
            r"\{\s*src/graphics\.o\(\.rodata\);\s*\}\s*>\s*ROM\s*=0",
            files[path]), "legacy graphics placement semantics drift: " + path)
    modern = files["ld_script_modern.ld"]
    require(not re.search(r"(?m)^\s*gfx_data\b", modern),
            "modern linker unexpectedly defines fixed graphics section")
    for section in (".text", ".data", ".rodata"):
        require(re.search(re.escape(section) + r"\s*:\s*ALIGN\(4\)\s*\{"
                          r"[\s\S]*?\}\s*>\s*ROM\s*=0", modern),
                "modern ROM section linkage drift: " + section)

    return {
        "rom_region_origin": "0x08000000",
        "rom_region_size_bytes": 32 * 1024 * 1024,
        "objcopy_pad_to_address": "0x09000000",
        "minimum_binary_length_from_origin_bytes": 16 * 1024 * 1024,
        "legacy_fixed_graphics_address": "0x08D00000",
        "legacy_fixed_graphics_offset_bytes": 13 * 1024 * 1024,
        "linker_scripts": {
            "original_default": "ld_script.ld",
            "original_revision_10": "ld_script_rev10.ld",
            "modern": "ld_script_modern.ld",
        },
        "modern_has_legacy_fixed_graphics_section": False,
        "proves_arbitrary_rom_expansion": False,
        "compiled_elf_or_emulator_test": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    def git(*command):
        return subprocess.check_output(
            ["git", "-C", str(root), *command], text=True,
            stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "upstream revision drift")
    files = {}
    for path, blob in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == blob,
                "pinned source blob drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)

    mutations = [
        ("ld_script.ld", "LENGTH = 32M", "LENGTH = 64M"),
        ("ld_script_rev10.ld", "LENGTH = 32M", "LENGTH = 64M"),
        ("ld_script_modern.ld", "LENGTH = 32M", "LENGTH = 64M"),
        ("ld_script.ld", "gfx_data 0x08D00000", "gfx_data 0x08E00000"),
        ("ld_script_rev10.ld", "gfx_data 0x08D00000",
         "gfx_data 0x08E00000"),
        ("ld_script_modern.ld", "    script_data :",
         "    gfx_data 0x08D00000 :\n    script_data :"),
        ("Makefile", "LD_SCRIPT := ld_script_rev10.ld",
         "LD_SCRIPT := ld_script_modern.ld"),
        ("Makefile", "--pad-to 0x9000000", "--pad-to 0xA000000"),
        ("Makefile", "CC1 := tools/agbcc/bin/agbcc$(EXE)",
         "CC1 := tools/agbcc/bin/other$(EXE)"),
        ("config.mk", "MODERN        ?= 0", "MODERN        ?= 1"),
    ]
    for index, (path, old, new) in enumerate(mutations, 1):
        require(old in files[path], "missing mutation fixture: " + str(index))
        changed = dict(files)
        changed[path] = files[path].replace(old, new, 1)
        try:
            contract(changed)
        except RuntimeError:
            continue
        raise RuntimeError("negative fixture accepted: " + str(index))

    result = {
        "evidence_class": "PINNED_FIRERED_LINKER_VARIANT_SOURCE_ONLY",
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unresolved": [
            "Actual linked ELF section ranges and per-variant map/symbol files",
            "Native emulator and cartridge addressing, including mirrors",
            "External storage protocol, relocation and pointer provenance",
            "Independent whole-file semantic dispositions and editor round trips",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("PINNED_FIRERED_LINKER_VARIANT_SOURCE_PASS negative_controls=10")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()

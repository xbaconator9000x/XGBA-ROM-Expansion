#!/usr/bin/env python3
"""Phase 1: reuse FireRed's ORIGINAL data-assembly Makefile pipeline for Poryscript.

The pinned CLI emits assembly; the pinned FireRed Makefile owns the two-pass
preproc/CPP/assembler integration. This test does not implement a new toolchain,
alter upstream sources, or prove native map-script execution in mGBA.
"""
import argparse
import hashlib
import json
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from verify_poryscript_actual_cli_arm_table import (
    BASE, EXPECTED_LINKED, EXPECTED_RAW, FR_BLOBS, FR_PIN, PORY,
    PS_BLOBS, PS_PIN, RELOC_OFFSETS, call, elf_section, macro, pin,
    require, validate,
)

RECIPE = "$(PREPROC) $< charmap.txt | $(CPP) $(INCLUDE_SCANINC_ARGS) - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@"
RULES = (
    "$(C_BUILDDIR)/%.o: $(C_SUBDIR)/%.s",
    "$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s",
)
EXPECTED_CLI_SHA256 = "411a9e954470723a9b0186e74eaaa3544aad2f12658737e35fc320b9da1d4b7d"

def get_recipe(makefile, rule):
    pattern = r"(?m)^" + re.escape(rule) + r"\s*\n\t([^\n]+)"
    matches = re.findall(pattern, makefile)
    require(len(matches) == 1, "missing/duplicate pinned native assembly rule " + rule)
    return matches[0]

def check_recipe(makefile):
    for rule in RULES:
        require(get_recipe(makefile, rule) == RECIPE,
                "FireRed native Makefile pipeline drifted: " + rule)
    require("PREPROC   := $(TOOLS_DIR)/preproc/preproc$(EXE)" in makefile,
            "pinned preprocessor ownership changed")
    require("AS := $(PREFIX)as" in makefile, "native assembler owner changed")
    require("PREFIX := arm-none-eabi-" in makefile, "native assembler prefix changed")
    require("INCLUDE_SCANINC_ARGS := $(INCLUDE_DIRS:%=-I %)" in makefile,
            "native include arguments changed")

def negative_source_controls(makefile):
    edits = (
        (RECIPE, RECIPE.replace("$(PREPROC) $< charmap.txt | ", "", 1)),
        (RECIPE, RECIPE.replace("$(CPP) $(INCLUDE_SCANINC_ARGS) - | ", "", 1)),
        (RECIPE, RECIPE.replace("$(PREPROC) -ie", "$(PREPROC) -i", 1)),
        (RECIPE, RECIPE.replace("$(AS) $(ASFLAGS)", "$(AS)")),
        (RECIPE, RECIPE.replace("$(CPP) $(INCLUDE_SCANINC_ARGS)", "$(CPP)")),
        ("$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s",
         "$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.asm"),
        ("PREPROC   := $(TOOLS_DIR)/preproc/preproc$(EXE)",
         "PREPROC   := $(TOOLS_DIR)/replacement/preproc$(EXE)"),
        ("PREFIX := arm-none-eabi-", "PREFIX := xgba-custom-"),
    )
    for index, (old, new) in enumerate(edits):
        require(old in makefile, "negative source anchor absent: " + str(index))
        altered = makefile.replace(old, new, 1)
        require(altered != makefile, "ineffective negative source mutation")
        try:
            check_recipe(altered)
        except ValueError:
            continue
        raise ValueError("native recipe mutation escaped: " + str(index))
    return len(edits)

def pipeline(source, fr, obj, *, original=True):
    # Use the exact upstream Makefile stage order, not a replacement parser.
    first = "tools/preproc/preproc " + shlex.quote(str(source)) + " charmap.txt | " if original else ""
    second = (" | tools/preproc/preproc -ie " + shlex.quote(str(source)) + " charmap.txt") if original else ""
    command = (first + "cc -E -I include -" + second +
               " | arm-none-eabi-as -mcpu=arm7tdmi --defsym FIRERED=1" +
               " --defsym REVISION=0 --defsym ENGLISH=1 --defsym MODERN=0" +
               " -o " + shlex.quote(str(obj)) + " -")
    return subprocess.run(["bash", "-o", "pipefail", "-c", command],
                          cwd=fr, text=True, capture_output=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poryscript", type=Path, required=True)
    ap.add_argument("--firered", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    ps, fr = args.poryscript.resolve(), args.firered.resolve()
    psrc, fsrc = pin(ps, PS_PIN, PS_BLOBS), pin(fr, FR_PIN, FR_BLOBS)
    check_recipe(fsrc["Makefile"])
    negatives = negative_source_controls(fsrc["Makefile"])
    for executable in ("go", "make", "cc", "arm-none-eabi-as", "arm-none-eabi-ld"):
        require(shutil.which(executable) is not None, "missing existing tool " + executable)
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        fixture = tmp / "input.pory"
        fixture.write_text(PORY)
        cli = tmp / "poryscript"
        call(["go", "build", "-o", str(cli), "."], cwd=ps)
        emitted = call([str(cli), "-cc", "", "-fc", "", "-lm=false",
                        "-optimize=true", "-i", str(fixture)], cwd=ps)
        require(hashlib.sha256(emitted.encode()).hexdigest() == EXPECTED_CLI_SHA256,
                "pinned CLI fixture output changed")
        native = fsrc["asm/macros/map.inc"]
        preamble = "\n".join((
            ".syntax unified", macro(native, "map_script"),
            macro(native, "map_script_2"),
            ".equ MAP_SCRIPT_ON_TRANSITION, 3",
            ".equ MAP_SCRIPT_ON_FRAME_TABLE, 2",
            '.section .rodata,"a",%progbits', "",
        ))
        source = tmp / "fixture.s"
        source.write_text(preamble + emitted)
        call(["make", "-C", str(fr / "tools/preproc"), "-j2"])
        require((fr / "tools/preproc/preproc").is_file(), "native preproc not built")
        obj = tmp / "fixture.o"
        run = pipeline(source, fr, obj)
        require(run.returncode == 0,
                "pinned Makefile-equivalent native pipeline failed: " + run.stderr[-3000:])
        linked = tmp / "fixture.elf"
        call(["arm-none-eabi-ld", "--section-start=.rodata=0x08000000",
              "-e", "XGBA_MapScripts", "-o", str(linked), str(obj)])
        object_bytes = obj.read_bytes()
        rel_header, rel_bytes = elf_section(object_bytes, ".rel.rodata")
        require(rel_header[9] == 8 and len(rel_bytes) % 8 == 0,
                "native recipe produced invalid ARM relocations")
        relocations = [struct.unpack_from("<II", rel_bytes, i)
                       for i in range(0, len(rel_bytes), 8)]
        header, linked_bytes = elf_section(linked.read_bytes(), ".rodata")
        result = {
            "raw": elf_section(object_bytes, ".rodata")[1],
            "linked": linked_bytes,
            "linked_address": header[3],
            "relocations": relocations,
        }
        validate(result)
        # Executable negative: the CLI's double-colon global label is NOT
        # accepted by the raw assembler without FireRed's preprocessor.
        raw_obj = tmp / "without-pinned-preproc.o"
        skipped = pipeline(source, fr, raw_obj, original=False)
        require(skipped.returncode != 0, "missing native preprocessor escaped")
        require(not raw_obj.exists() or raw_obj.stat().st_size == 0,
                "bypassed preprocessor unexpectedly emitted an object")
    evidence = {
        "class": "PINNED_PORYSCRIPT_ACTUAL_FIRERED_MAKEFILE_NATIVE_ASSEMBLY_PIPELINE",
        "firered_commit": FR_PIN, "poryscript_commit": PS_PIN,
        "firered_makefile_blob": FR_BLOBS["Makefile"],
        "firered_preproc_blob": FR_BLOBS["tools/preproc/preproc.cpp"],
        "poryscript_emitter_blob": PS_BLOBS["emitter/emitter.go"],
        "reused_upstream_make_rules": list(RULES),
        "reused_existing_native_stages": ["preproc", "cc -E", "preproc -ie",
                                          "arm-none-eabi-as", "arm-none-eabi-ld"],
        "linked_section_sha256": hashlib.sha256(EXPECTED_LINKED).hexdigest(),
        "raw_section_sha256": hashlib.sha256(EXPECTED_RAW).hexdigest(),
        "relocation_offsets": list(RELOC_OFFSETS),
        "source_mutations_rejected": negatives,
        "missing_preprocessor_executable_negative_rejected": True,
        "pinned_makefile_recipe_reused_without_upstream_edits": True,
        "full_rom_link_or_mgba_reader_execution": False,
        "license_clearance_for_distributed_rom_or_tools": False,
        "new_complete_file_reviews": 0, "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    def validate_evidence(d):
        require(d["phase1_gate"] == "FAIL_INCOMPLETE" and
                d["independent_approvals"] == 0, "gate/approval evidence changed")
        require(d["linked_section_sha256"] ==
                hashlib.sha256(EXPECTED_LINKED).hexdigest(), "linked bytes drifted")
        require(d["source_mutations_rejected"] == 8 and
                d["missing_preprocessor_executable_negative_rejected"],
                "negative evidence missing")
        require(d["full_rom_link_or_mgba_reader_execution"] is False,
                "native runtime claim escaped")
    validate_evidence(evidence)
    evidence_mutations = (
        {"phase1_gate": "PASS"},
        {"independent_approvals": 1},
        {"linked_section_sha256": "0" * 64},
        {"source_mutations_rejected": 7},
        {"missing_preprocessor_executable_negative_rejected": False},
        {"full_rom_link_or_mgba_reader_execution": True},
    )
    for index, edit in enumerate(evidence_mutations):
        try:
            validate_evidence({**evidence, **edit})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped: " + str(index))
    evidence["evidence_mutations_rejected"] = len(evidence_mutations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()

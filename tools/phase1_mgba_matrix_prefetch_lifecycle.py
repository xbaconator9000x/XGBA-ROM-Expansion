#!/usr/bin/env python3
"""Phase 1 source-only mGBA Matrix remap / ARM prefetch lifecycle evidence.

Pinned blobs, bounded source assertions, and deliberately failing mutations.
A pass does not certify runtime coherence or approve a whole-file review.
"""
import argparse
import json
import subprocess
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOBS = {
    "src/arm/arm.c": "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
    "include/mgba/internal/arm/isa-inlines.h": "ebda28e411f627c6cd1570aff6f29a3b79a60840",
    "src/gba/cart/matrix.c": "9ccbe883235b98bcf56cd609015e7b4003aa832c",
    "src/gba/serialize.c": "a307a51e751f412c64a7378323c56758304ebe85",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def scope(source, begin, end):
    start = source.find(begin)
    require(start >= 0, "missing scope start: " + begin)
    stop = source.find(end, start + len(begin))
    require(stop >= 0, "missing scope end: " + end)
    return source[start:stop]


def ordered(source, *needles):
    at = 0
    for needle in needles:
        found = source.find(needle, at)
        require(found >= 0, "missing/reordered semantic anchor: " + needle)
        at = found + len(needle)


def contract(src):
    arm = src["src/arm/arm.c"]
    inline = src["include/mgba/internal/arm/isa-inlines.h"]
    matrix = src["src/gba/cart/matrix.c"]
    serialize = src["src/gba/serialize.c"]
    memory = src["src/gba/memory.c"]

    arm_step = scope(arm, "static inline void ARMStep(", "static inline void ThumbStep(")
    thumb_step = scope(arm, "static inline void ThumbStep(", "void ARMRun(")
    ordered(arm_step, "uint32_t opcode = cpu->prefetch[0];",
            "cpu->prefetch[0] = cpu->prefetch[1];",
            "cpu->gprs[ARM_PC] += WORD_SIZE_ARM;",
            "LOAD_32(cpu->prefetch[1], cpu->gprs[ARM_PC] & cpu->memory.activeMask, cpu->memory.activeRegion);")
    ordered(thumb_step, "uint32_t opcode = cpu->prefetch[0];",
            "cpu->prefetch[0] = cpu->prefetch[1];",
            "cpu->gprs[ARM_PC] += WORD_SIZE_THUMB;",
            "LOAD_16(cpu->prefetch[1], cpu->gprs[ARM_PC] & cpu->memory.activeMask, cpu->memory.activeRegion);")
    run = scope(arm, "void ARMRun(", "void ARMRunFake(")
    require("ThumbStep(cpu);" in run and "ARMStep(cpu);" in run,
            "CPU run loop no longer uses inspected prefetch consumers")

    arm_write = scope(inline, "static inline int32_t ARMWritePC(", "static inline int32_t ThumbWritePC(")
    thumb_write = scope(inline, "static inline int32_t ThumbWritePC(", "static inline int _ARMModeHasSPSR(")
    ordered(arm_write, "cpu->memory.setActiveRegion(cpu, pc);",
            "LOAD_32(cpu->prefetch[0], pc & cpu->memory.activeMask, cpu->memory.activeRegion);",
            "pc += WORD_SIZE_ARM;",
            "LOAD_32(cpu->prefetch[1], pc & cpu->memory.activeMask, cpu->memory.activeRegion);")
    ordered(thumb_write, "cpu->memory.setActiveRegion(cpu, pc);",
            "LOAD_16(cpu->prefetch[0], pc & cpu->memory.activeMask, cpu->memory.activeRegion);",
            "pc += WORD_SIZE_THUMB;",
            "LOAD_16(cpu->prefetch[1], pc & cpu->memory.activeMask, cpu->memory.activeRegion);")

    region = scope(memory,
                   "static void GBASetActiveRegion(struct ARMCore* cpu, uint32_t address) {",
                   "#define LOAD_BAD")
    ordered(region, "if (newRegion == memory->activeRegion) {",
            "return;", "case GBA_REGION_ROM0:", "case GBA_REGION_ROM2_EX:",
            "cpu->memory.activeRegion = memory->rom;",
            "cpu->memory.activeMask = memory->romMask;")

    remap = scope(matrix, "static void _remapMatrix(", "void GBAMatrixReset(")
    write = scope(matrix, "void GBAMatrixWrite(", "void GBAMatrixWrite16(")
    replay = matrix[matrix.index("void GBAMatrixDeserialize("):]
    ordered(remap, "gba->romVf->seek(gba->romVf, gba->memory.matrix.paddr, SEEK_SET);",
            "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], gba->memory.matrix.size);")
    ordered(write, "case 0x01:", "case 0x11:", "_remapMatrix(gba);")
    ordered(replay, "gba->memory.matrix.size = 0x200;",
            "for (i = 0; i < 16; ++i)", "_remapMatrix(gba);")
    for label, segment in (("Matrix remap", remap), ("Matrix command", write), ("Matrix replay", replay)):
        for refresh in ("cpu->prefetch", "ARMWritePC(", "ThumbWritePC(", "setActiveRegion("):
            require(refresh not in segment, label + " gained a local prefetch/region refresh: " + refresh)

    restore = serialize[serialize.index("bool GBADeserialize("):]
    pipeline = scope(restore, "GBAUnlCartDeserialize(gba, state);",
                     "GBASerializedMiscFlags miscFlags = 0;")
    ordered(pipeline, "GBAUnlCartDeserialize(gba, state);",
            "gba->memory.activeRegion = -1;",
            "gba->cpu->memory.setActiveRegion(gba->cpu, gba->cpu->gprs[ARM_PC]);",
            "if (gba->cpu->cpsr.t) {",
            "if (state->cpuPrefetch[0] && state->cpuPrefetch[1]) {",
            "LOAD_32(gba->cpu->prefetch[0], 0, state->cpuPrefetch);",
            "LOAD_16(gba->cpu->prefetch[0], (gba->cpu->gprs[ARM_PC] - WORD_SIZE_THUMB)",
            "gba->cpu->executionMode = MODE_ARM;",
            "if (state->cpuPrefetch[0] && state->cpuPrefetch[1]) {",
            "LOAD_32(gba->cpu->prefetch[0], 0, state->cpuPrefetch);",
            "LOAD_32(gba->cpu->prefetch[0], (gba->cpu->gprs[ARM_PC] - WORD_SIZE_ARM)")
    require(pipeline.count("if (state->cpuPrefetch[0] && state->cpuPrefetch[1]) {") == 2
            and pipeline.count("LOAD_32(gba->cpu->prefetch[0], 0, state->cpuPrefetch);") == 2,
            "both ARM/Thumb saved-prefetch branches must be inspected")
    ordered(restore, "GBAUnlCartDeserialize(gba, state);",
            "gba->cpu->memory.setActiveRegion(gba->cpu, gba->cpu->gprs[ARM_PC]);",
            "GBAMemoryDeserialize(&gba->memory, state);",
            "if (gba->memory.matrix.size) {",
            "GBAMatrixDeserialize(gba, state);",
            "mTimingInterrupt(&gba->timing);")
    between = scope(restore, "GBAMatrixDeserialize(gba, state);", "mTimingInterrupt(&gba->timing);")
    require("prefetch" not in between and "setActiveRegion" not in between,
            "post-Matrix restore now contains a local pipeline refresh")
    return {
        "instruction_consumption": "ARM_and_Thumb_consume_saved_prefetch_0_then_shift_and_refill",
        "pc_write_refill": "ARMWritePC_and_ThumbWritePC_refill_both_prefetch_slots",
        "rom_active_region": "direct_ROM_buffer_pointer_and_mask",
        "matrix_command_remap": "0x01_or_0x11_copy_VFile_bytes_without_local_prefetch_refill",
        "savestate_prefetch": "saved_two_slots_when_both_nonzero_else_ROM_fallback",
        "savestate_order": "unlicensed_cart_then_prefetch_then_RAM_then_conditional_Matrix_replay",
        "post_matrix_local_prefetch_refresh": False,
        "runtime_coherence_certified": False,
    }


def mutation_controls(src):
    # Each edit changes a source-level semantic dependency, never the pinned input.
    cases = [
        ("src/arm/arm.c", "cpu->gprs[ARM_PC] += WORD_SIZE_ARM;", "cpu->gprs[ARM_PC] += WORD_SIZE_THUMB;"),
        ("src/arm/arm.c", "LOAD_16(cpu->prefetch[1], cpu->gprs[ARM_PC] & cpu->memory.activeMask, cpu->memory.activeRegion);", "LOAD_32(cpu->prefetch[1], cpu->gprs[ARM_PC] & cpu->memory.activeMask, cpu->memory.activeRegion);"),
        ("include/mgba/internal/arm/isa-inlines.h", "LOAD_32(cpu->prefetch[0], pc & cpu->memory.activeMask, cpu->memory.activeRegion);", "LOAD_16(cpu->prefetch[0], pc & cpu->memory.activeMask, cpu->memory.activeRegion);"),
        ("include/mgba/internal/arm/isa-inlines.h", "LOAD_16(cpu->prefetch[1], pc & cpu->memory.activeMask, cpu->memory.activeRegion);", "LOAD_32(cpu->prefetch[1], pc & cpu->memory.activeMask, cpu->memory.activeRegion);"),
        ("src/gba/memory.c", "cpu->memory.activeRegion = memory->rom;", "cpu->memory.activeRegion = memory->wram;"),
        ("src/gba/memory.c", "cpu->memory.activeMask = memory->romMask;", "cpu->memory.activeMask = GBA_SIZE_IWRAM - 1;"),
        ("src/gba/cart/matrix.c", "case 0x11:", "case 0x12:"),
        ("src/gba/cart/matrix.c", "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], gba->memory.matrix.size);", "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], 0);"),
        ("src/gba/cart/matrix.c", "gba->memory.matrix.size = 0x200;", "gba->memory.matrix.size = 0x400;"),
        ("src/gba/cart/matrix.c", "gba->romVf->seek(gba->romVf, gba->memory.matrix.paddr, SEEK_SET);", "ARMWritePC(gba->cpu);\n\tgba->romVf->seek(gba->romVf, gba->memory.matrix.paddr, SEEK_SET);"),
        ("src/gba/serialize.c", "LOAD_32(gba->cpu->prefetch[0], 0, state->cpuPrefetch);", "LOAD_32(gba->cpu->prefetch[0], 0, state->matrix2.mappings);"),
        ("src/gba/serialize.c", "LOAD_16(gba->cpu->prefetch[0], (gba->cpu->gprs[ARM_PC] - WORD_SIZE_THUMB)", "LOAD_32(gba->cpu->prefetch[0], (gba->cpu->gprs[ARM_PC] - WORD_SIZE_THUMB)"),
        ("src/gba/serialize.c", "GBAMatrixDeserialize(gba, state);", "GBAMatrixSerialize(gba, state);"),
        ("src/gba/serialize.c", "mTimingInterrupt(&gba->timing);", "ARMWritePC(gba->cpu);\n\tmTimingInterrupt(&gba->timing);"),
    ]
    for index, (path, before, after) in enumerate(cases, 1):
        require(before in src[path], "missing negative fixture " + str(index))
        mutated = dict(src)
        mutated[path] = src[path].replace(before, after, 1)
        try:
            contract(mutated)
        except RuntimeError:
            continue
        raise RuntimeError("negative fixture unexpectedly accepted: " + str(index))
    return len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mgba", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    root = args.mgba.resolve()

    def git(*command):
        return subprocess.check_output(["git", "-C", str(root), *command],
                                       text=True, stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "upstream commit mismatch")
    src = {}
    for path, expected in BLOBS.items():
        require((root / path).is_file(), "missing source: " + path)
        require(git("hash-object", path) == expected, "upstream Git blob mismatch: " + path)
        src[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(src)
    negatives = mutation_controls(src)
    result = {
        "class": "PINNED_MGBA_MATRIX_PREFETCH_SOURCE_CANDIDATE",
        "upstream_commit": PIN,
        "git_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": negatives,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unverified": [
            "live Matrix command during ARM/Thumb execution",
            "prefetch and translated-fetch coherence after savestate replay",
            "old savestate fallback and changed external VFile content",
            "editor interoperability, full runtime certification, independent reviews",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PINNED_MGBA_MATRIX_PREFETCH_SOURCE_PASS negative_controls={negatives}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pinned FireRed/mGBA save-continuation vs savestate ROM-mapping contracts.

Source evidence only. Never counts independent semantic approvals or runtime proof.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

FR_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MG_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FR_BLOBS = {
    "src/reset_save_heap.c": "745270dc7415b869c302daaa7b9c2b2e5b2865f1",
}
MG_BLOBS = {
    "src/gba/serialize.c": "a307a51e751f412c64a7378323c56758304ebe85",
    "include/mgba/internal/gba/serialize.h": "0192cd90ffeeb1d435cd51915325783bf18fb85c",
    "src/gba/cart/matrix.c": "9ccbe883235b98bcf56cd609015e7b4003aa832c",
    "include/mgba/internal/gba/cart/matrix.h": "27e32a75c0f521dac9ded53821591485089d7b76",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "src/gba/gba.c": "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
    "include/mgba/internal/gba/memory.h": "0aad912613e726560d06bbdbf6061986e69e5842",
    "include/mgba-util/vfs.h": "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
    "src/util/vfs/vfs-mem.c": "048194e2dd2d0b3b395a852d2092c694663c88a2",
    "src/util/vfs/vfs-fd.c": "2535bd0fb76740745ae038d5523ead28658f1035",
    "src/util/vfs/vfs-file.c": "4a63e53f842b31b24d6188e6525ddcf121a0c7da",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def ordered(source, *anchors):
    position = 0
    for anchor in anchors:
        found = source.find(anchor, position)
        require(found >= 0, "missing or reordered source anchor: " + anchor)
        position = found + len(anchor)


def section(source, start, end=None):
    i = source.find(start)
    require(i >= 0, "missing section start: " + start)
    j = source.find(end, i + len(start)) if end else len(source)
    require(j >= 0, "missing section end: " + str(end))
    return source[i:j]


def banking_contract(mg):
    """Pinned >32 MiB Matrix opt-in, CRC provenance and VFile short-read ABI."""
    gba = mg["src/gba/gba.c"]
    memory = mg["src/gba/memory.c"]
    memh = mg["include/mgba/internal/gba/memory.h"]
    matrix = mg["src/gba/cart/matrix.c"]
    vfs = mg["include/mgba-util/vfs.h"]
    vfmem = mg["src/util/vfs/vfs-mem.c"]
    vffd = mg["src/util/vfs/vfs-fd.c"]
    vffile = mg["src/util/vfs/vfs-file.c"]
    require("GBA_SIZE_ROM0 = 0x02000000," in memh, "ROM0 32 MiB extent drift")
    load = section(gba, "bool GBALoadROM(", "void GBAYankROM(")
    large = section(load, "if (gba->pristineRomSize > GBA_SIZE_ROM0) {",
                    "} else if (gba->pristineRomSize == 0x00100000)")
    ordered(large, "vf->seek(vf, 0xAC, SEEK_SET);",
            "vf->read(vf, &ident, 1);", "if (ident == 'M') {",
            "gba->memory.romSize = 0x01000000;",
            "gba->memory.rom = anonymousMemoryMap(GBA_SIZE_ROM0);",
            "gba->pristineRomSize = GBA_SIZE_ROM0;")
    require("vf->read(vf, gba->memory.rom" not in large,
            "Matrix branch now populates ROM buffer before CRC")
    ordered(load, "gba->pristineRomSize = vf->size(vf);",
            "if (gba->pristineRomSize > GBA_SIZE_ROM0)",
            "gba->pristineRomSize = GBA_SIZE_ROM0;",
            "gba->romCrc32 = doCrc32(gba->memory.rom, gba->pristineRomSize);")
    reset = section(gba, "void GBAReset(", "void GBASkipBIOS(")
    ordered(reset, "GBAMemoryReset(gba);",
            "if (gba->romVf && gba->romVf->size(gba->romVf) > GBA_SIZE_ROM0)",
            "gba->romVf->seek(gba->romVf, 0xAC, SEEK_SET);",
            "if (ident == 'M') {", "GBAMatrixReset(gba);")
    memreset = section(memory, "void GBAMemoryReset(", "void GBAMemoryClearAGBPrint(")
    require("memset(&gba->memory.matrix, 0, sizeof(gba->memory.matrix));" in memreset,
            "Matrix reset-to-disabled state changed")
    matrix_reset = section(matrix, "void GBAMatrixReset(", "void GBAMatrixWrite(")
    ordered(matrix_reset, "gba->memory.matrix.size = 0x1000;",
            "gba->memory.matrix.paddr = 0;",
            "gba->memory.matrix.vaddr = 0;",
            "_remapMatrix(gba);",
            "gba->memory.matrix.paddr = 0x200;",
            "gba->memory.matrix.vaddr = 0x1000;",
            "_remapMatrix(gba);")
    remap = section(matrix, "static void _remapMatrix(", "void GBAMatrixReset(")
    require("0xFFFFE000" in remap and "int start = gba->memory.matrix.vaddr >> 9;" in remap,
            "8 KiB Matrix window / 512-byte slot constraint changed")
    require("ssize_t (*read)(struct VFile* vf, void* buffer, size_t size);" in vfs
            and "off_t (*seek)(struct VFile* vf, off_t offset, int whence);" in vfs
            and "ssize_t (*size)(struct VFile* vf);" in vfs,
            "VFile seek/read/size return-value ABI changed")
    memread = section(vfmem, "\nssize_t _vfmRead(", "\nssize_t _vfmWrite(")
    require("size = vfm->size - vfm->offset;" in memread
            and "return size;" in memread,
            "memory-backed VFile short-read behaviour changed")
    require("return read(vfd->fd, buffer, size);" in
            section(vffd, "\nssize_t _vfdRead(", "\nssize_t _vfdWrite("),
            "FD VFile read return-value behaviour changed")
    require("return fread(buffer, 1, size, vff->file);" in
            section(vffile, "\nssize_t _vffRead(", "\nssize_t _vffWrite("),
            "FILE VFile read return-value behaviour changed")
    return {
        "matrix_activation": "ROM_file_gt_32MiB_and_header_byte_0xAC_equals_M",
        "matrix_rom_buffer_size": "32MiB",
        "matrix_reported_rom_size": "16MiB",
        "matrix_virtual_window": "8KiB_in_16_x_512B_slots",
        "rom_crc_provenance": "in_memory_ROM_buffer_before_GBAMatrixReset_not_entire_backing_VFile",
        "matrix_reset": "cleared_then_conditionally_enabled",
        "vfile_read_contract": "short_or_failed_reads_possible_no_local_matrix_result_check",
        "runtime_or_editor_certification": False,
    }


def contract(fr, mg):
    state = mg["src/gba/serialize.c"]
    header = mg["include/mgba/internal/gba/serialize.h"]
    matrix = mg["src/gba/cart/matrix.c"]
    matrixh = mg["include/mgba/internal/gba/cart/matrix.h"]
    memory = mg["src/gba/memory.c"]
    reload = fr["src/reset_save_heap.c"]

    require("GBASavestateMagic = 0x01000000;" in state
            and "GBASavestateVersion = 0x0000000B;" in state,
            "savestate format identity changed")
    require('static_assert(sizeof(struct GBASerializedState) == 0x61000' in header,
            "serialized struct extent changed")
    require("#define GBA_MATRIX_MAPPINGS_MAX 16" in matrixh,
            "matrix mapping cardinality changed")

    restore = section(state, "bool GBADeserialize(")
    version = section(restore, "LOAD_32(ucheck, 0, &state->versionMagic);",
                      "LOAD_32(ucheck, 0, &state->biosChecksum);")
    require("error = true;" in version and "continuing anyway" in version,
            "savestate version failure/warning branches changed")
    identity = section(restore, "if (gba->memory.rom) {",
                       "LOAD_32(ucheck, 0, &state->romCrc32);")
    require(re.search(r'if \(state->id != cart->id \|\| memcmp\(state->title, cart->title, sizeof\(state->title\)\)\)\s*\{\s*mLOG\(GBA_STATE, WARN, "Savestate is for a different game"\);\s*error = true;', identity),
            "cartridge ID/title hard rejection changed")
    crc = section(restore, "LOAD_32(ucheck, 0, &state->romCrc32);",
                  "LOAD_32(check, 0, &state->cpu.cycles);")
    require("if (ucheck != gba->romCrc32)" in crc
            and "Savestate is for a different version of the game" in crc
            and "error = true;" not in crc and "return false;" not in crc,
            "ROM CRC mismatch is no longer warning-only")
    pc = section(restore, "int region = (check >> BASE_OFFSET);", "if (error) {")
    require("region == GBA_REGION_ROM0" in pc and
            "region == GBA_REGION_ROM1" in pc and
            "region == GBA_REGION_ROM2" in pc and
            "gba->memory.romSize - WORD_SIZE_ARM" in pc and
            "Savestate created using a differently sized version of the ROM" in pc
            and "error = true;" in pc, "conditional ROM PC-size guard changed")
    require(re.search(r'if \(error\)\s*\{\s*return false;\s*\}\s*mTimingClear\(&gba->timing\);', restore),
            "hard validation no longer precedes state mutation")

    ordered(restore,
            "GBAUnlCartDeserialize(gba, state);",
            "gba->memory.activeRegion = -1;",
            "gba->cpu->memory.setActiveRegion(gba->cpu, gba->cpu->gprs[ARM_PC]);",
            "if (state->biosPrefetch)",
            "GBAVideoDeserialize(&gba->video, state);",
            "GBAMemoryDeserialize(&gba->memory, state);",
            "GBAIODeserialize(gba, state);",
            "GBAAudioDeserialize(&gba->audio, state);",
            "GBASavedataDeserialize(&gba->memory.savedata, state);",
            "if (gba->memory.matrix.size) {",
            "GBAMatrixDeserialize(gba, state);",
            "mTimingInterrupt(&gba->timing);",
            "return true;")
    require(re.search(r'if \(gba->memory.matrix.size\)\s*\{\s*GBAMatrixDeserialize\(gba, state\);\s*\}', restore),
            "matrix restore conditional changed")

    memrestore = section(memory, "void GBAMemoryDeserialize(",
                         "void _pristineCow(")
    ordered(memrestore,
            "memcpy(memory->wram, state->wram, GBA_SIZE_EWRAM);",
            "memcpy(memory->iwram, state->iwram, GBA_SIZE_IWRAM);")
    remap = section(matrix, "static void _remapMatrix(",
                    "void GBAMatrixReset(")
    ordered(remap,
            "if (gba->memory.matrix.vaddr & 0xFFFFE1FF)",
            "if (gba->memory.matrix.size & 0xFFFFE1FF)",
            "if ((gba->memory.matrix.vaddr + gba->memory.matrix.size - 1) & 0xFFFFE000)",
            "gba->romVf->seek(gba->romVf, gba->memory.matrix.paddr, SEEK_SET);",
            "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], gba->memory.matrix.size);")
    # The source does not inspect the seek/read results in this function.
    require(not re.search(r'if\s*\(\s*gba->romVf->(?:seek|read)', remap),
            "Matrix remap I/O return-value contract changed")
    matrix_restore = section(matrix, "void GBAMatrixDeserialize(")
    ordered(matrix_restore,
            "gba->memory.matrix.size = 0x200;",
            "for (i = 0; i < 16; ++i)",
            "LOAD_32(gba->memory.matrix.mappings[i], i << 2, state->matrix2.mappings);",
            "gba->memory.matrix.paddr = gba->memory.matrix.mappings[i];",
            "gba->memory.matrix.vaddr = i << 9;",
            "_remapMatrix(gba);",
            "LOAD_32(gba->memory.matrix.cmd, 0, &state->matrix.cmd);",
            "LOAD_32(gba->memory.matrix.size, 0, &state->matrix.size);")
    require("gba->memory.matrix.paddr = value & 0x03FFFFFF;" in matrix,
            "Matrix physical bank address mask changed")

    ordered(reload, "REG_IME = 0;", "RegisterRamReset(RESET_EWRAM);",
            "REG_IME = imeBackup;", "SetSaveBlocksPointers();",
            "LoadGameSave(SAVE_NORMAL);",
            "SetMainCallback2(CB2_ContinueSavedGame);")
    return {
        **banking_contract(mg),
        "savestate_bytes": 0x61000,
        "rom_crc_mismatch": "warning_only",
        "rom_identity_mismatch": "hard_reject",
        "rom_pc_size_guard": "conditional_hard_reject",
        "unlicensed_cart_remap": "before_pipeline_reselection",
        "matrix_restore": "after_memory_and_pipeline_restore_when_size_nonzero",
        "matrix_mapping_slots": 16,
        "matrix_physical_address_mask": "0x03FFFFFF",
        "matrix_remap_io_result_checked_locally": False,
        "firered_reload": "EWRAM_only_not_emulator_savestate_restore",
        "runtime_or_editor_certification": False,
    }


def pinned(root, commit, blobs):
    root = root.resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args],
                                       text=True, stderr=subprocess.PIPE).strip()
    require(git("rev-parse", "HEAD") == commit, "upstream commit drift: " + str(root))
    sources = {}
    for path, expected in blobs.items():
        require((root / path).is_file(), "missing pinned file: " + path)
        require(git("hash-object", path) == expected, "Git blob drift: " + path)
        sources[path] = (root / path).read_text(encoding="utf-8")
    return sources


def mutation_checks(fr, mg):
    cases = [
        ("mg", "src/gba/serialize.c", "GBASavestateVersion = 0x0000000B;", "GBASavestateVersion = 0x0000000C;"),
        ("mg", "include/mgba/internal/gba/serialize.h", "== 0x61000", "== 0x62000"),
        ("mg", "include/mgba/internal/gba/cart/matrix.h", "GBA_MATRIX_MAPPINGS_MAX 16", "GBA_MATRIX_MAPPINGS_MAX 8"),
        ("mg", "src/gba/serialize.c", "Savestate is for a different version of the game", "Savestate CRC mismatch ignored"),
        ("mg", "src/gba/serialize.c", 'mLOG(GBA_STATE, WARN, "Savestate is for a different game");\n\t\t\terror = true;', 'mLOG(GBA_STATE, WARN, "Savestate is for a different game");'),
        ("mg", "src/gba/serialize.c", "Savestate created using a differently sized version of the ROM", "ROM size unverified"),
        ("mg", "src/gba/serialize.c", "GBAUnlCartDeserialize(gba, state);\n\tgba->memory.activeRegion = -1;", "gba->memory.activeRegion = -1;\n\tGBAUnlCartDeserialize(gba, state);"),
        ("mg", "src/gba/serialize.c", "GBAMemoryDeserialize(&gba->memory, state);", "GBAMemorySerialize(&gba->memory, state);"),
        ("mg", "src/gba/serialize.c", "if (gba->memory.matrix.size) {\n\t\tGBAMatrixDeserialize(gba, state);", "if (false) {\n\t\tGBAMatrixDeserialize(gba, state);"),
        ("mg", "src/gba/memory.c", "memcpy(memory->iwram, state->iwram, GBA_SIZE_IWRAM);", "memcpy(memory->iwram, state->iwram, GBA_SIZE_IWRAM - 0x200);"),
        ("mg", "src/gba/cart/matrix.c", "gba->memory.matrix.paddr = value & 0x03FFFFFF;", "gba->memory.matrix.paddr = value;"),
        ("mg", "src/gba/cart/matrix.c", "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], gba->memory.matrix.size);", "gba->romVf->read(gba->romVf, &gba->memory.rom[gba->memory.matrix.vaddr >> 2], gba->memory.matrix.size - 1);"),
        ("mg", "src/gba/cart/matrix.c", "gba->memory.matrix.size = 0x200;", "gba->memory.matrix.size = 0x400;"),
        ("fr", "src/reset_save_heap.c", "RegisterRamReset(RESET_EWRAM);", "RegisterRamReset(RESET_ALL);"),
        ("mg", "src/gba/gba.c", "if (gba->pristineRomSize > GBA_SIZE_ROM0) {", "if (gba->pristineRomSize >= GBA_SIZE_ROM0) {"),
        ("mg", "src/gba/gba.c", "if (ident == 'M') {", "if (ident == 'N') {"),
        ("mg", "src/gba/gba.c", "gba->memory.romSize = 0x01000000;", "gba->memory.romSize = 0x02000000;"),
        ("mg", "src/gba/gba.c", "gba->romCrc32 = doCrc32(gba->memory.rom, gba->pristineRomSize);", "gba->romCrc32 = 0;"),
        ("mg", "src/gba/memory.c", "memset(&gba->memory.matrix, 0, sizeof(gba->memory.matrix));", "/* Matrix reset omitted */"),
        ("mg", "src/gba/cart/matrix.c", "gba->memory.matrix.paddr = 0x200;", "gba->memory.matrix.paddr = 0x400;"),
        ("mg", "include/mgba/internal/gba/memory.h", "GBA_SIZE_ROM0 = 0x02000000,", "GBA_SIZE_ROM0 = 0x04000000,"),
        ("mg", "include/mgba-util/vfs.h", "ssize_t (*size)(struct VFile* vf);", "void (*size)(struct VFile* vf);"),
        ("mg", "src/util/vfs/vfs-mem.c", "size = vfm->size - vfm->offset;", "size = size;"),
        ("mg", "src/util/vfs/vfs-fd.c", "return read(vfd->fd, buffer, size);", "return size;"),
        ("mg", "src/util/vfs/vfs-file.c", "return fread(buffer, 1, size, vff->file);", "return size;"),
    ]
    for index, (which, path, before, after) in enumerate(cases, 1):
        src = fr if which == "fr" else mg
        require(before in src[path], f"mutation {index} fixture missing: {path}")
        modified = dict(src)
        modified[path] = src[path].replace(before, after, 1)
        try:
            contract(modified, mg) if which == "fr" else contract(fr, modified)
        except RuntimeError:
            continue
        raise RuntimeError(f"mutation {index} incorrectly accepted: {path}")
    return len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--mgba", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    fr = pinned(args.firered, FR_PIN, FR_BLOBS)
    mg = pinned(args.mgba, MG_PIN, MG_BLOBS)
    facts = contract(fr, mg)
    negatives = mutation_checks(fr, mg)
    evidence = {
        "class": "PINNED_FIRERED_MGBA_SAVESTATE_MAPPING_SOURCE_ONLY",
        "firered_commit": FR_PIN, "firered_blobs": FR_BLOBS,
        "mgba_commit": MG_PIN, "mgba_blobs": MG_BLOBS,
        "facts": facts, "negative_controls_passed": negatives,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unverified": [
            "compiled savestate ABI under all supported variants",
            "ROM bank content identity and Matrix VFile read bounds",
            "Matrix opt-in by ROM header, CRC provenance and VFile short-read runtime effects",
            "pipeline and prefetch behaviour after Matrix restore",
            "save corruption and alternate BIOS/runtime execution",
            "editor round-trip and independent whole-file reviews",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"PINNED_MGBA_SAVESTATE_MAPPING_SOURCE_PASS negative_controls={negatives}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()

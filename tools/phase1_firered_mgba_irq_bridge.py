#!/usr/bin/env python3
"""Pinned FireRed <-> mGBA boot/IRQ vector and SWI RAM-reset dependency.

Cross-repository source evidence only; no hardware BIOS or runtime claim.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MGBA_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FIRERED_BLOBS = {
    "src/crt0.s": "a0d8a4b55237b38afc5b69d4e9aad0c2df232e14",
    "src/main.c": "542b0f5d16dd93107523d11163bfcb70a42b707a",
    "include/gba/defines.h": "5521e942c00cc2c263b842ae7608dfb7ac881a76",
}
MGBA_BLOBS = {
    "src/gba/bios.c": "edb21e2d4b02d90907f1a9b3f8f08e1bafdd3a5b",
    "src/gba/hle-bios.s": "eccbaa1433ee8316269a669109689f7fa44b941c",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "include/mgba/internal/gba/memory.h": "0aad912613e726560d06bbdbf6061986e69e5842",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def contract(fr, mg):
    crt, main, defines = (fr[x] for x in FIRERED_BLOBS)
    bios, hle, mem, memh = (mg[x] for x in MGBA_BLOBS)

    require("#define INTR_VECTOR    (*(void **)0x3007FFC)" in defines,
            "FireRed IRQ vector address drift")
    require(re.search(
        r"(?s)ldr r1, =INTR_VECTOR\s*adr r0, intr_main\s*str r0, \[r1\]",
        crt), "FireRed early IRQ vector source drift")
    require("DmaCopy32(3, intr_main, IntrMain_Buffer, sizeof(IntrMain_Buffer));"
            in main and "INTR_VECTOR = IntrMain_Buffer;" in main,
            "FireRed later IRQ vector relocation drift")
    require("RegisterRamReset(RESET_ALL & ~RESET_IWRAM);" in main
            and "#0xFC" in main and "#0x7" in main,
            "FireRed modern RAM clear path drift")

    require(re.search(r"(?m)^\s*GBA_SIZE_IWRAM\s*=\s*0x00008000,\s*$",
                      memh), "mGBA IWRAM aperture drift")
    require(re.search(
        r"(?s)static void _RegisterRamReset\(struct GBA\* gba\)\s*\{.*?"
        r"if \(registers & 0x02\)\s*\{\s*"
        r"memset\(gba->memory.iwram, 0, GBA_SIZE_IWRAM - 0x200\);\s*\}",
        bios), "mGBA SWI IWRAM clear/reserved-tail drift")
    swi = bios[bios.index("void GBASwi16("):]
    require(re.search(
        r"(?s)if \(gba->memory.fullBios\)\s*\{\s*"
        r"ARMRaiseSWI\(cpu\);\s*return;\s*\}.*?"
        r"case GBA_SWI_REGISTER_RAM_RESET:\s*"
        r"_RegisterRamReset\(gba\);\s*break;",
        swi), "mGBA full-BIOS versus HLE SWI dispatch drift")
    require(re.search(
        r"(?s)irqBase:\s*stmfd.*?mov\s+r0, #0x04000000\s*"
        r"add\s+lr, pc, #0\s*ldr\s+pc, \[r0, #-4\]",
        hle), "mGBA HLE IRQ trampoline address drift")
    require(re.search(r"(?m)^@ Unimplemented\s*\nRegisterRamReset:", hle),
            "mGBA HLE assembly stub status drift")
    require("#define LOAD_IWRAM LOAD_32(value, address & (GBA_SIZE_IWRAM - 4), memory->iwram);" in mem,
            "mGBA mirrored IWRAM 32-bit load mask drift")
    require(re.search(r"(?s)case GBA_REGION_IWRAM:\s*LOAD_IWRAM;\s*break;",
                      mem), "mGBA IWRAM 32-bit read dispatch drift")
    require(re.search(
        r"(?s)void GBAMemoryReset\(struct GBA\* gba\)\s*\{.*?"
        r"if \(gba->memory.iwram\)\s*\{\s*"
        r"memset\(gba->memory.iwram, 0, GBA_SIZE_IWRAM\);\s*\}",
        mem), "mGBA full machine reset IWRAM clearing drift")

    vector = 0x03007FFC
    bios_irq_load = 0x04000000 - 4
    iwram_mask = 0x8000 - 4
    require((bios_irq_load & iwram_mask) == (vector & iwram_mask) == 0x7FFC,
            "IRQ trampoline and FireRed vector no longer alias")
    return {
        "firered_vector_slot": "0x03007FFC",
        "mgba_hle_irq_trampoline_load": "0x03FFFFFC",
        "mgba_iwram_masked_word_offset": "0x7FFC",
        "mgba_hle_swi_reset_iwram_bytes_cleared": 0x7E00,
        "mgba_hle_swi_reserved_tail_bytes": 0x200,
        "mgba_machine_reset_iwram_bytes_cleared": 0x8000,
        "mgba_real_bios_uses_separate_swi_path": True,
        "native_runtime_or_real_bios_proof": False,
    }


def read_pinned(root, pin, blobs):
    root = root.resolve()

    def git(*parts):
        return subprocess.check_output(
            ["git", "-C", str(root), *parts], text=True,
            stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == pin, "upstream revision drift: " + str(root))
    files = {}
    for path, sha in blobs.items():
        require((root / path).is_file() and git("hash-object", path) == sha,
                "upstream Git blob drift: " + str(root) + ":" + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--firered", type=Path, required=True)
    parser.add_argument("--mgba", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fr = read_pinned(args.firered, FIRERED_PIN, FIRERED_BLOBS)
    mg = read_pinned(args.mgba, MGBA_PIN, MGBA_BLOBS)
    facts = contract(fr, mg)

    mutations = [
        ("fr", "include/gba/defines.h", "0x3007FFC", "0x3007FF8"),
        ("fr", "src/crt0.s", "adr r0, intr_main", "adr r0, AgbMain"),
        ("fr", "src/main.c", "INTR_VECTOR = IntrMain_Buffer;",
         "INTR_VECTOR = intr_main;"),
        ("mg", "src/gba/bios.c", "GBA_SIZE_IWRAM - 0x200",
         "GBA_SIZE_IWRAM"),
        ("mg", "src/gba/bios.c", "if (gba->memory.fullBios)",
         "if (!gba->memory.fullBios)"),
        ("mg", "src/gba/hle-bios.s", "ldr    pc, [r0, #-4]",
         "ldr    pc, [r0, #-8]"),
        ("mg", "src/gba/memory.c", "address & (GBA_SIZE_IWRAM - 4)",
         "address & (GBA_SIZE_IWRAM - 8)"),
        ("mg", "src/gba/memory.c", "memset(gba->memory.iwram, 0, GBA_SIZE_IWRAM);",
         "memset(gba->memory.iwram, 0, GBA_SIZE_IWRAM - 0x200);"),
        ("mg", "include/mgba/internal/gba/memory.h", "GBA_SIZE_IWRAM = 0x00008000",
         "GBA_SIZE_IWRAM = 0x00010000"),
    ]
    for n, (which, path, before, after) in enumerate(mutations, 1):
        source = fr if which == "fr" else mg
        require(before in source[path], f"negative fixture missing {n}: {path}")
        altered = dict(source)
        altered[path] = source[path].replace(before, after, 1)
        try:
            contract(altered, mg) if which == "fr" else contract(fr, altered)
        except RuntimeError:
            continue
        raise RuntimeError(f"negative fixture accepted {n}: {path}")

    result = {
        "evidence_class": "PINNED_CROSS_REPO_FIRERED_MGBA_IRQ_RESET_SOURCE_ONLY",
        "firered_commit": FIRERED_PIN,
        "mgba_commit": MGBA_PIN,
        "firered_blobs": FIRERED_BLOBS,
        "mgba_blobs": MGBA_BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unresolved": [
            "Real BIOS and HLE execution paths on hardware and emulator",
            "Actual compiled IRQ handler addresses, DMA copy and interrupt timing",
            "ROM bank remap and prefetch coherence under live IRQ/DMA",
            "Editor interoperability and independent semantic file approvals",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"PINNED_FIRERED_MGBA_IRQ_BRIDGE_PASS negative_controls={len(mutations)}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()

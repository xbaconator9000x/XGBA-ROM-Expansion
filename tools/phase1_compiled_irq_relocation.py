#!/usr/bin/env python3
"""Compiled FireRed IRQ-copy relocation proof for two immutable build variants.

Inspects actual linked ELFs and crt0 objects; no ROM, emulator or XGBA runtime
claim. Source blobs and commit are checked before interpreting compiler output.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/crt0.s": "a0d8a4b55237b38afc5b69d4e9aad0c2df232e14",
    "src/main.c": "542b0f5d16dd93107523d11163bfcb70a42b707a",
    "include/gba/defines.h": "5521e942c00cc2c263b842ae7608dfb7ac881a76",
}
VARIANTS = {
    "original_agbcc": ("pokefirered.elf", "build/firered/src/crt0.o"),
    "modern_gcc": ("pokefirered_modern.elf", "build/firered_modern/src/crt0.o"),
}
COPY_BYTES = 0x200 * 4
# Pinned src/main.c: 14 gIntrTableTemplate entries, one 32-bit IntrFunc each.
INTR_TABLE_BYTES = 14 * 4
IWRAM_TOP_RESERVED_START = 0x03007E00


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def cmd(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE)


def nm_symbols(path):
    found = {}
    for line in cmd("arm-none-eabi-nm", "-S", "--defined-only", str(path)).splitlines():
        match = re.fullmatch(
            r"([0-9a-fA-F]+)\s+(?:([0-9a-fA-F]+)\s+)?([a-zA-Z])\s+(\S+)",
            line.strip())
        if match:
            addr, size, typ, name = match.groups()
            found.setdefault(name, []).append({
                "address": int(addr, 16),
                "size": int(size, 16) if size else None,
                "type": typ,
            })
    return found


def unique(symbols, name):
    matches = symbols.get(name, [])
    require(len(matches) == 1, "missing or ambiguous compiled symbol: " + name)
    return matches[0]


def text_section_size(obj):
    listing = cmd("arm-none-eabi-readelf", "-SW", str(obj))
    sizes = re.findall(
        r"(?m)^\s*\[\s*\d+\]\s+\.text\s+PROGBITS\s+"
        r"[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)\s+",
        listing)
    require(len(sizes) == 1, "crt0 object .text extent ambiguous")
    return int(sizes[0], 16)


def verify_layout(irq_rom, buffer_ram, table_ram, obj_irq_offset,
                  obj_text_bytes, compiled_buffer_bytes, compiled_table_bytes):
    require(0x08000000 <= irq_rom < 0x0A000000,
            "linked IRQ source not in native ROM")
    require(irq_rom % 4 == 0 and irq_rom + COPY_BYTES <= 0x0A000000,
            "ROM IRQ copy window invalid")
    require(0x03000000 <= buffer_ram < IWRAM_TOP_RESERVED_START
            and buffer_ram % 4 == 0
            and buffer_ram + COPY_BYTES <= IWRAM_TOP_RESERVED_START,
            "IRQ destination overlaps IWRAM reserved tail or outside IWRAM")
    require(0x03000000 <= table_ram < 0x03008000 and table_ram % 4 == 0,
            "compiled IRQ callback table not in IWRAM")
    require(compiled_buffer_bytes == COPY_BYTES,
            "compiled IRQ buffer extent differs from 0x200 words")
    require(compiled_table_bytes == INTR_TABLE_BYTES,
            "compiled IRQ callback table extent differs from 14 pointers")
    require(table_ram + compiled_table_bytes <= IWRAM_TOP_RESERVED_START,
            "IRQ callback table overlaps reserved IWRAM tail")
    require(buffer_ram + COPY_BYTES <= table_ram
            or table_ram + compiled_table_bytes <= buffer_ram,
            "copied IRQ code overlaps callback table")
    require(0 <= obj_irq_offset < obj_text_bytes
            and 0 < obj_text_bytes - obj_irq_offset <= COPY_BYTES,
            "crt0 IRQ code plus trailing literal pool exceeds DMA copy")
    return {
        "rom_handler_address": f"0x{irq_rom:08X}",
        "iwram_copy_address": f"0x{buffer_ram:08X}",
        "iwram_callback_table_address": f"0x{table_ram:08X}",
        "copy_bytes": COPY_BYTES,
        "callback_table_bytes": compiled_table_bytes,
        "callback_table_end": f"0x{table_ram + compiled_table_bytes:08X}",
        "crt0_object_irq_offset": obj_irq_offset,
        "crt0_object_text_bytes": obj_text_bytes,
        "crt0_irq_through_text_end_bytes": obj_text_bytes - obj_irq_offset,
        "iwram_reserved_tail_starts": f"0x{IWRAM_TOP_RESERVED_START:08X}",
    }


def negative_controls():
    normal = (0x08000100, 0x03001000, 0x03002000, 0x40, 0x200, COPY_BYTES, INTR_TABLE_BYTES)
    verify_layout(*normal)
    cases = [
        (0x0A000000, *normal[1:]),
        (normal[0], 0x03007D00, *normal[2:]),
        (normal[0], normal[1], 0x08000000, *normal[3:]),
        (*normal[:4], 0x841, *normal[5:]),
        (*normal[:5], 0x400, *normal[6:]),
        (*normal[:3], normal[4], normal[4], normal[5], normal[6]),
        (*normal[:2], normal[1] + 0x10, *normal[3:]),
        (normal[0], normal[2] - 0x10, *normal[2:]),
        (*normal[:2], 0x03007DF0, *normal[3:]),
        (*normal[:6], INTR_TABLE_BYTES - 4),
    ]
    for number, candidate in enumerate(cases, 1):
        try:
            verify_layout(*candidate)
        except RuntimeError:
            continue
        raise RuntimeError(f"negative fixture {number} unexpectedly accepted")
    return len(cases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=Path("upstream/pokefirered"))
    ap.add_argument("--output", type=Path,
                    default=Path("firered-variant-evidence/compiled_irq_relocation.json"))
    args = ap.parse_args()
    root = args.source.resolve()
    require(cmd("git", "-C", str(root), "rev-parse", "HEAD").strip() == PIN,
            "upstream FireRed revision drift")
    for path, expected in BLOBS.items():
        require(cmd("git", "-C", str(root), "hash-object", path).strip() == expected,
                "pinned FireRed blob drift: " + path)
    crt = (root / "src/crt0.s").read_text()
    main_src = (root / "src/main.c").read_text()
    defines = (root / "include/gba/defines.h").read_text()
    require("ldr r1, =gIntrTable" in crt and "ldr r0, =gSTWIStatus" in crt
            and "intr_return:" in crt and ".pool" in crt,
            "IRQ callback/literal pool source dependency drift")
    require("DmaCopy32(3, intr_main, IntrMain_Buffer, sizeof(IntrMain_Buffer));"
            in main_src and "INTR_VECTOR = IntrMain_Buffer;" in main_src
            and "COMMON_DATA u32 IntrMain_Buffer[0x200]" in main_src,
            "IRQ relocation source contract drift")
    require("#define INTR_VECTOR    (*(void **)0x3007FFC)" in defines,
            "IRQ vector address drift")

    result = {}
    for variant, (elf_name, obj_name) in VARIANTS.items():
        elf, obj = root / elf_name, root / obj_name
        require(elf.is_file() and obj.is_file(),
                "missing actual compiler output: " + variant)
        syms = nm_symbols(elf)
        obj_syms = nm_symbols(obj)
        irq = unique(syms, "intr_main")
        buffer = unique(syms, "IntrMain_Buffer")
        table = unique(syms, "gIntrTable")
        obj_irq = unique(obj_syms, "intr_main")
        require(irq["type"].upper() == "T" and obj_irq["type"].upper() == "T",
                "IRQ handler not compiled as text")
        require(buffer["size"] is not None and table["size"] is not None,
                "compiler did not expose IRQ buffer/table size")
        relocations = cmd("arm-none-eabi-readelf", "-rW", str(obj))
        for external in ("AgbMain", "gIntrTable", "gSTWIStatus"):
            require(re.search(r"\b" + external + r"\b", relocations) is not None,
                    "crt0 external relocation missing: " + external)
        layout = verify_layout(
            irq["address"], buffer["address"], table["address"],
            obj_irq["address"], text_section_size(obj), buffer["size"],
            table["size"])
        layout.update({
            "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "crt0_object_sha256": hashlib.sha256(obj.read_bytes()).hexdigest(),
            "crt0_external_relocations": ["AgbMain", "gIntrTable", "gSTWIStatus"],
            "irq_symbol_type": irq["type"],
            "buffer_symbol_type": buffer["type"],
        })
        result[variant] = layout
    controls = negative_controls()
    output = {
        "evidence_class": "COMPILED_PINNED_FIRERED_IRQ_COPY_AND_LITERAL_POOL_EXTENT",
        "pinned_fire_red_commit": PIN,
        "source_blobs": BLOBS,
        "compiled_variants": result,
        "negative_controls_passed": controls,
        "not_proved": [
            "Executing copied IRQ handler or measuring DMA timing",
            "ROM bank remap/pre-fetch coherence and BIOS execution",
            "Any other FireRed revision, linker variant or custom ROM",
            "Editor round trip, independent whole-file semantic approval",
        ],
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"PINNED_COMPILED_IRQ_RELOCATION_PASS variants={len(result)} negative_controls={controls}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()

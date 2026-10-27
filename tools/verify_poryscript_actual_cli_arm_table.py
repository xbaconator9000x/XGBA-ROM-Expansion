#!/usr/bin/env python3
"""Phase 1: compile ACTUAL pinned Poryscript CLI output with pinned FireRed macros.

Only a synthetic .pory input is used. The emitted assembly is not rewritten.
This is GNU ARM assembler/linker evidence, not FireRed ROM/runtime evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

PS_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"
FR_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PS_BLOBS = {
    "main.go": "10db05ef1518460da78b0bd41f22bb091917a385",
    "emitter/emitter.go": "d35843ef29929ead47351646d7a33dd5c692b850",
    "emitter/emitter_test.go": "4c3209166937384a0dc26fc83a0341a5dac48ca5",
}
FR_BLOBS = {
    "asm/macros/map.inc": "83ef472c926ce767c9133ab9bd6922280b38bb2d",
    "src/script.c": "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
}
BASE = 0x08000000
PORY = """mapscripts XGBA_MapScripts {
    MAP_SCRIPT_ON_TRANSITION: XGBA_Transition
    MAP_SCRIPT_ON_FRAME_TABLE [
        0x4000, 0x1234: XGBA_A
        0x4001, 0x1235: XGBA_B
    ]
}
raw \`
XGBA_Transition:
    .byte 0x02
XGBA_A:
    .byte 0x03
XGBA_B:
    .byte 0x04
\`
"""
# Two 5-byte outer entries + one-byte sentinel; two 8-byte conditional
# records + two-byte sentinel; three raw one-byte script placeholders.
EXPECTED_RAW = bytes.fromhex(
    "03 1d 00 00 00 02 0b 00 00 00 00 "
    "00 40 34 12 1e 00 00 00 01 40 35 12 1f 00 00 00 "
    "00 00 02 03 04"
)
EXPECTED_LINKED = bytes.fromhex(
    "03 1d 00 00 08 02 0b 00 00 08 00 "
    "00 40 34 12 1e 00 00 08 01 40 35 12 1f 00 00 08 "
    "00 00 02 03 04"
)
RELOC_OFFSETS = (1, 6, 15, 23)


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def call(argv: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(argv, cwd=cwd, text=True, stderr=subprocess.PIPE)


def pin(root: Path, revision: str, blobs: dict[str, str]) -> dict[str, str]:
    require(call(["git", "-C", str(root), "rev-parse", "HEAD"]).strip() == revision,
            "upstream revision mismatch: " + str(root))
    sources = {}
    for path, expected in blobs.items():
        require(call(["git", "-C", str(root), "hash-object", path]).strip() == expected,
                "upstream blob mismatch: " + path)
        sources[path] = (root / path).read_text(encoding="utf-8")
    return sources


def macro(source: str, name: str) -> str:
    needle = "\t.macro " + name + " "
    start = source.find(needle)
    require(start >= 0, "missing native macro " + name)
    end = source.find("\t.endm", start)
    require(end > start, "unterminated native macro " + name)
    return source[start:end + len("\t.endm")]


def elf_section(blob: bytes, name: str) -> tuple[tuple[int, ...], bytes]:
    require(blob[:4] == b"\x7fELF" and blob[4:6] == b"\x01\x01",
            "expected little-endian ELF32")
    offset = struct.unpack_from("<I", blob, 32)[0]
    size, count, string_index = struct.unpack_from("<HHH", blob, 46)
    require(size >= 40 and string_index < count, "bad ELF section table")
    headers = [struct.unpack_from("<IIIIIIIIII", blob, offset + i * size)
               for i in range(count)]
    string_header = headers[string_index]
    strings = blob[string_header[4]:string_header[4] + string_header[5]]
    for h in headers:
        end = strings.find(b"\0", h[0])
        if end >= 0 and strings[h[0]:end].decode("ascii") == name:
            return h, blob[h[4]:h[4] + h[5]]
    raise ValueError("missing ELF section: " + name)


def compile_assembly(assembly: str, root: Path) -> dict:
    asm, obj, linked = (root / "fixture.s", root / "fixture.o", root / "fixture.elf")
    asm.write_text(assembly, encoding="utf-8")
    call(["arm-none-eabi-as", "-mcpu=arm7tdmi", "-o", str(obj), str(asm)])
    call(["arm-none-eabi-ld", "--section-start=.rodata=0x08000000",
          "-e", "XGBA_MapScripts", "-o", str(linked), str(obj)])
    object_data = obj.read_bytes()
    rel_header, rel_bytes = elf_section(object_data, ".rel.rodata")
    require(rel_header[9] == 8 and len(rel_bytes) % 8 == 0, "invalid REL table")
    relocations = [struct.unpack_from("<II", rel_bytes, i)
                   for i in range(0, len(rel_bytes), 8)]
    linked_header, linked_bytes = elf_section(linked.read_bytes(), ".rodata")
    return {
        "raw": elf_section(object_data, ".rodata")[1],
        "linked": linked_bytes,
        "linked_address": linked_header[3],
        "relocations": relocations,
    }


def validate(result: dict) -> None:
    require(result["raw"] == EXPECTED_RAW, "actual CLI unlinked bytes differ")
    require(result["linked"] == EXPECTED_LINKED, "actual CLI linked bytes differ")
    require(result["linked_address"] == BASE, "link address differs")
    relocs = result["relocations"]
    require(tuple(off for off, _ in relocs) == RELOC_OFFSETS,
            "unexpected relocation positions")
    require(all((info & 0xff) == 2 for _, info in relocs),
            "expected four R_ARM_ABS32 relocations")
    require([int.from_bytes(result["linked"][off:off + 4], "little")
             for off in RELOC_OFFSETS] == [BASE + 29, BASE + 11, BASE + 30, BASE + 31],
            "linked pointers target unexpected labels")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poryscript", required=True, type=Path)
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    ps, fr = args.poryscript.resolve(), args.firered.resolve()
    psrc, fsrc = pin(ps, PS_PIN, PS_BLOBS), pin(fr, FR_PIN, FR_BLOBS)
    require("func TestEmitMapScripts(" in psrc["emitter/emitter_test.go"],
            "pinned producer test missing")
    require("mapScripts += 5;" in fsrc["src/script.c"] and
            "varIndex1 = T1_READ_16(ptr);" in fsrc["src/script.c"],
            "FireRed reader stride/conditional semantics drifted")
    for tool in ("go", "arm-none-eabi-as", "arm-none-eabi-ld"):
        require(shutil.which(tool) is not None, "missing build tool: " + tool)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fixture = root / "input.pory"
        fixture.write_text(PORY, encoding="utf-8")
        exe = root / "poryscript"
        call(["go", "build", "-o", str(exe), "."], cwd=ps)
        outputs = []
        for optimized in (True, False):
            emitted = call([str(exe), "-cc", "", "-fc", "", "-lm=false",
                            "-optimize=" + str(optimized).lower(), "-i", str(fixture)],
                           cwd=ps)
            outputs.append(emitted)
        require(outputs[0] == outputs[1],
                "optimization changed the simple map-table fixture; review variants separately")
        emitted = outputs[0]
        anchors = [
            "XGBA_MapScripts::",
            "\tmap_script MAP_SCRIPT_ON_TRANSITION, XGBA_Transition",
            "\tmap_script MAP_SCRIPT_ON_FRAME_TABLE, XGBA_MapScripts_MAP_SCRIPT_ON_FRAME_TABLE",
            "\t.byte 0",
            "XGBA_MapScripts_MAP_SCRIPT_ON_FRAME_TABLE:",
            "\tmap_script_2 0x4000, 0x1234, XGBA_A",
            "\tmap_script_2 0x4001, 0x1235, XGBA_B",
            "\t.2byte 0",
            "XGBA_Transition:",
            "XGBA_A:",
            "XGBA_B:",
        ]
        pos = -1
        for anchor in anchors:
            found = emitted.find(anchor, pos + 1)
            require(found > pos, "missing/reordered actual emitter anchor: " + anchor)
            pos = found
        require(emitted.count("\tmap_script ") == 2 and
                emitted.count("\tmap_script_2 ") == 2,
                "unexpected extra emitted map records")
        native = fsrc["asm/macros/map.inc"]
        preamble = "\n".join([
            ".syntax unified",
            macro(native, "map_script"),
            macro(native, "map_script_2"),
            ".equ MAP_SCRIPT_ON_TRANSITION, 3",
            ".equ MAP_SCRIPT_ON_FRAME_TABLE, 2",
            '.section .rodata,"a",%progbits',
            "",
        ])
        original = preamble + emitted
        positive = compile_assembly(original, root)
        validate(positive)
        mutations = [
            ("outer-tag", "MAP_SCRIPT_ON_TRANSITION, XGBA_Transition",
             "4, XGBA_Transition"),
            ("outer-sentinel", "\t.byte 0\n\nXGBA_MapScripts_MAP_SCRIPT_ON_FRAME_TABLE:",
             "\t.2byte 0\n\nXGBA_MapScripts_MAP_SCRIPT_ON_FRAME_TABLE:"),
            ("conditional-var", "0x4000, 0x1234, XGBA_A",
             "0x4002, 0x1234, XGBA_A"),
            ("conditional-value", "0x4001, 0x1235, XGBA_B",
             "0x4001, 0x1236, XGBA_B"),
            ("conditional-pointer", "0x4001, 0x1235, XGBA_B",
             "0x4001, 0x1235, XGBA_A"),
            ("native-pointer-width", ".4byte \\script", ".2byte \\script"),
            ("script-payload", ".byte 0x03\nXGBA_B:", ".byte 0x05\nXGBA_B:"),
        ]
        for index, (label, old, new) in enumerate(mutations):
            require(old in original, "negative control anchor missing: " + label)
            changed = original.replace(old, new, 1)
            case = root / ("mutation-" + str(index))
            case.mkdir()
            try:
                validate(compile_assembly(changed, case))
            except (ValueError, subprocess.CalledProcessError):
                continue
            raise ValueError("negative mutation escaped detection: " + label)
        result = {
            "class": "PINNED_ACTUAL_PORYSCRIPT_CLI_GNU_ARM_OBJECT_WITNESS",
            "poryscript_commit": PS_PIN,
            "firered_commit": FR_PIN,
            "poryscript_git_blobs": PS_BLOBS,
            "firered_git_blobs": FR_BLOBS,
            "input_sha256": hashlib.sha256(PORY.encode()).hexdigest(),
            "actual_cli_emitted_sha256": hashlib.sha256(emitted.encode()).hexdigest(),
            "raw_rodata_sha256": hashlib.sha256(positive["raw"]).hexdigest(),
            "linked_rodata_sha256": hashlib.sha256(positive["linked"]).hexdigest(),
            "relocation_offsets": list(RELOC_OFFSETS),
            "relocation_type": "R_ARM_ABS32",
            "optimized_and_unoptimized_equal": True,
            "negative_controls_passed": len(mutations),
            "actual_poryscript_cli_executed": True,
            "actual_pinned_fire_red_macros_used": True,
            "original_agbcc_or_stock_rom_equivalence": False,
            "mGBA_execution": False,
            "new_unique_machine_processed_files": 0,
            "new_complete_file_reviews": 0,
            "independent_approvals": 0,
            "phase1_gate": "FAIL_INCOMPLETE",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pinned Poryscript -> FireRed map-table ARM object/link witness.

The generated input is a *synthetic* emitter-shaped fixture assembled using
unmodified, exact-pinned FireRed macros. No stock ROM/runtime claim is made.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

PS_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"
FR_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PS_BLOBS = {"emitter/emitter.go": "d35843ef29929ead47351646d7a33dd5c692b850"}
FR_BLOBS = {
    "asm/macros/map.inc": "83ef472c926ce767c9133ab9bd6922280b38bb2d",
    "src/script.c": "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
    "include/constants/map_scripts.h": "1353de360cf1e00b6efbb26ec59c4822c99b59bf",
}
BASE = 0x08000000
EXPECTED_RAW = bytes.fromhex(
    "02 0b 00 00 00 03 1d 00 00 00 00 "
    "00 40 34 12 1f 00 00 00 01 40 35 12 20 00 00 00 "
    "00 00 02 00 03 04"
)
EXPECTED_LINKED = bytes.fromhex(
    "02 0b 00 00 08 03 1d 00 00 08 00 "
    "00 40 34 12 1f 00 00 08 01 40 35 12 20 00 00 08 "
    "00 00 02 00 03 04"
)
EXPECTED_RELOCS = (1, 6, 15, 23)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def pinned(root, commit, blobs):
    check(git(root, "rev-parse", "HEAD") == commit, "upstream commit differs")
    out = {}
    for path, sha in blobs.items():
        check(git(root, "hash-object", path) == sha, "upstream blob differs: " + path)
        out[path] = (root / path).read_text(encoding="utf-8")
    return out


def macro(source, name):
    needle = "\t.macro " + name + " "
    i = source.find(needle)
    check(i >= 0, "missing native macro " + name)
    end = source.find("\t.endm", i)
    check(end >= 0, "unterminated macro " + name)
    return source[i:end + len("\t.endm")]


def source_contract(ps, fr):
    emitter = ps["emitter/emitter.go"]
    native = fr["asm/macros/map.inc"]
    reader = fr["src/script.c"]
    constants = fr["include/constants/map_scripts.h"]
    anchors = [
        'sb.WriteString(fmt.Sprintf("\\tmap_script %s, %s\\n",',
        'sb.WriteString("\\t.byte 0\\n\\n")',
        'sb.WriteString(fmt.Sprintf("\\tmap_script_2 %s, %s, %s\\n",',
        'sb.WriteString("\\t.2byte 0\\n\\n")',
    ]
    check(all(a in emitter for a in anchors), "Poryscript emitter record/sentinel contract differs")
    for a in ("mapScripts += 5;", "if (*mapScripts == 0)",
              "varIndex1 = T1_READ_16(ptr);", "if (!varIndex1)",
              "varIndex2 = T1_READ_16(ptr);", "ptr += 4;"):
        check(a in reader, "FireRed reader contract differs: " + a)
    check("#define MAP_SCRIPT_ON_FRAME_TABLE          2" in constants,
          "native type-2 constant differs")
    check("#define MAP_SCRIPT_ON_TRANSITION           3" in constants,
          "native type-3 constant differs")
    return macro(native, "map_script"), macro(native, "map_script_2")


def fixture(m1, m2):
    return "\n".join([
        ".syntax unified", m1, m2,
        '.section .rodata,"a",%progbits',
        ".global xgba_script_table", "xgba_script_table:",
        "map_script 2, xgba_onframe", "map_script 3, xgba_ontransition",
        ".byte 0", "xgba_onframe:",
        "map_script_2 0x4000, 0x1234, xgba_script_a",
        "map_script_2 0x4001, 0x1235, xgba_script_b",
        ".2byte 0", "xgba_ontransition:",
        ".byte 0x02, 0x00", "xgba_script_a:",
        ".byte 0x03", "xgba_script_b:", ".byte 0x04", "",
    ])


def elf_section(blob, name):
    check(blob[:4] == b"\x7fELF" and blob[4] == 1 and blob[5] == 1,
          "not little-endian ELF32")
    e_shoff = struct.unpack_from("<I", blob, 32)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", blob, 46)
    check(e_shentsize >= 40 and e_shstrndx < e_shnum, "invalid ELF section headers")
    headers = [struct.unpack_from("<IIIIIIIIII", blob, e_shoff + i * e_shentsize)
               for i in range(e_shnum)]
    names = headers[e_shstrndx]
    strings = blob[names[4]:names[4] + names[5]]
    for h in headers:
        start = h[0]
        end = strings.find(b"\0", start)
        if end >= 0 and strings[start:end].decode("ascii") == name:
            return h, blob[h[4]:h[4] + h[5]]
    raise ValueError("missing ELF section " + name)


def run_fixture(source, directory):
    asm = directory / "fixture.s"
    obj = directory / "fixture.o"
    linked = directory / "fixture.elf"
    asm.write_text(source, encoding="utf-8")
    subprocess.run(["clang", "--target=armv4t-none-eabi", "-c", str(asm),
                    "-o", str(obj)], check=True, capture_output=True, text=True)
    subprocess.run(["ld.lld", "-flavor", "gnu", "-m", "armelf",
                    "--section-start=.rodata=0x08000000", "-e", "xgba_script_table",
                    str(obj), "-o", str(linked)], check=True,
                   capture_output=True, text=True)
    raw_object = obj.read_bytes()
    rel_hdr, rel_data = elf_section(raw_object, ".rel.rodata")
    check(rel_hdr[9] == 8 and len(rel_data) % 8 == 0,
          "unexpected ARM ELF32 REL entry size")
    relocations = [struct.unpack_from("<II", rel_data, i)
                   for i in range(0, len(rel_data), 8)]
    return {
        "raw": elf_section(raw_object, ".rodata")[1],
        "linked": elf_section(linked.read_bytes(), ".rodata"),
        "relocs": relocations,
    }


def validate(result):
    raw, (header, linked), relocations = (result["raw"], result["linked"], result["relocs"])
    check(raw == EXPECTED_RAW, "unlinked ARM table bytes differ")
    check(header[3] == BASE and linked == EXPECTED_LINKED,
          "linked ARM table bytes or address differ")
    check(tuple(offset for offset, _ in relocations) == EXPECTED_RELOCS,
          "relocation offsets differ")
    check(all(info & 0xff == 2 for _, info in relocations),
          "expected R_ARM_ABS32 relocations")
    check([int.from_bytes(linked[i:i + 4], "little") for i in EXPECTED_RELOCS]
          == [BASE + 11, BASE + 29, BASE + 31, BASE + 32],
          "linked pointers do not target expected label offsets")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poryscript", type=Path)
    parser.add_argument("--firered", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    check(shutil.which("clang") and shutil.which("ld.lld"),
          "clang and ld.lld required")
    if args.self_test:
        m1 = ".macro map_script type:req, script:req\n.byte \\type\n.4byte \\script\n.endm"
        m2 = ".macro map_script_2 var:req, compare:req, script:req\n.2byte \\var\n.2byte \\compare\n.4byte \\script\n.endm"
    else:
        check(args.poryscript and args.firered and args.output,
              "pinned upstream checkouts and output required")
        ps = pinned(args.poryscript, PS_PIN, PS_BLOBS)
        fr = pinned(args.firered, FR_PIN, FR_BLOBS)
        m1, m2 = source_contract(ps, fr)
    original = fixture(m1, m2)
    mutations = [
        ("type-3-tag", "map_script 3,", "map_script 4,"),
        ("table-terminator-width", ".byte 0\nxgba_onframe:", ".2byte 0\nxgba_onframe:"),
        ("first-var-sentinel", "map_script_2 0x4000,", "map_script_2 0,"),
        ("second-var", "map_script_2 0x4001,", "map_script_2 0x4002,"),
        ("compare-value", "0x1234, xgba_script_a", "0x1235, xgba_script_a"),
        ("table-sentinel-truncated", ".2byte 0\nxgba_ontransition:", ".byte 0\nxgba_ontransition:"),
        ("pointer-target", "0x1235, xgba_script_b", "0x1235, xgba_script_a"),
        ("script-byte", ".byte 0x03\nxgba_script_b:", ".byte 0x05\nxgba_script_b:"),
        ("native-pointer-width", ".4byte \\script", ".2byte \\script"),
    ]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        positive = run_fixture(original, root)
        validate(positive)
        for n, (label, old, new) in enumerate(mutations):
            check(old in original, "missing negative fixture " + label)
            modified = original.replace(old, new, 1)
            try:
                case = root / ("mutation" + str(n))
                case.mkdir()
                validate(run_fixture(modified, case))
            except (ValueError, subprocess.CalledProcessError):
                continue
            raise ValueError("negative fixture escaped validation: " + label)
    result = {
        "status": "PINNED_COMPILED_SYNTHETIC_WITNESS" if not args.self_test else "LOCAL_SYNTHETIC_SELF_TEST",
        "poryscript_commit": PS_PIN, "firered_commit": FR_PIN,
        "poryscript_blobs": PS_BLOBS, "firered_blobs": FR_BLOBS,
        "target": "armv4t-none-eabi", "link_address": hex(BASE),
        "unlinked_rodata_sha256": hashlib.sha256(positive["raw"]).hexdigest(),
        "linked_rodata_sha256": hashlib.sha256(positive["linked"][1]).hexdigest(),
        "relocation_offsets": list(EXPECTED_RELOCS),
        "relocation_type": "R_ARM_ABS32", "negative_controls_passed": len(mutations),
        "new_unique_machine_triaged_files": 0, "new_independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
        "not_proven": ["original_agbcc_linker_equivalence", "stock_ROM_bytes",
                       "native_GBA_or_mGBA_execution", "malformed_table_safety",
                       "lossless_source_reconstruction"],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

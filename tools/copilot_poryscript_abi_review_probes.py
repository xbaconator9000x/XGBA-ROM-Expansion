#!/usr/bin/env python3
"""Compile malformed-table probes from the pinned Poryscript CLI output."""
import argparse
import hashlib
import importlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


PORYSCRIPT_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"
FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
WITNESS_COMMIT = "587132181ef728b635968dd091b1cf171e78f753"
WITNESS_BLOB = "4a137032662f0c711fcf1aee7a0fdd6ddfa001cb"
CHARACTERS_BLOB = "d00ecf0a3afcd9fc1fa9534c00f4b74793d5f06f"
BASE = 0x08000000
RELOCATION_OFFSETS = (1, 6, 11, 16, 21, 26, 35, 45, 53, 63, 71)
LINK_TARGET_OFFSETS = (77, 78, 79, 31, 41, 59, 80, 81, 82, 83, 84)
FIXTURE = """mapscripts XGBA_MapScripts {
    MAP_SCRIPT_ON_TRANSITION: XGBA_First
    MAP_SCRIPT_ON_TRANSITION: XGBA_Second
    MAP_SCRIPT_ON_FRAME_TABLE: XGBA_Direct
    MAP_SCRIPT_ON_TRANSITION [
        0x4000, 0x1234: XGBA_MisTyped
    ]
    MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE [
        0x0000, 0x1234: XGBA_Zero
        0x4001, 0x1235: XGBA_AfterZero
    ]
    MAP_SCRIPT_ON_FRAME_TABLE [
        0x4002, 0x1236: XGBA_Valid
        0x10000, 0x1237: XGBA_Overflow
    ]
}
raw `
XGBA_First:
    .byte 0x02
XGBA_Second:
    .byte 0x03
XGBA_Direct:
    .byte 0x04
XGBA_MisTyped:
    .byte 0x05
XGBA_Zero:
    .byte 0x06
XGBA_AfterZero:
    .byte 0x07
XGBA_Valid:
    .byte 0x08
XGBA_Overflow:
    .byte 0x09
`
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def call(argv, cwd=None):
    try:
        return subprocess.check_output(
            argv, cwd=cwd, text=True, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as exc:
        print("FAILED COMMAND:", " ".join(argv), file=sys.stderr)
        print("STDERR:", exc.stderr, file=sys.stderr)
        raise


def git_blob_sha1(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest()


def pin_source(root, revision, blobs, source_files_only):
    if (root / ".git").exists():
        require(call(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
                == revision, "upstream revision mismatch: " + str(root))
        sources = {}
        for path, expected in blobs.items():
            require(call(["git", "-C", str(root), "hash-object", path]).strip()
                    == expected, "upstream file blob mismatch: " + path)
            sources[path] = (root / path).read_text(encoding="utf-8")
        return sources, "EXACT_PINNED_COMMITS_AND_BLOBS"
    require(source_files_only,
            "upstream checkout lacks .git metadata; use source-files-only only "
            "when the exact file blobs are independently available")
    sources = {}
    for path, expected in blobs.items():
        data = (root / path).read_bytes()
        require(git_blob_sha1(data) == expected,
                "upstream file blob mismatch: " + path)
        sources[path] = data.decode("utf-8")
    return sources, "FILE_BLOBS_ONLY"


def define_value(header, name):
    match = re.search(r"^#define\s+" + re.escape(name) + r"\s+([0-9]+)\b",
                      header, re.MULTILINE)
    require(match is not None, "missing pinned map-script constant: " + name)
    return int(match.group(1))


def expected_rodata(zero_operand=0, overflow_operand=0):
    outer = ((3, 77), (3, 78), (2, 79), (3, 31), (4, 41), (2, 59))
    tables = (
        ((0x4000, 0x1234, 80),),
        ((zero_operand, 0x1234, 81), (0x4001, 0x1235, 82)),
        ((0x4002, 0x1236, 83), (overflow_operand, 0x1237, 84)),
    )
    raw = bytearray()
    relocations = []
    for tag, target in outer:
        raw.append(tag)
        relocations.append(len(raw))
        raw.extend(struct.pack("<I", target))
    raw.append(0)
    for table in tables:
        for variable, comparison, target in table:
            raw.extend(struct.pack("<HH", variable, comparison))
            relocations.append(len(raw))
            raw.extend(struct.pack("<I", target))
        raw.extend(b"\0\0")
    raw.extend(bytes(range(2, 10)))
    linked = bytearray(raw)
    for offset, target in zip(relocations, LINK_TARGET_OFFSETS):
        linked[offset:offset + 4] = struct.pack("<I", BASE + target)
    return bytes(raw), bytes(linked), tuple(relocations)


def compile_fixture(emitted, preamble, root, preproc, charmap, witness,
                    zero_operand=0, overflow_operand=0):
    root.mkdir(parents=True, exist_ok=True)
    result = witness.compile_assembly(preamble + emitted, root, preproc, charmap)
    raw = result["raw"]
    linked = result["linked"]
    expected_raw, expected_linked, expected_relocations = expected_rodata(
        zero_operand, overflow_operand
    )
    require(raw == expected_raw, "compiled bytes differ from the actual CLI fixture")
    require(linked == expected_linked, "linked bytes differ from expected relocations")
    relocations = result["relocations"]
    require(tuple(offset for offset, _ in relocations) == expected_relocations
            == RELOCATION_OFFSETS,
            "unexpected unaligned relocation offsets")
    require(all((info & 0xFF) == 2 for _, info in relocations),
            "expected only R_ARM_ABS32 relocations")
    require(result["linked_address"] == BASE, "unexpected link base")
    linked_targets = [
        int.from_bytes(linked[offset:offset + 4], "little") - BASE
        for offset in RELOCATION_OFFSETS
    ]
    require(tuple(linked_targets) == LINK_TARGET_OFFSETS,
            "linked pointers target unexpected generated/authored labels")
    return result


def run_probe(poryscript_root, firered_root, witness_root,
              source_files_only=False):
    poryscript_root = poryscript_root.resolve()
    firered_root = firered_root.resolve()
    witness_root = witness_root.resolve()
    helper_path = witness_root / "tools/verify_poryscript_actual_cli_arm_table.py"
    if (witness_root / ".git").exists():
        require(call(["git", "-C", str(witness_root), "rev-parse", "HEAD"]).strip()
                == WITNESS_COMMIT, "PR #20 witness commit differs")
        witness_identity_mode = "EXACT_COMMIT_AND_BLOB"
        helper_blob = call([
            "git", "-C", str(witness_root), "hash-object", str(helper_path)
        ]).strip()
    else:
        require(source_files_only,
                "witness checkout lacks .git metadata; exact helper blob required")
        witness_identity_mode = "FILE_BLOB_ONLY"
        helper_blob = git_blob_sha1(helper_path.read_bytes())
    require(helper_blob == WITNESS_BLOB, "PR #20 witness helper blob differs")
    sys.path.insert(0, str(helper_path.parent))
    witness = importlib.import_module("verify_poryscript_actual_cli_arm_table")
    poryscript_sources, poryscript_identity_mode = pin_source(
        poryscript_root, PORYSCRIPT_PIN, witness.PS_BLOBS,
        source_files_only
    )
    firered_sources, firered_identity_mode = pin_source(
        firered_root, FIRERED_PIN, witness.FR_BLOBS, source_files_only
    )
    characters_header = firered_root / "include/characters.h"
    characters_blob = (
        call(["git", "-C", str(firered_root), "hash-object",
              str(characters_header)]).strip()
        if (firered_root / ".git").exists()
        else git_blob_sha1(characters_header.read_bytes())
    )
    require(characters_blob == CHARACTERS_BLOB,
            "pinned preprocessor dependency blob differs")
    require(poryscript_identity_mode == firered_identity_mode,
            "upstream identity verification modes differ")
    require("func TestEmitMapScripts(" in
            poryscript_sources["emitter/emitter_test.go"],
            "pinned emitter test is missing")

    for tool in ("go", "g++", "make", "arm-none-eabi-as", "arm-none-eabi-ld"):
        require(shutil.which(tool) is not None, "missing build tool: " + tool)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        fixture_path = root / "input.pory"
        fixture_path.write_text(FIXTURE, encoding="utf-8")
        executable = root / "poryscript"
        call(["go", "build", "-o", str(executable), "."], cwd=poryscript_root)
        outputs = []
        for optimize in (True, False):
            outputs.append(call([
                str(executable), "-cc", "", "-fc", "", "-lm=false",
                "-optimize=" + str(optimize).lower(), "-i", str(fixture_path),
            ], cwd=poryscript_root))
        require(outputs[0] == outputs[1],
                "optimized and unoptimized CLI output differs for this fixture")
        emitted = outputs[0]
        anchors = (
            "map_script MAP_SCRIPT_ON_TRANSITION, XGBA_First",
            "map_script MAP_SCRIPT_ON_TRANSITION, XGBA_Second",
            "map_script MAP_SCRIPT_ON_FRAME_TABLE, XGBA_Direct",
            "map_script MAP_SCRIPT_ON_TRANSITION, XGBA_MapScripts_MAP_SCRIPT_ON_TRANSITION",
            "map_script MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE, XGBA_MapScripts_MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE",
            "map_script MAP_SCRIPT_ON_FRAME_TABLE, XGBA_MapScripts_MAP_SCRIPT_ON_FRAME_TABLE",
            "map_script_2 0x0000, 0x1234, XGBA_Zero",
            "map_script_2 0x10000, 0x1237, XGBA_Overflow",
        )
        for anchor in anchors:
            require(anchor in emitted, "actual CLI output lacks: " + anchor)

        map_scripts_header = (
            firered_root / "include/constants/map_scripts.h"
        ).read_text(encoding="utf-8")
        expected_constants = {
            "MAP_SCRIPT_ON_FRAME_TABLE": 2,
            "MAP_SCRIPT_ON_TRANSITION": 3,
            "MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE": 4,
        }
        for name, value in expected_constants.items():
            require(define_value(map_scripts_header, name) == value,
                    "pinned map-script constant changed: " + name)
        native_macros = firered_sources["asm/macros/map.inc"]
        preamble = "\n".join([
            ".syntax unified",
            witness.macro(native_macros, "map_script"),
            witness.macro(native_macros, "map_script_2"),
            *(".equ %s, %d" % item for item in expected_constants.items()),
            '.section .rodata,"a",%progbits',
            "",
        ])
        call(["make", "-C", str(firered_root / "tools/preproc"), "-j2"])
        preproc = firered_root / "tools/preproc/preproc"
        require(preproc.is_file(), "pinned FireRed preprocessor did not build")
        charmap = firered_root / "charmap.txt"
        positive = compile_fixture(
            emitted, preamble, root / "positive", preproc, charmap, witness
        )

        mutations = [
            ("zero-operand", "0x0000, 0x1234: XGBA_Zero",
             "0x0001, 0x1234: XGBA_Zero", 41, b"\x01\x00"),
            ("overflow-operand", "0x10000, 0x1237: XGBA_Overflow",
             "0x10001, 0x1237: XGBA_Overflow", 67, b"\x01\x00"),
        ]
        negative_controls = {}
        for index, (name, old, new, offset, expected) in enumerate(mutations):
            require(old in FIXTURE, "mutation anchor missing: " + name)
            changed_fixture = FIXTURE.replace(old, new, 1)
            changed_path = root / (name + ".pory")
            changed_path.write_text(changed_fixture, encoding="utf-8")
            changed_output = call([
                str(executable), "-cc", "", "-fc", "", "-lm=false",
                "-optimize=false", "-i", str(changed_path),
            ], cwd=poryscript_root)
            changed = compile_fixture(
                changed_output, preamble, root / ("mutation-" + str(index)),
                preproc, charmap, witness,
                zero_operand=1 if name == "zero-operand" else 0,
                overflow_operand=1 if name == "overflow-operand" else 0,
            )
            require(changed["raw"][offset:offset + 2] == expected,
                    "negative control escaped: " + name)
            negative_controls[name] = "PASS"

        as_version = call(["arm-none-eabi-as", "--version"]).splitlines()[0]
        ld_version = call(["arm-none-eabi-ld", "--version"]).splitlines()[0]
        return {
            "status": "PASS_ACTUAL_PINNED_CLI_PREPROCESSOR_GNU_ARM_OBJECT_FIXTURE",
            "poryscript_commit": PORYSCRIPT_PIN,
            "firered_commit": FIRERED_PIN,
            "witness_commit": WITNESS_COMMIT,
            "witness_helper_blob": WITNESS_BLOB,
            "identity_verification": {
                "upstream": poryscript_identity_mode,
                "witness": witness_identity_mode,
            },
            "fixture_sha256": hashlib.sha256(FIXTURE.encode()).hexdigest(),
            "emitted_assembly_sha256": hashlib.sha256(emitted.encode()).hexdigest(),
            "unlinked_rodata_sha256": hashlib.sha256(positive["raw"]).hexdigest(),
            "linked_rodata_sha256": hashlib.sha256(positive["linked"]).hexdigest(),
            "relocation_type": "R_ARM_ABS32",
            "relocation_offsets": list(RELOCATION_OFFSETS),
            "linked_target_offsets": list(LINK_TARGET_OFFSETS),
            "outer_record_bytes": 5,
            "outer_sentinel_offset": 30,
            "conditional_record_bytes": 8,
            "conditional_sentinel_offsets": [39, 57, 75],
            "negative_controls": negative_controls,
            "optimized_equals_unoptimized": True,
            "tool_versions": {
                "go": call(["go", "version"]).strip(),
                "gnu_arm_as": as_version,
                "gnu_arm_ld": ld_version,
            },
            "execution_scope": (
                "Actual pinned Poryscript CLI output compiled with the pinned "
                "FireRed preprocessor/macros and GNU ARM assembler/linker; "
                "synthetic input fixture only."
            ),
            "not_proven": [
                "FireRed C consumer execution or malformed-table memory safety",
                "full pinned FireRed ROM build or Poryscript integration into that build",
                "mGBA runtime or original stock gameplay",
            ],
            "approval_count_changed": False,
            "phase1_gate": "FAIL_INCOMPLETE",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poryscript-root", required=True, type=Path)
    parser.add_argument("--firered-root", required=True, type=Path)
    parser.add_argument("--witness-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-files-only", action="store_true")
    args = parser.parse_args()
    result = run_probe(
        args.poryscript_root, args.firered_root, args.witness_root,
        args.source_files_only
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

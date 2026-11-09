#!/usr/bin/env python3
"""Reproduce the conditional Braille scroll-table bounds witness on a host."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SOURCE_BLOB = "d4afdf87f19a5b3345dd561d0cd1360683b30a6a"
SOURCE_SHA256 = "def45ae49f0e1666908c39e5ddd0f63f57cf834d8e23e779cb756e5e9b161c03"
ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
ARCHIVE_ROW_SHA256 = "56061998283611826e1ced1922b932d8a8d40d4ad597348648aedc22483bb134"
DOSSIER_SHA256 = "dcda24274c44df7a6d4ed2e984667b1ddf2f7b3349b7d9b9a572edcdc26a56e9"
HANDOFF = ROOT / "docs/phase1-review-readiness/firered-braille-runtime-consumer-handoff-20261109.json"
ARCHIVE = ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
TEST_C = ROOT / "tests/phase1_firered_braille_host.c"
STUB_INCLUDE = ROOT / "tests/phase1_firered_braille_host_stubs/include"

DEPENDENCIES = {
    "src/new_game.c": (
        "3768b3ccb98cdad514b858cbc59244f21bedb7b0",
        "55f03492ea90ee853550a40008089d44ca59c28cb47b8aa10aa2494e8d8608cc",
    ),
    "src/option_menu.c": (
        "0b55a34ffd8869e3c616553108e1487c9db657df",
        "a315b476fffc1fc3f4cfd644e190d1a55adb21206a5531b6347083e23c9b25a5",
    ),
    "src/new_menu_helpers.c": (
        "08c032027cda2c34bf0dded37458adeb250aa553",
        "d115f81a76f93ba1a34894acd58f266a1920215784176f94188e4bad8ba51b1c",
    ),
    "src/scrcmd.c": (
        "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
        "898dad5a07ce0a125731b998654d86808885a8d48163d607478a5e70c1cac553",
    ),
    "src/save.c": (
        "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
        "24f0b70d72cc83c50f7b2d6d73cb211c9b1272ab5fa40dc1d553ad48d1f4511c",
    ),
    "include/global.h": (
        "77155b09014aa854fcf87260e6ad2969e222da53",
        "044325b90e7c79146cc0cf73d31b6be3e4840059e2e778b63d9b5448fe538429",
    ),
    "include/constants/global.h": (
        "21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9",
        "7ecf4a63c7be65328135a75f8620786e40343bbe7688e7017e6d780526fd6a0c",
    ),
    "graphics_file_rules.mk": (
        "39b952cd45b6a34eb98318a76aa531fcafff134d",
        "bd56e518ab9527f844642230673ce27a5bae73c7208d917d3288b073859fb685",
    ),
    "README.md": (
        "819422657623aae0cb0d2d0d23893b2927fcf0d7",
        "ab59004406fa7c682aed5f7d034e527ac9b9c8cf4a0257920b1340bc25e99f3d",
    ),
}


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def pinned_file(source_root: Path, relative_path: str, expected: tuple[str, str]) -> bytes:
    data = (source_root / relative_path).read_bytes()
    if git_blob_sha1(data) != expected[0]:
        raise AssertionError(f"{relative_path}: Git blob identity mismatch")
    if hashlib.sha256(data).hexdigest() != expected[1]:
        raise AssertionError(f"{relative_path}: SHA-256 identity mismatch")
    return data


class BrailleHostWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source_value = os.environ.get("PHASE1_FIRERED_SOURCE")
        if not source_value:
            raise RuntimeError("PHASE1_FIRERED_SOURCE must name the pinned FireRed checkout")
        cls.source_root = Path(source_value).resolve()
        cls.source_path = cls.source_root / "src/braille_text.c"
        cls.original_source = cls.source_path.read_bytes()
        cls.compiler = shutil.which(os.environ.get("CC", "gcc"))
        if cls.compiler is None:
            raise RuntimeError("GCC is required for the sanitizer host witness")

        cls.temp_dir = tempfile.TemporaryDirectory(prefix="phase1-braille-host-")
        cls.build_dir = Path(cls.temp_dir.name)
        cls.original_binary = cls.build_dir / "braille-original"
        cls.mutated_binary = cls.build_dir / "braille-fixed-index"
        cls._compile(cls.original_binary, cls.source_path)

        old_index = b"sScrollDistances[gSaveBlock2Ptr->optionsTextSpeed]"
        if cls.original_source.count(old_index) != 3:
            raise AssertionError("pinned renderer no longer has the three expected option reads")
        mutated = cls.original_source.replace(
            old_index, b"sScrollDistances[OPTIONS_TEXT_SPEED_MID]"
        )
        cls.mutated_source_path = cls.build_dir / "braille-fixed-index.c"
        cls.mutated_source_path.write_bytes(mutated)
        cls._compile(cls.mutated_binary, cls.mutated_source_path)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    @classmethod
    def _compile(cls, output: Path, source: Path) -> None:
        command = [
            cls.compiler,
            "-std=gnu11",
            "-O1",
            "-g",
            "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all",
            "-fno-omit-frame-pointer",
            f'-DBRAILLE_SOURCE_PATH="{source}"',
            f"-I{STUB_INCLUDE}",
            str(TEST_C),
            "-o",
            str(output),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise AssertionError(
                f"host compile failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
            )

    def _run(self, binary: Path, mode: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=0"
        return subprocess.run(
            [str(binary), mode],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_pinned_source_archive_and_review_record(self) -> None:
        self.assertEqual(hashlib.sha256(self.original_source).hexdigest(), SOURCE_SHA256)
        self.assertEqual(git_blob_sha1(self.original_source), SOURCE_BLOB)
        if (self.source_root / ".git").exists():
            revision = subprocess.check_output(
                ["git", "-C", str(self.source_root), "rev-parse", "HEAD"], text=True
            ).strip()
            self.assertEqual(revision, PIN)

        archive_bytes = ARCHIVE.read_bytes()
        self.assertEqual(hashlib.sha256(archive_bytes).hexdigest(), ARCHIVE_SHA256)
        rows = gzip.decompress(archive_bytes).splitlines(keepends=True)
        row = next(item for item in rows if b'"path":"src/braille_text.c"' in item)
        self.assertEqual(hashlib.sha256(row).hexdigest(), ARCHIVE_ROW_SHA256)
        self.assertEqual(hashlib.sha256(row.rstrip(b"\n")).hexdigest(), DOSSIER_SHA256)
        dossier = json.loads(row)
        self.assertEqual(dossier["provenance"]["pinned_revision"], PIN)
        self.assertEqual(dossier["provenance"]["git_blob_sha"], SOURCE_BLOB)
        self.assertEqual(dossier["provenance"]["source_content_sha256"], SOURCE_SHA256)
        self.assertFalse(dossier["review"]["semantic_signoff"])

        handoff = json.loads(HANDOFF.read_text())
        record = handoff["source_records"][0]
        self.assertEqual(record["packet_index"], 294)
        self.assertEqual(record["source"]["git_blob_sha1"], SOURCE_BLOB)
        self.assertEqual(record["source"]["sha256"], SOURCE_SHA256)
        self.assertEqual(
            record["original_dossier_provenance"]["archive_sha256"], ARCHIVE_SHA256
        )
        self.assertEqual(
            record["original_dossier_provenance"]["archive_row_sha256_including_newline"],
            ARCHIVE_ROW_SHA256,
        )
        self.assertEqual(handoff["status"]["handoff"], "NON_APPROVING")
        self.assertEqual(handoff["status"]["phase1_gate"], "FAIL_INCOMPLETE")
        self.assertEqual(handoff["status"]["independent_approvals_added"], 0)
        self.assertEqual(
            record["licensing"]["status"], "PENDING_ORIGINAL_LICENSE_REVIEW"
        )

    def test_pinned_option_script_save_and_asset_dependencies(self) -> None:
        for relative_path, identity in DEPENDENCIES.items():
            pinned_file(self.source_root, relative_path, identity)

        default_options = pinned_file(
            self.source_root, "src/new_game.c", DEPENDENCIES["src/new_game.c"]
        ).decode()
        self.assertIn(
            "gSaveBlock2Ptr->optionsTextSpeed = OPTIONS_TEXT_SPEED_MID;",
            default_options,
        )

        menu = pinned_file(
            self.source_root, "src/option_menu.c", DEPENDENCIES["src/option_menu.c"]
        ).decode()
        self.assertIn("sOptionMenuItemCounts[MENUITEM_COUNT] = {3,", menu)
        self.assertIn(
            "sOptionMenuPtr->option[i] > (sOptionMenuItemCounts[i]) - 1", menu
        )
        self.assertIn(
            "gSaveBlock2Ptr->optionsTextSpeed = sOptionMenuPtr->option[MENUITEM_TEXTSPEED];",
            menu,
        )
        option_menu_body = re.search(
            r"static u8 OptionMenu_ProcessInput\(void\)\s*\{(.*?)\n\}",
            menu,
            re.S,
        )
        self.assertIsNotNone(option_menu_body)
        self.assertIn(
            "sOptionMenuItemCounts[sOptionMenuPtr->cursorPos]",
            option_menu_body.group(1),
        )

        writer_paths = set()
        assignment = re.compile(r"\boptionsTextSpeed\s*=(?!=)")
        for path in (self.source_root / "src").rglob("*.[ch]"):
            if assignment.search(path.read_text(errors="replace")):
                writer_paths.add(path.relative_to(self.source_root).as_posix())
        self.assertEqual(
            writer_paths,
            {"src/new_game.c", "src/option_menu.c", "src/new_menu_helpers.c"},
        )

        speed_helper = pinned_file(
            self.source_root,
            "src/new_menu_helpers.c",
            DEPENDENCIES["src/new_menu_helpers.c"],
        ).decode()
        self.assertIn(
            "if (gSaveBlock2Ptr->optionsTextSpeed > OPTIONS_TEXT_SPEED_FAST)", speed_helper
        )
        self.assertIn(
            "gSaveBlock2Ptr->optionsTextSpeed = OPTIONS_TEXT_SPEED_MID;", speed_helper
        )

        script_commands = pinned_file(
            self.source_root, "src/scrcmd.c", DEPENDENCIES["src/scrcmd.c"]
        ).decode()
        braille_handler = script_commands.split(
            "bool8 ScrCmd_braillemessage", 1
        )[1].split("bool8 ScrCmd_getbraillestringwidth", 1)[0]
        self.assertIn(
            "AddTextPrinterParameterized(0, FONT_BRAILLE, msg, 0, 1, 0, NULL);",
            braille_handler,
        )
        self.assertNotIn("GetTextSpeedSetting", braille_handler)

        save_source = pinned_file(
            self.source_root, "src/save.c", DEPENDENCIES["src/save.c"]
        ).decode()
        copy_save_match = re.search(
            r"static u8 CopySaveSlotData\([^\n]*\)\n\{(.*?)^\}",
            save_source,
            re.S | re.M,
        )
        self.assertIsNotNone(copy_save_match)
        copy_save = copy_save_match.group(1)
        self.assertIn("gSaveDataBufferPtr->checksum == checksum", copy_save)
        self.assertIn(
            "locations[id].data[j] = gSaveDataBufferPtr->data[j];", copy_save
        )
        self.assertNotIn("optionsTextSpeed", copy_save)
        valid_status_match = re.search(
            r"static u8 GetSaveValidStatus\([^\n]*\)\n\{(.*?)^\}",
            save_source,
            re.S | re.M,
        )
        self.assertIsNotNone(valid_status_match)
        valid_status = valid_status_match.group(1)
        self.assertIn("validSectors == ALL_SECTORS", valid_status)
        self.assertNotIn("optionsTextSpeed", valid_status)

        global_header = pinned_file(
            self.source_root, "include/global.h", DEPENDENCIES["include/global.h"]
        ).decode()
        self.assertIn("u16 optionsTextSpeed:3;", global_header)
        speed_constants = pinned_file(
            self.source_root,
            "include/constants/global.h",
            DEPENDENCIES["include/constants/global.h"],
        ).decode()
        self.assertIn("#define OPTIONS_TEXT_SPEED_SLOW  0", speed_constants)
        self.assertIn("#define OPTIONS_TEXT_SPEED_MID   1", speed_constants)
        self.assertIn("#define OPTIONS_TEXT_SPEED_FAST  2", speed_constants)

        graphics_rules = pinned_file(
            self.source_root,
            "graphics_file_rules.mk",
            DEPENDENCIES["graphics_file_rules.mk"],
        ).decode()
        self.assertIn(
            "$(FONTGFXDIR)/braille.fwjpnfont: $(FONTGFXDIR)/braille.png",
            graphics_rules,
        )

        readme = pinned_file(self.source_root, "README.md", DEPENDENCIES["README.md"])
        self.assertFalse((self.source_root / "LICENSE").exists())
        self.assertTrue(readme.strip())

    def test_valid_speed_values_0_through_2(self) -> None:
        result = self._run(self.original_binary, "valid")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS valid speed scroll controls", result.stdout)

    def test_injected_speed_three_triggers_sanitizer_and_mutation_control(self) -> None:
        original = self._run(self.original_binary, "speed-three")
        self.assertNotEqual(original.returncode, 0, original.stdout + original.stderr)
        self.assertIn("RUN injected invalid-speed control", original.stdout)
        self.assertTrue(
            "index 3 out of bounds" in original.stderr
            or "global-buffer-overflow" in original.stderr,
            original.stderr,
        )

        mutated = self._run(self.mutated_binary, "speed-three")
        self.assertEqual(mutated.returncode, 0, mutated.stdout + mutated.stderr)
        self.assertIn("PASS fixed-index mutation control", mutated.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

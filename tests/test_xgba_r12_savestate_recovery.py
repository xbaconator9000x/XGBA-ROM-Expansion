"""XGBA R12: actual FireRed/mGBA rollback and post-load sidecar fetch.

Two SELECT events in native FireRed with a real emulator savestate restore
between them; verifies VRAM bytes, provider read counts, original map state,
genuine emulator PNGs, and fail-closed disabled mode. Not a stress test.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"tools"), str(ROOT/"tests"), str(ROOT/"integration/mgba")]
import test_xgba_r10_pallet_town_live_swap as r10
import xgba_mgba_run as launcher


class ActualFireRedSavestateRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = r10.ActualFireRedPalletTownLiveSwap
        fixture.setUpClass()
        cls.addClassCleanup(fixture.doClassCleanups)
        cls.fixture = fixture
        cls.rom_sha = hashlib.sha256(fixture.rom.read_bytes()).hexdigest()
        cls.runs = {}
        for mode in ("enabled", "disabled"):
            folder = Path(fixture.temp.name) / ("r12-" + mode)
            folder.mkdir()
            completed = launcher.launch(
                fixture.rom, fixture.manifest, "graphic.crystal",
                emulator=fixture.emulator, frames=1800,
                probe_address=fixture.probe,
                second_resource_id="graphic.magma",
                r12_dir=folder, disabled=(mode == "disabled"))
            marker = "PASS_R12_REAL_FIRERED_SAVESTATE_ROLLBACK mode=" + mode
            if marker not in completed.stdout:
                raise AssertionError("Native R12 result missing for " + mode)
            report = json.loads((folder / "proof.json").read_text("utf-8"))
            if report["milestone"] != "R12_FIRERED_SAVESTATE_ROLLBACK":
                raise AssertionError("R12 native proof missing")
            for i in range(1, 5):
                images = sorted(folder.glob(f"{i:02d}-*.png"))
                if len(images) != 1:
                    raise AssertionError("Missing genuine native LCD frame")
                with Image.open(images[0]) as frame:
                    frame.load()
                    if frame.size != (240, 160):
                        raise AssertionError("Bad native GBA LCD size")
            if any(p.name.endswith(".tmp") for p in folder.iterdir()):
                raise AssertionError("Native savestate must not remain")
            cls.runs[mode] = {"proof": report, "folder": folder}

        dest = os.getenv("XGBA_R12_EVIDENCE_DIR")
        if dest:
            target = Path(dest)
            target.mkdir(parents=True, exist_ok=True)
            for mode in ("enabled", "disabled"):
                subdir = target / mode
                subdir.mkdir()
                origin = cls.runs[mode]["folder"]
                for path in origin.glob("*.png"):
                    shutil.copy2(path, subdir / path.name)
                shutil.copy2(origin / "proof.json", subdir / "proof.json")
            (target / "summary.json").write_text(json.dumps({
                "milestone": "R12_REAL_NATIVE_FIRE_RED_SAVESTATE",
                "rom_sha256": cls.rom_sha,
                "pinned_firered": r10.r6.FIRERED_PIN,
                "pinned_mgba": r10.r6.MGBA_PIN,
                "enabled": cls.runs["enabled"]["proof"],
                "disabled": cls.runs["disabled"]["proof"],
                "limitations": "Native headless emulation only, not Android, mGBA GUI audio/VSync, in-game save files, or unmodified emulator compatibility",
                "roms_or_savestates_distributed": False,
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_native_restore_rewinds_real_game_and_crystal_vram(self):
        p = self.runs["enabled"]["proof"]
        self.assertTrue(p["native_save_and_load"])
        self.assertTrue(p["state_file_deleted"])
        self.assertEqual(p["map"], "MAP_PALLET_TOWN")
        self.assertEqual(p["sha_initial"], p["sha_restored"])
        self.assertLess(p["ticks_initial"], p["ticks_restored"])
        self.assertLess(p["ticks_restored"], p["ticks_after_select"])

    def test_second_select_reloads_magma_with_real_native_provider(self):
        p = self.runs["enabled"]["proof"]
        self.assertEqual([p[k] for k in (
            "reads_initial", "reads_first_select",
            "reads_after_restore", "reads_after_replay")], [1,2,2,3])
        self.assertNotEqual(p["sha_initial"], p["sha_after_select"])
        self.assertEqual(p["sha_after_select"], p["sha_replayed"])
        directory = self.runs["enabled"]["folder"]
        delta = r10.compare_region(directory / "01-initial.png",
                                   directory / "02-after-select.png",
                                   r10.NATIVE_SPRITE_RECT)
        self.assertGreater(delta, 250)

    def test_disabled_baseline_never_reads_sidecar_even_after_restore(self):
        p = self.runs["disabled"]["proof"]
        for k in ("reads_initial", "reads_first_select",
                  "reads_after_restore", "reads_after_replay"):
            self.assertEqual(p[k], 0)
        self.assertEqual(len({p[k] for k in (
            "sha_initial", "sha_after_select", "sha_restored",
            "sha_replayed")}), 1)

    def test_source_rom_not_reloaded_and_no_state_exported(self):
        self.assertEqual(self.rom_sha, self.fixture.rom_sha)
        for entry in self.runs.values():
            self.assertTrue(entry["proof"]["one_rom_one_emulator_process"])
            self.assertFalse(any(p.suffix in (".gba", ".elf", ".tmp")
                                 for p in entry["folder"].iterdir()))


if __name__ == "__main__":
    unittest.main()

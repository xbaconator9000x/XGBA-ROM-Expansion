"""R15: native FireRed original Flash save, separate mGBA processes and external assets.

This fixture actually builds pinned FireRed + patched mGBA, strips the original
external geometry and secondary tilesets, executes the game's ordinary Flash
sector save, unloads the complete emulator process, and cold-continues from
an actual 128 KiB save with freshly fetched external house/route tiles.

No game ROM, save, extracted tiles, external pack or savestate is ever uploaded.
Only genuine native LCD 240x160 PNGs and a non-proprietary proof JSON are kept.
"""
from __future__ import annotations
import hashlib, json, os, shutil, sys, unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests")]
import test_xgba_r14_external_tilesets as r14
import xgba_mgba_run as launcher

class NativeFlashPersistence(unittest.TestCase):
    R15_SAVE_TEST=True

    @classmethod
    def setUpClass(cls):
        # Reuse the exact passing R14 integration fixture and native hardware
        # checks, while compiling the R15 FireRed save/continue code variant.
        r14.NativeNavigation.setUpClass.__func__(cls)
        root=Path(cls.tmp.name)
        rom=r14.r7.FIRERED/"pokefirered_modern.gba"
        manifest=root/"manifest.json"
        executable=root/"build/xgba-mgba-headless"
        ids=("map.route1.tiles","map.house.tiles")
        savefile=root/"fire-red-real-flash.sav" # private, never published
        cls.save_path=savefile
        cls.evidence=root/"r15-evidence"
        cls.evidence.mkdir()
        def execute(phase):
            return launcher.launch(
                rom,manifest,ids[0],emulator=executable,frames=1800,
                probe_address=cls.probe,second_resource_id=ids[1],
                r15_dir=cls.evidence,r15_savefile=savefile,
                r15_phase=phase,r15_save_probe=cls.save_probe)
        if savefile.exists():raise AssertionError("R15 save must be absent on first launch")
        written=execute("write")
        cls.write_log=written.stdout
        if "PASS_R15_REAL_FIRERED_FLASH_WRITE" not in cls.write_log:
            raise AssertionError("Actual FireRed Flash write never completed")
        if not savefile.exists() or savefile.stat().st_size!=131072:
            raise AssertionError("Real FireRed 128KiB Flash save absent")
        cls.save_sha=hashlib.sha256(savefile.read_bytes()).hexdigest()
        # The previous invocation has returned: its mGBA process and all
        # CPU/EWRAM/VRAM state are now gone, not a restore/loadstate API.
        resumed=execute("continue")
        cls.continue_log=resumed.stdout
        if "PASS_R15_REAL_FIRERED_COLD_CONTINUE" not in cls.continue_log:
            raise AssertionError("Original FireRed LoadGameSave/continue did not boot")
        cls.save_sha_after=hashlib.sha256(savefile.read_bytes()).hexdigest()
        if cls.save_sha_after!=cls.save_sha:
            raise AssertionError("Cold continuation silently changed saved Flash bytes")
        # Wrong-pack failure is assessed AFTER correctly loading the real save
        # in another new emulator process, never by mutating the ROM or save.
        external=root/"external.bin"
        house_offset=32*1024*1024+32768+64
        with external.open("r+b") as f:
            f.seek(house_offset)
            original=f.read(1)
            if len(original)!=1:raise AssertionError("External house pack missing")
            f.seek(house_offset);f.write(bytes([original[0]^0xFF]))
        try:
            refused=execute("corrupt")
            cls.corrupt_log=refused.stdout
            if "PASS_R15_CORRUPT_PACK_REFUSED" not in cls.corrupt_log:
                raise AssertionError("Corrupt external pack was not refused")
        finally:
            with external.open("r+b") as f:
                f.seek(house_offset);f.write(original)
        if hashlib.sha256(savefile.read_bytes()).hexdigest()!=cls.save_sha:
            raise AssertionError("Invalid sidecar changed legitimate game save")
        cls.report={
            "milestone":"R15_REAL_FIRERED_FLASH_COLD_CONTINUE",
            "verified_compiled_rom_sha256":cls.rom_sha,
            "native_original_flash_sector_save":True,
            "native_mgba_subprocesses":3,
            "saved_flash_size":131072,
            "flash_sha256":cls.save_sha,
            "flash_unchanged_after_resume_and_corrupt_pack":True,
            "separate_mgba_process_restart":True,
            "true_original_LoadGameSave_and_CB2_ContinueSavedGame":True,
            "save_source":"TrySavingData(SAVE_NORMAL) inside source-built FireRed",
            "saveram_and_sidecar_privately_deleted_on_test_cleanup":True,
            "real_map_reacquisition":"saved house -> Pallet Town with secondary tiles and grid inspected in native EWRAM and BG VRAM",
            "corrupt_pack":"wrong SHA-256 explicitly refused by native provider; game fail-closed (not yet user-facing recovery)",
            "firered_pin":r14.r6.FIRERED_PIN,
            "mgba_pin":r14.r6.MGBA_PIN,
            "native_write_log":cls.write_log,
            "native_resume_log":cls.continue_log,
            "native_corrupt_log":cls.corrupt_log,
        }
        output=os.getenv("XGBA_R15_EVIDENCE_DIR")
        if output:
            folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
            for image in cls.evidence.glob("*.png"):
                shutil.copy2(image,folder/image.name)
            (folder/"proof.json").write_text(json.dumps(cls.report,indent=2))

    def test_real_gba_flash_persistent_between_processes(self):
        self.assertEqual(self.save_sha,self.save_sha_after)
        self.assertIn("original_save=1",self.write_log)
        self.assertIn("native_flash_loaded=1",self.continue_log)

    def test_native_house_geometry_and_tiles_reacquired(self):
        self.assertIn("saved_map=4:0",self.write_log)
        self.assertIn("external_reacquire=1",self.continue_log)
        self.assertIn("maps=house_to_pallet",self.continue_log)

    def test_actual_wrong_pack_is_refused_with_save_preserved(self):
        self.assertIn("invalid_pack_read=0",self.corrupt_log)
        self.assertIn("guest_fail_closed=1",self.corrupt_log)

    def test_four_real_mgba_lcd_frames(self):
        frames=sorted(self.evidence.glob("*.png"))
        self.assertEqual(len(frames),4)
        for frame in frames:
            with Image.open(frame) as im:
                self.assertEqual(im.size,(240,160))
                im.verify()
        self.assertNotEqual(frames[0].read_bytes(),frames[2].read_bytes())
        self.assertNotEqual(frames[1].read_bytes(),frames[3].read_bytes())

if __name__=="__main__":unittest.main()

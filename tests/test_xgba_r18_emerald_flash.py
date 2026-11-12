"""R18: original Pokémon Emerald native Flash save -> process exit -> cold continue.

Stacked on R17's genuine original Emerald external Littleroot map+tileset.
This MUST use actual TrySavingData and LoadGameSave, not mGBA savestates,
RAM copying or host-authored save images. Save bytes never leave CI tempdir.
"""
from __future__ import annotations
import hashlib,json,os,shutil,sys,unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher

def sha_file(path:Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class NativeEmeraldFlashColdContinue(unittest.TestCase):
    R18_SAVE_TEST=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        root=cls.native_root
        sav=root/"native-emerald-original-flash.sav"
        cls.save=sav
        cls.output=root/"r18-evidence"
        cls.output.mkdir()
        if sav.exists():
            raise AssertionError("R18 first boot must not have a preexisting save")
        def execute(phase):
            return launcher.launch(
                cls.rom,cls.manifest_path,r17.RID,
                emulator=cls.executable,frames=3200,
                probe_address=cls.probe,second_resource_id=r17.BOOT,
                r18_dir=cls.output,r18_savefile=sav,
                r18_phase=phase,r18_save_probe=cls.save_probe,
                extra_resource_ids=(("emerald.r40.script",)
                    if getattr(cls,"R40_SCRIPT_TEST",False) else ()))
        write=execute("write")
        cls.write_log=write.stdout
        if "PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE" not in cls.write_log:
            raise AssertionError("Original native Emerald Flash sector write did not succeed")
        if not sav.exists() or sav.stat().st_size not in (131072,131088):
            raise AssertionError("Original native 128 KiB Flash absent; got "+(
                str(sav.stat().st_size) if sav.exists() else "no backing file"))
        cls.flash_bytes=sav.stat().st_size
        cls.flash_sha=sha_file(sav)
        # The first process COMPLETELY terminates here. A new process must
        # reacquire the original full external map/tileset on Continue.
        continuation=execute("continue")
        cls.continue_log=continuation.stdout
        if "PASS_R18_EMERALD_COLD_FLASH_CONTINUE" not in cls.continue_log:
            raise AssertionError("Emerald original cold LoadGameSave / map continuation missing")
        if sha_file(sav)!=cls.flash_sha:
            raise AssertionError("Cold continuation silently mutated native Emerald Flash")

        # A third new native mGBA process loads the good Flash but attempts
        # to acquire a deliberately wrong-hash external map. The ROM+save
        # remain unchanged; the fixture MUST reject that sidecar.
        external=root/"extracted-assets.bin"
        with external.open("r+b") as stream:
            stream.seek(cls.offset)
            previous=stream.read(1)
            if len(previous)!=1:
                raise AssertionError("Original Emerald external map pack missing")
            stream.seek(cls.offset);stream.write(bytes([previous[0]^0x5A]))
        try:
            bad=execute("corrupt")
            cls.bad_log=bad.stdout
            if "PASS_R18_EMERALD_COLD_BAD_PACK_REFUSED" not in cls.bad_log:
                raise AssertionError("Bad external Emerald map was not refused after valid Flash load")
        finally:
            with external.open("r+b") as stream:
                stream.seek(cls.offset);stream.write(previous)
        if sha_file(sav)!=cls.flash_sha:
            raise AssertionError("Valid Emerald Flash altered by rejected external pack")
        cls.report={
            "milestone":"R18_EMERALD_ORIGINAL_FLASH_COLD_CONTINUE_WITH_EXTERNAL_MAP",
            "native_game":"pret/pokeemerald MODERN=1",
            "emerald_pin":r17.e16.EMERALD_PIN,"mgba_pin":r17.e16.MGBA_PIN,
            "native_rom_sha256":cls.rom_sha,
            "actual_guest_map":"original Littleroot 0:9 external map and secondary tileset",
            "real_original_flash_write":True,
            "first_save_mode":"Emerald SAVE_OVERWRITE_DIFFERENT_FILE if different file",
            "save_size_original_flash_bytes":131072,
            "save_on_disk_bytes_including_mgba_footer":cls.flash_bytes,
            "private_flash_sha256":cls.flash_sha,
            "exactly_three_fresh_mgba_processes":True,
            "native_original_LoadGameSave":True,
            "native_original_CB2_ContinueSavedGame":True,
            "native_external_map_and_bg_vram_reacquired_after_cold_boot":True,
            "bad_external_pack_rejected_without_changing_saved_game":True,
            "executed_write":cls.write_log,
            "executed_continue":cls.continue_log,
            "executed_bad_pack":cls.bad_log,
            "private_save_not_published":True,
            "scope":"Actual Emerald Flash sector save from test-only SELECT, not graphical Start menu; source-built Emerald original callback and external Littleroot. Requires opt-in patched mGBA, not stock/hardware. Missing pack fails closed in fixture, not polished recovery."
        }
        target=os.getenv("XGBA_R18_EVIDENCE_DIR")
        if target:
            path=Path(target);path.mkdir(parents=True,exist_ok=True)
            for screenshot in cls.output.glob("*.png"):
                shutil.copy2(screenshot,path/screenshot.name)
            (path/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_real_emerald_flash_written_and_persisted(self):
        self.assertIn("game_save=1 sector_write=1",self.write_log)
        self.assertIn("map=0:9",self.write_log)
        self.assertIn(self.flash_bytes,(131072,131088))

    def test_separate_native_mgba_process_original_continue(self):
        self.assertIn("original_LoadGameSave=1 CB2_ContinueSavedGame=1",self.continue_log)

    def test_real_external_emerald_map_reacquired_after_power_cycle(self):
        self.assertIn("external_littleroot_reacquired=1",self.continue_log)
        self.assertIn("native_grid=1 bg_vram=1",self.continue_log)

    def test_corrupt_external_resource_fails_closed_without_changing_flash(self):
        self.assertIn("original_flash_valid=1 corrupt_external_map_refused=1",self.bad_log)
        self.assertEqual(sha_file(self.save),self.flash_sha)

    def test_real_emerald_before_after_and_cold_lcd_frames(self):
        pngs=sorted(self.output.glob("*.png"))
        self.assertEqual(len(pngs),3)
        for png in pngs:
            with Image.open(png) as image:
                self.assertEqual(image.size,(240,160))
                self.assertGreater(len(set(image.convert("RGB").getdata())),8)

if __name__=="__main__":
    unittest.main()

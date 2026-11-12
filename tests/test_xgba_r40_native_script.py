"""R40: genuine external Emerald script -> native interpreter -> Flash save -> cold load.

Runs pinned real pret/pokeemerald MODERN=1 under patched native mGBA. The
fixture script is original test-authored bytecode, NOT private Team Rocket or
Heart & Soul code, and runs via Emerald's original RunScriptImmediately.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r18_emerald_flash as r18
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher
import xgba_r40_native_event as script


class NativeEmeraldExternalScriptFlash(r18.NativeEmeraldFlashColdContinue):
    R40_SCRIPT_TEST=True

    @classmethod
    def setUpClass(cls):
        # Inherits the full real native R18 source compilation, three fresh
        # mGBA processes, Flash integrity checks, and LCD proof requirements.
        super().setUpClass()
        if "PASS_R40_NATIVE_EMERALD_SCRIPT_FLASH_WRITE" not in cls.write_log:
            raise AssertionError("Original Emerald script engine never executed source-external script")
        if "PASS_R40_NATIVE_EMERALD_COLD_SCRIPT_FLASH_RESTORE" not in cls.continue_log:
            raise AssertionError("Emerald original Flash did not restore the external script event data")
        if cls.flash_sha!=r18.sha_file(cls.save):
            raise AssertionError("Flash changed after cold source script verification")
        if cls.r40_script!=script.script_bytes():
            raise AssertionError("R40 script fixture differs from source-authored original")
        if cls.r40_script in cls.rom.read_bytes():
            raise AssertionError("R40 event script unexpectedly appears in compiled game ROM")

        # Negative test is a distinct fresh mGBA process with NO prior Flash:
        # mutate only external script bytes, leaving manifest SHA unchanged.
        payload=cls.native_root/"extracted-assets.bin"
        with payload.open("r+b") as stream:
            stream.seek(script.SCRIPT_OFFSET)
            old=stream.read(len(cls.r40_script))
            if old!=cls.r40_script:
                raise AssertionError("Test sidecar byte position drift")
            stream.seek(script.SCRIPT_OFFSET)
            stream.write(bytes([old[0]^0x80])+old[1:])
        bad_save=cls.native_root/"r40-rejected-new-game.sav"
        if bad_save.exists():
            raise AssertionError("R40 rejected-script test must boot without Flash")
        try:
            result=launcher.launch(
                cls.rom,cls.manifest_path,r17.RID,
                emulator=cls.executable,frames=3200,
                probe_address=cls.probe,second_resource_id=r17.BOOT,
                extra_resource_ids=(script.RESOURCE_ID,),
                r18_dir=cls.output,r18_savefile=bad_save,
                r18_phase="r40-corrupt",r18_save_probe=cls.save_probe)
            cls.corrupt_script_log=result.stdout
        finally:
            with payload.open("r+b") as stream:
                stream.seek(script.SCRIPT_OFFSET);stream.write(old)
        if "PASS_R40_BAD_EXTERNAL_SCRIPT_SHA_REFUSED" not in cls.corrupt_script_log:
            raise AssertionError("Bad external bytecode was not rejected before guest execution")
        # mGBA may allocate/flush an erased blank Flash backing file even
        # when the guest never invokes TrySavingData. The native proof checks
        # gXgbaR18Proof.save_requests == 0 before reporting PASS; do not
        # confuse file allocation with a game-authored save-sector write.
        if bad_save.exists() and bad_save.stat().st_size not in (0,131072,131088):
            raise AssertionError("Unexpected rejected-boot Flash backing size")
        if cls.flash_sha!=r18.sha_file(cls.save):
            raise AssertionError("Corrupt-script boot modified legitimate saved Emerald game")
        cls.r40_report={
            "milestone":"R40_NATIVE_EMERALD_ORIGINAL_SCRIPT_INTERPRETER_FLASH",
            "native_game":"pret/pokeemerald MODERN=1",
            "native_guest":"real RunScriptImmediately / original gScriptCmdTable",
            "source_script":"authored synthetic 9-byte XGBA sidecar payload",
            "resource_id":script.RESOURCE_ID,
            "script_sha256":hashlib.sha256(cls.r40_script).hexdigest(),
            "script_original_rom_embedded":False,
            "native_original_flag_id":script.FLAG_ID,
            "native_original_variable_id":script.VAR_ID,
            "native_original_variable_value":script.VALUE,
            "actual_gba_flash_written":True,
            "fresh_mgba_processes":4,
            "cold_continue_without_script_reexecution":True,
            "malformed_external_script_rejected_before_dispatch":True,
            "flash_unchanged_after_rejected_script":True,
            "native_emulator_patched":True,
            "real_team_rocket_script_runtime_test":False,
            "heart_and_soul_runtime_test":False,
            "common_multi_rom_game_save":False,
        }
        out=os.getenv("XGBA_R40_EVIDENCE_DIR")
        if out:
            directory=Path(out)
            directory.mkdir(parents=True,exist_ok=True)
            (directory/"proof.json").write_text(
                json.dumps(cls.r40_report,indent=2,sort_keys=True)+"\n")
            # Original native LCD screenshots only, no ROM, Flash, map,
            # proprietary script or copyrighted asset payload exported.
            for src in cls.output.glob("*.png"):
                (directory/src.name).write_bytes(src.read_bytes())

    def test_external_script_original_emerald_dispatch(self):
        self.assertIn("interpreter=original_scripttable",self.write_log)
        self.assertIn("script_reexecutions=0",self.continue_log)

    def test_original_flash_persists_event_values_across_new_process(self):
        self.assertIn("original_LoadGameSave=1",self.continue_log)
        self.assertTrue(self.r40_report["actual_gba_flash_written"])

    def test_external_script_is_not_embedded_in_rom(self):
        self.assertNotIn(script.script_bytes(),self.rom.read_bytes())
        self.assertGreater(script.SCRIPT_OFFSET,32*1024*1024)

    def test_damaged_script_is_refused_without_flash_write(self):
        self.assertIn("no_flash_write=1",self.corrupt_script_log)
        self.assertEqual(self.flash_sha,r18.sha_file(self.save))

    def test_exact_provenance_scope(self):
        self.assertFalse(self.r40_report["real_team_rocket_script_runtime_test"])
        self.assertFalse(self.r40_report["heart_and_soul_runtime_test"])
        self.assertFalse(self.r40_report["common_multi_rom_game_save"])


if __name__=="__main__":
    unittest.main()

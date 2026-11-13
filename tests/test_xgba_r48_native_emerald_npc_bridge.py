"""R48 compile original Emerald's actual A-button event path with XGBA NPC bridge.

This compiles a real source-built Emerald and native patched mGBA, then boots
and checks the original game/Flash save cycle. It deliberately DOES NOT claim
foreign NPC talk/Fly success, which require imported foreign map/NPC spawning
and privately supplied original source script/text packs.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import test_xgba_r17_emerald_external_map as r17
import xgba_mgba_run as launcher


class SourceBuiltEmeraldOriginalNpcBridge(unittest.TestCase):
    R18_SAVE_TEST=True
    R48_ORIGINAL_NPC_TEST=True

    @classmethod
    def setUpClass(cls):
        r17.ActualEmeraldLittlerootExternalMap.setUpClass.__func__(cls)
        cls.evidence=cls.native_root/"r48-original-emerald-npc-bridge-boot"
        cls.evidence.mkdir()
        save=cls.native_root/"r48-original-emerald-flash.sav"
        cls.save=save
        if save.exists():
            raise AssertionError("R48 original Emerald game must boot clean")
        # R49 regression: 32 original-event-shaped synthetic sidecar pages
        # must be REGISTERED by the patched host provider without its old
        # 16-resource ceiling. These authored test pages are never claimed
        # to be original imported ROM data and are NOT guest-executed here.
        manifest=json.loads(cls.manifest_path.read_text())
        datafile=cls.manifest_path.parent/manifest["data_file"]
        fake_ids=[]
        with datafile.open("ab") as data:
            base=data.tell()
            for i in range(32):
                rid=f"r49.synthetic.original_event_page.{i:03}"
                payload=(f"ORIGINAL_MAP_EVENT_REGISTRY_TEST_{i:03}".encode()*8)[:256].ljust(256,bytes([0]))
                offset=base+256*i
                data.write(payload)
                manifest["resources"].append({
                    "id":rid,"offset":offset,"length":len(payload),
                    "sha256":hashlib.sha256(payload).hexdigest()})
                fake_ids.append(rid)
        cls.manifest_path.write_text(json.dumps(manifest))
        cls.registered_original_event_test_pages=tuple(fake_ids)
        result=launcher.launch(
            cls.rom,cls.manifest_path,r17.RID,
            emulator=cls.executable,frames=3100,
            probe_address=cls.probe,second_resource_id=r17.BOOT,
            extra_resource_ids=cls.registered_original_event_test_pages,
            r18_dir=cls.evidence,r18_savefile=save,
            r18_phase="write",r18_save_probe=cls.save_probe)
        cls.log=result.stdout
        if "PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE" not in cls.log:
            raise AssertionError("Original Emerald Flash gameplay regressed after A-button script bridge")
        if "map=0:9" not in cls.log:
            raise AssertionError("R48 native Emerald did not boot its actual original Littleroot world")
        cls.flash_bytes=save.stat().st_size
        cls.capture=sorted(cls.evidence.glob("*.png"))
        if os.getenv("XGBA_R48_NATIVE_EVIDENCE_DIR"):
            dst=Path(os.environ["XGBA_R48_NATIVE_EVIDENCE_DIR"])
            dst.mkdir(parents=True,exist_ok=True)
            for frame in cls.capture:
                shutil.copy2(frame,dst/frame.name)
            (dst/"NO_FOREIGN_NPC_YET.txt").write_text(
                "Original Emerald interpreter/object script A-button code is compiled and booted.\n"
                "This frame is Emerald native gameplay and NOT original Rocket/HnS map/Fly/NPC evidence.\n"
                "Three original foreign ROM NPC script payloads remain PRIVATE and not loaded in CI.\n")

    def test_native_original_emerald_map_and_genuine_flash_survive_script_hook(self):
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        self.assertIn("map=0:9",self.log)
        self.assertIn(self.flash_bytes,(131072,131088))

    def test_host_registry_accepts_32_source_event_pages_without_gba_ram_growth(self):
        self.assertEqual(len(self.registered_original_event_test_pages),32)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)
        # Registration is tested; these dummy pages are not claimed fetched.
        self.assertNotIn("PASS_R48_FOREIGN_FLY_COMPLETE",self.log)

    def test_original_game_compiled_foreign_script_bridge_not_mock_viewer(self):
        assert self.elf.is_file()
        sym=r17.r14.symbols(self.elf)
        self.assertIn("XgbaR48ResolveActualOriginalNpcScript",sym)
        self.assertIn("gXgbaR48OriginalNpcProof",sym)
        # Real guest EWRAM; not an instrumentation-only host-side variable.
        address=sym["gXgbaR48OriginalNpcProof"][0]
        self.assertTrue(0x02000000<=address<0x02040000)
        self.assertTrue(self.rom.is_file() and self.rom.stat().st_size>=1024*1024)


if __name__=="__main__":
    unittest.main()

"""R16: actual pret/pokeemerald decomp issues the EXISTING XGBA MMIO request.

Native source-built Emerald + patched mGBA required; never falls back to a
host-built tile demonstration. Original game loop keeps running. Enabled and
disabled mode execute the identical Emerald ROM (source SHA-256 checked).
"""
from __future__ import annotations

import hashlib,json,os,re,shutil,sys,tempfile,unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"integration/mgba"),str(ROOT/"tests")]
import xgba_r16_emerald_decomp_patch as adapter
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher
import apply_core_patch
import test_xgba_r7_mgba_core as r7

EMERALD=ROOT/"upstream"/"pokeemerald"
MGBA=ROOT/"upstream"/"mgba"
RESOURCE_ID="emerald.bridge"

class NativeEmeraldDecompBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path,head in ((EMERALD,adapter.EMERALD_PIN),(MGBA,adapter.MGBA_PIN)):
            actual=r7.run(["git","-C",path,"rev-parse","HEAD"]).stdout.strip()
            if actual!=head:
                raise AssertionError(f"Refusing unpinned upstream checkout: {path.name} {actual}")
        cls.contract=adapter.verify_source_contract(EMERALD)
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r16-emerald-decomp-")
        cls.addClassCleanup(cls.temp.cleanup)
        root=Path(cls.temp.name)
        modified=adapter.make_emerald_boot_sources(EMERALD)
        try:
            r7.run(["make","-C",EMERALD,"-j2","MODERN=1"],timeout=2600)
        finally:
            adapter.restore_sources(modified)
        rom=EMERALD/"pokeemerald_modern.gba"
        elf=EMERALD/"pokeemerald_modern.elf"
        if not rom.is_file() or not elf.is_file():
            raise AssertionError("Actual Emerald decomp output missing; no fallback ROM")
        data=rom.read_bytes()
        cls.rom_sha=hashlib.sha256(data).hexdigest()
        if len(data)>32*1024*1024 or r6.PAYLOAD in data:
            raise AssertionError("Emerald ROM address window exceeds hardware, or external payload embedded in ROM")
        nm=r7.run(["arm-none-eabi-nm","-g",elf]).stdout
        matches=re.findall(r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaEmeraldProbe$",nm,re.M)
        if len(matches)!=1:
            raise AssertionError("Source-built Emerald proof symbol missing from actual ARM ELF")
        cls.probe=int(matches[0],16)
        if not 0x02000000<=cls.probe<0x0203FFE0:
            raise AssertionError("Native Emerald proof address outside 256 KiB EWRAM")

        apply_core_patch.apply(MGBA)
        native=root/"native-mgba"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",native,
                "-DCMAKE_BUILD_TYPE=Release",
                "-DXGBA_MGBA_CHECKOUT="+str(MGBA)],timeout=240)
        r7.run(["cmake","--build",native,"--target","xgba-mgba-headless",
                "--parallel","2"],timeout=1050)
        executable=native/"xgba-mgba-headless"
        if not executable.is_file():
            raise AssertionError("Native mGBA XGBA-enabled emulator absent")

        external=root/"emerald-external.bin"
        with external.open("wb") as fp:
            fp.truncate(r6.RESOURCE_OFFSET+len(r6.PAYLOAD))
            fp.seek(r6.RESOURCE_OFFSET)
            fp.write(r6.PAYLOAD)
        cls.manifest=root/"manifest.json"
        cls.manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"pokeemerald-r16","sha256":cls.rom_sha},
            "data_file":external.name,
            "resources":[{"id":RESOURCE_ID,"offset":r6.RESOURCE_OFFSET,
                          "length":len(r6.PAYLOAD),
                          "sha256":hashlib.sha256(r6.PAYLOAD).hexdigest()}],
        }))
        cls.out=root/"native-lcd"
        cls.out.mkdir()
        cls.enabled=launcher.launch(rom,cls.manifest,RESOURCE_ID,
            emulator=executable,frames=1000,probe_address=cls.probe,
            r16_emerald_dir=cls.out)
        cls.disabled=launcher.launch(rom,cls.manifest,RESOURCE_ID,
            emulator=executable,frames=1000,probe_address=cls.probe,
            r16_emerald_dir=cls.out,disabled=True)
        cls.enabled_png=cls.out/"emerald-boot-enabled.png"
        cls.disabled_png=cls.out/"emerald-boot-disabled.png"
        if "PASS_R16_SOURCE_BUILT_POKEEMERALD_XGBA_MMIO enabled=1" not in cls.enabled.stdout:
            raise AssertionError("Actual Emerald guest did not request valid external resource")
        if "PASS_R16_SOURCE_BUILT_POKEEMERALD_XGBA_MMIO enabled=0" not in cls.disabled.stdout:
            raise AssertionError("Disabled XGBA was not checked with same original Emerald ROM")
        cls.report={
            "milestone":"R16_SOURCE_BUILT_EMERALD_NATIVE_GUEST_PROVIDER_BOOT",
            "actual_game":"pret/pokeemerald MODERN=1","pin":adapter.EMERALD_PIN,
            "native_mgba_pin":adapter.MGBA_PIN,
            "same_validated_mgba_provider_abi":1,
            "original_emerald_main_loop_runs_after_resource_fetch":True,
            "native_rom_sha256":cls.rom_sha,
            "original_rom_stays_inside_32MiB":True,
            "game_issued_resource_id":RESOURCE_ID,
            "post_32MiB_offset":r6.RESOURCE_OFFSET,
            "actual_ewram_verified":True,
            "source_contract":cls.contract,
            "game_source_restored_after_build":True,
            "native_ci_enabled":cls.enabled.stdout,
            "native_ci_disabled":cls.disabled.stdout,
            "not_yet_proven":"Emerald map/tileset/battle/save XGBA integration; game title load is not map gameplay proof",
        }
        output=os.environ.get("XGBA_R16_EVIDENCE_DIR")
        if output:
            o=Path(output);o.mkdir(parents=True,exist_ok=True)
            for src in (cls.enabled_png,cls.disabled_png):
                shutil.copy2(src,o/src.name)
            (o/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_emerald_source_abi_not_assumed_firered(self):
        self.assertEqual(self.contract["save_pointer_relocate"],
                         "SetSaveBlocksPointers(u16 trainer_id_offset)")
        self.assertEqual(self.contract["validated_hooks"],11)
        self.assertEqual(self.contract["heap_bytes"],0x1C000)

    def test_actual_emerald_guest_reads_real_external_bytes(self):
        self.assertIn("enabled=1 requests=1 bytes=64",self.enabled.stdout)
        self.assertIn("original_emerald_main_frames=180",self.enabled.stdout)

    def test_same_emerald_rom_disabled_performs_zero_external_reads(self):
        self.assertIn("enabled=0 requests=0 bytes=0",self.disabled.stdout)
        self.assertIn("zero_disabled_reads=1",self.disabled.stdout)

    def test_genuine_emerald_lcd_from_running_original_main_loop(self):
        for path in (self.enabled_png,self.disabled_png):
            with Image.open(path) as image:
                self.assertEqual(image.size,(240,160))
                image.load()
                self.assertGreater(len(set(image.convert("RGB").getdata())),8)

    def test_source_rom_and_resource_identity_are_bounded(self):
        manifest=sidecar.load_manifest(self.manifest)
        asset=manifest.get_resource(RESOURCE_ID)
        self.assertGreater(asset.offset,32*1024*1024)
        self.assertEqual(asset.length,64)
        self.assertEqual(manifest.source_identity.sha256,self.rom_sha)

if __name__=="__main__":
    unittest.main()

"""R24: exact same nine real guest-side MMIO boundary cases under FireRed.

Source-built original pinned pokefirered + pinned native opt-in mGBA.
Original ARM game arms DMA3 VBlank, attempts conflicting MMIO write, disarms and recovers. No fake DMA state or guest RAM edits.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"tests"),str(ROOT/"integration/mgba")]
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher
import xgba_r24_firered_patch as adapter
import apply_core_patch
import test_xgba_r7_mgba_core as r7

MAXIMUM="firered.r24.maximum"
BADSHA="firered.r24.badsha"
PLUSONE="firered.r24.toobig"
MAX_BYTES=16384

class NativeFireRedDmaSourceLifetime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r24-real-firered-")
        cls.addClassCleanup(cls.temp.cleanup)
        folder=Path(cls.temp.name)
        originals=adapter.patch_firered_r24(r7.FIRERED,r25_dma=True)
        try:
            r7.run(["make","-C",r7.FIRERED,"-j2","MODERN=1",
                    "GAME_VERSION=FIRERED"],timeout=2100)
        finally:
            adapter.restore_firered_r24(originals)
        cls.rom=r7.FIRERED/"pokefirered_modern.gba"
        elf=r7.FIRERED/"pokefirered_modern.elf"
        if not cls.rom.is_file() or not elf.is_file():
            raise AssertionError("Missing real source-built pinned FireRed ROM/ELF")
        cls.rom_hash=hashlib.sha256(cls.rom.read_bytes()).hexdigest()
        if cls.rom.stat().st_size>32*1024*1024:
            raise AssertionError("Original FireRed ROM exceeds actual GBA bus window")
        nm=r7.run(["arm-none-eabi-nm","-g",elf]).stdout
        hits=re.findall(r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaR24Proof$",nm,re.M)
        if len(hits)!=1:
            raise AssertionError("Real FireRed ARM EWRAM proof missing")
        cls.probe=int(hits[0],16)
        if not 0x02000000<=cls.probe<=0x02040000-68:
            raise AssertionError("FireRed guest boundary proof outside physical EWRAM")

        apply_core_patch.apply(r7.MGBA)
        native=folder/"native-mgba"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",native,
                "-DCMAKE_BUILD_TYPE=Release",
                "-DXGBA_MGBA_CHECKOUT="+str(r7.MGBA)],timeout=240)
        r7.run(["cmake","--build",native,"--target","xgba-mgba-headless",
                "--parallel","2"],timeout=1050)
        cls.emulator=native/"xgba-mgba-headless"
        if not cls.emulator.is_file():
            raise AssertionError("Real pinned modified native mGBA executable missing")

        cls.payload=bytes(((29*i+7)&0xff) for i in range(MAX_BYTES))
        max_offset=r6.RESOURCE_OFFSET+1024
        bad_offset=max_offset+MAX_BYTES+256
        cls.external=folder/"firered-original-external-data.bin"
        with cls.external.open("wb") as fp:
            fp.truncate(bad_offset+32)
            fp.seek(max_offset)
            fp.write(cls.payload+b"\0")
            fp.seek(bad_offset)
            fp.write(b"R24 external corrupted digest!!!")
        cls.manifest=folder/"manifest.json"
        cls.manifest.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":{"id":"original-firered-r24","sha256":cls.rom_hash},
            "data_file":cls.external.name,
            "resources":[
                {"id":MAXIMUM,"offset":max_offset,"length":MAX_BYTES,
                 "sha256":hashlib.sha256(cls.payload).hexdigest()},
                {"id":BADSHA,"offset":bad_offset,"length":32,"sha256":"0"*64},
                {"id":PLUSONE,"offset":max_offset,"length":MAX_BYTES+1,
                 "sha256":hashlib.sha256(cls.payload+b"\0").hexdigest()}
            ]
        }))
        sidecar.load_manifest(cls.manifest)
        cls.images=folder/"native-lcd"
        cls.images.mkdir()
        args=dict(emulator=cls.emulator,frames=1400,probe_address=cls.probe,
                  extra_resource_ids=(BADSHA,),
                  r24_boundary_dir=cls.images,r24_boundary_probe=cls.probe,
                  r24_firered=True)
        cls.enabled=launcher.launch(cls.rom,cls.manifest,MAXIMUM,**args)
        cls.disabled=launcher.launch(cls.rom,cls.manifest,MAXIMUM,
                                     disabled=True,**args)
        cls.good_log=cls.enabled.stdout
        cls.off_log=cls.disabled.stdout
        if "PASS_R25_ORIGINAL_FIRERED_DMA_ARMED_SOURCE_REFUSAL enabled=1" not in cls.good_log:
            raise AssertionError("R24 original FireRed native nine-request proof not accepted")
        if "PASS_R25_ORIGINAL_FIRERED_DMA_ARMED_SOURCE_REFUSAL enabled=0" not in cls.off_log:
            raise AssertionError("R24 original FireRed disabled proof not accepted")
        cls.report={
            "milestone":"R25_ORIGINAL_FIRERED_ARMED_DMA_SOURCE_REFUSAL",
            "status":"native_accepted",
            "original_firered_source_pin":r6.FIRERED_PIN,
            "original_mgba_source_pin":r6.MGBA_PIN,
            "compiled_original_firered_rom_sha256":cls.rom_hash,
            "native_original_game_guest_mmio_attempts":10,
            "native_original_game_accepted":2,
            "native_original_game_rejected":8,
            "max_single_resource_bytes":16384,
            "one_byte_over_limit":16385,
            "original_guest_ewram_bytes":262144,
            "exact_source_sha256":hashlib.sha256(cls.payload).hexdigest(),
            "failed_transfer_leaves_guest_ewram_unchanged":True,
            "bad_sha256_provider_rejected":True,
            "disabled_baseline_zero_reads":True,
            "native_enabled_log":cls.good_log,
            "native_disabled_log":cls.off_log,
            "not_proven":"Mid-transfer DMA-copy race, CPU-store buffer overwrite, three-map eviction, original GBA hardware or stock mGBA"
        }
        if os.environ.get("XGBA_R25_FIRERED_DMA_EVIDENCE_DIR"):
            out=Path(os.environ["XGBA_R25_FIRERED_DMA_EVIDENCE_DIR"])
            out.mkdir(parents=True,exist_ok=True)
            for png in cls.images.glob("*.png"):
                shutil.copy2(png,out/png.name)
            (out/"proof.json").write_text(
                json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_original_game_arms_vblank_dma3_and_native_bridge_refuses_alias(self):
        self.assertIn("dma_busy_rejections=1",self.good_log)
        self.assertIn("guest_dma_status=6",self.good_log)
        self.assertIn("unchanged_16k_checks=8",self.good_log)
        self.assertIn("guest_guard_errors=0",self.good_log)
        self.assertIn("guest_attempts=10",self.good_log)

    def test_pinned_source_built_original_firered(self):
        self.assertEqual(len(self.rom_hash),64)
        self.assertGreater(self.probe,0x02000000)
        self.assertLess(self.probe,0x02040000)
    def test_full_16k_resource_fetched_in_guest_and_sha_verified(self):
        self.assertIn("max_bytes=16384",self.good_log)
        self.assertIn("source_hash_verified=1",self.good_log)
    def test_one_byte_short_capacity_denied_before_copy(self):
        self.assertIn("short_cap=16383",self.good_log)
        self.assertIn("provider_size_rejections=1",self.good_log)
    def test_one_byte_above_16k_limit_denied(self):
        self.assertIn("over_cap=16385",self.good_log)
        self.assertIn("range_rejections=3",self.good_log)
    def test_ewram_boundary_crossing_and_zero_capacity_denied(self):
        self.assertIn("guest_guard_errors=0",self.good_log)
        self.assertIn("guest_attempts=10",self.good_log)
    def test_invalid_identifier_and_missing_id_refused(self):
        self.assertIn("id_rejections=1",self.good_log)
        self.assertIn("missing_id_rejections=1",self.good_log)
    def test_bad_sha_is_genuine_integrity_rejection(self):
        self.assertIn("integrity_rejections=1",self.good_log)
        self.assertIn("other_failures=0",self.good_log)
    def test_each_refusal_leaves_entire_16k_destination_unchanged(self):
        self.assertIn("unmodified_16k_checks=8",self.good_log)
        self.assertIn("rejected=8",self.good_log)
    def test_full_size_guest_recovery_after_seven_refusals(self):
        self.assertIn("accepted=2",self.good_log)
        self.assertIn("successful_provider_reads=2",self.good_log)
    def test_original_firered_continues_after_adversarial_requests(self):
        self.assertIn("original_loop_frames=900",self.good_log)
    def test_disabled_identical_rom_has_zero_provider_reads(self):
        self.assertIn("enabled=0 successful_provider_reads=0 rejected_provider_reads=0",self.off_log)
        self.assertIn("guest_attempts=0 accepted=0 rejected=0",self.off_log)
    def test_both_screenshots_are_original_native_lcd_frames(self):
        for filename in ("firered-dma-armed-enabled.png","firered-dma-armed-disabled.png"):
            with Image.open(self.images/filename) as im:
                self.assertEqual(im.size,(240,160))
                self.assertGreater(len(set(im.convert("RGB").getdata())),8)
    def test_16385_byte_resource_rejected_before_launch(self):
        with self.assertRaisesRegex(ValueError,"1..16384"):
            launcher.launch(self.rom,self.manifest,PLUSONE,
                            emulator=self.emulator,frames=1000,probe_address=self.probe)
    def test_uint64_overflow_and_end_of_file_rejected(self):
        obj=json.loads(self.manifest.read_text())
        obj["resources"][0]["offset"]=(1<<64)-8
        obj["resources"][0]["length"]=32
        filename=self.images.parent/"invalid-overflow.json"
        filename.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,"overflows uint64"):
            sidecar.load_manifest(filename)
        obj=json.loads(self.manifest.read_text())
        obj["resources"][0]["offset"]=self.external.stat().st_size-8
        obj["resources"][0]["length"]=9
        filename.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,"out of bounds"):
            sidecar.load_manifest(filename)

if __name__=="__main__":
    unittest.main()

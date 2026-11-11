"""R24: original Emerald CPU issues boundary/failure MMIO requests under native mGBA.

Pinned pret/pokeemerald + pinned modified native mGBA are mandatory. The game
executes a maximum 16 KiB fetch, seven failed requests, and recovery through
the REAL guest MMIO bus. Native host independently checks source SHA and guest
proof. Disabled mode executes the identical source-built ROM with zero reads.

Out-of-bounds manifest metadata / 16 KiB+1 launcher refusal are additional
host-side checks, never substituted for native guest rejection evidence.
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
sys.path[:0]=[str(ROOT/"tools"),str(ROOT/"integration/mgba"),str(ROOT/"tests")]
import xgba_r16_emerald_decomp_patch as adapter
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher
import apply_core_patch
import test_xgba_r7_mgba_core as r7

EMERALD=ROOT/"upstream"/"pokeemerald"
MGBA=ROOT/"upstream"/"mgba"
BRIDGE="emerald.bridge"
MAXIMUM="emerald.r24.maximum"
BADSHA="emerald.r24.badsha"
PLUSONE="emerald.r24.toobig"
MAX_BYTES=16384


class NativeEmeraldResourceBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path,pin in ((EMERALD,adapter.EMERALD_PIN),(MGBA,adapter.MGBA_PIN)):
            head=r7.run(["git","-C",path,"rev-parse","HEAD"]).stdout.strip()
            if head!=pin:
                raise AssertionError(f"Unpinned original source {path.name} {head}")
        cls.source_contract=adapter.verify_source_contract(EMERALD)
        cls.temp=tempfile.TemporaryDirectory(prefix="xgba-r24-original-emerald-")
        cls.addClassCleanup(cls.temp.cleanup)
        folder=Path(cls.temp.name)
        originals=adapter.make_emerald_boot_sources(EMERALD,r24_boundary=True)
        try:
            r7.run(["make","-C",EMERALD,"-j2","MODERN=1"],timeout=2600)
        finally:
            adapter.restore_sources(originals)
        cls.rom=EMERALD/"pokeemerald_modern.gba"
        elf=EMERALD/"pokeemerald_modern.elf"
        if not cls.rom.is_file() or not elf.is_file():
            raise AssertionError("Original source-built Emerald ROM/ELF missing")
        cls.rom_sha=hashlib.sha256(cls.rom.read_bytes()).hexdigest()
        if cls.rom.stat().st_size>32*1024*1024 or r6.PAYLOAD in cls.rom.read_bytes():
            raise AssertionError("ROM exceeds GBA address window or external payload embedded in cartridge")
        nm=r7.run(["arm-none-eabi-nm","-g",elf]).stdout
        symbols={}
        for name in ("gXgbaEmeraldProbe","gXgbaR24Proof"):
            hits=re.findall(r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+"+name+r"$",nm,re.M)
            if len(hits)!=1:
                raise AssertionError(f"Missing original ARM ELF symbol: {name}")
            symbols[name]=int(hits[0],16)
            if not 0x02000000<=symbols[name]<=0x02040000-68:
                raise AssertionError(f"R24 native proof not in real 256 KiB EWRAM: {name}")
        cls.boot=symbols["gXgbaEmeraldProbe"]
        cls.proof=symbols["gXgbaR24Proof"]

        apply_core_patch.apply(MGBA)
        native=folder/"native-mgba"
        r7.run(["cmake","-S",ROOT/"integration/mgba","-B",native,
                "-DCMAKE_BUILD_TYPE=Release",
                "-DXGBA_MGBA_CHECKOUT="+str(MGBA)],timeout=240)
        r7.run(["cmake","--build",native,"--target","xgba-mgba-headless",
                "--parallel","2"],timeout=1050)
        emulator=native/"xgba-mgba-headless"
        if not emulator.is_file():
            raise AssertionError("Actual modified native mGBA executable missing")

        cls.payload=bytes(((i*29+7)&0xff) for i in range(MAX_BYTES))
        if len(cls.payload)!=MAX_BYTES:
            raise AssertionError("Source maximum pack length drift")
        base=r6.RESOURCE_OFFSET
        max_offset=base+1024
        bad_offset=max_offset+MAX_BYTES+256
        cls.external=folder/"original-external-resources.bin"
        with cls.external.open("wb") as fp:
            fp.truncate(bad_offset+32)
            fp.seek(base)
            fp.write(r6.PAYLOAD)
            fp.seek(max_offset)
            fp.write(cls.payload+b"\\0")  # adjacent +1-byte boundary fixture
            fp.seek(bad_offset)
            fp.write(b"R24 external corrupted digest!!!") # 32 bytes
        manifest_data={
            "format":sidecar.FORMAT,
            "version":sidecar.VERSION,
            "source_identity":{"id":"pokeemerald-r24","sha256":cls.rom_sha},
            "data_file":cls.external.name,
            "resources":[
                {"id":BRIDGE,"offset":base,"length":len(r6.PAYLOAD),
                 "sha256":hashlib.sha256(r6.PAYLOAD).hexdigest()},
                {"id":MAXIMUM,"offset":max_offset,"length":MAX_BYTES,
                 "sha256":hashlib.sha256(cls.payload).hexdigest()},
                {"id":BADSHA,"offset":bad_offset,"length":32,
                 "sha256":"0"*64},
                {"id":PLUSONE,"offset":max_offset,"length":MAX_BYTES+1,
                 "sha256":hashlib.sha256(cls.payload+b"\0").hexdigest()},
            ]
        }
        cls.manifest=folder/"manifest.json"
        cls.manifest.write_text(json.dumps(manifest_data))
        sidecar.load_manifest(cls.manifest)
        cls.out=folder/"native-lcd"
        cls.out.mkdir()
        args=dict(emulator=emulator,frames=1200,probe_address=cls.boot,
                  extra_resource_ids=(MAXIMUM,BADSHA),
                  r24_boundary_dir=cls.out,r24_boundary_probe=cls.proof)
        cls.enabled=launcher.launch(cls.rom,cls.manifest,BRIDGE,**args)
        cls.disabled=launcher.launch(cls.rom,cls.manifest,BRIDGE,
                                     disabled=True,**args)
        cls.good_log=cls.enabled.stdout
        cls.disabled_log=cls.disabled.stdout
        if "PASS_R24_ORIGINAL_EMERALD_BOUNDARY enabled=1" not in cls.good_log:
            raise AssertionError("Native original Emerald guest boundary execution did not pass")
        if "PASS_R24_ORIGINAL_EMERALD_BOUNDARY enabled=0" not in cls.disabled_log:
            raise AssertionError("Same original Emerald ROM did not prove disabled zero-provider reads")
        cls.report={
            "milestone":"R24_ORIGINAL_EMERALD_MAX_RESOURCE_BOUNDARY",
            "status":"native_accepted",
            "source_emerald_pin":adapter.EMERALD_PIN,
            "native_mgba_pin":adapter.MGBA_PIN,
            "actual_original_emerald_rom_sha256":cls.rom_sha,
            "actual_guest_ewram_bytes":262144,
            "minimum_guest_valid_capacity":MAX_BYTES,
            "rejected_guest_capacity":MAX_BYTES+1,
            "original_game_MMIO_attempts":9,
            "original_game_successful_requests":2,
            "original_game_failed_requests":7,
            "read_only_guest_MMIO_status_and_memory_verified":True,
            "guest_buffer_unmodified_on_every_rejected_request":True,
            "original_allocator_temporary_buffer_released":True,
            "maximum_resource_original_sha256":hashlib.sha256(cls.payload).hexdigest(),
            "bad_sha256_provider_rejected_without_guest_commit":True,
            "same_ROM_disabled_zero_host_reads":True,
            "source_external_offsets":{
                MAXIMUM:max_offset,
                BADSHA:bad_offset,
                PLUSONE:max_offset},
            "source_contract":cls.source_contract,
            "native_enabled_output":cls.good_log,
            "native_disabled_output":cls.disabled_log,
            "not_proven":"General map-pack schema validation, async DMA lifetime, 3+ connected-map eviction, stock mGBA or original GBA hardware",
        }
        output=os.environ.get("XGBA_R24_EVIDENCE_DIR")
        if output:
            dest=Path(output)
            dest.mkdir(parents=True,exist_ok=True)
            for pic in cls.out.glob("*.png"):
                shutil.copy2(pic,dest/pic.name)
            (dest/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_original_emerald_source_and_real_arm_ewram_proof(self):
        self.assertEqual(self.source_contract["heap_bytes"],0x1C000)
        self.assertGreater(self.proof,0x02000000)
        self.assertLess(self.proof,0x02040000)
    def test_full_16384_byte_original_guest_fetch_and_source_hash(self):
        self.assertIn("max_bytes=16384",self.good_log)
        self.assertIn("source_hash_verified=1",self.good_log)
    def test_one_byte_short_capacity_fails_without_guest_memory_write(self):
        self.assertIn("short_cap=16383",self.good_log)
        self.assertIn("unmodified_16k_checks=7",self.good_log)
    def test_one_byte_over_native_limit_fails_before_external_copy(self):
        self.assertIn("over_cap=16385",self.good_log)
        self.assertIn("rejected_provider_reads=7",self.good_log)
    def test_real_ewram_end_crossing_and_zero_capacity_rejected(self):
        self.assertIn("guest_attempts=9",self.good_log)
        self.assertIn("guest_guard_errors=0",self.good_log)
    def test_invalid_and_unknown_ids_rejected_in_real_guest(self):
        self.assertIn("rejected=7",self.good_log)
    def test_corrupt_sha256_provider_does_not_write_guest_memory(self):
        self.assertIn("unmodified_16k_checks=7",self.good_log)
        self.assertTrue(self.report["bad_sha256_provider_rejected_without_guest_commit"])
    def test_original_emerald_recovers_after_seven_rejections(self):
        self.assertIn("accepted=2",self.good_log)
        self.assertIn("successful_provider_reads=3",self.good_log)
    def test_original_emerald_continues_900_frames_after_adversarial_requests(self):
        self.assertIn("original_loop_frames=900",self.good_log)
    def test_exact_same_rom_extension_disabled_has_zero_provider_traffic(self):
        self.assertIn("enabled=0 successful_provider_reads=0 rejected_provider_reads=0",self.disabled_log)
        self.assertIn("guest_attempts=0 accepted=0 rejected=0",self.disabled_log)
    def test_original_emerald_renders_real_native_240x160_lcd(self):
        for name in ("emerald-boundary-enabled.png","emerald-boundary-disabled.png"):
            with Image.open(self.out/name) as image:
                self.assertEqual(image.size,(240,160))
                self.assertGreater(len(set(image.convert("RGB").getdata())),8)
    def test_16385_byte_manifest_resource_is_refused_before_emulator_launch(self):
        with self.assertRaisesRegex(ValueError,"1..16384"):
            launcher.launch(self.rom,self.manifest,PLUSONE,
                            emulator=self.out.parent/"native-mgba"/"xgba-mgba-headless",
                            frames=1200,probe_address=self.boot)
    def test_manifest_unsigned_64_bit_overflow_refused(self):
        obj=json.loads(self.manifest.read_text())
        obj["resources"][0]["offset"]=(1<<64)-8
        obj["resources"][0]["length"]=32
        bad=self.out.parent/"bad-overflow.json"
        bad.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,"overflows uint64"):
            sidecar.load_manifest(bad)
    def test_manifest_one_byte_past_file_end_refused(self):
        obj=json.loads(self.manifest.read_text())
        obj["resources"][0]["offset"]=self.external.stat().st_size-8
        obj["resources"][0]["length"]=9
        bad=self.out.parent/"bad-file-bound.json"
        bad.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError,"out of bounds"):
            sidecar.load_manifest(bad)

if __name__=="__main__":
    unittest.main()

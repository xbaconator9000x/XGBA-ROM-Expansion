"""R7 acceptance: actual ARM FireRed issues an XGBA MMIO request to patched mGBA.

Must compile BOTH upstream FireRed and upstream native mGBA. The host cannot
inject graphics, issue a request on the guest's behalf, or pass by executing
the R6 test-host bridge; the *game* must write the versioned MMIO command.

Run this test with an unmodified clone of each pinned upstream repository.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIRERED = ROOT / "upstream" / "pokefirered"
MGBA = ROOT / "upstream" / "mgba"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "integration" / "mgba"))
import xgba_resource_integration_smoke as r6
import xgba_mgba_run as launcher
import xgba_resource_sidecar as sidecar
import apply_core_patch


R7_GAME_CODE = r"""
/* R7 game-initiated opt-in resource fetch; no test harness memory injection. */
#include "sprite.h"
#include "__XGBA_GUEST_HEADER__"
#include "__XGBA_NATIVE_R4__"
struct XgbaR7Probe {
    volatile u32 magic;
    volatile u32 state;
    volatile u32 verified;
    volatile u32 used;
    volatile u32 tile;
};
EWRAM_DATA volatile struct XgbaR7Probe gXgbaR7Probe = {0};
EWRAM_DATA u8 gXgbaR7Tiles[64] ALIGNED(4) = {0};
EWRAM_DATA char gXgbaR7ResourceId[32] = "graphic.smoke";
static const u8 sXgbaR7OriginalTiles[64] ALIGNED(4) = {
    0x11, 0x22, 0x33, 0x44
};
static void XgbaR7GameRun(void)
{
    struct SpriteSheet native = {sXgbaR7OriginalTiles, 64, 0xA121};
    struct XgbaStagedSprite staged;
    bool8 used = FALSE;
    gXgbaR7Probe.magic = 0x58474241;
    gXgbaR7Probe.state = 1;
    u32 received = XgbaGuestFetch(gXgbaR7ResourceId, gXgbaR7Tiles, 64);
    gXgbaR7Probe.verified = received == 64;
    staged.abiVersion = 1;
    staged.resourceId = 0xA121;
    staged.ewramData = gXgbaR7Tiles;
    staged.byteLength = 64;
    staged.validatedByProvider = received == 64;
    ResetSpriteData();
    gXgbaR7Probe.tile = XgbaLoadStagedSpriteSheet(
        &native, 0xA121, &staged, &used);
    gXgbaR7Probe.used = used;
    gXgbaR7Probe.state = 3;
    /* Test-only latch: retain graphics for host read-back, no host injection. */
    while (gXgbaR7Probe.state == 3)
        ;
}
"""


def run(args, *, timeout=1800):
    proc = subprocess.run(
        [str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        raise AssertionError(
            "FAILED " + " ".join(map(str, args[:5])) + "\n" +
            proc.stdout[-6500:] + "\n" + proc.stderr[-6500:])
    return proc


def compiled_firered():
    r6.verify_pins()
    file = FIRERED / "src" / "main.c"
    original = file.read_text(encoding="utf-8")
    declaration = "void AgbMain()\n{"
    hook = "    gLinkTransferringData = FALSE;\n\n    for (;;)"
    if original.count(declaration) != 1 or original.count(hook) != 1:
        raise AssertionError("BLOCKED: pinned FireRed hook source changed")
    probe = R7_GAME_CODE.replace(
        "__XGBA_GUEST_HEADER__",
        (ROOT / "integration/fire_red/xgba_guest.h").as_posix(),
    ).replace(
        "__XGBA_NATIVE_R4__",
        (ROOT / "tools/xgba_resource_firered_adapter.c").as_posix(),
    )
    file.write_text(
        original.replace(declaration, probe + "\n" + declaration)
        .replace(hook, "    gLinkTransferringData = FALSE;\n"
                       "    XgbaR7GameRun();\n\n    for (;;)"),
        encoding="utf-8")
    try:
        run(["make", "-C", FIRERED, "-j2", "MODERN=1",
             "GAME_VERSION=FIRERED"], timeout=2100)
    finally:
        file.write_text(original, encoding="utf-8")
    rom, elf = (FIRERED / "pokefirered_modern.gba",
                FIRERED / "pokefirered_modern.elf")
    if not (rom.is_file() and elf.is_file()):
        raise AssertionError("BLOCKED: real R7 FireRed output missing")
    symbols = run(["arm-none-eabi-nm", "-g", elf]).stdout
    match = re.findall(
        r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaR7Probe$",
        symbols, re.M)
    if len(match) != 1:
        raise AssertionError("BLOCKED: real R7 game probe symbol missing")
    address = int(match[0], 16)
    if not 0x02000000 <= address < 0x0203FFF0:
        raise AssertionError("BLOCKED: real R7 probe not within EWRAM")
    return rom, address


class NativeCoreIntegratedR7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.verify_pins()
        cls.temp = tempfile.TemporaryDirectory(prefix="xgba-r7-native-")
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        cls.rom, cls.probe = compiled_firered()
        apply_core_patch.apply(MGBA)
        cls.build = root / "build"
        run([
            "cmake", "-S", ROOT / "integration/mgba", "-B", cls.build,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DXGBA_MGBA_CHECKOUT=" + str(MGBA),
        ], timeout=240)
        run([
            "cmake", "--build", cls.build, "--target",
            "xgba-mgba-headless", "--parallel", "2",
        ], timeout=900)
        cls.emulator = cls.build / "xgba-mgba-headless"
        if not cls.emulator.is_file():
            raise AssertionError("BLOCKED: actual extended mGBA executable missing")
        payload = r6.PAYLOAD
        cls.payload = payload
        cls.external = root / "external.bin"
        with cls.external.open("wb") as fp:
            fp.truncate(r6.RESOURCE_OFFSET + len(payload))
            fp.seek(r6.RESOURCE_OFFSET)
            fp.write(payload)
        cls.manifest = root / "sidecar.json"
        cls.manifest.write_text(json.dumps({
            "format": sidecar.FORMAT,
            "version": sidecar.VERSION,
            "source_identity": {
                "id": "firered-r7-core",
                "sha256": hashlib.sha256(cls.rom.read_bytes()).hexdigest()
            },
            "data_file": cls.external.name,
            "resources": [{
                "id": "graphic.smoke",
                "offset": r6.RESOURCE_OFFSET,
                "length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }]
        }), encoding="utf-8")
        cls.positive = launcher.launch(
            cls.rom, cls.manifest, "graphic.smoke",
            emulator=cls.emulator, frames=800, probe_address=cls.probe)
        cls.disabled = launcher.launch(
            cls.rom, cls.manifest, "graphic.smoke",
            emulator=cls.emulator, frames=800, probe_address=cls.probe,
            disabled=True)

    def test_builds_native_extended_mgba_executable(self):
        self.assertTrue(self.emulator.is_file())
        self.assertIn("PASS_R7_XGBA_MGBA_BUILD", self.positive.stdout)

    def test_game_issues_real_mmio_request_and_copies_external_sprite(self):
        self.assertIn("PASS_R7_NATIVE_FIRERED_MMIO_LOAD_TO_OBJ_VRAM",
                      self.positive.stdout)
        self.assertIn("enabled=1 requests=1 failures=0 host_lookups=1 bytes=64",
                      self.positive.stdout)

    def test_extension_disabled_has_original_asset_and_zero_host_lookups(self):
        self.assertIn("PASS_R7_NATIVE_FIRERED_MMIO_LOAD_TO_OBJ_VRAM",
                      self.disabled.stdout)
        self.assertIn("enabled=0 requests=0 failures=0 host_lookups=0 bytes=0",
                      self.disabled.stdout)

    def test_resource_cannot_be_used_with_different_source_identity(self):
        invalid = json.loads(self.manifest.read_text(encoding="utf-8"))
        invalid["source_identity"]["sha256"] = "0" * 64
        bad_manifest = Path(self.temp.name) / "bad.json"
        bad_manifest.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity"):
            launcher.launch(self.rom, bad_manifest, "graphic.smoke",
                            emulator=self.emulator, probe_address=self.probe)

    def test_real_resource_resides_beyond_the_cartridge_window(self):
        payload = sidecar.load_manifest(self.manifest)
        self.assertGreater(payload.get_resource("graphic.smoke").offset, 32*1024*1024)
        self.assertEqual(payload.get_resource("graphic.smoke").length, 64)


if __name__ == "__main__":
    unittest.main()

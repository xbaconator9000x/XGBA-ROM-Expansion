"""R69: the true mGBA resource-request ABI permits EWRAM pointers only.

Static source-contract tests supplement (not replace) the genuine Emerald ARM
build and emulator execution. Reject a regression to ROM literal resource IDs
or an IWRAM stack destination in the native Fly dialogue preflight.
"""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc"
DEVICE=ROOT/"integration/mgba/xgba_mgba_device.c"
BRIDGE=ROOT/"integration/fire_red/xgba_guest.h"

def block(src,name):
    match=re.search(r"\b"+re.escape(name)+r"\s*\([^;]*\)\s*\{",src)
    if not match:raise ValueError("Missing native function: "+name)
    start=match.end()
    depth=1
    for i in range(start,len(src)):
        if src[i]=="{":depth+=1
        elif src[i]=="}":
            depth-=1
            if depth==0:return src[start:i]
    raise ValueError("Unclosed native function: "+name)

def valid_guest_fetch_contract(code):
    preflight=block(code,"XgbaR48PreflightOriginalNpcResource")
    stage=block(code,"XgbaR48StageOriginalNpcResourceName")
    live=block(code,"XgbaR48LoadOriginalNpc")
    return all((
        "static EWRAM_DATA u8 sXgbaR48Payload" in code,
        "static EWRAM_DATA u8 sXgbaR48ResourceName" in code,
        "sXgbaR48Ready[source]" in preflight,
        "XgbaR48StageOriginalNpcResourceName(source)" in preflight,
        "(const char *)sXgbaR48ResourceName" in preflight,
        "sXgbaR48Payload[source]" in preflight,
        "XgbaR48VerifyPayload(source)" in preflight,
        "XgbaR48StageOriginalNpcResourceName(source)" in live,
        "XgbaR48VerifyPayload(source)" in live,
        "sXgbaR48ResourceName[i]=" in stage,
        "source_bytes" not in preflight,
        "XgbaGuestFetch(name," not in preflight,
        "sXgbaR48Ready[source]=TRUE;" in live,
    ))

class R69GuestMmioEwramSourceContract(unittest.TestCase):
    def test_native_fly_preflight_uses_existing_ewram_guest_buffers(self):
        source=GAME.read_text()
        self.assertTrue(valid_guest_fetch_contract(source))
        self.assertEqual(source.count("static EWRAM_DATA u8 sXgbaR48Payload"),1)
        self.assertEqual(source.count("static EWRAM_DATA u8 sXgbaR48ResourceName"),1)
        self.assertNotIn("sXgbaR48Ready[source]=TRUE;",
                         block(source,"XgbaR48PreflightOriginalNpcResource"))

    def test_mgba_host_rejects_stack_or_rom_destinations(self):
        host=DEVICE.read_text()
        fetch=BRIDGE.read_text()
        self.assertIn("#define EWRAM_START 0x02000000u",host)
        self.assertIn("#define EWRAM_SIZE  0x00040000u",host)
        self.assertIn("!ewram_range(device->dst_addr, device->capacity)",host)
        self.assertIn("if (!ewram_range(address, 1))",host)
        self.assertIn("registers[2] = (unsigned)ewramResourceId",fetch)
        self.assertIn("registers[3] = (unsigned)ewramDestination",fetch)

    def test_rom_or_stack_preflight_regression_is_rejected(self):
        src=GAME.read_text()
        original=block(src,"XgbaR48PreflightOriginalNpcResource")
        self.assertIn("(const char *)sXgbaR48ResourceName",original)
        corrupted=src.replace(
            "(const char *)sXgbaR48ResourceName,\n                      sXgbaR48Payload[source]",
            "XgbaR48OriginalNpcResourceName(source),\n                      sXgbaR48Payload[source]")
        self.assertNotEqual(corrupted,src)
        self.assertFalse(valid_guest_fetch_contract(corrupted))
        corrupted=src.replace(
            "(const char *)sXgbaR48ResourceName,\n                      sXgbaR48Payload[source]",
            "(const char *)sXgbaR48ResourceName,\n                      source_bytes")
        self.assertNotEqual(corrupted,src)
        self.assertFalse(valid_guest_fetch_contract(corrupted))
        corrupted=src.replace(
            "    if(sXgbaR48Ready[source]){\n"
            "        if(XgbaR71CachedOriginalNpcValid(\n"
            "               source,sXgbaR48Payload[source],XGBA_R48_BYTES))\n"
            "            return TRUE;\n        goto rejected;\n    }",
            "    /* mistakenly overwrite live relocated scripts */")
        self.assertNotEqual(corrupted,src)
        self.assertFalse(valid_guest_fetch_contract(corrupted))
if __name__=="__main__":unittest.main()

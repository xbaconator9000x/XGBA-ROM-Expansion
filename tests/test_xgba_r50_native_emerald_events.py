"""R50 exact native source-built original Emerald map-event hook acceptance.

This compiles the REAL Emerald MapHeader/GetMapLayout/CB2_Overworld and
physical A-button R48 bridge, verifies original boot/Flash save and guest
EWRAM proof. NO private foreign-ROM data are published in CI, and this
is NOT proof that original foreign NPC/Fly gameplay has completed.
"""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_xgba_r48_native_emerald_npc_bridge import SourceBuiltEmeraldOriginalNpcBridge as R48

class NativeEmeraldR50OriginalEngineEventHooks(R48):
    R50_ENGINE_EVENT_TEST=True

    def test_real_original_emeraldoverworld_has_r50_event_bridge(self):
        symbols=self.r14.symbols(self.elf) if hasattr(self,"r14") else None
        # The runner's real ELF symbol reader, not an authored source grep.
        import test_xgba_r17_emerald_external_map as r17
        symbols=r17.r14.symbols(self.elf)
        self.assertIn("gXgbaR50BridgeProof",symbols)
        address=symbols["gXgbaR50BridgeProof"][0]
        self.assertTrue(0x02000000<=address<0x02040000)
        self.assertIn("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE",self.log)

    def test_no_unverified_real_foreign_fly_claim(self):
        import test_xgba_r17_emerald_external_map as r17
        syms=r17.r14.symbols(self.elf)
        self.assertIn("gXgbaR48OriginalNpcProof",syms)
        self.assertIn("gXgbaR50BridgeProof",syms)
        self.assertNotIn("PASS_R50_FOREIGN_FLY_COMPLETE",self.log)
        self.assertNotIn("PASS_R50_FOREIGN_NPC_TALK",self.log)

if __name__=="__main__":
    unittest.main()

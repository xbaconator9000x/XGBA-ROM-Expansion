"""R71: original NPC source CRC and cached relocated script integrity wiring."""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
NPC=(ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc").read_text()
HEADER=(ROOT/"integration/common/xgba_r71_original_script_cache_integrity.h").read_text()
class R71CachedScriptIntegrity(unittest.TestCase):
    def test_private_source_authenticated_crc_identifiers(self):
        for crc in ("0x3ee29fb3","0xdc79ff6b","0xfa898797"):
            self.assertIn(crc,HEADER)
        self.assertIn("XgbaR71OriginalNpcPacketValid(",NPC)
        self.assertIn("XgbaR71CachedOriginalNpcValid(",NPC)
        self.assertIn("XgbaR71OriginalTextPointer(world)",HEADER)
        self.assertIn("p+XGBA_R71_SCRIPT_TEXT_OFF",HEADER)
        self.assertIn("if(relocated && i>=XGBA_R71_TEXT_PTR_OFF",HEADER)
        self.assertNotIn("EWRAM_DATA",HEADER)
    def test_live_preflight_and_execution_both_verify_cached_ewram(self):
        self.assertGreaterEqual(NPC.count("XgbaR71CachedOriginalNpcValid("),3)
        self.assertIn("XgbaR71CachedOriginalNpcValid(\n               source,sXgbaR48Payload[source],XGBA_R48_BYTES)",NPC)
        self.assertIn("XgbaR71OriginalNpcPacketValid(\n        source,sXgbaR48Payload[source],XGBA_R48_BYTES)",NPC)
        self.assertIn("if(!XgbaR71CachedOriginalNpcValid(",NPC)
        self.assertNotRegex(NPC,r"if\(sXgbaR48Ready\[source\]\)\s*return TRUE;")
if __name__=="__main__":unittest.main()

"""R74: ALL original-guest R49/R51/R52/R53 MMIO ID pointers must live in EWRAM.

R69 already secured original NPC dialogue MMIO. R74 extends that hardware
requirement to the data pagers, reusing R48's existing EWRAM resource ID.
Static checks complement, not replace, actual Emerald ARM/mGBA execution.
"""
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
FILES={
 "r49":"integration/emerald/xgba_r50_original_engine_events.inc",
 "r51":"integration/emerald/xgba_r51_original_terrain.inc",
 "r52":"integration/emerald/xgba_r52_native_source_layout.inc",
 "r53":"integration/emerald/xgba_r53_original_graphics.inc",
}
class R74GuestMmioSourcePagerContract(unittest.TestCase):
 def test_shared_id_is_ewram_and_validated(self):
  r48=(ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc").read_text()
  self.assertEqual(r48.count("static EWRAM_DATA u8 sXgbaR48ResourceName"),1)
  self.assertIn("static bool8 XgbaR48StagePagedResourceName(const char *name)",r48)
  self.assertIn("sizeof(sXgbaR48ResourceName)",r48)
  self.assertIn("sXgbaR48ResourceName[i]=0u;",r48)
  self.assertIn("if(i==0u || name[i])return FALSE;",r48)
 def test_all_original_guest_page_callbacks_stage_ewram(self):
  for name,path in FILES.items():
   with self.subTest(resource=name):
    s=(ROOT/path).read_text()
    self.assertIn("XgbaR48StagePagedResourceName(",s)
    self.assertIn("XgbaGuestFetch((const char *)sXgbaR48ResourceName,",s)
    self.assertNotIn("XgbaGuestFetch(id,",s)
    self.assertNotIn("XgbaGuestFetch(name,",s)
    self.assertNotRegex(s,r"static EWRAM_DATA (?:u8|char) .*ResourceName")
 def test_direct_guest_resource_reads_are_pinned_to_ewram(self):
  guest=(ROOT/"integration/fire_red/xgba_guest.h").read_text()
  device=(ROOT/"integration/mgba/xgba_mgba_device.c").read_text()
  self.assertIn("registers[2] = (unsigned)ewramResourceId",guest)
  self.assertIn("if (!ewram_range(address, 1))",device)
  self.assertIn("!ewram_range(device->dst_addr, device->capacity)",device)
  guest_r51=(ROOT/"integration/emerald/xgba_r51_original_terrain.inc").read_text()
  self.assertIn("reader.scratch=(u8 *)gXgbaR17Arena",guest_r51)
if __name__=="__main__":unittest.main()

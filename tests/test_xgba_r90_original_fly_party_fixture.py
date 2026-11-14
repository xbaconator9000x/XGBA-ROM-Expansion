"""R90 original Emerald capability-test Fly readiness, no teleport shortcuts."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r90_original_fly_party_fixture as r90

class NativeFlyPartyFixtureTests(unittest.TestCase):
 def test_opt_in_only_and_exact_native_pokemon_apis(self):
  s=(ROOT/"tools/xgba_r17_emerald_patch.py").read_text()
  self.assertIn("if r90_fly_fixture:",s)
  self.assertIn('XGBA_R90_REAL_FLY_TEST',s)
  self.assertIn('enable_original_emerald_fly_party_fixture',s)
  self.assertIn("r90_fly_fixture and not",s)
  new=(ROOT/"tests/test_xgba_r54_native_emerald_faded_warp.py").read_text()
  self.assertIn("R90_NATIVE_FLY_DEMO_TEST=True",new)
  src=(ROOT/"tools/xgba_r90_original_fly_party_fixture.py").read_text()
  self.assertIn("CreateMon(&gPlayerParty[0], SPECIES_SWELLOW",src)
  self.assertIn("SetMonMoveSlot(&gPlayerParty[0], MOVE_FLY, 0);",src)
  self.assertIn("FlagSet(FLAG_BADGE06_GET);",src)
  self.assertNotIn("SetWarpDestination(",src)
  self.assertNotIn("WarpIntoMap(",src)
  self.assertNotIn("XgbaR48QueueOriginalFly(",src)
 def test_owned_temp_source_patched_without_any_fly_warp_and_restored(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/"src"/"new_game.c";p.parent.mkdir()
   orig='#include "constants/items.h"\n'+(
      "void NewGameInitData(void) {\n    ResetContestLinkResults();\n}\n")
   p.write_text(orig)
   backups=r90.enable_original_emerald_fly_party_fixture(root)
   out=p.read_text()
   self.assertEqual(backups[p],orig)
   self.assertIn("SPECIES_SWELLOW",out)
   self.assertIn("MOVE_FLY",out)
   self.assertIn("FLAG_BADGE06_GET",out)
   self.assertIn("gPlayerPartyCount = CalculatePlayerPartyCount();",out)
   p.write_text(backups[p])
   self.assertEqual(p.read_text(),orig)
 def test_duplicate_patch_is_refused(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/"src"/"new_game.c";p.parent.mkdir()
   p.write_text('#include "constants/items.h"\nvoid NewGameInitData(void) {\n    ResetContestLinkResults();\n}')
   r90.enable_original_emerald_fly_party_fixture(root)
   with self.assertRaises(Exception):
    r90.enable_original_emerald_fly_party_fixture(root)

if __name__=="__main__":unittest.main()

"""R93 official public source HnS tests use authored stand-ins, never ROM assets."""
import json,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r93_hns_official_source as r93
class HnsPublicV206Tests(unittest.TestCase):
 def fixture(self,root):
  p=root/"data/maps/GoldenrodCity_hns/map.json";p.parent.mkdir(parents=True)
  p.write_text(json.dumps({"id":"MAP_GOLDENROD_CITY_HNS",
   "layout":"LAYOUT_GOLDENROD_CITY_HNS","object_events":[{"x":39,"y":22,
   "graphics_id":"OBJ_EVENT_GFX_BOY_2_HNS"}]}))
  p=root/"data/layouts/layouts.json";p.parent.mkdir(parents=True)
  p.write_text(json.dumps({"layouts":[{"id":"LAYOUT_GOLDENROD_CITY_HNS",
   "width":58,"height":46,"primary_tileset":r93.SETS[0][0],
   "secondary_tileset":r93.SETS[1][0],
   "blockdata_filepath":"data/layouts/GoldenrodCity_hns/map.bin"}]}))
  q=root/"data/layouts/GoldenrodCity_hns";q.mkdir(parents=True)
  (q/"map.bin").write_bytes(b"\0"*5336)
  for name,logical,secondary,prefix in r93.SETS:
   q=root/prefix;(q/"palettes").mkdir(parents=True)
   for f in ("tiles.png","metatiles.bin","metatile_attributes.bin"):
    (q/f).write_bytes(b"TEST_ONLY")
   for n in (range(7,13) if secondary else range(7)):
    (q/"palettes"/f"{n:02d}.pal").write_bytes(b"TEST_ONLY")
  q=root/"graphics/object_events/pics/people";q.mkdir(parents=True)
  (q/"boy_2_hns.png").write_bytes(b"TEST_ONLY")
 def test_official_original_goldenrod_map_and_source_asset_paths(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.fixture(p)
   x=r93.attest(p,require_git=False)
   self.assertEqual(x["size"],[58,46])
   self.assertEqual(x["npc_xy"],[39,22])
   self.assertEqual(x["commit"],r93.RELEASE)
 def test_rejects_unverified_actor_and_missing_art(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.fixture(p)
   (p/"graphics/object_events/pics/people/boy_2_hns.png").unlink()
   with self.assertRaisesRegex(r93.HnsSourceError,"NPC art"):
    r93.attest(p,require_git=False)
 def test_source_build_elf_symbol_resolution(self):
  x=r93.source_symbols("08f8823c D gTileset_Johto_General_Hns\n"+
    "08f885e4 D gTileset_Goldenrod_Hns\n")
  self.assertEqual(x["gTileset_Goldenrod_Hns"],0x08f885e4)
  self.assertEqual([v[1] for v in r93.SETS],[0xf8823c,0xf885e4])
  src=(ROOT/"tools/xgba_r93_hns_official_source.py").read_text()
  self.assertIn("r53.descriptor_asset(blob,2,2,actual,secondary)",src)
  self.assertIn('"actual_player_three_world_fly_complete":False',src)
if __name__=="__main__":unittest.main()

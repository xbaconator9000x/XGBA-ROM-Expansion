"""Author-created tests for R79 original 480-tile source retention."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r79_rocket_oversized_bg_source as m
class TestR79(unittest.TestCase):
 def fixture(self):
  # No game art in the public suite. 480 authored different 4bpp tiles.
  graphics=bytes((i*17+7)&255 for i in range(480*32))
  cells=bytearray(196*16)
  cells[0:2]=(640+341).to_bytes(2,"little")
  cells[2:4]=(640+12).to_bytes(2,"little")
  return graphics,bytes(cells)
 def test_fully_retains_original_480_source_and_native_384_window(self):
  g,c=self.fixture()
  p=m.validate_full_source_graphics(g,c,0)
  self.assertEqual(p["source_tiles"],480)
  self.assertEqual(p["native_render_tiles"],384)
  self.assertEqual(p["max_static_secondary_tile_index"],341)
  self.assertEqual(p["source_unused_tail_tiles"],96)
  records=m.native_source_meta(g,c,bytes(392),bytes(192),0x1234)
  self.assertEqual(len(records),5)
  self.assertEqual([row[0] for row in records],[m.STEM+s for s in
      (".meta",".g00",".m00",".a00",".p00")])
  self.assertEqual(len(records[1][1]),m.PAGE)
  self.assertEqual(records[1][1][:384*32],g[:384*32])
  self.assertEqual(g[384*32:],g[12288:])
 def test_rejects_source_animation_callback_and_extra_tile_refs(self):
  g,c=self.fixture()
  with self.assertRaises(m.SourceCapacityError):
   m.validate_full_source_graphics(g,c,0x0800abcd)
  # A GBA metatile stores only 10 tile-index bits: 640+384 == 1024
  # would wrap to zero. 1023 (secondary index 383) is the true ceiling.
  arr=bytearray(c);arr[0:2]=(640+383).to_bytes(2,"little")
  self.assertEqual(
   m.validate_full_source_graphics(g,bytes(arr),0)["max_static_secondary_tile_index"],383)
  with self.assertRaises(m.SourceCapacityError):
   m.validate_full_source_graphics(g[:-32],c,0)
 def test_wrong_complete_rom_sha_must_fail_before_any_output(self):
  with self.assertRaises(m.SourceCapacityError):
   m.authenticate_original_descriptor(b"not-an-original-rom")
if __name__=="__main__":unittest.main()

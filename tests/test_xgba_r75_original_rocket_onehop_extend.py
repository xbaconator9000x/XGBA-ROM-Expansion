"""R75 author-owned exact source profile/extension safety tests."""
from pathlib import Path
import sys,unittest,zlib,struct
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r75_original_rocket_onehop_extend as m
class R75PrivateOneHop(unittest.TestCase):
 def _pages(self,corrupt=False):
  rows=bytearray(2856*32)
  for i,(key,parts) in enumerate(m.ROCKET_SOURCE_MAPS.items()):
   row=bytearray(32)
   struct.pack_into("<I",row,0,key);row[4]=2
   struct.pack_into("<II",row,20,*parts)
   struct.pack_into("<I",row,28,zlib.crc32(row[:28])&0xffffffff)
   rows[i*32:i*32+32]=row
  if corrupt:rows[16]^=1
  return {f"r52.mapmeta.{i:03d}":
          bytes(rows[i*16384:(i+1)*16384]).ljust(16384,b"\0")
          for i in range(6)}
 def test_source_original_r52_descriptor_is_map_bound(self):
  pages=self._pages()
  self.assertEqual(len(m.required_rocket_tiles(pages)),4)
  self.assertEqual(m.source_map_tiles(pages,0x012302),
                   (2,0x00e9ff80,0x00e9fdd0))
  with self.assertRaises(m.PrivateOneHopError):
   m.source_map_tiles(pages,0x022302)
  pages["r52.mapmeta.000"]=bytes([0])*16384
  with self.assertRaises(m.PrivateOneHopError):
   m.required_rocket_tiles(pages)
 def test_duplicate_page_and_oversize_refused(self):
  buf=bytearray();rows=[];seen=set()
  m.add_page(buf,rows,seen,"authored.r56.f00",b"\x00")
  self.assertEqual(len(rows),1)
  with self.assertRaises(m.PrivateOneHopError):
   m.add_page(buf,rows,seen,"authored.r56.f00",b"\x01")
  with self.assertRaises(m.PrivateOneHopError):
   m.add_page(buf,rows,seen,"oversize",bytes(m.PAGE+1))
  self.assertEqual(len(rows),1)
 def test_wrong_original_rom_is_rejected_before_output(self):
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   wrong=Path(d)/"wrong.gba";wrong.write_bytes(b"author-owned fixture")
   with self.assertRaises(m.PrivateOneHopError):
    m.extend(Path(d)/"missing.zip",wrong,Path(d)/"private.zip")
   self.assertFalse((Path(d)/"private.zip").exists())
if __name__=="__main__":unittest.main()

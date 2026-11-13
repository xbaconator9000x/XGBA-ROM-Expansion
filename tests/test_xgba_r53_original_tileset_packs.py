"""R53 original GBA asset importer tests, strictly authored input only."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r53_original_tileset_packs as r53
import xgba_resource_sidecar as sidecar

def synthetic_rom(version=2,compressed=False,secondary=False):
    data=bytearray(125000)
    descriptor=64
    tiles=512
    metas=40000
    physical_count=(1024-(640 if version in (1,2) else 512)) if secondary else (640 if version in (1,2) else 512)
    attrs=metas+physical_count*16
    pals=76000
    for i in range(30000):data[tiles+i]=(17*i+13)&255
    for i in range(physical_count*16):data[metas+i]=(i*3+1)&255
    for i in range(physical_count*(4 if version==1 else 2)):data[attrs+i]=i&255
    for i in range(500):data[pals+i]=(i*7)&255
    data[descriptor]=int(compressed)
    data[descriptor+1]=int(secondary)
    struct.pack_into("<4I",data,descriptor+4,
       *[0x08000000+x for x in (tiles,pals,metas,attrs)])
    return data,descriptor,tiles

class OriginalSourceTilesetTests(unittest.TestCase):
    def test_native_original_asset_ranges_and_manifest(self):
        rom,desc,_=synthetic_rom(2)
        ident,header,parts=r53.descriptor_asset(rom,1,2,desc,False)
        self.assertEqual(ident,"r53.w1.v2.t00000040")
        self.assertEqual([len(p) for p in parts],[20480,10240,1280,224])
        self.assertEqual(header[:4],b"X53T")
        self.assertEqual(header[4:8],bytes((1,2,0,0)))
        self.assertEqual(struct.unpack_from("<I",header,60)[0],
                         zlib.crc32(header[:60])&0xffffffff)
        for i,part in enumerate(parts):
            self.assertEqual(struct.unpack_from("<I",header,40+4*i)[0],
                             zlib.crc32(part)&0xffffffff)
        with tempfile.TemporaryDirectory() as d:
            manifest=r53.write_private_pack(
                {(1,2,desc):(ident,header,parts)},{},{"maps":1},Path(d)/"new")
            self.assertEqual(len(manifest["resources"]),6)
            parsed=sidecar.load_manifest(Path(d)/"new"/"manifest.json")
            for entry in manifest["resources"]:
                self.assertEqual(b"".join(sidecar.iter_resource_chunks(parsed,entry["id"])).__len__(),
                                 entry["length"])

    def test_secondary_slot_selection_and_pointers(self):
        rom,desc,_=synthetic_rom(secondary=True)
        ident,header,parts=r53.descriptor_asset(rom,2,2,desc,True)
        self.assertEqual([len(p) for p in parts],[12288,6144,768,192])
        self.assertEqual(parts[3],bytes(rom[76000+224:76000+416]))
        self.assertEqual(header[6],1)
        with self.assertRaisesRegex(r53.TilesetFormatError,"flag mismatch"):
            r53.descriptor_asset(rom,2,2,desc,False)

    def test_bad_source_graphics_rejected_not_faked_as_raw(self):
        rom,desc,tiles=synthetic_rom(compressed=True)
        rom[tiles]=0x06
        with self.assertRaisesRegex(r53.TilesetFormatError,"Invalid original Smol"):
            r53.descriptor_asset(rom,1,2,desc,False)
        rom[tiles]=0x10
        rom[tiles+1:tiles+4]=bytes((0xff,0xff,0xff))
        with self.assertRaisesRegex(r53.TilesetFormatError,"output size"):
            r53.descriptor_asset(rom,1,2,desc,False)

    def test_lz77_decoder_genuine_bios_literal_and_overlapping_match(self):
        compressed=bytes([0x10,0x0c,0,0,0b00000000])+b"ABCDEFGH"+bytes([0b10000000,0x10,0x07])
        self.assertEqual(r53.gba_lz77(compressed,0),b"ABCDEFGHABCD")
        with self.assertRaisesRegex(r53.TilesetFormatError,"backref"):
            r53.gba_lz77(bytes([0x10,0x04,0,0,0x80,0x00,0xff]),0)
        with self.assertRaisesRegex(r53.TilesetFormatError,"Truncated"):
            r53.gba_lz77(bytes([0x10,0x08,0,0,0x00,0x33]),0)

    def test_original_emerald_short_lz77_secondary_preserves_real_length(self):
        rom,desc,tile_at=synthetic_rom(version=0,secondary=True,compressed=True)
        # A real Emerald secondary sometimes decompresses only a few
        # 4bpp tiles, although the BG tile reservation holds 512 slots.
        compressed=(bytes([0x10,32,0,0])+
                    b"".join(bytes([0])+bytes(range(i,i+8))
                             for i in (0,8,16,24)))
        rom[tile_at:tile_at+len(compressed)]=compressed
        ident,header,parts=r53.descriptor_asset(rom,0,0,desc,True)
        self.assertEqual(ident,"r53.w0.v0.t00000040")
        self.assertEqual(len(parts[0]),32)
        self.assertEqual(parts[0],bytes(range(32)))
        self.assertEqual(struct.unpack_from("<H",header,28)[0],512)
        self.assertEqual(struct.unpack_from("<I",header,12)[0],32)
        self.assertEqual(header[34],1)

    def test_layouts_not_interchanged(self):
        rom,desc,_=synthetic_rom(version=0)
        _,old,parts=r53.descriptor_asset(rom,0,0,desc,False)
        self.assertEqual([len(p) for p in parts],[16384,8192,1024,192])
        self.assertEqual(old[5],0)
        self.assertEqual(old[33],6)
        with self.assertRaisesRegex(r53.TilesetFormatError,"descriptor identity"):
            r53.descriptor_asset(rom,0,2,len(rom),False)

if __name__=="__main__":unittest.main()

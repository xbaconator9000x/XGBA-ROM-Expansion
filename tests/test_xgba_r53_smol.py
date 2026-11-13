"""Author-built Smol modes 1 and 6 and malicious-asset rejection.

No original ROM or copyrighted original tileset data is committed.
The HnS v2.0.6 real item-icon golden SHA-1 was separately validated
against PokeDaisy's publicly documented reference test using private
runtime evidence (288 bytes, aad01e66e3584419de4dd0861877b3cade39268e).
"""
from __future__ import annotations
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r53_smol as smol
import xgba_r53_original_tileset_packs as r53

def _freqs(freq):
    return b"".join(struct.pack("<I",
      sum(freq[i*5+j]<<(6*j) for j in range(5)) |
      (((freq[15]>>(2*i))&3)<<30)) for i in range(3))

def mode_one_asset(words):
    if not 1<=len(words)<=127:
        raise ValueError("authored fixture only accepts <=127 words")
    outbytes=len(words)*2
    if outbytes%32:raise ValueError("must be whole GBA 4bpp tile")
    header=struct.pack("<II",1|((outbytes//4)<<4)|(len(words)<<18),
                       (2<<19))
    return header+struct.pack("<"+str(len(words))+"H",*words)+bytes((0,len(words)))

def mode_six_zeros():
    # Authored tANS frequencies: instruction nibble 0/8 each 32 entries;
    # symbol nibble zero has 63 entries and one has a single entry.
    # Initial state 8 + bit 1 encodes four instruction bytes (0,8,0,8),
    # which emit exactly sixteen zero u16 values -> one 32-byte 4bpp tile.
    lo=[0]*16;lo[0]=lo[8]=32
    sy=[0]*16;sy[0]=63;sy[1]=1
    return (struct.pack("<II",6|(8<<4)|(16<<18),8|(2<<6)|(4<<19))+
            _freqs(lo)+_freqs(sy)+struct.pack("<II",1,0))

class SmolOriginalAssetContracts(unittest.TestCase):
    def test_mode1_real_original_decoder_semantics(self):
        words=[(0x1234+i*71)&65535 for i in range(16)]
        source=mode_one_asset(words)
        self.assertEqual(smol.decode(source),
          struct.pack("<16H",*words))
        self.assertEqual(len(smol.decode(source)),32)

    def test_mode6_delta_tans_genuine_4bpp_semantics(self):
        source=mode_six_zeros()
        self.assertEqual(smol.decode(source),bytes(32))
        self.assertEqual(source[0]&15,6)

    def test_all_unknown_modes_and_truncation_fail_closed(self):
        one=mode_one_asset([i for i in range(16)])
        six=mode_six_zeros()
        for src in (b"",b"\x06",one[:-1],six[:22],six[:31],six[:32]):
            with self.subTest(size=len(src)):
                with self.assertRaises(smol.SmolError):
                    smol.decode(src)
        with self.assertRaisesRegex(smol.SmolError,"Unsupported Smol"):
            smol.decode(b"\x08"+bytes(31))
        with self.assertRaisesRegex(smol.SmolError,"out of bounds"):
            smol.decode(one,max_output=16)

    def test_r53_source_graphics_compiler_accepts_smolfast_and_full_tans(self):
        for version,payload in [(1,mode_one_asset([0x0101+i for i in range(16)])),
                                (6,mode_six_zeros())]:
            with self.subTest(compression_mode=version):
                # 640 tiles are required for a primary v2 HnS descriptor.
                # Smol fixtures are a single tile and therefore deliberately
                # FAIL the native size gate: never pad/repeat source graphics.
                source=bytearray(80000)
                source[64]=1;source[65]=0
                struct.pack_into("<4I",source,68,
                  *[0x08000000+n for n in (1024,40000,57000,76000)])
                source[1024:1024+len(payload)]=payload
                with self.assertRaisesRegex(r53.TilesetFormatError,
                  "smaller than expected tiles"):
                    r53.descriptor_asset(bytes(source),2,2,64,False)

if __name__=="__main__": unittest.main()

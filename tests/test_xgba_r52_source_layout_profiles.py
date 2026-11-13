"""R52 original source-layout ABI regression with authored byte fixtures."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r52_source_layout_profiles as r52
import xgba_resource_sidecar as sidecar

def original_format(world,version):
    buf=bytearray(2048)
    w,h=(20,20) if world==0 else ((24,25) if world==1 else (58,46))
    header,layout,pdesc,sdesc=64,256,512,640
    struct.pack_into("<I",buf,header,0x08000000+layout)
    struct.pack_into("<II",buf,layout,w,h)
    struct.pack_into("<II",buf,layout+16,0x08000000+pdesc,0x08000000+sdesc)
    buf[layout+24:layout+28]=bytes([version,2 if version==1 else 0,
                                    2 if version==1 else 0,0])
    buf[pdesc]=1;buf[sdesc]=1
    idx=struct.pack("<IHHIIIIII",
      (world<<16)|((9 if world<2 else 4)),
      w,h,0,w*h*2,0,0,0,header)
    return bytes(buf),idx

class ExactOriginalLayoutProfileTests(unittest.TestCase):
    def sources(self,other_version=2):
        b0,i0=original_format(0,0)
        b1,i1=original_format(1,other_version)
        b2,i2=original_format(2,2)
        original=(b0,b1,b2)
        return original,i0+i1+i2,tuple(hashlib.sha256(b).hexdigest() for b in original)

    def test_source_versions_primary_split_crc_and_private_sha_pages(self):
        originals,index,checksums=self.sources()
        with patch.object(r52,"EXPECTED_SHA",checksums),patch.object(r52,"ALL_MAPS",3):
            pages,report=r52.extract_profiles(originals,index,require_complete=False)
        self.assertEqual(report["maps"],3)
        self.assertEqual(report["variants"]["emerald"],{"0":1})
        self.assertEqual(report["variants"]["rocket"],{"2":1})
        self.assertEqual(report["variants"]["heart_soul"],{"2":1})
        a,b,c=[struct.unpack_from(r52.LAYOUT_ROW,pages[0],32*i) for i in range(3)]
        self.assertEqual([z[0] for z in (a,b,c)],[0x000009,0x010009,0x020004])
        self.assertEqual([z[6] for z in (a,b,c)],[512,640,640])
        self.assertEqual([z[8] for z in (a,b,c)],[6,7,7])
        self.assertEqual([z[9] for z in (a,b,c)],[2,2,2])
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"profiles"
            manifest=r52.export_profiles(pages,report,out)
            parsed=sidecar.load_manifest(out/"manifest.json")
            self.assertEqual(len(parsed.resources),1)
            self.assertEqual(manifest["resources"][0]["id"],"r52.mapmeta.000")

    def test_version3_preserved_but_no_native_semantic_claim(self):
        originals,index,checksums=self.sources(3)
        with patch.object(r52,"EXPECTED_SHA",checksums),patch.object(r52,"ALL_MAPS",3):
            pages,report=r52.extract_profiles(originals,index,require_complete=False)
        self.assertEqual(len(report["unknown_or_unsafe_layouts"]),1)
        row=struct.unpack_from(r52.LAYOUT_ROW,pages[0],32)
        self.assertEqual(row[1],3)
        self.assertEqual(row[10]&1,0)

    def test_unknown_source_and_geometry_mismatch_fail_closed(self):
        originals,index,checksums=self.sources()
        with patch.object(r52,"EXPECTED_SHA",checksums),patch.object(r52,"ALL_MAPS",3):
            corrupt=list(originals);corrupt[1]=corrupt[1][:-1]+b"X"
            with self.assertRaisesRegex(r52.LayoutProfileError,"SHA"):
                r52.extract_profiles(tuple(corrupt),index,require_complete=False)
            bad=bytearray(index);struct.pack_into("<H",bad,32+4,99)
            with self.assertRaisesRegex(r52.LayoutProfileError,"geometry"):
                r52.extract_profiles(originals,bytes(bad),require_complete=False)
            empty=bytearray(index);struct.pack_into("<I",empty,32+28,5000)
            with self.assertRaisesRegex(r52.LayoutProfileError,"offset"):
                r52.extract_profiles(originals,bytes(empty),require_complete=False)

if __name__=="__main__":
    unittest.main()

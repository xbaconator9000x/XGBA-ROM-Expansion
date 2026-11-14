"""R51 source-preserving map/collision page compiler regressions.

Public CI uses authored bytes; the complete owner ROM test runs locally with
exact SHA identities and never publishes original Nintendo-derived payloads.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r51_original_grid_pages as r51
import xgba_resource_sidecar as sidecar

def authored_fixture(width=20,height=20):
    blob=bytearray((i*19+7)&255 for i in range(max(24000,width*height*2+256)))
    grid=128
    border=grid+width*height*2+16
    row={"group":0,"map":9,"width":width,"height":height,
         "map_grid_offset":grid,"border_offset":border,
         "map_grid_bytes":width*height*2,"header_offset":64}
    parsed={"maps":[row],"null_slot_count":0}
    return bytes(blob),parsed

class OriginalThreeWorldTerrainPages(unittest.TestCase):
    def synthetic_worlds(self,large=False):
        examples={
          "emerald":authored_fixture(),
          "rocket":authored_fixture(24,25),
          "heart_soul":authored_fixture(100,100) if large else authored_fixture(58,46)}
        hashes={n:(hashlib.sha256(blob).hexdigest(),1,0)
                for n,(blob,_) in examples.items()}
        return examples,hashes

    def test_all_source_terrain_bytes_preserved_and_source_keys_collide_safely(self):
        examples,hashes=self.synthetic_worlds()
        with patch.object(r51,"SOURCES",hashes):
            index,terrain,report=r51.pack_original_grids(examples,require_complete=False)
        self.assertEqual(report["maps"],3)
        self.assertEqual(report["native_guest_fit_maps"],3)
        self.assertEqual(len(index),1)
        rows=[struct.unpack_from(r51.INDEX_FORMAT,index[0],i*32)
              for i in range(3)]
        self.assertEqual([x[0] for x in rows],[0x000009,0x010009,0x020009])
        stream=b"".join(terrain)
        for name,row in zip(examples,rows):
            blob,parsed=examples[name]
            source=parsed["maps"][0]
            expected=blob[source["map_grid_offset"]:
                source["map_grid_offset"]+source["map_grid_bytes"]]+(
                blob[source["border_offset"]:source["border_offset"]+8])
            self.assertEqual(stream[row[3]:row[3]+row[4]+8],expected)

    def test_oversized_original_map_preserved_not_discarded_for_guest_limit(self):
        examples,hashes=self.synthetic_worlds(large=True)
        with patch.object(r51,"SOURCES",hashes):
            index,terrain,report=r51.pack_original_grids(examples,require_complete=False)
        self.assertEqual(report["maps"],3)
        self.assertEqual(report["native_guest_fit_maps"],2)
        self.assertGreater(len(terrain),1)
        row=struct.unpack_from(r51.INDEX_FORMAT,index[0],64)
        self.assertEqual((row[0],row[4]),(0x020009,20000))
        self.assertEqual(len(b"".join(terrain)),len(terrain)*r51.PAGE)

    def test_atomic_refusal_on_corrupt_original_blob_pointer_and_sha(self):
        examples,hashes=self.synthetic_worlds()
        with patch.object(r51,"SOURCES",hashes):
            altered=dict(examples)
            blob,parsed=altered["rocket"]
            altered["rocket"]=(blob[:-1]+b"X",parsed)
            with self.assertRaisesRegex(r51.OriginalGridError,"SHA"):
                r51.pack_original_grids(altered,require_complete=False)
            bad={n:(blob,dict(p)) for n,(blob,p) in examples.items()}
            bb,orig=bad["rocket"]
            bad["rocket"]=(bb,{"maps":[dict(orig["maps"][0],map_grid_offset=len(bb)-1)],
                              "null_slot_count":0})
            with self.assertRaisesRegex(r51.OriginalGridError,"pointer/bounds"):
                r51.pack_original_grids(bad,require_complete=False)

    def test_private_manifest_exact_sha_resource_integrity(self):
        examples,hashes=self.synthetic_worlds()
        with patch.object(r51,"SOURCES",hashes):
            idx,terrain,report=r51.pack_original_grids(examples,require_complete=False)
            with tempfile.TemporaryDirectory() as td:
                folder=Path(td)/"private-originals"
                manifest=r51.write_private_pages(idx,terrain,report,folder)
                loaded=sidecar.load_manifest(folder/"manifest.json")
                self.assertEqual(len(loaded.resources),len(idx)+len(terrain))
                self.assertEqual(manifest["resources"][0]["id"],"r51.index.000")
                self.assertTrue(all(x["length"]==r51.PAGE for x in manifest["resources"]))
                with self.assertRaises(r51.OriginalGridError):
                    r51.write_private_pages(idx,terrain,report,folder)

if __name__=="__main__":
    unittest.main()

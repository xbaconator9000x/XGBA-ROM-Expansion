"""R31: source-generated original identities executed in original Emerald.

Inherits all NINE R30 original Emerald physical navigation, EWRAM, PNG and
disabled-provider acceptance tests. Adds three source-catalogue assertions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"tests"),str(ROOT/"tools"),str(ROOT/"integration/mgba")]
import test_xgba_r30_emerald_four_maps as r30
import test_xgba_r17_emerald_external_map as r17


class RealEmeraldOriginalIdentityCatalogue(r30.RealEmeraldFourExternalMaps):
    R31_AUTO_CATALOG=True

    def test_original_source_group_map_numbers_never_renumbered(self):
        ids=[(m["name"],m["group"],m["map"]) for m in self.r31_catalog]
        self.assertEqual(ids,[
            ("LittlerootTown",0,9),("Route101",0,16),
            ("OldaleTown",0,10),("Route102",0,17)])
        source=json.loads((r17.EMERALD/"data/maps/map_groups.json").read_text())
        group=source[source["group_order"][0]]
        for name,g,num in ids:
            self.assertEqual(g,0)
            self.assertEqual(group[num],name)

    def test_original_connection_graph_generates_neighbors(self):
        self.assertEqual([r["prefetch_index"] for r in self.r31_catalog],
                         [1,0,1,2])
        generated=self.r31_catalog_header.read_text()
        self.assertIn("#define XGBA_R31_CATALOG_COUNT 4u",generated)
        self.assertIn("{0x00000009u, 0u}",generated)
        self.assertIn("{0x0000000au, 2u}",generated)
        self.assertIn("{0x00000010u, 1u}",generated)
        self.assertIn("{0x00000011u, 3u}",generated)

    def test_unselected_original_route103_needs_no_external_resource(self):
        self.assertNotIn("Route103",self.r31_catalog_header.read_text())
        self.assertFalse(any("Route103" in x["asset"] for x in self.removed))
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertIn("source_verified=1 backup_grids_verified=7",self.log)
        self.assertIn("map_sequence=9,16,10,17,10,16,9",self.log)


if __name__=="__main__":
    import unittest
    unittest.main()

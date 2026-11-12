"""R27 huge map geometry bounds, transfer/rejection and original map samples.

Portable preflight only; genuine original game graphics verification is in the
R27 native test and MUST pass separately.
"""
import struct
import unittest
from xgba_r27_huge_map_geometry import (
    GeometryCapacityError,plan_map,source_tiled_grid,MAX_MAP_DATA_CELLS,
    MAX_SINGLE_XGBA_TRANSFER)
class OversizedAndBoundedGeometry(unittest.TestCase):
    FULL_ORIGINAL_TILESET_OVERHEAD=6244-800
    def test_two_requested_huge_shapes_fit_both_original_bounds(self):
        for w,h in ((64,64),(128,32)):
            with self.subTest(shape=(w,h)):
                p=plan_map(w,h,base_pack_without_grid=self.FULL_ORIGINAL_TILESET_OVERHEAD)
                self.assertEqual(p.grid_bytes,8192)
                self.assertEqual(p.packed_bytes,13636)
                self.assertLessEqual(p.backup_cells,MAX_MAP_DATA_CELLS)
                self.assertLessEqual(p.packed_bytes,MAX_SINGLE_XGBA_TRANSFER)
                self.assertEqual(p.reserved_ewram_bytes,13636)
    def test_96_by_96_rejected_before_backup_grid_overrun(self):
        with self.assertRaisesRegex(GeometryCapacityError,"backup map overflow"):
            plan_map(96,96,base_pack_without_grid=self.FULL_ORIGINAL_TILESET_OVERHEAD)
    def test_128_by_64_rejected_before_backup_grid_or_pack_overrun(self):
        with self.assertRaises(GeometryCapacityError):
            plan_map(128,64,base_pack_without_grid=self.FULL_ORIGINAL_TILESET_OVERHEAD)
    def test_exact_16k_allowed_and_one_extra_byte_refused(self):
        p=plan_map(20,20,base_pack_without_grid=MAX_SINGLE_XGBA_TRANSFER-800)
        self.assertEqual(p.packed_bytes,16384)
        with self.assertRaisesRegex(GeometryCapacityError,"transfer overflow"):
            plan_map(20,20,base_pack_without_grid=MAX_SINGLE_XGBA_TRANSFER-800+1)
    def test_oversized_secondary_tileset_rejected_even_when_map_fits(self):
        with self.assertRaisesRegex(GeometryCapacityError,"transfer overflow"):
            plan_map(64,64,base_pack_without_grid=9000)
    def test_overflow_and_invalid_dimensions_rejected(self):
        for w,h in ((0,64),(-1,40),(1,0),(65536,1),(10,10.5),(True,20)):
            with self.subTest(shape=(w,h)):
                with self.assertRaises(GeometryCapacityError):
                    plan_map(w,h,base_pack_without_grid=self.FULL_ORIGINAL_TILESET_OVERHEAD)
    def test_precisely_bounded_padding_and_fully_sourced_metatiles(self):
        original=struct.pack("<400H",*[i for i in range(400)])
        for w,h in ((64,64),(128,32)):
            grid=source_tiled_grid(original,w,h)
            self.assertEqual(len(grid),w*h*2)
            for x,y in ((0,0),(w-1,h-1),(32,16),(10,10)):
                want=(y%20)*20+(x%20)
                self.assertEqual(struct.unpack_from("<H",grid,2*(y*w+x))[0],want)
if __name__=="__main__":
    unittest.main()

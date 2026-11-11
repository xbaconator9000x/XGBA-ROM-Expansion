"""R21 genuine source-built Emerald malloc pressure + real battle reentry.

The six inherited R20 native original-game checks remain mandatory.
Four additional checks assert that actual guest src/malloc.c completed
two bounded fragmentation/guard-pressure cycles, refused oversize requests,
and retained the physical 16 KiB arena outside the original heap.
"""
import test_xgba_r20_ewram_reentry as r20


class NativeOriginalEmeraldMallocPressure(r20.NativeEmeraldArenaReentry):
    R21_HEAP_PRESSURE_TEST = True

    def test_original_emerald_allocator_stressed_before_both_battles(self):
        self.assertIn("PASS_R21_ORIGINAL_EMERALD_HEAP_PRESSURE",self.log)
        self.assertIn("cycles=2",self.log)
        self.assertIn("original_battles=2",self.log)

    def test_allocator_fragmentation_alloc_free_and_oversize_rejection(self):
        self.assertIn("allocations=8",self.log)
        self.assertIn("frees=8",self.log)
        self.assertIn("oversized_rejected=2",self.log)

    def test_guest_allocator_metadata_and_guard_integrity(self):
        self.assertIn("verified_guard_bytes=12288",self.log)
        self.assertIn("original_allocator_audits=",self.log)
        self.assertIn("error_flags=0",self.log)

    def test_16k_heap_tail_remains_excluded_from_original_allocator(self):
        self.assertIn("arena_reserved_bytes=16384",self.log)
        self.assertIn("native_ewram=1",self.log)
        self.assertEqual(self.simultaneous_bytes,16384)
        self.assertEqual(self.report["heap_tail_reserved_not_released"],True)
        self.assertEqual(self.report["guest_alloc_pressure_cycles"],2)


if __name__ == "__main__":
    import unittest
    unittest.main()

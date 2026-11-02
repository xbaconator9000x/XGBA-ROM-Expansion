#!/usr/bin/env python3
"""Synthetic-only physical .sav integrity tests; no native or hardware claim."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from phase1_firered_interrupted_save import assert_interrupted_snapshot, counter3_ids

SECTOR=4096
SIZE=131072
SIGNATURE=0x08012025

def baseline():
    data=bytearray(SIZE)
    for physical in range(28):
        counter=2 if physical<14 else 1
        struct.pack_into("<HHII",data,physical*SECTOR+0xFF4,
                         physical%14,0,SIGNATURE,counter)
    return bytes(data)

def partial(count):
    data=bytearray(baseline())
    for physical in range(14,14+count):
        struct.pack_into("<I",data,physical*SECTOR+0xFFC,3)
    return bytes(data)

def native(count):
    return dict(counter=3,valid_counter3_sectors=count,try_save_entries=1,
                try_save_returns=0,no_host_writes=True,no_graceful_close=True)

class InterruptedSnapshotIntegrityTests(unittest.TestCase):
    def reject(self,data,event,threshold):
        with self.assertRaises(AssertionError):
            assert_interrupted_snapshot(data,baseline(),event,threshold)

    def test_three_valid_synthetic_thresholds(self):
        for count in (1,7,13):
            with self.subTest(count=count):
                self.assertEqual(assert_interrupted_snapshot(
                    partial(count),baseline(),native(count),count),list(range(count)))
                self.assertEqual(counter3_ids(partial(count)),list(range(count)))

    def test_unaccounted_tail_write_rejected(self):
        for count in (1,7,13):
            data=bytearray(partial(count))
            data[28*SECTOR+0x20]^=1
            self.reject(data,native(count),count)

    def test_unaccounted_in_slot_write_rejected(self):
        for count in (1,7,13):
            data=bytearray(partial(count))
            data[(14+count)*SECTOR+0x20]^=1
            self.reject(data,native(count),count)

    def test_older_slot_write_rejected(self):
        data=bytearray(partial(7))
        data[0x20]^=1
        self.reject(data,native(7),7)

    def test_duplicate_counter3_id_rejected(self):
        data=bytearray(partial(7))
        struct.pack_into("<H",data,15*SECTOR+0xFF4,0)
        self.reject(data,native(7),7)

    def test_completed_sector_checksum_corruption_rejected(self):
        data=bytearray(partial(7))
        data[14*SECTOR+0x20]^=1
        self.reject(data,native(7),7)

    def test_native_count_mismatch_rejected(self):
        event=native(7)
        event["valid_counter3_sectors"]=8
        self.reject(partial(7),event,7)

    def test_truthy_string_flags_rejected(self):
        for field in ("no_host_writes","no_graceful_close"):
            event=native(7)
            event[field]="true"
            self.reject(partial(7),event,7)

    def test_boolean_numeric_evidence_rejected(self):
        for field in ("valid_counter3_sectors","counter",
                      "try_save_entries","try_save_returns"):
            event=native(1)
            event[field]=True
            self.reject(partial(1),event,1)

    def test_incomplete_threshold_rejected(self):
        self.reject(partial(1),native(1),7)

    def test_invalid_threshold_rejected(self):
        self.reject(partial(7),native(7),14)

    def test_truncated_snapshot_rejected(self):
        self.reject(partial(7)[:-1],native(7),7)

    def test_no_flash_change_rejected(self):
        self.reject(baseline(),native(7),7)

    def test_save_returned_rejected(self):
        event=native(7)
        event["try_save_returns"]=1
        self.reject(partial(7),event,7)

    def test_host_writes_reported_rejected(self):
        event=native(7)
        event["no_host_writes"]=False
        self.reject(partial(7),event,7)

if __name__=="__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from phase1_firered_connection_object_audit import (
    map_id_index,
    validate_include_order,
    validate_header_pointer,
    validate_pointer,
    validate_record,
)


class ConnectionObjectAuditTests(unittest.TestCase):
    def setUp(self):
        self.groups = {
            "group_order": ["group_a"],
            "group_a": ["MapA", "MapB"],
        }
        self.map_ids = map_id_index(self.groups)

    def test_decodes_group_then_map_number(self):
        self.assertEqual(
            validate_record(bytes.fromhex("020000000000000000010000"), self.map_ids),
            "MapB",
        )

    def test_rejects_bad_record_shapes(self):
        valid = bytes.fromhex("020000000000000000000000")
        for invalid in (
            valid[:-1],
            b"\xff" + valid[1:],
            valid[:1] + b"\x01" + valid[2:],
            valid[:8] + b"\xff" + valid[9:],
        ):
            with self.subTest(invalid=invalid.hex()):
                with self.assertRaises(ValueError):
                    validate_record(invalid, self.map_ids)

    def test_rejects_include_reordering(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_include_order(["MapB", "MapA"], ["MapA", "MapB"])

    def test_requires_zero_null_sentinel(self):
        validate_pointer(bytes(4), 0, None, {})
        with self.assertRaisesRegex(ValueError, "NULL"):
            validate_pointer(b"\x04\0\0\0", 0, None, {})

    def test_requires_count_and_relocated_list_pointer(self):
        data = bytearray(20)
        data[0:12] = bytes.fromhex("020000000000000000000000")
        data[12:20] = bytes.fromhex("0100000000000000")
        relocation = {16: {"type": 2, "targets_rodata": True}}
        validate_header_pointer(bytes(data), 12, 0, relocation)
        with self.assertRaisesRegex(ValueError, "count"):
            validate_header_pointer(bytes(data), 12, 4, relocation)
        with self.assertRaisesRegex(ValueError, "relocation"):
            validate_header_pointer(bytes(data), 12, 0, {})


if __name__ == "__main__":
    unittest.main()

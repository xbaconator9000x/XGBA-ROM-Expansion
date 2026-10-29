"""XGBA Phase 1 read-only ROM discovery: fail-closed regression controls."""
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "xgba_rom_compatibility_preflight.py"
SPEC = importlib.util.spec_from_file_location("xgba_preflight", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def make_rom():
    header = bytearray(b"\x00" * 0xC0)
    header[0xA0:0xAC] = b"TEST FIRERED"
    header[0xAC:0xB0] = b"BPRE"
    header[0xB0:0xB2] = b"01"
    header[0xB2] = 0x96
    header[0xBD] = module._checksum(header)
    return bytes(header) + b"synthetic-test-only-data"


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.dir = TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.path = self.root / "synthetic.gba"
        self.data = make_rom()
        self.path.write_bytes(self.data)

    def profile(self):
        data = {"schema": 1, "profiles": [{
            "profile_id": "test-only", "sha256": hashlib.sha256(self.data).hexdigest(),
            "byte_length": len(self.data), "game_code": "BPRE",
        }]}
        path = self.root / "profiles.json"
        path.write_text(json.dumps(data))
        return path

    def test_unknown_valid_header_remains_unapproved(self):
        before = self.path.read_bytes()
        result = module.inspect(self.path)
        self.assertEqual(result["status"], "UNKNOWN_ROM")
        self.assertEqual(result["game_code"], "BPRE")
        self.assertFalse(result["conversion_permitted"])
        self.assertFalse(result["engine_confirmed"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_exact_known_identity_only_not_conversion(self):
        result = module.inspect(self.path, self.profile())
        self.assertEqual(result["status"], "EXACT_PROFILE_IDENTITY_ONLY")
        self.assertEqual(result["matched_profile"], "test-only")
        self.assertFalse(result["conversion_permitted"])
        self.assertFalse(result["semantic_approval_claimed"])

    def test_one_byte_mutation_invalidates_exact_match(self):
        catalog = self.profile()
        modified = bytearray(self.data)
        modified[-1] ^= 1  # header/title/code/size remain unchanged
        self.path.write_bytes(modified)
        result = module.inspect(self.path, catalog)
        self.assertEqual(result["status"], "UNKNOWN_ROM")
        self.assertIsNone(result["matched_profile"])

    def test_truncated_header_rejected(self):
        self.path.write_bytes(b"\x00" * 0xBF)
        self.assertEqual(module.inspect(self.path)["status"], "INVALID_OR_UNSAFE_INPUT")

    def test_bad_fixed_header_byte_rejected(self):
        modified = bytearray(self.data)
        modified[0xB2] = 0
        self.path.write_bytes(modified)
        result = module.inspect(self.path)
        self.assertEqual(result["status"], "INVALID_OR_UNSAFE_INPUT")

    def test_bad_header_checksum_rejected(self):
        modified = bytearray(self.data)
        modified[0xA0] ^= 1
        self.path.write_bytes(modified)
        self.assertEqual(module.inspect(self.path)["status"], "INVALID_OR_UNSAFE_INPUT")

    def test_invalid_and_duplicate_catalogs_fail_closed(self):
        p = self.profile()
        entry = json.loads(p.read_text())["profiles"][0]
        p.write_text(json.dumps({"schema": 1, "profiles": [entry, dict(entry, profile_id="dup")]}))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            module.inspect(self.path, p)
        p.write_text(json.dumps({"schema": 2, "profiles": []}))
        with self.assertRaisesRegex(ValueError, "schema"):
            module.inspect(self.path, p)

    def test_read_limit_rejected_without_mutation(self):
        with self.assertRaisesRegex(ValueError, "read limit"):
            module.inspect(self.path, max_size=0xC0)
        self.assertEqual(self.path.read_bytes(), self.data)


if __name__ == "__main__":
    unittest.main()

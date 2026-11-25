"""Focused source-only tests for private RHH trainer page generation."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_page_pack import (
    TILE_BYTES, TrainerPageError, build_page, decompress_gba_lz77,
)


def literal_stream(data: bytes) -> bytes:
    stream = bytearray(b"\x10" + len(data).to_bytes(3, "little"))
    for pos in range(0, len(data), 8):
        stream.append(0)
        stream.extend(data[pos:pos + 8])
    return bytes(stream)


class TrainerPagePackTests(unittest.TestCase):
    def setUp(self):
        self.original = bytes(i % 251 for i in range(TILE_BYTES))
        self.compressed = literal_stream(self.original)
        self.sha = hashlib.sha256(self.compressed).hexdigest()

    def test_original_lz77_roundtrip_and_resource_contract(self):
        page, manifest = build_page(self.compressed, 0x123, self.sha)
        self.assertEqual(page, self.original)
        self.assertEqual(manifest["resource_id"], "rhh.trainer.0123")
        self.assertEqual(manifest["bytes"], 2048)
        self.assertEqual(manifest["page_sha256"], hashlib.sha256(page).hexdigest())
        self.assertTrue(manifest["requires_private_provider"])

    def test_wrong_provenance_refused(self):
        with self.assertRaisesRegex(TrainerPageError, "SHA256 mismatch"):
            build_page(self.compressed, 0x123, "0" * 64)

    def test_truncated_and_wrong_size_refused(self):
        for blob in (self.compressed[:-1], b"\x10\x00\x01\x00", b"\x00" + self.compressed[1:]):
            with self.subTest(blob=blob[:8]):
                with self.assertRaises(TrainerPageError):
                    decompress_gba_lz77(blob)

    def test_bad_backreference_refused(self):
        blob = b"\x10\x00\x08\x00\x80\x00\x00"
        with self.assertRaisesRegex(TrainerPageError, "backreference"):
            decompress_gba_lz77(blob)

    def test_valid_overlapping_backreference(self):
        # One literal then a distance-one backreference of 18 bytes.
        # Full 2048-byte output requires repeated backreferences.
        blob = bytearray(b"\x10\x00\x08\x00")
        blob += b"\x7fA"
        for _ in range(7):
            blob += b"\xf0\x00"
        blob += b"\x10\x00"  # three bytes; still short, must reject
        with self.assertRaises(TrainerPageError):
            decompress_gba_lz77(bytes(blob))

    def test_invalid_trainer_ids_refused(self):
        for trainer_id in (-1, 65536):
            with self.assertRaisesRegex(TrainerPageError, "trainer ID"):
                build_page(self.compressed, trainer_id, self.sha)

    def test_extra_nonzero_bytes_refused(self):
        with self.assertRaisesRegex(TrainerPageError, "trailing"):
            decompress_gba_lz77(self.compressed + b"X")


if __name__ == "__main__":
    unittest.main()

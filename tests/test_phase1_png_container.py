"""PNG container negative controls for Phase 1 binary evidence; no semantic approvals."""
import hashlib
import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_bulk_triage as triage

SIG = b"\x89PNG\r\n\x1a\n"

def chunk(tag, payload=b""):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))

def ihdr(depth=8, color=2, compression=0, filtering=0, interlace=0):
    return chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, depth, color,
                                      compression, filtering, interlace))

IDAT = chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
IEND = chunk(b"IEND")

class PNGContainerControls(unittest.TestCase):
    def test_valid_rgb_with_ancillary_text(self):
        data = SIG + ihdr() + chunk(b"tEXt", b"EEPROM SaveSector") + IDAT + IEND
        self.assertTrue(triage.valid_png(data))
        result = triage.typed_structure("asset.png", data)
        self.assertEqual(result["file_kind"], "image_png")
        self.assertIsNone(result["source_lines"])
        self.assertEqual(result["risk_flags_line_anchors"], {})
        self.assertEqual(result["whole_blob_sha256"], hashlib.sha256(data).hexdigest())

    def test_valid_palette_with_plte(self):
        data = SIG + ihdr(1, 3) + chunk(b"PLTE", b"\x00\x00\x00\xff\xff\xff") + IDAT + IEND
        self.assertTrue(triage.valid_png(data))

    def test_fail_closed_on_bad_container(self):
        cases = {
            "missing_idat": SIG + ihdr() + IEND,
            "duplicate_ihdr": SIG + ihdr() + ihdr() + IDAT + IEND,
            "bad_depth_for_rgb": SIG + ihdr(1, 2) + IDAT + IEND,
            "bad_compression": SIG + ihdr(compression=1) + IDAT + IEND,
            "bad_filter": SIG + ihdr(filtering=1) + IDAT + IEND,
            "bad_interlace": SIG + ihdr(interlace=2) + IDAT + IEND,
            "indexed_without_plte": SIG + ihdr(1, 3) + IDAT + IEND,
            "plte_after_idat": SIG + ihdr() + IDAT + chunk(b"PLTE", b"\x00\x00\x00") + IEND,
            "duplicate_plte": SIG + ihdr() + chunk(b"PLTE", b"\x00\x00\x00") * 2 + IDAT + IEND,
            "noncontiguous_idat": SIG + ihdr() + IDAT + chunk(b"tEXt", b"x") + IDAT + IEND,
            "unknown_critical": SIG + ihdr() + chunk(b"ABCD", b"x") + IDAT + IEND,
            "missing_iend": SIG + ihdr() + IDAT,
            "trailing_data": SIG + ihdr() + IDAT + IEND + b"EEPROM",
            "bad_crc": SIG + ihdr() + IDAT + IEND[:-1] + b"\x00",
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertFalse(triage.valid_png(data))
                result = triage.typed_structure("asset.png", data)
                self.assertEqual(result["file_kind"], "unknown_binary")
                self.assertIsNone(result["source_lines"])
                self.assertEqual(result["risk_flags_line_anchors"], {})

if __name__ == "__main__":
    unittest.main()

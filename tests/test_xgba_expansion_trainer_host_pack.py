"""Synthetic-only private trainer host pack regression tests."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_host_pack import (
    HEADER, MAGIC, build_pack, write_private_pack,
)
from xgba_expansion_trainer_provider_catalogue import (
    PAGE_BYTES, PAGE_CAPACITY, PINNED_RHH, ProviderPackError,
)


class TrainerHostPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pages = {}
        for ident in ("0002", "0001"):
            name = "rhh.trainer." + ident
            page = bytes([int(ident)] * PAGE_BYTES)
            self.pages[name] = page
            (self.root / (name + ".bin")).write_bytes(page)
            (self.root / (name + ".json")).write_text(json.dumps({
                "resource_id": name,
                "source_release_sha": PINNED_RHH,
                "bytes": PAGE_BYTES,
                "page_capacity": PAGE_CAPACITY,
                "requires_private_provider": True,
                "page_sha256": hashlib.sha256(page).hexdigest(),
            }), encoding="utf-8")

    def test_deterministic_offsets_and_payload(self):
        packed, index = build_pack(self.root)
        self.assertEqual(packed[:HEADER.size], HEADER.pack(MAGIC, 2, PAGE_BYTES * 2))
        self.assertEqual([x["resource_id"] for x in index["entries"]],
                         ["rhh.trainer.0001", "rhh.trainer.0002"])
        for entry in index["entries"]:
            offset = HEADER.size + entry["offset"]
            self.assertEqual(packed[offset:offset + entry["bytes"]],
                             self.pages[entry["resource_id"]])
        self.assertEqual(index["pack_sha256"], hashlib.sha256(packed).hexdigest())
        self.assertEqual(build_pack(self.root), (packed, index))

    def test_changed_page_fails_closed(self):
        (self.root / "rhh.trainer.0001.bin").write_bytes(b"Z" * PAGE_BYTES)
        with self.assertRaisesRegex(ProviderPackError, "digest mismatch"):
            build_pack(self.root)

    def test_private_atomic_outputs(self):
        pack = self.root / "trainer.pack"
        index = self.root / "trainer.index.json"
        result = write_private_pack(self.root, pack, index)
        self.assertEqual(hashlib.sha256(pack.read_bytes()).hexdigest(),
                         result["pack_sha256"])
        self.assertEqual(json.loads(index.read_text()), result)

    def test_rejects_public_or_symlink_destinations(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(ProviderPackError, "private staging"):
                write_private_pack(self.root, Path(outside) / "pack", self.root / "index")
        destination = self.root / "trainer.pack"
        destination.symlink_to(self.root / "rhh.trainer.0001.bin")
        with self.assertRaisesRegex(ProviderPackError, "unsafe"):
            write_private_pack(self.root, destination, self.root / "index")


if __name__ == "__main__":
    unittest.main()

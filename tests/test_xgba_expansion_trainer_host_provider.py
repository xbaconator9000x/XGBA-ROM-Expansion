"""Synthetic-only verification of the private trainer host pack provider."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_host_pack import build_pack
from xgba_expansion_trainer_host_provider import TrainerHostProvider
from xgba_expansion_trainer_provider_catalogue import (
    PAGE_BYTES, PAGE_CAPACITY, PINNED_RHH, ProviderPackError,
)


class TrainerHostProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.resource = "rhh.trainer.0001"
        self.page = bytes(range(256)) * (PAGE_BYTES // 256)
        (self.root / (self.resource + ".bin")).write_bytes(self.page)
        (self.root / (self.resource + ".json")).write_text(json.dumps({
            "resource_id": self.resource,
            "source_release_sha": PINNED_RHH,
            "bytes": PAGE_BYTES,
            "page_capacity": PAGE_CAPACITY,
            "requires_private_provider": True,
            "page_sha256": hashlib.sha256(self.page).hexdigest(),
        }))
        self.pack, self.index = build_pack(self.root)
        self.pack_path = self.root / "trainer.pack"
        self.index_path = self.root / "trainer.index.json"
        self.save(self.pack, self.index)

    def save(self, pack, index):
        self.pack_path.write_bytes(pack)
        self.index_path.write_text(json.dumps(index))

    def test_valid_page_and_missing_resource_fallback(self):
        provider = TrainerHostProvider(self.pack_path, self.index_path)
        self.assertEqual(provider.acquire(self.resource, PAGE_BYTES), self.page)
        self.assertIsNone(provider.acquire("rhh.trainer.0002", PAGE_BYTES))
        self.assertIsNone(provider.acquire("../trainer.pack", PAGE_BYTES))
        self.assertIsNone(provider.acquire(self.resource, PAGE_BYTES + 1))
        self.assertIsNone(provider.acquire(self.resource, True))

    def test_mutated_pack_rejected(self):
        changed = bytearray(self.pack)
        changed[-1] ^= 1
        self.save(bytes(changed), self.index)
        with self.assertRaisesRegex(ProviderPackError, "digest"):
            TrainerHostProvider(self.pack_path, self.index_path)

    def test_truncated_pack_rejected(self):
        truncated = self.pack[:-1]
        index = dict(self.index, pack_sha256=hashlib.sha256(truncated).hexdigest())
        self.save(truncated, index)
        with self.assertRaisesRegex(ProviderPackError, "header mismatch"):
            TrainerHostProvider(self.pack_path, self.index_path)

    def test_overlapping_or_duplicate_entries_rejected(self):
        entries = [dict(self.index["entries"][0]), dict(self.index["entries"][0])]
        index = dict(self.index, entries=entries)
        self.save(self.pack, index)
        with self.assertRaisesRegex(ProviderPackError, "header mismatch"):
            TrainerHostProvider(self.pack_path, self.index_path)

    def test_wrong_page_digest_rejected_even_with_valid_pack_hash(self):
        entry = dict(self.index["entries"][0], sha256="0" * 64)
        index = dict(self.index, entries=[entry])
        self.save(self.pack, index)
        with self.assertRaisesRegex(ProviderPackError, "page digest"):
            TrainerHostProvider(self.pack_path, self.index_path)

    def test_rejects_symlink_input(self):
        alias = self.root / "alias.pack"
        alias.symlink_to(self.pack_path)
        with self.assertRaisesRegex(ProviderPackError, "unsafe"):
            TrainerHostProvider(alias, self.index_path)


if __name__ == "__main__":
    unittest.main()

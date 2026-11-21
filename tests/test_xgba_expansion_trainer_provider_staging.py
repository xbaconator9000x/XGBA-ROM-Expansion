"""Bounded host-to-MMIO staging transfer regression, no proprietary resources."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_host_pack import HEADER, MAGIC
from xgba_expansion_trainer_host_provider import TrainerHostProvider
from xgba_expansion_trainer_provider_catalogue import PAGE_BYTES, PINNED_RHH


class TrainerProviderStagingTests(unittest.TestCase):
    def test_bounded_copy_and_original_fallback(self):
        page = bytes((i * 17) % 256 for i in range(PAGE_BYTES))
        packed = HEADER.pack(MAGIC, 1, PAGE_BYTES) + page
        index = {
            "format": "xgba-private-trainer-pack-v1",
            "source_release_sha": PINNED_RHH,
            "header_bytes": HEADER.size,
            "payload_bytes": PAGE_BYTES,
            "pack_sha256": hashlib.sha256(packed).hexdigest(),
            "entries": [{
                "resource_id": "rhh.trainer.0001",
                "offset": 0,
                "bytes": PAGE_BYTES,
                "sha256": hashlib.sha256(page).hexdigest(),
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack_path = root / "private.bin"
            index_path = root / "private.json"
            pack_path.write_bytes(packed)
            index_path.write_text(json.dumps(index), encoding="utf-8")
            provider = TrainerHostProvider(pack_path, index_path)
            destination = bytearray(PAGE_BYTES)
            self.assertTrue(provider.copy_into("rhh.trainer.0001", destination))
            self.assertEqual(bytes(destination), page)
            for resource in ("rhh.trainer.0002", "invalid"):
                destination[:] = b"\\x7a" * PAGE_BYTES
                self.assertFalse(provider.copy_into(resource, destination))
                self.assertEqual(destination, b"\\x7a" * PAGE_BYTES)
            short = bytearray(PAGE_BYTES - 1)
            self.assertFalse(provider.copy_into("rhh.trainer.0001", short))
            self.assertEqual(short, bytearray(PAGE_BYTES - 1))
            self.assertFalse(provider.copy_into("rhh.trainer.0001", bytes(PAGE_BYTES)))
            self.assertFalse(provider.copy_into("rhh.trainer.0001", memoryview(bytearray(PAGE_BYTES))[::2]))


if __name__ == "__main__":
    unittest.main()

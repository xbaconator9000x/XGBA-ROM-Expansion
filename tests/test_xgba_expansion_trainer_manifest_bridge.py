"""End-to-end private trainer manifest to host MMIO window regression."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_host_pack import HEADER, MAGIC
from xgba_expansion_trainer_manifest_bridge import TrainerManifestBridge
from xgba_expansion_trainer_mmio_manifest import write_manifest
from xgba_expansion_trainer_provider_catalogue import PAGE_BYTES, PAGE_CAPACITY, PINNED_RHH, ProviderPackError


class ManifestBridgeTests(unittest.TestCase):
    def test_verified_page_and_fallback_preserve_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = bytes(range(256)) * (PAGE_BYTES // 256)
            packed = HEADER.pack(MAGIC, 1, PAGE_BYTES) + page
            pack, index, manifest = root / "trainer.bin", root / "index.json", root / "manifest.json"
            pack.write_bytes(packed)
            index.write_text(json.dumps({
                "format": "xgba-private-trainer-pack-v1",
                "source_release_sha": PINNED_RHH,
                "header_bytes": HEADER.size,
                "payload_bytes": PAGE_BYTES,
                "pack_sha256": hashlib.sha256(packed).hexdigest(),
                "entries": [{"resource_id": "rhh.trainer.0001", "offset": 0,
                             "bytes": PAGE_BYTES, "sha256": hashlib.sha256(page).hexdigest()}],
            }))
            digest = hashlib.sha256(b"private source identity").hexdigest()
            write_manifest(pack, index, manifest, digest, "emerald")
            bridge = TrainerManifestBridge(manifest, index)
            window = bytearray([0xA5] * PAGE_CAPACITY)
            self.assertTrue(bridge.stage("rhh.trainer.0001", PAGE_BYTES, window))
            self.assertEqual(window[:PAGE_BYTES], page)
            self.assertEqual(window[PAGE_BYTES:], bytes(PAGE_CAPACITY - PAGE_BYTES))
            before = bytes(window)
            self.assertFalse(bridge.stage("rhh.trainer.0002", PAGE_BYTES, window))
            self.assertFalse(bridge.stage("rhh.trainer.0001", PAGE_CAPACITY, window))
            self.assertEqual(bytes(window), before)
            data = json.loads(manifest.read_text())
            data["resources"][0]["offset"] += 1
            manifest.write_text(json.dumps(data))
            with self.assertRaises(ProviderPackError):
                TrainerManifestBridge(manifest, index)


if __name__ == "__main__":
    unittest.main()

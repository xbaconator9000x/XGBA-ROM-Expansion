"""Private trainer pack to patched-mGBA manifest acceptance tests."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_host_pack import HEADER, MAGIC
from xgba_expansion_trainer_mmio_manifest import export_manifest, write_manifest
from xgba_expansion_trainer_provider_catalogue import PAGE_BYTES, PINNED_RHH, ProviderPackError


class TrainerMmioManifestTests(unittest.TestCase):
    def test_existing_mmio_manifest_offsets_and_private_write(self):
        pages = [bytes([n]) * PAGE_BYTES for n in (17, 93)]
        payload = b"".join(pages)
        packed = HEADER.pack(MAGIC, 2, len(payload)) + payload
        entries = [{
            "resource_id": f"rhh.trainer.{i:04x}",
            "offset": i * PAGE_BYTES,
            "bytes": PAGE_BYTES,
            "sha256": hashlib.sha256(page).hexdigest(),
        } for i, page in enumerate(pages)]
        index = {
            "format": "xgba-private-trainer-pack-v1",
            "source_release_sha": PINNED_RHH,
            "header_bytes": HEADER.size,
            "payload_bytes": len(payload),
            "pack_sha256": hashlib.sha256(packed).hexdigest(),
            "entries": entries,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pack, meta, manifest_path = (root / n for n in ("trainer.bin", "trainer.json", "mmio.json"))
            pack.write_bytes(packed)
            meta.write_text(json.dumps(index), encoding="utf-8")
            digest = hashlib.sha256(b"authentic source ROM test identity").hexdigest()
            manifest = write_manifest(pack, meta, manifest_path, digest, "emerald")
            self.assertEqual(json.loads(manifest_path.read_text()), manifest)
            self.assertEqual(manifest["format"], "xgba-resource-manifest")
            self.assertEqual(manifest["source_identity"]["sha256"], digest)\n            self.assertEqual(manifest["source_identity"]["id"], "rhh-emerald-expansion-1.17.2")\n            with self.assertRaises(ProviderPackError):\n                export_manifest(pack, meta, digest, "unsupported")
            self.assertEqual([r["offset"] for r in manifest["resources"]],
                             [HEADER.size, HEADER.size + PAGE_BYTES])
            for row, page in zip(manifest["resources"], pages):
                self.assertEqual(packed[row["offset"]:row["offset"] + row["length"]], page)
                self.assertEqual(row["sha256"], hashlib.sha256(page).hexdigest())
            with self.assertRaises(ProviderPackError):
                export_manifest(pack, meta, "not-a-sha", "emerald")
            with self.assertRaises(ProviderPackError):
                write_manifest(pack, meta, pack, digest, "emerald")
            pack.write_bytes(packed[:-1] + b"x")
            with self.assertRaises(ProviderPackError):
                export_manifest(pack, meta, digest, "emerald")


if __name__ == "__main__":
    unittest.main()

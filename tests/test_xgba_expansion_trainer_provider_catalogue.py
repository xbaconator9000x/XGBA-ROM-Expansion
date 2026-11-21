"""Private provider catalogue contract tests; synthetic tiles only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_provider_catalogue import (
    PAGE_BYTES, PAGE_CAPACITY, PINNED_RHH, ProviderPackError, build_catalogue,
)


class TrainerProviderCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.resource = "rhh.trainer.0123"
        self.page = bytes(i % 251 for i in range(PAGE_BYTES))
        self.path = self.root / (self.resource + ".bin")
        self.path.write_bytes(self.page)
        self.manifest = {
            "resource_id": self.resource, "source_release_sha": PINNED_RHH,
            "bytes": PAGE_BYTES, "page_capacity": PAGE_CAPACITY,
            "requires_private_provider": True,
            "page_sha256": hashlib.sha256(self.page).hexdigest(),
        }
        self.manifest_path = self.root / (self.resource + ".json")
        self.save()

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_catalogue_uses_verified_original_resource_keys(self):
        result = build_catalogue(self.root)
        self.assertEqual(result["format"], "xgba-private-trainer-pages-v1")
        self.assertEqual(result["lease_capacity"], 16384)
        self.assertEqual(result["entries"][0]["resource_id"], self.resource)
        self.assertEqual(result["entries"][0]["sha256"], hashlib.sha256(self.page).hexdigest())

    def test_modified_page_rejected(self):
        self.path.write_bytes(b"X" * PAGE_BYTES)
        with self.assertRaisesRegex(ProviderPackError, "digest mismatch"):
            build_catalogue(self.root)

    def test_wrong_release_and_capacity_rejected(self):
        for field, value in (("source_release_sha", "0" * 40),
                             ("page_capacity", PAGE_CAPACITY * 2),
                             ("requires_private_provider", False)):
            with self.subTest(field=field):
                original = self.manifest[field]
                self.manifest[field] = value
                self.save()
                with self.assertRaisesRegex(ProviderPackError, "page contract"):
                    build_catalogue(self.root)
                self.manifest[field] = original
                self.save()

    def test_missing_and_truncated_page_rejected(self):
        self.path.write_bytes(self.page[:-1])
        with self.assertRaisesRegex(ProviderPackError, "size mismatch"):
            build_catalogue(self.root)
        self.path.unlink()
        with self.assertRaisesRegex(ProviderPackError, "missing"):
            build_catalogue(self.root)

    def test_mismatched_resource_identity_rejected(self):
        self.manifest["resource_id"] = "rhh.trainer.ffff"
        self.save()
        with self.assertRaisesRegex(ProviderPackError, "identity mismatch"):
            build_catalogue(self.root)

    def test_no_pages_rejected(self):
        self.manifest_path.unlink()
        with self.assertRaisesRegex(ProviderPackError, "no private trainer"):
            build_catalogue(self.root)


if __name__ == "__main__":
    unittest.main()

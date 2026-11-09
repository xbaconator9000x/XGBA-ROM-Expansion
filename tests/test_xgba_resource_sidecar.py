"""Positive and fail-closed controls for the opt-in XGBA sidecar reader."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "xgba_resource_sidecar.py"
SPEC = importlib.util.spec_from_file_location("xgba_resource_sidecar", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def identity():
    return {"id": "test-source", "sha256": "a" * 64}


class ResourceSidecarTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_path = self.root / "assets.bin"
        self.manifest_path = self.root / "assets.json"
        self.payload = b"synthetic-resource-data"
        self.data_path.write_bytes(self.payload)
        self.write_manifest()

    def resource(self, *, resource_id="texture.main", offset=0, data=None, length=None,
                 digest=None):
        data = self.payload if data is None else data
        return {
            "id": resource_id,
            "offset": offset,
            "length": len(data) if length is None else length,
            "sha256": hashlib.sha256(data).hexdigest() if digest is None else digest,
        }

    def write_manifest(self, *, resources=None, data_file="assets.bin", source=None,
                       version=1, extra=None):
        document = {
            "format": module.FORMAT,
            "version": version,
            "source_identity": identity() if source is None else source,
            "data_file": data_file,
            "resources": [self.resource()] if resources is None else resources,
        }
        if extra:
            document.update(extra)
        self.manifest_path.write_text(json.dumps(document), encoding="utf-8")

    def test_reads_resource_in_bounded_chunks_and_checks_source_identity(self):
        manifest = module.load_manifest(self.manifest_path, identity())
        chunks = list(module.iter_resource_chunks(manifest, "texture.main", 5))
        self.assertEqual(b"".join(chunks), self.payload)
        self.assertTrue(all(0 < len(chunk) <= 5 for chunk in chunks))
        self.assertEqual(manifest.source_identity, module.SourceIdentity(**identity()))

    def test_sparse_96_mib_sidecar_reads_asset_above_32_mib_in_chunks(self):
        offset = 40 * 1024 * 1024
        total_size = 96 * 1024 * 1024
        asset = bytes(range(251)) * 37
        with self.data_path.open("wb") as handle:
            handle.truncate(total_size)
            handle.seek(offset)
            handle.write(asset)
        self.write_manifest(resources=[self.resource(
            offset=offset, data=asset
        )])

        manifest = module.load_manifest(self.manifest_path)
        chunks = list(module.iter_resource_chunks(manifest, "texture.main", 1024))
        self.assertEqual(self.data_path.stat().st_size, total_size)
        self.assertEqual(b"".join(chunks), asset)
        self.assertGreater(offset, 32 * 1024 * 1024)
        self.assertTrue(all(len(chunk) <= 1024 for chunk in chunks))

    def test_rejects_duplicate_resource_ids_and_duplicate_json_keys(self):
        resource = self.resource()
        self.write_manifest(resources=[resource, dict(resource)])
        with self.assertRaisesRegex(ValueError, "Duplicate resource ID"):
            module.load_manifest(self.manifest_path)
        self.manifest_path.write_text(
            '{"format":"xgba-resource-manifest","format":"other"}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate manifest key"):
            module.load_manifest(self.manifest_path)

    def test_rejects_unknown_version_malformed_fields_and_source_mismatch(self):
        self.write_manifest(version=2)
        with self.assertRaisesRegex(ValueError, "version"):
            module.load_manifest(self.manifest_path)
        self.write_manifest(extra={"unexpected": True})
        with self.assertRaisesRegex(ValueError, "Malformed manifest fields"):
            module.load_manifest(self.manifest_path)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "does not match"):
            module.load_manifest(
                self.manifest_path,
                {"id": "other-source", "sha256": "a" * 64},
            )

    def test_rejects_invalid_resource_metadata_and_hash_format(self):
        for value in (True, 1.5, -1, module.MAX_U64 + 1):
            with self.subTest(offset=value):
                self.write_manifest(resources=[self.resource(offset=value)])
                with self.assertRaisesRegex(ValueError, "offset"):
                    module.load_manifest(self.manifest_path)
        self.write_manifest(resources=[self.resource(digest="not-a-digest")])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            module.load_manifest(self.manifest_path)
        self.write_manifest(resources=[self.resource(resource_id="../escape")])
        with self.assertRaisesRegex(ValueError, "resource ID"):
            module.load_manifest(self.manifest_path)

    def test_rejects_uint64_overflow_and_out_of_bounds_ranges(self):
        self.write_manifest(resources=[self.resource(
            offset=module.MAX_U64 - 1, length=3
        )])
        with self.assertRaisesRegex(ValueError, "overflows uint64"):
            module.load_manifest(self.manifest_path)
        self.write_manifest(resources=[self.resource(
            offset=len(self.payload) - 2, length=3
        )])
        with self.assertRaisesRegex(ValueError, "out of bounds"):
            module.load_manifest(self.manifest_path)
        self.write_manifest(resources=[self.resource(length=0)])
        with self.assertRaisesRegex(ValueError, "length"):
            module.load_manifest(self.manifest_path)

    def test_rejects_path_escape_and_symlink_escape(self):
        self.write_manifest(data_file="../outside.bin")
        with self.assertRaisesRegex(ValueError, "within the manifest directory"):
            module.load_manifest(self.manifest_path)

        outside = self.root.parent / (self.root.name + "-outside.bin")
        outside.write_bytes(self.payload)
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        link = self.root / "outside-link.bin"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError):
            self.skipTest("symlinks are unavailable")
        self.write_manifest(data_file=link.name)
        with self.assertRaisesRegex(ValueError, "escapes"):
            module.load_manifest(self.manifest_path)

    def test_rejects_truncation_after_manifest_load_and_hash_mismatch(self):
        manifest = module.load_manifest(self.manifest_path)
        chunks = module.iter_resource_chunks(manifest, "texture.main", 4)
        self.assertEqual(next(chunks), self.payload[:4])
        with self.data_path.open("r+b") as handle:
            handle.truncate(4)
        with self.assertRaisesRegex(ValueError, "Truncated resource content"):
            next(chunks)

        self.data_path.write_bytes(b"X" + self.payload[1:])
        manifest = module.load_manifest(self.manifest_path)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            list(module.iter_resource_chunks(manifest, "texture.main", 4))

    def test_rejects_invalid_chunk_sizes_and_unknown_resources(self):
        manifest = module.load_manifest(self.manifest_path)
        for size in (0, -1, module.MAX_CHUNK_SIZE + 1, True):
            with self.subTest(chunk_size=size):
                with self.assertRaisesRegex(ValueError, "chunk_size"):
                    list(module.iter_resource_chunks(manifest, "texture.main", size))
        with self.assertRaisesRegex(ValueError, "Unknown resource ID"):
            list(module.iter_resource_chunks(manifest, "missing"))


if __name__ == "__main__":
    unittest.main()

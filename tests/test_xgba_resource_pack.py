"""Deterministic packing and failure controls for XGBA resource sidecars."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
PACK_SPEC = importlib.util.spec_from_file_location(
    "xgba_resource_pack", TOOLS / "xgba_resource_pack.py"
)
packer = importlib.util.module_from_spec(PACK_SPEC)
sys.modules[PACK_SPEC.name] = packer
PACK_SPEC.loader.exec_module(packer)
sidecar = packer.sidecar

PACK_IDENTITY = {"id": "test-pack", "sha256": "c" * 64}


class ResourcePackTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = []

    def write_source(self, name, resources):
        data_path = self.root / f"{name}.bin"
        manifest_path = self.root / f"{name}.json"
        data = bytearray()
        entries = []
        for resource_id, content in resources:
            entries.append({
                "id": resource_id,
                "offset": len(data),
                "length": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
            data.extend(content)
        data_path.write_bytes(data)
        manifest_path.write_text(json.dumps({
            "format": sidecar.FORMAT,
            "version": sidecar.VERSION,
            "source_identity": {"id": name, "sha256": "a" * 64},
            "data_file": data_path.name,
            "resources": entries,
        }), encoding="utf-8")
        self.sources.append((manifest_path, data_path))
        return manifest_path, data_path

    def assert_no_temporary_outputs(self):
        self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_build_is_byte_identical_and_emits_sorted_stable_ids(self):
        first, _ = self.write_source(
            "first", [("zeta", b"last"), ("alpha", b"first")]
        )
        second, _ = self.write_source("second", [("middle", b"middle")])
        output = self.root / "packed.json"

        packer.build_pack([first, second], output, PACK_IDENTITY, chunk_size=2)
        first_manifest = output.read_bytes()
        manifest = sidecar.load_manifest(output, PACK_IDENTITY)
        self.assertEqual(list(manifest.resources), ["alpha", "middle", "zeta"])
        self.assertEqual(
            b"".join(sidecar.iter_resource_chunks(manifest, "alpha", 1)),
            b"first",
        )
        self.assertEqual(
            b"".join(sidecar.iter_resource_chunks(manifest, "middle", 2)),
            b"middle",
        )
        self.assertEqual(
            b"".join(sidecar.iter_resource_chunks(manifest, "zeta", 3)),
            b"last",
        )
        first_blob = manifest.data_path.read_bytes()

        packer.build_pack([first, second], output, PACK_IDENTITY, chunk_size=7)
        self.assertEqual(output.read_bytes(), first_manifest)
        self.assertEqual(manifest.data_path.read_bytes(), first_blob)

    def test_rejects_duplicate_ids_across_source_manifests(self):
        first, _ = self.write_source("first", [("same", b"one")])
        second, _ = self.write_source("second", [("same", b"two")])
        output = self.root / "packed.json"

        with self.assertRaisesRegex(ValueError, "Duplicate resource ID: same"):
            packer.build_pack([first, second], output, PACK_IDENTITY)
        self.assertFalse(output.exists())
        self.assert_no_temporary_outputs()

    def test_corrupted_source_payload_is_not_published(self):
        source, data_path = self.write_source("source", [("texture", b"original")])
        data_path.write_bytes(b"corrupt!")
        output = self.root / "packed.json"

        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            packer.build_pack([source], output, PACK_IDENTITY)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob("xgba-*.bin")))
        self.assert_no_temporary_outputs()

    def test_write_failure_preserves_existing_pack(self):
        source, _ = self.write_source("source", [("texture", b"replacement")])
        output = self.root / "packed.json"
        old_source, _ = self.write_source("old", [("old", b"preserve me")])
        packer.build_pack([old_source], output, PACK_IDENTITY)
        old_manifest = output.read_bytes()
        old_blob = sidecar.load_manifest(output).data_path
        old_data = old_blob.read_bytes()

        with mock.patch.object(
            packer, "_write_all", side_effect=OSError("simulated write failure")
        ):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                packer.build_pack([source], output, PACK_IDENTITY)

        self.assertEqual(output.read_bytes(), old_manifest)
        self.assertEqual(old_blob.read_bytes(), old_data)
        self.assert_no_temporary_outputs()

    def test_failed_manifest_replace_rolls_back_new_blob(self):
        source, _ = self.write_source("source", [("texture", b"new payload")])
        old_source, _ = self.write_source("old", [("old", b"old payload")])
        output = self.root / "packed.json"
        packer.build_pack([old_source], output, PACK_IDENTITY)
        old_manifest = output.read_bytes()
        old_blob = sidecar.load_manifest(output).data_path
        old_data = old_blob.read_bytes()

        with mock.patch.object(
            packer.os, "replace", side_effect=OSError("simulated publish failure")
        ):
            with self.assertRaisesRegex(OSError, "simulated publish failure"):
                packer.build_pack([source], output, PACK_IDENTITY)

        self.assertEqual(output.read_bytes(), old_manifest)
        self.assertEqual(old_blob.read_bytes(), old_data)
        self.assertEqual(list(self.root.glob("xgba-*.bin")), [old_blob])
        self.assert_no_temporary_outputs()

    def test_rejects_invalid_chunk_size_and_output_alias(self):
        source, data_path = self.write_source("source", [("texture", b"asset")])
        for chunk_size in (0, -1, True, sidecar.MAX_CHUNK_SIZE + 1):
            with self.subTest(chunk_size=chunk_size):
                with self.assertRaisesRegex(ValueError, "chunk_size"):
                    packer.build_pack(
                        [source], self.root / "packed.json", PACK_IDENTITY,
                        chunk_size=chunk_size,
                    )
        with self.assertRaisesRegex(ValueError, "input file"):
            packer.build_pack([source], data_path, PACK_IDENTITY)


if __name__ == "__main__":
    unittest.main()

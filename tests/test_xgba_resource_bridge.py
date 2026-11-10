"""Lifecycle and negative controls for opt-in XGBA host resource staging."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import xgba_resource_bridge as bridge_module
import xgba_resource_pack as packer

SOURCE_ID = "synthetic-rom"


class NativeRoutes:
    def __init__(self):
        self.calls = []
        self.routes = {
            "rom0": lambda: self._read("rom0"),
            "matrix": lambda: self._read("matrix"),
            "eeprom": lambda: self._read("eeprom"),
            "ereader": lambda: self._read("ereader"),
            "flash_read": lambda: self._read("flash_read"),
            "flash_write": lambda: self._read("flash_write"),
        }

    def _read(self, name):
        self.calls.append(name)
        return f"native:{name}"

    def dispatch(self, name):
        return self.routes[name]()


class ResourceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rom = bytearray(32 * 1024 * 1024)
        self.source_identity = {
            "id": SOURCE_ID,
            "sha256": hashlib.sha256(self.rom).hexdigest(),
        }
        self.bridge = bridge_module.ResourceBridge(
            self.rom,
            self.source_identity,
            max_resource_bytes=32,
            max_staged_bytes=48,
            chunk_size=3,
        )

    def make_pack(self, name, resources, identity=None):
        identity = self.source_identity if identity is None else identity
        data_path = self.root / f"{name}-source.bin"
        source_path = self.root / f"{name}-source.json"
        packed_path = self.root / f"{name}-pack.json"
        data = bytearray()
        entries = []
        for resource_id, content in resources.items():
            entries.append({
                "id": resource_id,
                "offset": len(data),
                "length": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
            data.extend(content)
        data_path.write_bytes(data)
        source_path.write_text(json.dumps({
            "format": packer.sidecar.FORMAT,
            "version": packer.sidecar.VERSION,
            "source_identity": identity,
            "data_file": data_path.name,
            "resources": entries,
        }), encoding="utf-8")
        packer.build_pack([source_path], packed_path, identity, chunk_size=2)
        return packed_path

    def test_open_stage_close_and_reopen_preserve_original_rom_reference(self):
        pack = self.make_pack("first", {"map.main": b"synthetic map"})
        original_contents = bytes(self.rom[:32])

        self.bridge.open(pack)
        staged = self.bridge.stage("map.main")
        self.assertEqual(bytes(staged), b"synthetic map")
        self.assertTrue(staged.readonly)
        self.assertIs(self.bridge.original_rom, self.rom)
        self.assertEqual(bytes(self.rom[:32]), original_contents)
        self.bridge.close()
        self.assertFalse(self.bridge.is_open)
        self.assertEqual(self.bridge.staged_resource_ids, ())
        with self.assertRaisesRegex(RuntimeError, "not open"):
            self.bridge.stage("map.main")

        self.bridge.open(pack)
        self.assertEqual(bytes(self.bridge.stage("map.main")), b"synthetic map")
        self.assertIs(self.bridge.original_rom, self.rom)

    def test_pack_replacement_replaces_only_named_host_staging(self):
        first = self.make_pack("first", {"texture.main": b"old"})
        second = self.make_pack("second", {"texture.main": b"new payload"})
        self.bridge.open(first)
        old_buffer = self.bridge.stage("texture.main")

        self.bridge.open(second)

        self.assertEqual(self.bridge.staged_resource_ids, ())
        self.assertEqual(bytes(old_buffer), b"old")
        self.assertEqual(bytes(self.bridge.stage("texture.main")), b"new payload")
        self.assertIs(self.bridge.original_rom, self.rom)

    def test_wrong_rom_identity_fails_without_replacing_active_pack_or_buffers(self):
        valid = self.make_pack("valid", {"texture.main": b"valid"})
        wrong = self.make_pack(
            "wrong",
            {"texture.main": b"wrong"},
            {"id": "different-rom", "sha256": "b" * 64},
        )
        self.bridge.open(valid)
        staged = self.bridge.stage("texture.main")

        with self.assertRaisesRegex(ValueError, "does not match original ROM"):
            bridge_module.ResourceBridge(
                self.rom,
                {"id": SOURCE_ID, "sha256": "c" * 64},
            )
        with self.assertRaisesRegex(ValueError, "does not match expected"):
            self.bridge.open(wrong)

        self.assertTrue(self.bridge.is_open)
        self.assertEqual(bytes(self.bridge.staged_resource("texture.main")), b"valid")
        self.assertEqual(bytes(staged), b"valid")

    def test_savestate_identity_drift_is_rejected(self):
        pack = self.make_pack("state", {"map.main": b"map"})
        self.bridge.open(pack)

        self.bridge.validate_savestate_identity(self.source_identity)
        with self.assertRaisesRegex(ValueError, "Savestate source identity"):
            self.bridge.validate_savestate_identity(
                {"id": "synthetic-rom", "sha256": "b" * 64}
            )

    def test_corrupt_replacement_rolls_back_to_previous_staged_buffer(self):
        pack = self.make_pack("corrupt", {"texture.main": b"verified"})
        self.bridge.open(pack)
        previous = self.bridge.stage("texture.main")
        manifest = packer.sidecar.load_manifest(pack)
        with manifest.data_path.open("r+b") as handle:
            handle.seek(0)
            handle.write(b"X")

        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.bridge.stage("texture.main")

        self.assertEqual(bytes(self.bridge.staged_resource("texture.main")), b"verified")
        self.assertEqual(bytes(previous), b"verified")

    def test_resource_and_total_limits_are_enforced_without_partial_staging(self):
        pack = self.make_pack(
            "bounded", {"small": b"12345", "large": b"x" * 33, "other": b"67890"}
        )
        self.bridge.max_staged_bytes = 8
        self.bridge.open(pack)

        with self.assertRaisesRegex(ValueError, "per-resource"):
            self.bridge.stage("large")
        self.bridge.stage("small")
        with self.assertRaisesRegex(ValueError, "aggregate"):
            self.bridge.stage("other")
        self.assertEqual(self.bridge.staged_resource_ids, ("small",))
        self.assertEqual(self.bridge.staged_bytes, 5)

    def test_native_cartridge_routes_are_never_replaced_or_intercepted(self):
        pack = self.make_pack("routes", {"sprite": b"host-only"})
        native = NativeRoutes()
        original_routes = dict(native.routes)

        self.bridge.open(pack)
        self.bridge.stage("sprite")
        self.bridge.close()
        self.bridge.open(pack)
        self.bridge.stage("sprite")

        self.assertEqual(native.routes.keys(), original_routes.keys())
        for route, handler in original_routes.items():
            with self.subTest(route=route):
                self.assertIs(native.routes[route], handler)
                self.assertEqual(native.dispatch(route), f"native:{route}")
        self.assertEqual(
            native.calls,
            ["rom0", "matrix", "eeprom", "ereader", "flash_read", "flash_write"],
        )
        self.assertIs(self.bridge.original_rom, self.rom)


if __name__ == "__main__":
    unittest.main()

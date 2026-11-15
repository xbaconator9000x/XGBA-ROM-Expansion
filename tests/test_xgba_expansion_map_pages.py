"""Source-owned original map and 4bpp tile page packaging regression."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_expansion_map_pages as source_pages
import xgba_resource_sidecar as sidecar


class SourcePagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "upstream"
        (self.source / "data/layouts/Town").mkdir(parents=True)
        self.raw = bytes((i * 3) % 256 for i in range(20 * 30 * 2))
        (self.source / "data/layouts/Town/map.bin").write_bytes(self.raw)
        (self.source / "data/layouts/layouts.json").write_text(json.dumps({
            "layouts": [
                {"id": "LAYOUT_SAMPLE", "name": "Town_Layout",
                 "width": 20, "height": 30,
                 "layout_version": "emerald",
                 "blockdata_filepath": "data/layouts/Town/map.bin"},
            ]}))
        (self.source / "pokeemerald.gba").write_bytes(b"private unit test rom")
        self.output = self.root / "output"

    def test_real_source_map_bytes_and_id_no_recataloguing(self):
        report = source_pages.build(self.source, "emerald", "LAYOUT_SAMPLE", self.output)
        self.assertEqual(report["map_pages"], 1)
        self.assertEqual(report["resource_ids"], ["rhh.m.0001.00"])
        manifest = sidecar.load_manifest(report["private_manifest"])
        resource = manifest.get_resource("rhh.m.0001.00")
        self.assertEqual(resource.sha256, hashlib.sha256(self.raw).hexdigest())
        with manifest.data_path.open("rb") as stream:
            stream.seek(resource.offset)
            self.assertEqual(stream.read(resource.length), self.raw)
        self.assertFalse(report["runtime_gameplay_verified"])

    def test_dimensions_corruption_rejected(self):
        (self.source / "data/layouts/Town/map.bin").write_bytes(self.raw[:-2])
        with self.assertRaisesRegex(source_pages.SourceAssetError, "dimensions"):
            source_pages.build(self.source, "emerald", "LAYOUT_SAMPLE", self.output)

    def test_wrong_game_and_path_traversal_rejected(self):
        with self.assertRaisesRegex(source_pages.SourceAssetError, "does not belong"):
            source_pages.build(self.source, "firered", "LAYOUT_SAMPLE", self.output)
        with self.assertRaisesRegex(source_pages.SourceAssetError, "escapes checkout"):
            source_pages.safe_source_path(self.source, "../outside")
        with self.assertRaisesRegex(source_pages.SourceAssetError, "not found"):
            source_pages.safe_source_path(self.source, "missing.png")

    def test_original_layout_ids_not_swapped(self):
        doc = json.loads((self.source / "data/layouts/layouts.json").read_text())
        doc["layouts"].insert(0, {
            "id": "LAYOUT_OTHER", "width": 3, "height": 3,
            "layout_version": "frlg", "blockdata_filepath": "not/loaded.bin"})
        (self.source / "data/layouts/layouts.json").write_text(json.dumps(doc))
        report = source_pages.build(self.source, "emerald", "LAYOUT_SAMPLE", self.output)
        self.assertEqual(report["resource_ids"], ["rhh.m.0002.00"])

    def test_original_frlg_20k_primary_tileset_spans_two_pages(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed; required in native build matrix")
        layout = json.loads((self.source / "data/layouts/layouts.json").read_text())
        layout["layouts"][0]["layout_version"] = "frlg"
        (self.source / "data/layouts/layouts.json").write_text(json.dumps(layout))
        (self.source / "pokefirered.gba").write_bytes(b"private synthetic firered test")
        tile = Image.new("P", (128, 320), 0)
        tile.putpalette([i % 256 for i in range(768)])
        (self.source / "data/tilesets").mkdir(parents=True)
        tile.save(self.source / "data/tilesets/primary.png")
        report = source_pages.build(self.source, "firered", "LAYOUT_SAMPLE",
                                    self.output, "data/tilesets/primary.png")
        self.assertEqual(report["primary_pages"], 2)
        manifest = sidecar.load_manifest(report["private_manifest"])
        self.assertEqual(manifest.get_resource("rhh.p.0001.00").length, 16384)
        self.assertEqual(manifest.get_resource("rhh.p.0001.01").length, 4096)
        with manifest.data_path.open("rb") as stream:
            stream.seek(manifest.get_resource("rhh.p.0001.01").offset)
            self.assertEqual(stream.read(4096), bytes(4096))

    def test_partial_tileset_rejected_instead_of_zero_padding(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        (self.source / "data/tilesets").mkdir(parents=True)
        tile = Image.new("P", (128, 80), 0)
        tile.save(self.source / "data/tilesets/partial.png")
        with self.assertRaisesRegex(source_pages.SourceAssetError, "full tileset"):
            source_pages.build(self.source, "emerald", "LAYOUT_SAMPLE",
                               self.output, "data/tilesets/partial.png")


if __name__ == "__main__":
    unittest.main()

"""Regression contract for inherited private battle graphics page validation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_expansion_trainer_pages as trainer


class TrainerInheritedPageContract(unittest.TestCase):
    def test_rejects_overlapping_and_out_of_bounds_pages(self):
        import inspect
        source = inspect.getsource(trainer.build)
        self.assertIn("offset + length > file_size", source)
        self.assertIn("offset < end and start < offset + length", source)
        self.assertIn("intervals.append((offset, offset + length))", source)
        self.assertLess(source.index("offset + length > file_size"),
                        source.index("handle.seek(offset)"))

    def test_original_red_leaf_hiker_page_ids_and_source_bindings(self):
        import inspect
        source = inspect.getsource(trainer.build)
        for number, name, symbol, filename in (
            (3, "RED", "Red", "red.png"),
            (4, "LEAF", "Leaf", "leaf.png"),
            (11, "HIKER", "Hiker", "hiker.png"),
            (105, "HIKER_FRLG", "HikerFrlg", "hiker_frlg.png"),
        ):
            self.assertIn(
                f'({number}, "{name}", "{symbol}", "{filename}", "{symbol}")',
                source)
        self.assertIn('declaration not in graphics or not re.search(binding, graphics)', source)
        self.assertIn('if image.size != (64, 64)', source)
        self.assertIn('if len(raw) != 2048', source)
        self.assertIn('pages.append((f"rhh.trainer.{number:04x}", raw))', source)

    def test_rejects_bool_offsets_and_malformed_entries(self):
        import inspect
        source = inspect.getsource(trainer.build)
        self.assertIn("type(offset) is not int", source)
        self.assertIn("type(length) is not int", source)
        self.assertIn('isinstance(base.get("resources"), list)', source)
        self.assertIn('isinstance(entry, dict)', source)


    def test_written_graphics_verified_before_manifest_publication(self):
        import inspect
        source = inspect.getsource(trainer.build)
        self.assertIn('with data.open("rb") as verify:', source)
        self.assertIn('verify.seek(entry["offset"])', source)
        self.assertIn('actual = verify.read(entry["length"])', source)
        self.assertIn('hashlib.sha256(actual).hexdigest() != entry["sha256"]', source)
        self.assertIn('raise SourceAssetError("private trainer provider write verification failed")', source)
        self.assertLess(source.index('with data.open("rb") as verify:'),
                        source.index('with private_create(manifest, text=True)'))
        self.assertLess(source.index('with private_create(data) as handle:'),
                        source.index('with data.open("rb") as verify:'))

    def test_private_pack_is_exclusively_created_and_failure_cleaned(self):
        import inspect
        source = inspect.getsource(trainer.build)
        self.assertIn('with private_create(data) as handle:', source)
        self.assertIn('with private_create(manifest, text=True) as handle:', source)
        self.assertIn("created_data = False", source)
        self.assertIn("created_data = True", source)
        self.assertIn("created_manifest = True", source)
        self.assertIn("if created_manifest and manifest.exists():", source)
        self.assertIn("manifest.unlink()", source)
        self.assertIn("if created_data and data.exists():", source)
        self.assertIn("data.unlink()", source)
        self.assertLess(source.index('with private_create(data)'),
                        source.index('with manifest.open("x"'))
        self.assertLess(source.index("handle.flush()"),
                        source.index('with manifest.open("x"'))


if __name__ == "__main__":
    unittest.main()

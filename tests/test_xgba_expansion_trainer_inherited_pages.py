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


if __name__ == "__main__":
    unittest.main()

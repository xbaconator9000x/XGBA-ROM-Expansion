"""Safety regressions for private source-authentic trainer provider destinations."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_pages import build, SourceAssetError


class TrainerPrivateOutputSafetyTests(unittest.TestCase):
    def test_rejects_symlinked_output_before_upstream_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "upstream"
            source.mkdir()
            private = root / "private"
            private.mkdir()
            alias = root / "alias"
            alias.symlink_to(private, target_is_directory=True)
            with self.assertRaisesRegex(SourceAssetError, "symlinked private trainer output"):
                build(source, "emerald", alias / "trainer")

    def test_rejects_symlinked_ancestor_before_upstream_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "upstream"
            source.mkdir()
            private = root / "private"
            private.mkdir()
            (root / "alias").symlink_to(private, target_is_directory=True)
            with self.assertRaisesRegex(SourceAssetError, "symlinked private trainer output"):
                build(source, "firered", root / "alias" / "nested" / "trainer")


if __name__ == "__main__":
    unittest.main()

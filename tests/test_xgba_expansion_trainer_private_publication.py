"""Regression tests for private, source-authentic battle provider publication."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from xgba_expansion_trainer_pages import private_create


class PrivateTrainerPublicationTests(unittest.TestCase):
    def test_binary_and_manifest_are_owner_only_even_with_permissive_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.umask(0)
            try:
                binary = Path(directory) / "trainer.bin"
                manifest = Path(directory) / "trainer.json"
                with private_create(binary) as handle:
                    handle.write(b"private trainer tiles")
                with private_create(manifest, text=True) as handle:
                    handle.write('{"private": true}\n')
            finally:
                os.umask(previous)
            for path in (binary, manifest):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(binary.read_bytes(), b"private trainer tiles")
            self.assertEqual(manifest.read_text(), '{"private": true}\n')

    def test_existing_private_pack_cannot_be_clobbered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trainer.bin"
            path.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                private_create(path)
            self.assertEqual(path.read_bytes(), b"original")

    def test_symlink_swap_cannot_redirect_private_asset_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            victim = root / "victim.bin"
            victim.write_bytes(b"preserve")
            link = root / "trainer.bin"
            link.symlink_to(victim)
            with self.assertRaises(OSError):
                private_create(link)
            self.assertEqual(victim.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()

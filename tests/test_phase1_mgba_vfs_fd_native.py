"""Synthetic negative controls; not native or independent semantic approval."""
import importlib.util
import unittest
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_fd_native", ROOT / "tools/phase1_mgba_vfs_fd_native.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
GOOD = (
    "PHASE1_VFS_CASE mappings shared_child=165 private_child=34\n"
    "PHASE1_VFS_CASE cleanup async_ms=1 sync_ms=1 fsync=0 rtc=1 dirty=0 age=100\n"
    "PHASE1_VFS_CASE failure async_ms=1 fsync=2 rtc=0 dirty=0 retried=0 fsync_error=1\n"
    "PHASE1_VFS_CASE close active_mapping_survives=1\n"
    "PHASE1_VFS_DONE\n"
)

class TestVfsFdEvidence(unittest.TestCase):
    def bad(self, source, target):
        changed = GOOD.replace(source, target, 1)
        self.assertNotEqual(changed, GOOD)
        with self.assertRaises(ValueError):
            runner.parse_output(changed)

    def test_positive(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(result["failed_cleanup_retries"], 0)
        self.assertEqual(result["explicit_fsync_calls"], 2)
        self.assertTrue(result["fsync_error_propagated"])

    def test_shared(self): self.bad("shared_child=165", "shared_child=164")
    def test_private(self): self.bad("private_child=34", "private_child=35")
    def test_async(self): self.bad("cleanup async_ms=1", "cleanup async_ms=0")
    def test_sync(self): self.bad("sync_ms=1", "sync_ms=0")
    def test_cleanup_fsync(self): self.bad("cleanup async_ms=1 sync_ms=1 fsync=0", "cleanup async_ms=1 sync_ms=1 fsync=1")
    def test_rtc(self): self.bad("rtc=1", "rtc=0")
    def test_dirty(self): self.bad("dirty=0 age=100", "dirty=1 age=100")
    def test_age(self): self.bad("age=100", "age=99")
    def test_failed_async(self): self.bad("failure async_ms=1", "failure async_ms=0")
    def test_fsync_count(self): self.bad("fsync=2", "fsync=1")
    def test_failed_rtc(self): self.bad("fsync=2 rtc=0", "fsync=2 rtc=1")
    def test_failed_dirty(self): self.bad("fsync=2 rtc=0 dirty=0", "fsync=2 rtc=0 dirty=1")
    def test_retry(self): self.bad("retried=0", "retried=1")
    def test_fsync_error(self): self.bad("fsync_error=1", "fsync_error=0")
    def test_close(self): self.bad("active_mapping_survives=1", "active_mapping_survives=0")
    def test_duplicate_terminal(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD + "PHASE1_VFS_DONE\n")
    def test_missing_terminal(self): self.bad("PHASE1_VFS_DONE\n", "")
    def test_extra_case(self): self.bad("PHASE1_VFS_DONE\n", "PHASE1_VFS_CASE injected=1\nPHASE1_VFS_DONE\n")
    def test_swapped_lines(self):
        lines = GOOD.splitlines(keepends=True)
        lines[1], lines[2] = lines[2], lines[1]
        with self.assertRaises(ValueError):
            runner.parse_output("".join(lines))
    def test_fixture_hash(self):
        fixture = (ROOT / "tests/phase1_mgba_vfs_fd_native.c").read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(), runner.FIXTURE_SHA256)
    def test_internal_mutations(self):
        self.assertEqual(runner.reject_evidence_mutations(GOOD), 6)

if __name__ == "__main__":
    unittest.main()

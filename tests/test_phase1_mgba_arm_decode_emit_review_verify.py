#!/usr/bin/env python3
"""Fail-closed controls for the pinned mGBA ARM source review verifier."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import phase1_mgba_arm_decode_emit_review_verify as verifier


class PinnedARMVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xgba-arm-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = "src/arm/example.c"
        self.raw = b"first\nsecond\n"
        self.target = self.root / self.path
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_bytes(self.raw)
        self.blob = hashlib.sha1(
            b"blob " + str(len(self.raw)).encode() + b"\0" + self.raw
        ).hexdigest()
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def test_real_git_blob_identity(self):
        self.assertEqual(verifier.git_blob(self.raw), self.blob)

    def test_exact_source_bytes_pass(self):
        self.assertEqual(
            verifier.require_source(self.root, self.path, self.blob, self.digest),
            self.raw,
        )

    def test_mutated_source_bytes_fail(self):
        self.target.write_bytes(self.raw + b"X")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verifier.require_source(self.root, self.path, self.blob, self.digest)

    def test_wrong_blob_fails(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verifier.require_source(self.root, self.path, "0" * 40, self.digest)

    def test_wrong_sha256_fails(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verifier.require_source(self.root, self.path, self.blob, "0" * 64)

    def test_missing_source_fails(self):
        with self.assertRaises(FileNotFoundError):
            verifier.require_source(self.root, "missing.c", self.blob, self.digest)

    def test_correct_line_anchor_passes(self):
        verifier.check_anchors(self.raw, self.path, [(1, "first"), (2, "second")])

    def test_wrong_line_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "anchor mismatch"):
            verifier.check_anchors(self.raw, self.path, [(2, "first")])

    def test_out_of_range_line_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "anchor mismatch"):
            verifier.check_anchors(self.raw, self.path, [(3, "third")])

    def test_zero_line_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "anchor mismatch"):
            verifier.check_anchors(self.raw, self.path, [(0, "second")])

    def test_negative_line_anchor_fails(self):
        with self.assertRaisesRegex(ValueError, "anchor mismatch"):
            verifier.check_anchors(self.raw, self.path, [(-1, "second")])

    def test_missing_git_checkout_fails_closed(self):
        with mock.patch.object(
            verifier.subprocess, "check_output",
            side_effect=subprocess.CalledProcessError(128, ["git"]),
        ):
            with self.assertRaisesRegex(ValueError, "HEAD is unavailable"):
                verifier.verify_sources(self.root)

    def test_wrong_git_commit_fails_closed(self):
        with mock.patch.object(
            verifier.subprocess, "check_output", return_value="0" * 40 + "\n",
        ):
            with self.assertRaisesRegex(ValueError, "not the pinned commit"):
                verifier.verify_sources(self.root)

    def test_pinned_git_commit_still_requires_all_source_bytes(self):
        with mock.patch.object(
            verifier.subprocess, "check_output", return_value=verifier.PIN + "\n",
        ):
            with self.assertRaises(FileNotFoundError):
                verifier.verify_sources(self.root)


if __name__ == "__main__":
    unittest.main()

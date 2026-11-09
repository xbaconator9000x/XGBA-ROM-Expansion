#!/usr/bin/env python3
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import phase1_mgba_arm_decoder_abi_probe as probe
from tools.phase1_bulk_triage import canonical, digest


LAYOUT_DUMP = """
         0 | struct ARMInstructionInfo
        32:0-0 |   unsigned int execMode
        32:1-1 |   _Bool traps
        32:2-2 |   _Bool affectsCPSR
        32:3-5 |   unsigned int branchType
        32:6-9 |   unsigned int condition
        33:2-7 |   unsigned int mnemonic
        34:0-2 |   unsigned int iCycles
        34:3-6 |   unsigned int cCycles
       34:7-10 |   unsigned int sInstructionCycles
        35:3-6 |   unsigned int nInstructionCycles
        36:0-9 |   unsigned int sDataCycles
        37:2-11 |   unsigned int nDataCycles
           | [sizeof=40, align=4]
"""


class ARMDecoderABIProbeTests(unittest.TestCase):
    def test_exact_arm_target_layout_is_parsed(self):
        layout = probe.parse_record_layout(LAYOUT_DUMP)
        self.assertEqual(layout, probe.EXPECTED_LAYOUT)

    def test_mutated_bitfield_layout_fails_closed(self):
        mutated = LAYOUT_DUMP.replace("32:3-5", "32:2-4")
        with self.assertRaisesRegex(ValueError, "differs"):
            probe.parse_record_layout(mutated)

    def test_missing_layout_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            probe.parse_record_layout("no record layout")

    def test_source_mutation_fails_blob_and_sha256_checks(self):
        data = b"pinned header\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decoder.h"
            path.write_bytes(data + b"mutated\n")
            expected_blob = hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest()
            expected_sha = hashlib.sha256(data).hexdigest()
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                probe.require_source(Path(directory), "decoder.h", expected_blob, expected_sha)

    def test_dossier_identity_and_row_hash_mutations_fail(self):
        dossier = {
            "provenance": {
                "repository": "mgba-emu/mgba",
                "pinned_revision": "pin",
                "path": "decoder.h",
                "git_blob_sha": "blob",
                "source_content_sha256": "source",
            },
            "review": {"semantic_signoff": False},
        }
        row = {
            "blob_sha": "blob",
            "evidence_sha256": digest(canonical(dossier)),
            "category": "source",
            "priority": "P0",
            "machine_review_status": "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
        }
        with mock.patch.multiple(
            probe,
            DOSSIER_SHA256=row["evidence_sha256"],
            SOURCE_BLOB="blob",
            SOURCE_SHA256="source",
            PIN="pin",
            SOURCE="decoder.h",
        ):
            probe._check_dossier_row(row, dossier)
            changed = dict(dossier)
            changed["provenance"] = dict(dossier["provenance"], source_content_sha256="changed")
            with self.assertRaisesRegex(ValueError, "row SHA-256 mismatch"):
                probe._check_dossier_row(row, changed)
            with self.assertRaisesRegex(ValueError, "row SHA-256 mismatch"):
                probe._check_dossier_row(dict(row, evidence_sha256="0" * 64), dossier)

    def test_status_is_never_an_approval_or_gate_disposition(self):
        self.assertEqual(probe.SCHEMA, "xgba.phase1.mgba_arm_decoder_abi_probe.v1")
        self.assertEqual(probe.EXPECTED_LAYOUT["size"], 40)
        self.assertEqual(probe.PIN, "fd9dc5c2cbf234365068855851107e762fc6211b")


if __name__ == "__main__":
    unittest.main()

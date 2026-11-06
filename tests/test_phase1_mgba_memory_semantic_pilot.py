import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import phase1_mgba_memory_semantic_pilot as pilot
from phase1_bulk_triage import git_blob


class MGBAMemorySemanticPilotTests(unittest.TestCase):
    def test_exact_source_blob_is_required(self):
        source = b"pinned source\n"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.c"
            path.write_bytes(source)
            spec = {"path": "source.c", "blob": git_blob(source)}
            self.assertEqual(pilot._read_source(Path(temporary), spec), source)
            path.write_bytes(source + b"drift\n")
            with self.assertRaisesRegex(ValueError, "source drift"):
                pilot._read_source(Path(temporary), spec)

    def test_unknown_or_unfetched_documentation_cannot_support_claims(self):
        pilot.validate_references(list(pilot.REFERENCES), set())
        with self.assertRaisesRegex(ValueError, "ungrounded"):
            pilot.validate_references(list(pilot.REFERENCES), {"unlisted-doc"})

        unverified_claim = [dict(reference) for reference in pilot.REFERENCES]
        unverified_claim[0]["used_to_support_pilot_claim"] = True
        with self.assertRaisesRegex(ValueError, "lacks retrieved content hash"):
            pilot.validate_references(unverified_claim, {"GBATEK"})

    def test_document_claim_ids_and_flags_must_agree_in_both_directions(self):
        # A caller may not cite GBATEK while the reference marks it unused.
        with self.assertRaisesRegex(ValueError, "flags and claimed IDs disagree"):
            pilot.validate_references(list(pilot.REFERENCES), {"GBATEK"})

        references = [dict(reference) for reference in pilot.REFERENCES]
        references[0]["used_to_support_pilot_claim"] = True
        # Nor may the reference claim support without a corresponding citation.
        with self.assertRaisesRegex(ValueError, "flags and claimed IDs disagree"):
            pilot.validate_references(references, set())
        # Matching claim flags still require retrieved-and-hashed provenance.
        with self.assertRaisesRegex(ValueError, "lacks retrieved content hash"):
            pilot.validate_references(references, {"GBATEK"})

        references[0]["content_sha256"] = hashlib.sha256(b"test-only retrieved document").hexdigest()
        references[0]["retrieval"] = "RETRIEVED_AND_HASHED"
        pilot.validate_references(references, {"GBATEK"})
        references[0]["retrieval"] = "UNVERIFIED_EXTERNAL_REFERENCE_ONLY"
        with self.assertRaisesRegex(ValueError, "not verified"):
            pilot.validate_references(references, {"GBATEK"})
        references[0]["used_to_support_pilot_claim"] = "yes"
        with self.assertRaisesRegex(ValueError, "explicit boolean"):
            pilot.validate_references(references, {"GBATEK"})

    def test_all_six_rom_window_bases_are_individually_anchored(self):
        bases = [
            ("ROM0", "0x08000000"),
            ("ROM0_EX", "0x09000000"),
            ("ROM1", "0x0A000000"),
            ("ROM1_EX", "0x0B000000"),
            ("ROM2", "0x0C000000"),
            ("ROM2_EX", "0x0D000000"),
        ]
        lines = [f"GBA_BASE_{name} = {value}," for name, value in bases]
        lines.append("GBA_SIZE_ROM0 = 0x02000000,")
        source = ("\n".join(lines) + "\n").encode()
        anchors = pilot.SOURCES[0]["anchors"]
        result = pilot._anchors(source, anchors, "include/mgba/internal/gba/memory.h")
        self.assertEqual(len(result), 7)
        for name, value in bases:
            mutated = source.replace(f"GBA_BASE_{name} = {value}".encode(),
                                     f"GBA_BASE_{name} = 0x00000000".encode())
            with self.subTest(selector=name), self.assertRaisesRegex(ValueError, "Missing source anchor"):
                pilot._anchors(mutated, anchors, "include/mgba/internal/gba/memory.h")

    def test_missing_upstream_test_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Missing upstream test"):
            pilot.validate_coverage({})

        source = b""
        bad_coverage = {
            pilot.REQUIRED_TEST_PATH: source,
            "src/gba/CMakeLists.txt": b"set(TEST_FILES test/cheats.c)",
        }
        with self.assertRaisesRegex(ValueError, "case is absent"):
            pilot.validate_coverage(bad_coverage)

    def test_missing_license_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Missing pinned license"):
            pilot.validate_license({})

    def test_license_text_must_match_mpl_and_source_notices(self):
        license_source = b"Mozilla Public License Version 2.0"
        source_by_path = {
            "LICENSE": license_source,
            "src/gba/gba.c": b"Copyright; Mozilla Public License, v. 2.0.",
            "src/gba/memory.c": b"Copyright; Mozilla Public License, v. 2.0.",
            "src/gba/core.c": b"Copyright; Mozilla Public License, v. 2.0.",
            "src/gba/test/core.c": b"Copyright; Mozilla Public License, v. 2.0.",
        }
        pilot.validate_license(source_by_path)
        source_by_path["LICENSE"] = b"MIT"
        with self.assertRaisesRegex(ValueError, "not MPL-2.0"):
            pilot.validate_license(source_by_path)

    def test_output_hash_uses_git_blob_and_sha256_distinctly(self):
        data = b"abc"
        self.assertEqual(git_blob(data), "f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f")
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main()

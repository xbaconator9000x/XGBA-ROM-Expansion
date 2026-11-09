import gzip
import json
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import phase1_inventory_source_index as indexer
from phase1_bulk_triage import (
    PINS, TOTAL, canonical, checked_dossiers, digest, git_blob, read_queue,
)


class InventorySourceIndexTests(unittest.TestCase):
    def test_persisted_inventory_artifact_is_complete_and_never_approves(self):
        artifact = ROOT / (
            "docs/phase1-review-readiness/"
            "inventory-source-index-20261101.json.gz"
        )
        data = json.loads(gzip.decompress(artifact.read_bytes()))
        queue = read_queue(ROOT / "semantic-snapshots/current")
        dossiers = checked_dossiers(ROOT / "semantic-snapshots/current", queue)
        expected = {
            (row["repo"], row["path"]): row for row in queue
        }
        records = data["source_records"]
        self.assertEqual(len(records), TOTAL)
        self.assertEqual(len({
            (record["identity"]["repository"], record["identity"]["path"])
            for record in records
        }), TOTAL)
        self.assertEqual(data["gate"]["decision"], "FAIL_INCOMPLETE")
        self.assertEqual(data["gate"]["legacy_approvals"], 0)
        self.assertEqual(data["gate"]["semantic_dispositions_added"], 0)
        self.assertEqual(data["run"]["indexed_count"], TOTAL)
        self.assertEqual(data["run"]["indexed_p0_count"], 338)
        self.assertEqual(data["run"]["blocked_count"], 0)
        self.assertEqual(data["run"]["unindexed_count"], 0)
        self.assertEqual(data["blocked_or_unindexed_records"], [])
        for record in records:
            identity = record["identity"]
            queue_row = expected[(identity["repository"], identity["path"])]
            self.assertEqual(identity["git_blob_sha1"], queue_row["blob_sha"])
            self.assertEqual(
                record["machine_dossier"]["sha256"],
                queue_row["evidence_sha256"],
            )
            self.assertFalse(record["machine_dossier"]["semantic_signoff"])
            self.assertEqual(record["semantic_review_state"], "NOT_SEMANTICALLY_REVIEWED")
            self.assertEqual(record["approval_state"], "NOT_APPROVED")
            assessment = dossiers[
                (identity["repository"], identity["path"])
            ]["machine_assessment"]
            self.assertEqual(
                record["original_machine_triage"]["rule_counts"],
                assessment["rule_counts"],
            )
            self.assertEqual(
                record["original_machine_triage"]["lexical_sites_total"],
                assessment["lexical_sites_total"],
            )

    def test_cached_index_record_is_bound_to_source_and_original_dossier(self):
        source = b"#include \"memory.h\"\n"
        row = {
            "repo": "mgba-emu/mgba",
            "path": "src/gba/memory.c",
            "blob_sha": git_blob(source),
            "evidence_sha256": "a" * 64,
            "category": "source",
        }
        dossier = {
            "provenance": {
                "tracked_bytes": str(len(source)),
                "source_content_sha256": None,
            },
            "review": {"semantic_signoff": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / row["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(source)
            key = indexer._row_key(row["repo"], row["path"])
            entry = indexer._cache_record(key, row["repo"], row, dossier, source)
            self.assertEqual(
                indexer._validated_cached_record(
                    key, entry, row, dossier, root, None,
                ),
                entry,
            )
            path.write_bytes(source + b"drift")
            with self.assertRaisesRegex(ValueError, "SOURCE_DRIFT_FROM_CACHE"):
                indexer._validated_cached_record(
                    key, entry, row, dossier, root, None,
                )
            path.write_bytes(source)
            wrong_dossier = {
                "provenance": {
                    "tracked_bytes": str(len(source) + 1),
                    "source_content_sha256": None,
                },
                "review": {"semantic_signoff": False},
            }
            with self.assertRaisesRegex(ValueError, "TRACKED_BYTES"):
                indexer._validated_cached_record(
                    key, entry, row, wrong_dossier, root, None,
                )

    def test_crlf_archive_materialization_requires_pinned_attributes_and_blob_match(self):
        stored = b"JASC-PAL\n0100\n"
        attributes = b"*.pal text eol=crlf\n"
        row = {"path": "art/palette.pal", "blob_sha": git_blob(stored)}
        attributes_row = {
            "path": ".gitattributes",
            "blob_sha": git_blob(attributes),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".gitattributes").write_bytes(attributes)
            target = root / row["path"]
            target.parent.mkdir()
            target.write_bytes(stored.replace(b"\n", b"\r\n"))
            actual, materialization = indexer._verified_source_content(
                root, row, attributes_row,
            )
            self.assertEqual(actual, stored)
            self.assertEqual(
                materialization,
                "CRLF_NORMALIZED_USING_PINNED_GITATTRIBUTES",
            )
            target.write_bytes(b"not the pinned palette")
            with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_MISMATCH"):
                indexer._verified_source_content(root, row, attributes_row)

    def test_cache_fails_closed_on_corruption_or_wrong_snapshot(self):
        snapshot_id = {"queue": "a" * 40}
        entry = {
            "cache_key": "mgba-emu/mgba:src/a.c",
            "facts": {"direct_include_literals": []},
        }
        entry["cache_record_sha256"] = digest(canonical(entry))
        payload = {
            "schema": indexer.CACHE_SCHEMA,
            "snapshot_identity": snapshot_id,
            "entries": {entry["cache_key"]: entry},
        }
        with tempfile.TemporaryDirectory() as temporary:
            cache_path = Path(temporary) / "cache.json.gz"
            cache_path.write_bytes(gzip.compress(canonical(payload), mtime=0))
            self.assertEqual(indexer._cache_payload(cache_path, snapshot_id).keys(),
                             {entry["cache_key"]})
            with self.assertRaisesRegex(ValueError, "SNAPSHOT_IDENTITY"):
                indexer._cache_payload(cache_path, {"queue": "b" * 40})
            payload["entries"][entry["cache_key"]]["facts"]["direct_include_literals"] = [
                {"line": 1, "literal": "../outside.h"}
            ]
            cache_path.write_bytes(gzip.compress(canonical(payload), mtime=0))
            with self.assertRaisesRegex(ValueError, "CHECKSUM_MISMATCH"):
                indexer._cache_payload(cache_path, snapshot_id)
            cache_path.write_bytes(b"not gzip")
            with self.assertRaisesRegex(ValueError, "CACHE_INVALID"):
                indexer._cache_payload(cache_path, snapshot_id)

    def test_inventory_path_and_symlink_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            outside = Path(temporary) / "outside.txt"
            root.mkdir()
            outside.write_text("outside")
            with self.assertRaisesRegex(ValueError, "INVALID_INVENTORY_PATH"):
                indexer._source_bytes(root, "../outside.txt")
            (root / "escape").symlink_to(outside)
            self.assertEqual(
                indexer._source_bytes(root, "escape"),
                str(outside).encode(),
            )
            external_dir = Path(temporary) / "external"
            external_dir.mkdir()
            (external_dir / "file.c").write_text("outside")
            (root / "linked-dir").symlink_to(external_dir, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "SOURCE_PATH_ESCAPES_ROOT"):
                indexer._source_bytes(root, "linked-dir/file.c")

    def test_include_candidates_are_not_reported_as_compiler_resolution(self):
        inventory = {"src/x.h", "x.h"}
        ambiguous = indexer._resolve_include("src/main.c", "x.h", inventory)
        self.assertEqual(ambiguous["resolution"], "AMBIGUOUS_PINNED_PATH_CANDIDATES")
        self.assertEqual(ambiguous["candidate_paths"], ["src/x.h", "x.h"])
        unresolved = indexer._resolve_include("src/main.c", "stdint.h", inventory)
        self.assertEqual(
            unresolved["resolution"],
            "UNRESOLVED_OUTSIDE_OR_ABSENT_FROM_PINNED_INVENTORY",
        )

    def test_test_docs_and_license_roles_are_presence_only(self):
        facts = indexer._extract_file_facts(
            b"// test source\n", "tests/test_memory.c", "source",
        )
        self.assertIn(
            "UPSTREAM_TEST_SOURCE_FILE_HASH_VERIFIED_NOT_EXECUTED",
            facts["upstream_evidence_roles"],
        )
        self.assertNotIn("TEST_EXECUTED", facts["upstream_evidence_roles"])
        catalog = {
            "license_file_paths": ["LICENSE"],
            "inventory_license_candidate_paths": ["LICENSE"],
        }
        assessment = indexer._license_assessment(catalog)
        self.assertEqual(assessment["distribution_clearance"], "NOT_ASSESSED")
        self.assertEqual(assessment["state"], "LICENSE_FILES_HASH_VERIFIED")
        self.assertEqual(
            indexer._license_assessment({"license_file_paths": []})["reason_code"],
            "LICENSE_EVIDENCE_MISSING",
        )
        indexer._validate_license_boundary({
            "repo": {"license_assessment": assessment},
        })
        with self.assertRaisesRegex(ValueError, "LICENSE_CLEARANCE_ASSUMPTION"):
            indexer._validate_license_boundary({
                "repo": {"license_assessment": {
                    "distribution_clearance": "CLEARED",
                }},
            })

    def test_test_links_are_candidates_not_coverage(self):
        self.assertEqual(
            indexer._test_link_state(["tests/test_memory.c"], ["tests/test_memory.c"]),
            "DIRECT_TEST_INCLUDE_CANDIDATE_FOUND_NOT_COVERAGE",
        )
        self.assertEqual(
            indexer._test_link_state([], ["tests/test_memory.c"]),
            "NO_DIRECT_TEST_INCLUDE_CANDIDATE_FOUND",
        )
        self.assertEqual(
            indexer._test_link_state([], []),
            "NO_HASH_VERIFIED_TEST_SOURCE_IN_CURRENT_INDEX",
        )

    def test_include_limit_marks_partial_scan_without_blocking_source_identity(self):
        source = b'#include "candidate.h"\n' * (indexer.MAX_INCLUDES_PER_FILE + 1)
        facts = indexer._extract_file_facts(source, "src/main.c", "source")
        self.assertEqual(
            len(facts["direct_include_literals"]),
            indexer.MAX_INCLUDES_PER_FILE,
        )
        self.assertFalse(facts["direct_include_scan_complete"])
        macro_source = b"#include HEADER\n" * (indexer.MAX_INCLUDES_PER_FILE + 1)
        macro_facts = indexer._extract_file_facts(
            macro_source, "src/main.c", "source",
        )
        self.assertEqual(
            len(macro_facts["unsupported_include_lines"]),
            indexer.MAX_INCLUDES_PER_FILE,
        )
        self.assertTrue(macro_facts["unsupported_include_scan_truncated"])
        self.assertFalse(macro_facts["direct_include_scan_complete"])

    def test_missing_test_evidence_cannot_be_claimed(self):
        with self.assertRaisesRegex(ValueError, "UPSTREAM_TEST_EVIDENCE_MISSING"):
            indexer._require_test_evidence([])
        indexer._require_test_evidence(["tests/test_memory.c"])

    def test_unverified_external_references_cannot_support_claims(self):
        indexer._validate_no_unsupported_inference(
            indexer.UNVERIFIED_EXTERNAL_REFERENCES,
            [{"claim_id": "identity", "reference_ids": []}],
        )
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_REFERENCE"):
            indexer._validate_no_unsupported_inference(
                indexer.UNVERIFIED_EXTERNAL_REFERENCES,
                [{"claim_id": "hardware", "reference_ids": ["GBATEK"]}],
            )
        with self.assertRaisesRegex(ValueError, "UNGROUNDED"):
            indexer._validate_no_unsupported_inference(
                indexer.UNVERIFIED_EXTERNAL_REFERENCES,
                [{"claim_id": "unsupported", "reference_ids": ["unknown"]}],
            )

    def test_pins_are_the_canonical_five_repository_set(self):
        self.assertEqual(set(PINS), {
            "pret/pokefirered",
            "mgba-emu/mgba",
            "huderlem/porymap",
            "huderlem/poryscript",
            "pret/agbcc",
        })


if __name__ == "__main__":
    unittest.main()

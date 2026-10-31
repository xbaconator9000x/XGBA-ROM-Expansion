import copy
import gzip
import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import phase1_copilot_receipts_v1 as verifier


class FixtureGit:
    def __init__(self, record, evidence_blobs=None):
        self.record = record
        self.evidence_blobs = evidence_blobs or {}
        self.parent_map = {
            "d" * 40: ["e" * 40],
            "c" * 40: ["d" * 40],
        }
        self.ancestors = {("d" * 40, "c" * 40)}
        self.timestamps = {"d" * 40: 1_700_000_000}

    def commit(self, revision):
        if revision not in {"c" * 40, "d" * 40, "e" * 40}:
            raise ValueError("missing fixture commit")
        return revision

    def parents(self, revision):
        return self.parent_map.get(revision, [])

    def is_ancestor(self, older, newer):
        return (older, newer) in self.ancestors

    def show(self, revision, path):
        if revision == "e" * 40 and path in self.evidence_blobs:
            return self.evidence_blobs[path]
        if revision != "d" * 40 or path != self.record["receipt_path"]:
            raise ValueError("missing fixture blob")
        return verifier.canonical_receipt_file(self.record)

    def commit_timestamp(self, revision):
        return self.timestamps[revision]


class FixtureAPI:
    def __init__(self):
        self.pr = {
            "head": {
                "sha": "c" * 40,
                "ref": "review-branch",
                "repo": {"full_name": "xbaconator9000x/XGBA-ROM-Expansion"},
            },
        }
        self.review = {
            "id": 41,
            "user": {
                "login": "Copilot",
                "id": verifier.BOT_ID,
                "node_id": verifier.BOT_NODE_ID,
                "type": "Bot",
            },
            "commit_id": "c" * 40,
            "state": "COMMENTED",
            "body": "COPILOT_REVIEWED/PASSED",
            "submitted_at": "2026-10-31T12:00:00Z",
        }
        self.runs = {
            51: {
                "run_attempt": 1,
                "event": "pull_request",
                "head_sha": "c" * 40,
                "head_branch": "review-branch",
                "pull_requests": [{"number": 12}],
                "path": verifier.REQUIRED_CHECK_WORKFLOW,
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-10-31T13:00:00Z",
                "run_started_at": "2026-10-31T12:50:00Z",
                "updated_at": "2026-10-31T13:02:00Z",
            },
            52: {
                "run_attempt": 1,
                "event": "push",
                "head_sha": "c" * 40,
                "head_branch": "review-branch",
                "pull_requests": [],
                "path": verifier.REQUIRED_CHECK_WORKFLOW,
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-10-31T13:00:00Z",
                "run_started_at": "2026-10-31T12:50:00Z",
                "updated_at": "2026-10-31T13:02:00Z",
            },
        }
        self.jobs = {
            51: [{"status": "completed", "conclusion": "success",
                  "started_at": "2026-10-31T13:00:00Z",
                  "completed_at": "2026-10-31T13:01:00Z",
                  "steps": [{"status": "completed", "conclusion": "success",
                             "started_at": "2026-10-31T13:00:00Z",
                             "completed_at": "2026-10-31T13:01:00Z"}]}],
            52: [{"status": "completed", "conclusion": "success",
                  "started_at": "2026-10-31T13:00:00Z",
                  "completed_at": "2026-10-31T13:01:00Z",
                  "steps": [{"status": "completed", "conclusion": "success",
                             "started_at": "2026-10-31T13:00:00Z",
                             "completed_at": "2026-10-31T13:01:00Z"}]}],
            53: [{"status": "completed", "conclusion": "success",
                  "started_at": "2026-10-31T13:00:00Z",
                  "completed_at": "2026-10-31T13:01:00Z",
                  "steps": [{"status": "completed", "conclusion": "success",
                             "started_at": "2026-10-31T13:00:00Z",
                             "completed_at": "2026-10-31T13:01:00Z"}]}],
        }
        self.commit = {"author": {"id": 343442676, "login": "xbaconator9000x"}}
        self.artifact_content = b"synthetic runtime trace"
        self.artifact_created_at = "2026-10-31T13:01:00Z"
        self.artifact_run = {
            "run_attempt": 1,
            "head_sha": "c" * 40,
            "path": ".github/workflows/compiled-mgba-semantics.yml",
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-10-31T13:00:00Z",
            "run_started_at": "2026-10-31T12:50:00Z",
            "updated_at": "2026-10-31T13:02:00Z",
        }

    def get(self, endpoint):
        path = endpoint.split("?", 1)[0]
        if path == "pulls/12":
            return self.pr
        if path == "pulls/12/reviews":
            return [self.review]
        if path == "commits/" + "e" * 40:
            return self.commit
        if path == "actions/artifacts/91":
            return {
                "id": 91,
                "expired": False,
                "created_at": self.artifact_created_at,
                "workflow_run": {"id": 53, "head_sha": "c" * 40},
            }
        if path in ("actions/runs/51/attempts/1",
                    "actions/runs/52/attempts/1"):
            return self.runs[int(path.split("/")[2])]
        if path == "actions/runs/53/attempts/1":
            return self.artifact_run
        if path.startswith("actions/runs/51/attempts/1/jobs"):
            return {"total_count": len(self.jobs[51]), "jobs": self.jobs[51]}
        if path.startswith("actions/runs/52/attempts/1/jobs"):
            return {"total_count": len(self.jobs[52]), "jobs": self.jobs[52]}
        if path.startswith("actions/runs/53/attempts/1/jobs"):
            return {"total_count": len(self.jobs[53]), "jobs": self.jobs[53]}
        raise AssertionError(f"Unexpected API request: {endpoint}")

    def download_artifact(self, artifact_id):
        if artifact_id != 91:
            raise AssertionError("Unexpected artifact")
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("runtime/trace.txt", self.artifact_content)
        return out.getvalue()


class CopilotReceiptV1Tests(unittest.TestCase):
    def setUp(self):
        self.source_bytes = b"int example(void) { return 1; }\n"
        self.dossier_bytes = gzip.compress(json.dumps({
            "provenance": {
                "repository": "pret/pokefirered",
                "path": "src/example.c",
                "pinned_revision": "a" * 40,
                "git_blob_sha": verifier.git_blob_sha(self.source_bytes),
            },
        }, sort_keys=True).encode())
        self.pin = {
            "schema": verifier.PIN_SCHEMA,
            "repository": "pret/pokefirered",
            "path": "src/example.c",
            "source": {
                "repository": "pret/pokefirered",
                "path": "src/example.c",
                "revision": "a" * 40,
                "git_blob_sha": verifier.git_blob_sha(self.source_bytes),
                "sha256": verifier.sha256(self.source_bytes),
            },
            "dossier": {
                "path": "dossiers/example.json.gz",
                "compressed_sha256": verifier.sha256(self.dossier_bytes),
            },
        }
        self.record = {
            "schema": verifier.SCHEMA,
            "classification": {"status": "COPILOT_REVIEWED", "verdict": "PASSED"},
            "source": copy.deepcopy(self.pin["source"]),
            "dossier": copy.deepcopy(self.pin["dossier"]),
            "review": {
                "coverage": "whole_file",
                "whole_file": True,
                "semantics": {
                    "summary": "Traces the whole source file and its externally visible behavior.",
                    "dependency_closure": {
                        "complete": True,
                        "edges": [],
                        "unresolved": [],
                    },
                    "licensing": {
                        "assessed": True,
                        "scope": "Source file and its declared dependencies",
                        "status": "compatible",
                    },
                    "objections": {"raised": [], "unresolved": []},
                },
                "evidence": [{
                    "kind": "source",
                    "artifact": "source",
                    "sha256": verifier.sha256(self.source_bytes),
                }],
                "claims": [{
                    "kind": "source",
                    "text": "The function returns the literal value one.",
                    "evidence": [0],
                }],
            },
            "reviewer": {
                "login": "Copilot",
                "id": verifier.BOT_ID,
                "node_id": verifier.BOT_NODE_ID,
                "type": "Bot",
            },
            "authorship": {
                "analyst_user_ids": [343442676],
            },
            "ancestry": {"evidence_commit": "e" * 40},
            "receipt_path": "semantic-snapshots/independent-reviews/copilot/example.json",
            "github": {
                "pull_request": 12,
                "review_id": 41,
                "head_sha": "c" * 40,
                "ci_runs": [
                    {"event": "pull_request", "run_id": 51, "attempt": 1},
                    {"event": "push", "run_id": 52, "attempt": 1},
                ],
            },
        }
        self.rehash()
        self.api = FixtureAPI()
        self.git = FixtureGit(self.record)

    def rehash(self):
        self.record["canonical_sha256"] = verifier.sha256(verifier.canonical_bytes(self.record))

    def validate(self, record=None, source=verifier.UNSET, dossier=verifier.UNSET,
                 pin=None, api=None, git=None):
        return verifier.validate_record(
            self.record if record is None else record,
            self.pin if pin is None else pin,
            self.source_bytes if source is verifier.UNSET else source,
            self.dossier_bytes if dossier is verifier.UNSET else dossier,
            ".",
            "xbaconator9000x/XGBA-ROM-Expansion",
            self.api if api is None else api,
            FixtureGit(
                self.record if record is None else record,
                {"copied/source.bin": self.source_bytes},
            ) if git is None else git,
            receipt_commit="d" * 40,
        )

    def test_synthetic_positive_fixture_validates_but_is_not_a_review(self):
        self.assertEqual([], self.validate())

    def test_canonical_digest_detects_tampering(self):
        changed = copy.deepcopy(self.record)
        changed["review"]["semantics"]["summary"] = "tampered"
        self.assertIn("Canonical per-file receipt digest mismatch", self.validate(record=changed))

    def test_source_and_original_compressed_dossier_are_required_and_pinned(self):
        self.assertTrue(any("source bytes are missing" in e for e in self.validate(source=None)))
        self.assertTrue(any("dossier bytes are missing" in e for e in self.validate(dossier=None)))
        self.assertTrue(any("source identity/hash mismatch" in e
                            for e in self.validate(source=b"different")))
        self.assertTrue(any("dossier bytes/hash mismatch" in e
                            for e in self.validate(dossier=b"different")))
        wrong_pin = copy.deepcopy(self.pin)
        wrong_pin["source"]["revision"] = "f" * 40
        self.assertTrue(any("immutable source pin" in e for e in self.validate(pin=wrong_pin)))

    def test_whole_file_dependency_license_and_objection_requirements_fail_closed(self):
        changes = [
            (lambda r: r["review"].update(whole_file=False), "Whole-file"),
            (lambda r: r["review"]["semantics"]["dependency_closure"].update(
                unresolved=["missing dependency"]), "Dependency closure"),
            (lambda r: r["review"]["semantics"]["licensing"].update(assessed=False),
             "Licensing scope"),
            (lambda r: r["review"]["semantics"]["objections"].update(
                unresolved=["unresolved risk"]), "objections remain"),
        ]
        for mutate, expected in changes:
            with self.subTest(expected=expected):
                changed = copy.deepcopy(self.record)
                mutate(changed)
                self.rehash_record(changed)
                self.assertTrue(any(expected in error for error in self.validate(record=changed)))

    def test_reviewer_identity_and_authorship_must_be_independent(self):
        changed = copy.deepcopy(self.record)
        changed["reviewer"]["id"] = 343442676
        self.rehash_record(changed)
        self.assertTrue(any("verified Copilot Bot identity" in e
                            for e in self.validate(record=changed)))
        changed = copy.deepcopy(self.record)
        changed["authorship"]["analyst_user_ids"] = [verifier.BOT_ID]
        self.rehash_record(changed)
        self.assertTrue(any("authored the semantic analysis" in e
                            for e in self.validate(record=changed)))
        api = FixtureAPI()
        api.commit["author"]["id"] = verifier.BOT_ID
        self.assertTrue(any("reviewer authored the semantic evidence" in e
                            for e in self.validate(api=api)))
        api = FixtureAPI()
        api.commit["author"]["id"] = 999
        self.assertTrue(any("does not match the evidence commit author" in e
                            for e in self.validate(api=api)))

    def test_only_the_two_observed_login_aliases_are_accepted(self):
        changed = copy.deepcopy(self.record)
        changed["reviewer"]["login"] = "copilot-swe-agent[bot]"
        self.rehash_record(changed)
        api = FixtureAPI()
        api.review["user"]["login"] = "copilot-swe-agent[bot]"
        self.assertEqual([], self.validate(record=changed, api=api))
        api.review["user"]["login"] = "copilot"
        self.assertTrue(any("verified Copilot Bot identity" in e
                            for e in self.validate(record=changed, api=api)))

    def test_quoted_marker_wrong_review_head_and_legacy_approval_are_rejected(self):
        for body in (
            "> COPILOT_REVIEWED/PASSED",
            "> quoted text\nCOPILOT_REVIEWED/PASSED",
            "```\nCOPILOT_REVIEWED/PASSED\n```",
            "COPILOT_REVIEWED/PASSED\nCOPILOT_REVIEWED/PASSED",
            "    COPILOT_REVIEWED/PASSED",
            "\tCOPILOT_REVIEWED/PASSED",
            "<!--\nCOPILOT_REVIEWED/PASSED\n-->",
            "<!-- visible --> <!--\nCOPILOT_REVIEWED/PASSED\n-->",
        ):
            api = FixtureAPI()
            api.review["body"] = body
            self.assertTrue(any("quoted" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.review["state"] = "APPROVED"
        self.assertTrue(any("not a legacy GitHub approval" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.review["commit_id"] = "b" * 40
        self.assertTrue(any("exact validated head" in e for e in self.validate(api=api)))

    def test_exact_head_ci_rejects_action_required_stale_and_unexecuted_jobs(self):
        api = FixtureAPI()
        api.runs[51]["conclusion"] = "action_required"
        self.assertTrue(any("unsuccessful" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.runs[51]["run_attempt"] = 2
        self.assertTrue(any("attempt is stale" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.runs[52]["head_sha"] = "b" * 40
        self.assertTrue(any("exact target head" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.jobs[51] = []
        self.assertTrue(any("no executed jobs" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.jobs[52][0]["conclusion"] = "skipped"
        self.assertTrue(any("unsuccessful job" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.jobs[51][0]["steps"] = []
        self.assertTrue(any("unsuccessful job" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.runs[51]["created_at"] = "2020-01-01T00:00:00Z"
        self.assertTrue(any("predates the receipt commit" in e for e in self.validate(api=api)))
        api = FixtureAPI()
        api.runs[52]["path"] = ".github/workflows/unrelated.yml"
        self.assertTrue(any("exact target head" in e for e in self.validate(api=api)))
        changed = copy.deepcopy(self.record)
        changed["github"]["ci_runs"].pop()
        self.rehash_record(changed)
        self.assertTrue(any("one PR and one push" in e
                            for e in self.validate(record=changed)))

    def test_receipt_and_evidence_parent_ancestry_is_mandatory(self):
        git = FixtureGit(self.record)
        git.parent_map["d" * 40] = ["f" * 40]
        self.assertTrue(any("direct parent" in e for e in self.validate(git=git)))
        git = FixtureGit(self.record)
        git.ancestors.clear()
        self.assertTrue(any("not an ancestor" in e for e in self.validate(git=git)))
        git = FixtureGit(self.record)
        git.show = lambda _revision, _path: b"tampered"
        self.assertTrue(any("does not contain" in e for e in self.validate(git=git)))

    def test_runtime_claim_requires_matching_hashed_runtime_evidence(self):
        changed = copy.deepcopy(self.record)
        changed["review"]["claims"][0]["kind"] = "runtime"
        self.rehash_record(changed)
        self.assertTrue(any("matching hashed evidence" in e
                            for e in self.validate(record=changed)))
        changed = copy.deepcopy(self.record)
        changed["review"]["evidence"][0]["kind"] = "runtime"
        changed["review"]["claims"][0]["kind"] = "runtime"
        self.rehash_record(changed)
        self.assertTrue(any("pinned Actions artifact" in e
                            for e in self.validate(record=changed)))
        changed = copy.deepcopy(self.record)
        api = FixtureAPI()
        evidence = api.artifact_content
        changed["review"]["evidence"][0] = {
            "kind": "runtime",
            "artifact_id": 91,
            "run_id": 53,
            "run_attempt": 1,
            "artifact_path": "runtime/trace.txt",
            "sha256": verifier.sha256(evidence),
        }
        changed["review"]["claims"][0]["kind"] = "runtime"
        self.rehash_record(changed)
        self.assertEqual([], self.validate(record=changed, api=api))
        api = FixtureAPI()
        api.artifact_run["path"] = ".github/workflows/unrelated.yml"
        self.assertTrue(any("unsupported workflow" in e
                            for e in self.validate(record=changed, api=api)))
        api = FixtureAPI()
        api.artifact_created_at = "2026-10-31T12:40:00Z"
        self.assertTrue(any("during the validated run attempt" in e
                            for e in self.validate(record=changed, api=api)))
        api = FixtureAPI()
        api.artifact_content = self.source_bytes
        copied = copy.deepcopy(changed)
        copied["review"]["evidence"][0]["sha256"] = verifier.sha256(self.source_bytes)
        self.rehash_record(copied)
        self.assertTrue(any("cannot copy source or dossier bytes" in e
                            for e in self.validate(record=copied, api=api)))

    def test_source_claims_must_bind_to_the_exact_pinned_source(self):
        changed = copy.deepcopy(self.record)
        changed["review"]["evidence"][0] = {
            "kind": "source",
            "path": "copied/source.bin",
            "sha256": verifier.sha256(self.source_bytes),
        }
        self.rehash_record(changed)
        self.assertEqual([], self.validate(record=changed))
        changed = copy.deepcopy(changed)
        changed["review"]["evidence"][0]["path"] = "unrelated/file.txt"
        self.rehash_record(changed)
        self.assertTrue(any("Evidence bytes are missing" in e
                            for e in self.validate(record=changed)))

    def test_compressed_dossier_decompression_is_bounded(self):
        compressed = gzip.compress(b"x" * 32_000_001)
        with self.assertRaises(ValueError):
            verifier.decompress_dossier(compressed)

    def test_duplicate_source_or_digest_receipts_are_rejected(self):
        self.assertTrue(verifier.check_duplicates([
            ("one.json", self.record), ("two.json", self.record),
        ]))
        changed = copy.deepcopy(self.record)
        changed["source"]["path"] = "src/other.c"
        self.assertTrue(verifier.check_duplicates([
            ("one.json", self.record), ("two.json", changed),
        ]))

    @staticmethod
    def rehash_record(record):
        record["canonical_sha256"] = verifier.sha256(verifier.canonical_bytes(record))


if __name__ == "__main__":
    unittest.main()

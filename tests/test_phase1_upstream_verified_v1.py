import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_upstream_verified_v1 as upstream


class FixtureContext:
    def __init__(self):
        self.repo = "pret/pokefirered"
        self.pins = {repo: revision for repo, revision, _ in upstream.PINS}
        self.revision = self.pins[self.repo]
        self.files = {}
        self.queue = {(self.repo, "src/target.c"): {}}
        self.dossiers = {}
        self.legacy_counts = {
            "legacy_external_independent_approved": 0,
            "legacy_p0_external_independent_approved": 0,
            "legacy_p0_review_candidates": 338,
        }
        self.target_ref = self.add_file("src/target.c", b"int value(void) { return 7; }\n")
        self.impl_repo = "mgba-emu/mgba"
        self.impl_ref = self.add_file(
            "src/implementation.c",
            self.files[("pret/pokefirered", "src/target.c")],
            repository=self.impl_repo,
        )
        self.spec_ref = self.add_file("docs/spec.md", b"Expected value is seven.\n")
        self.test_ref = self.add_file("tests/test_value.c", b"assert(value() == 7);\n")
        self.workflow_ref = self.add_file(
            ".github/workflows/test.yml", b"run: test tests/test_value.c\n"
        )
        self.license_ref = self.add_file(
            "LICENSE", b"SPDX-License-Identifier: MIT\n"
        )
        self.impl_license_ref = self.add_file(
            "LICENSE", b"SPDX-License-Identifier: MIT\n", repository=self.impl_repo
        )
        self.semantic_ref = self.add_file("docs/contracts.md", b"Contract: value returns seven.\n")
        self.target_dossier_sha = "f" * 64

    def add_file(self, path, data, repository=None):
        repository = repository or self.repo
        self.files[(repository, path)] = data
        return {
            "repository": repository,
            "revision": self.pins[repository],
            "path": path,
            "git_blob_sha1": upstream.git_blob_sha(data),
            "source_sha256": upstream.sha256(data),
        }

    def source_bytes(self, reference):
        key = (reference["repository"], reference["path"])
        data = self.files[key]
        if (
            reference["revision"] != self.pins[reference["repository"]]
            or reference["git_blob_sha1"] != upstream.git_blob_sha(data)
            or reference["source_sha256"] != upstream.sha256(data)
        ):
            raise upstream.EvidenceError("fixture source identity mismatch", upstream.BLOCKED)
        return data

    def verify_target(self, reference, dossier):
        if dossier != {
            "archive_sha256": upstream.DOSSIER_SHA256,
            "canonical_sha256": self.target_dossier_sha,
        }:
            raise upstream.EvidenceError("fixture dossier identity mismatch", upstream.BLOCKED)
        if reference != self.target_ref:
            raise upstream.EvidenceError("fixture target identity mismatch", upstream.BLOCKED)
        data = self.source_bytes(reference)
        return data, {"provenance": {"tracked_bytes": str(len(data))}}


class UpstreamVerifiedV1Tests(unittest.TestCase):
    def setUp(self):
        self.context = FixtureContext()
        self.artifact = {
            "schema": upstream.MAPPING_SCHEMA,
            "target": self.context.target_ref,
            "dossier": {
                "archive_sha256": upstream.DOSSIER_SHA256,
                "canonical_sha256": self.context.target_dossier_sha,
            },
            "implementation": self.context.impl_ref,
            "proof_mode": "exact_bytes",
            "scope": {
                "claim_level": "source",
                "semantic_claim": "exact_pinned_bytes_and_include_closure",
                "whole_file": True,
                "covered_lines": [[1, 1]],
            },
            "dependency_closure": {
                "complete": True,
                "pairs": [],
                "sha256": upstream.sha256(upstream.canonical_bytes([])),
            },
            "semantic_dependencies": [{
                "kind": "specification",
                "evidence": [self.context.semantic_ref],
            }],
            "licensing": {
                "status": "permitted",
                "evidence": [
                    {
                        "source": ref,
                        "sha256": ref["source_sha256"],
                        "spdx_id": "MIT",
                    }
                    for ref in (self.context.license_ref, self.context.impl_license_ref)
                ],
            },
            "objections": [],
            "tests": {
                "specification": self.context.spec_ref,
                "test_files": [self.context.test_ref],
                "workflow": self.context.workflow_ref,
                "actions_run": {
                    "repository": self.context.repo,
                    "run_id": 123,
                    "head_sha": self.context.revision,
                    "workflow_path": ".github/workflows/test.yml",
                },
            },
        }
        self.artifact["record_sha256"] = upstream.sha256(
            upstream.canonical_bytes(self.artifact)
        )

    def _validate(self, artifact=None):
        if artifact is not None:
            self.artifact = artifact
            body = {key: value for key, value in artifact.items() if key != "record_sha256"}
            artifact["record_sha256"] = upstream.sha256(upstream.canonical_bytes(body))
        with patch.object(
            upstream, "_include_closure",
            side_effect=lambda context, ref: {ref["path"]: context.source_bytes(ref)},
        ), patch.object(upstream, "_verify_actions_run", return_value=2):
            return upstream._record_result(self.artifact, self.context, lambda _: {})

    def test_exact_pinned_byte_match_with_verified_evidence_passes(self):
        result = self._validate()
        self.assertEqual(result["disposition"], upstream.PASSED)
        self.assertEqual(result["proof_mode"], "exact_bytes")
        self.assertEqual(result["test_jobs"], 2)

    def test_behavioral_equivalence_is_not_passed_without_pinned_harness(self):
        artifact = dict(self.artifact, proof_mode="behavioral_equivalence")
        with self.assertRaisesRegex(upstream.EvidenceError, "conformance harness"):
            self._validate(artifact)

    def test_changed_implementation_bytes_needs_review(self):
        ref = self.context.add_file("src/implementation.c", b"int value(void) { return 8; }\n")
        artifact = dict(self.artifact, implementation=ref)
        with self.assertRaisesRegex(upstream.EvidenceError, "Exact-byte congruence failed"):
            self._validate(artifact)

    def test_missing_original_dossier_is_blocked(self):
        artifact = dict(self.artifact, dossier={"archive_sha256": "0" * 64, "canonical_sha256": "f" * 64})
        with self.assertRaises(upstream.EvidenceError) as error:
            self._validate(artifact)
        self.assertEqual(error.exception.disposition, upstream.BLOCKED)

    def test_missing_pinned_source_is_blocked(self):
        artifact = dict(self.artifact)
        artifact["target"] = dict(self.context.target_ref, path="src/missing.c")
        with self.assertRaises(upstream.EvidenceError) as error:
            self._validate(artifact)
        self.assertEqual(error.exception.disposition, upstream.BLOCKED)

    def test_unpinned_specification_is_blocked(self):
        artifact = dict(self.artifact)
        bad_spec = dict(self.context.spec_ref, revision="0" * 40)
        artifact["tests"] = dict(artifact["tests"], specification=bad_spec)
        with self.assertRaises(upstream.EvidenceError) as error:
            self._validate(artifact)
        self.assertEqual(error.exception.disposition, upstream.BLOCKED)

    def test_partial_file_coverage_needs_review(self):
        artifact = dict(self.artifact)
        artifact["scope"] = dict(artifact["scope"], covered_lines=[[1, 0]])
        with self.assertRaisesRegex(upstream.EvidenceError, "scope is incomplete"):
            self._validate(artifact)

    def test_runtime_claim_is_not_a_source_level_pass(self):
        artifact = dict(self.artifact)
        artifact["scope"] = dict(artifact["scope"], claim_level="runtime")
        with self.assertRaisesRegex(upstream.EvidenceError, "scope is incomplete"):
            self._validate(artifact)

    def test_unsupported_or_missing_specification_needs_review(self):
        artifact = dict(self.artifact)
        artifact["tests"] = dict(artifact["tests"], specification=None)
        with self.assertRaises(upstream.EvidenceError):
            self._validate(artifact)

    def test_unresolved_objection_needs_review(self):
        artifact = dict(self.artifact, objections=["Dependency behavior conflicts with the spec"])
        with self.assertRaisesRegex(upstream.EvidenceError, "objections"):
            self._validate(artifact)

    def test_incomplete_dependency_closure_needs_review(self):
        artifact = dict(self.artifact)
        artifact["dependency_closure"] = dict(artifact["dependency_closure"], complete=False)
        with self.assertRaisesRegex(upstream.EvidenceError, "closure is incomplete"):
            self._validate(artifact)

    def test_changed_dependency_bytes_needs_review(self):
        target_data = b'#include "dep.h"\nint value(void) { return 7; }\n'
        self.context.target_ref = self.context.add_file("src/target.c", target_data)
        self.context.impl_ref = self.context.add_file(
            "src/implementation.c", target_data, repository=self.context.impl_repo
        )
        target_dep = self.context.add_file("include/dep.h", b"#define VALUE 7\n")
        implementation_dep = self.context.add_file(
            "include/dep.h", b"#define VALUE 8\n", repository=self.context.impl_repo
        )
        artifact = dict(self.artifact, target=self.context.target_ref,
                        implementation=self.context.impl_ref)
        artifact["scope"] = dict(artifact["scope"], covered_lines=[[1, 2]])
        pairs = [{"target": target_dep, "implementation": implementation_dep}]
        artifact["dependency_closure"] = {
            "complete": True,
            "pairs": pairs,
            "sha256": upstream.sha256(upstream.canonical_bytes(pairs)),
        }

        def closure(context, ref):
            root = context.source_bytes(ref)
            dependency = target_dep if ref["repository"] == self.context.repo else implementation_dep
            return {ref["path"]: root, "include/dep.h": context.source_bytes(dependency)}

        with patch.object(upstream, "_include_closure", side_effect=closure), \
             patch.object(upstream, "_verify_actions_run", return_value=2):
            with self.assertRaisesRegex(upstream.EvidenceError, "Dependency bytes differ"):
                self._validate(artifact)

    def test_incompatible_license_needs_review(self):
        artifact = dict(self.artifact)
        artifact["licensing"] = dict(artifact["licensing"], status="incompatible")
        with self.assertRaisesRegex(upstream.EvidenceError, "Licensing clearance"):
            self._validate(artifact)

    def test_duplicate_register_records_block_count(self):
        context = self.context
        context.queue = {("pret/pokefirered", "src/target.c"): {}}
        with patch.object(upstream, "_include_closure",
                          side_effect=lambda ctx, ref: {ref["path"]: ctx.source_bytes(ref)}), \
             patch.object(upstream, "_verify_actions_run", return_value=2):
            report = upstream.evaluate_records([self.artifact, self.artifact], context, lambda _: {})
        self.assertEqual(report["upstream_verified_passed_count"], 0)
        self.assertEqual(report["dispositions"][0]["disposition"], upstream.BLOCKED)

    def test_index_only_artifact_is_not_mapping_evidence(self):
        with self.assertRaisesRegex(upstream.EvidenceError, "Unsupported or malformed"):
            upstream._record_result(
                {"state": "MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW"},
                self.context,
                lambda _: {},
            )

    def test_actions_run_requires_successful_executed_jobs(self):
        run = {
            "id": 123,
            "run_attempt": 1,
            "head_sha": self.context.revision,
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/test.yml",
        }
        url = f"{upstream.API_ROOT}/{self.context.repo}/actions/runs/123"
        def good_api(request_url):
            if request_url == url:
                return run
            return {
                "total_count": 1,
                "jobs": [{
                    "id": 10,
                    "status": "completed",
                    "conclusion": "success",
                    "steps": [{
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-10-31T12:00:00Z",
                        "completed_at": "2026-10-31T12:01:00Z",
                    }],
                }],
            }
        self.assertEqual(upstream._verify_actions_run(
            self.artifact["tests"]["actions_run"], good_api
        ), 1)

        def blocked_api(request_url):
            if request_url == url:
                return dict(run, conclusion="action_required")
            return {"total_count": 0, "jobs": []}
        with self.assertRaisesRegex(upstream.EvidenceError, "unsuccessful"):
            upstream._verify_actions_run(self.artifact["tests"]["actions_run"], blocked_api)

    def test_report_keeps_legacy_metrics_and_fixture_records_separate(self):
        context = self.context
        context.queue = {("pret/pokefirered", "src/target.c"): {}}
        with patch.object(upstream, "_include_closure",
                          side_effect=lambda ctx, ref: {ref["path"]: ctx.source_bytes(ref)}), \
             patch.object(upstream, "_verify_actions_run", return_value=2):
            report = upstream.evaluate_records([self.artifact], context, lambda _: {})
        self.assertEqual(report["upstream_verified_passed_count"], 1)
        self.assertEqual(report["legacy_external_independent_approved"], 0)
        self.assertEqual(report["legacy_p0_external_independent_approved"], 0)
        self.assertEqual(report["inventory_total"], 1)
        self.assertEqual(report["prospective_completion_gate"], "FAIL_INCOMPLETE")


if __name__ == "__main__":
    unittest.main()

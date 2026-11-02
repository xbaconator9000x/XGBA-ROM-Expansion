import copy
import hashlib
import json
import os
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts_v4_adapter as v4
import phase1_copilot_receipts_v6_adapter as v6
import phase1_copilot_receipts_v7_adapter as adapter

EIGHTH_PATH = "include/mgba/internal/arm/emitter-thumb.h"


def fixture_receipts():
    original = adapter.EXPECTED_RECEIPTS
    expected = {}
    receipts = []
    for index, key in enumerate(adapter.EXPECTED_ORDER):
        source_sha = f"{index + 1:064x}"
        record = {
            "schema": "xgba.phase1.copilot_semantic_review_receipt.v4",
            "source": {
                "repository": key[0],
                "path": key[1],
                "revision": adapter.MGBA_REVISION,
                "git_blob_sha1": f"{index + 1:040x}",
                "source_sha256": source_sha,
            },
            "machine_dossier_sha256": f"{index + 11:064x}",
            "target": {
                "repository": v4.OWNER_REPOSITORY,
                "pull_number": 8,
                "receipt_path": adapter.RECEIPT_PATH,
                "evidence_commit": f"{index + 21:040x}",
            },
            "review": {
                "decision": "APPROVED",
                "reviewer_classification": (
                    "COPILOT_REVIEWED/PASSED (user-authorized source review; not human or external approval)"
                ),
                "whole_file_coverage": {
                    "scope": "WHOLE_FILE",
                    "source_sha256": source_sha,
                    "source_lines": 2,
                    "reviewed_line_ranges": [[1, 2]],
                },
                "dependency_closure": {
                    "status": "COMPLETE",
                    "dependencies": [{"repository": "synthetic/source"}],
                    "rationale": "Synthetic fixture includes a bounded dependency statement.",
                },
                "licensing": {
                    "status": "CLEARED",
                    "evidence": [{"fixture": True}],
                    "rationale": "Source-file scoped only; combined distribution is NOT CLEARED.",
                },
                "objections": [{
                    "status": "RESOLVED",
                    "resolution": "Synthetic fixture includes a scoped resolution.",
                }],
                "evidence_distinctions": {
                    "source": {"status": "VERIFIED", "source_sha256": source_sha},
                    "synthetic": {"status": "NOT_CLAIMED"},
                    "compiled_native": {"status": "NOT_CLAIMED"},
                    "runtime_gameplay": {"status": "NOT_CLAIMED"},
                    "save_restart": {"status": "NOT_APPLICABLE"},
                    "physical_flash": {"status": "NOT_APPLICABLE"},
                },
            },
        }
        digest = v4.receipt_digest(record)
        record["attestation"] = {"mode": "conversation_comment", "receipt_sha256": digest}
        expected[key] = {
            "blob": record["source"]["git_blob_sha1"],
            "source_sha256": source_sha,
            "dossier_sha256": record["machine_dossier_sha256"],
            "receipt_sha256": digest,
            "evidence_commit": record["target"]["evidence_commit"],
            "receipt_commit": f"{index + 31:040x}",
        }
        receipts.append(record)
    adapter.EXPECTED_RECEIPTS = expected
    return original, receipts


class FixtureAPI:
    def __init__(self, comments=None, runs=None, jobs=None):
        self.comments = comments or []
        self.runs = runs or []
        self.jobs = jobs or {}

    def paginate(self, url, *, result_key=None):
        if urlparse(url).path.endswith("/issues/8/comments"):
            return self.comments
        if urlparse(url).path.endswith("/actions/runs"):
            return self.runs
        raise AssertionError(f"Unexpected paginated URL: {url}")

    def __call__(self, url):
        parts = urlparse(url).path.split("/")
        if "jobs" in parts:
            run_id = int(parts[parts.index("runs") + 1])
            jobs = copy.deepcopy(self.jobs.get(run_id, []))
            return {"total_count": len(jobs), "jobs": jobs}
        raise AssertionError(f"Unexpected API URL: {url}")


def fixture_run(event, run_id, *, conclusion="success", status="completed", head=adapter.PR8_HEAD):
    run = {
        "id": run_id,
        "run_attempt": 1,
        "event": event,
        "head_sha": head,
        "path": v4.PR_WORKFLOW if event == "pull_request" else v4.CENSUS_WORKFLOW,
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-11-02T05:50:00Z",
        "run_started_at": "2026-11-02T05:51:00Z",
        "pull_requests": [],
    }
    if event == "pull_request":
        run.update({
            "name": v4.PR_WORKFLOW_NAME,
            "pull_requests": [{"number": 8, "head": {"sha": head}}],
            "referenced_workflows": [{
                "path": f"{v4.OWNER_REPOSITORY}/{v4.CENSUS_WORKFLOW}@refs/pull/8/merge",
            }],
        })
    return run


def fixture_job(job_id, *, conclusion="success", executed=True):
    return {
        "id": job_id,
        "status": "completed",
        "conclusion": conclusion,
        "steps": [{
            "status": "completed" if executed else "queued",
            "conclusion": "success" if executed else None,
            "started_at": "2026-11-02T05:52:00Z" if executed else None,
            "completed_at": "2026-11-02T05:53:00Z" if executed else None,
        }],
    }


class StrictFixtureVerifier:
    RECEIPT_MARKER = "XGBA-Phase1-Receipt-SHA256: "
    INTRO_COMMIT_MARKER = "XGBA-Phase1-Receipt-Commit: "
    EVIDENCE_COMMIT_MARKER = "XGBA-Phase1-Evidence-Commit: "
    DECISION_MARKER = "XGBA-Phase1-Decision: APPROVED"
    ATTESTATION_BEGIN = "XGBA-Phase1-Attestation: BEGIN"
    ATTESTATION_END = "XGBA-Phase1-Attestation: END"

    @classmethod
    def _attestation_section_is_valid(cls, body, markers):
        if not isinstance(body, str):
            return False
        active = []
        for line in body.splitlines():
            if line.lstrip().startswith(">") or line.startswith("```"):
                continue
            active.append(line)
        begins = [i for i, line in enumerate(active) if line == cls.ATTESTATION_BEGIN]
        ends = [i for i, line in enumerate(active) if line == cls.ATTESTATION_END]
        return (
            len(begins) == len(ends) == 1
            and ends[0] > begins[0]
            and active[begins[0]:ends[0] + 1]
            == [cls.ATTESTATION_BEGIN, *markers, cls.ATTESTATION_END]
            and all(active.count(marker) == 1 for marker in markers)
        )


class V7AdapterTests(unittest.TestCase):
    def setUp(self):
        self.original_expected, self.receipts = fixture_receipts()

    def tearDown(self):
        adapter.EXPECTED_RECEIPTS = self.original_expected

    def _refresh_fixture_digest(self, receipt):
        key = (receipt["source"]["repository"], receipt["source"]["path"])
        digest = v4.receipt_digest(receipt)
        receipt["attestation"]["receipt_sha256"] = digest
        adapter.EXPECTED_RECEIPTS[key]["receipt_sha256"] = digest

    def test_exact_eight_synthetic_records_pass_without_approving_a_review(self):
        self.assertTrue(adapter.validate_receipt_inventory(self.receipts))
        self.assertEqual(adapter.PR8_HEAD, "b455f218537f7aad7876f51ced2542486835c3bf")
        self.assertEqual(adapter.REGISTER_BLOB, "ce4dc0e369d54041caf39306440d519098790f9b")
        self.assertEqual(adapter.EXPECTED_ORDER[:7], v6.EXPECTED_ORDER)
        self.assertEqual(
            adapter.EIGHTH_RECEIPT,
            {
                "blob": "7d27524b2e723696df642a72135bac024bbd8071",
                "source_sha256": "b7a0167782c8fd63665345ed4520bd00a530e792be712e111bd9b056900b7353",
                "dossier_sha256": "482d2a7131cef6f320f3e4786f2d3482e7a4217ca931428dd409e92d3e7da729",
                "receipt_sha256": "18261796a7ce6cb74f884a53a37cdcbe72284cc542b67264e1c41deb691075de",
                "evidence_commit": "4fbd104c22d0e3fca64dfd2fe3bbdd2dc6d75b15",
                "receipt_commit": "279077f773f0eb472696328ccea2ed3c554c1b0b",
            },
        )

    def test_register_history_requires_exact_seven_record_prefix_and_pinned_append(self):
        previous = b"".join(f'{{"record":{i}}}\n'.encode() for i in range(7))
        appended = {
            "source": {"repository": "mgba-emu/mgba", "path": EIGHTH_PATH},
            "synthetic": True,
        }
        digest = v4.receipt_digest(appended)
        eighth = json.dumps(appended, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        introduced = previous + eighth
        adapter.verify_register_history(introduced, previous, introduced, expected_digest=digest)

        with self.assertRaisesRegex(ValueError, "seven receipt lines"):
            adapter.verify_register_history(
                previous + b'{"record":"changed"}\n',
                previous,
                introduced,
                expected_digest=digest,
            )
        with self.assertRaisesRegex(ValueError, "identity"):
            adapter.verify_register_history(
                introduced,
                previous,
                introduced,
                expected_digest="0" * 64,
            )

    def test_receipt_inventory_rejects_reordering_duplicates_and_tampering(self):
        variants = [
            self.receipts[:-1],
            self.receipts + [copy.deepcopy(self.receipts[-1])],
            list(reversed(self.receipts)),
            self.receipts[:-1] + [copy.deepcopy(self.receipts[0])],
        ]
        for records in variants:
            with self.subTest(count=len(records)), self.assertRaises(ValueError):
                adapter.validate_receipt_inventory(records)
        for field_path, value in (
            (("source", "git_blob_sha1"), "0" * 40),
            (("source", "source_sha256"), "0" * 64),
            (("machine_dossier_sha256",), "0" * 64),
            (("target", "evidence_commit"), "0" * 40),
            (("attestation", "receipt_sha256"), "0" * 64),
        ):
            records = copy.deepcopy(self.receipts)
            target = records[-1]
            for key in field_path[:-1]:
                target = target[key]
            target[field_path[-1]] = value
            with self.subTest(field=field_path), self.assertRaises(ValueError):
                adapter.validate_receipt_inventory(records)

    def test_scope_and_unsupported_runtime_claims_fail_closed(self):
        cases = (
            (("whole_file_coverage", "reviewed_line_ranges"), [[2, 2]]),
            (("dependency_closure", "status"), "INCOMPLETE"),
            (("licensing", "rationale"), "Distribution status unavailable."),
            (("objections", 0, "status"), "OPEN"),
            (("evidence_distinctions", "compiled_native", "status"), "VERIFIED"),
            (("evidence_distinctions", "runtime_gameplay", "status"), "VERIFIED"),
        )
        for path, value in cases:
            receipt = copy.deepcopy(self.receipts[-1])
            target = receipt["review"]
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                v6.validate_semantic_scope(receipt)

    def test_exact_eighth_receipt_license_disclaimer_is_v7_only(self):
        receipt = self.receipts[-1]
        receipt["review"]["licensing"]["rationale"] = adapter.EIGHTH_LICENSING_RATIONALE
        self._refresh_fixture_digest(receipt)

        self.assertTrue(adapter.validate_receipt_inventory(self.receipts))
        with self.assertRaisesRegex(ValueError, "Licensing scope"):
            v6.validate_semantic_scope(receipt)

    def test_v7_license_exception_rejects_altered_disclaimer_and_missing_evidence(self):
        original = copy.deepcopy(self.receipts[-1])
        variants = []

        altered = copy.deepcopy(original)
        altered["review"]["licensing"]["rationale"] = (
            adapter.EIGHTH_LICENSING_RATIONALE.replace(
                "distribution clearance is not claimed",
                "distribution clearance may be permitted",
            )
        )
        variants.append(altered)

        no_evidence = copy.deepcopy(original)
        no_evidence["review"]["licensing"]["rationale"] = adapter.EIGHTH_LICENSING_RATIONALE
        no_evidence["review"]["licensing"]["evidence"] = []
        variants.append(no_evidence)

        for receipt in variants:
            self._refresh_fixture_digest(receipt)
            records = copy.deepcopy(self.receipts)
            records[-1] = receipt
            with self.subTest(rationale=receipt["review"]["licensing"]["rationale"],
                              evidence=receipt["review"]["licensing"]["evidence"]), self.assertRaises(ValueError):
                adapter.validate_receipt_inventory(records)

    def test_exact_head_ci_rejects_missing_stale_blocked_or_unexecuted_runs(self):
        runs = [fixture_run("pull_request", 11), fixture_run("push", 12)]
        api = FixtureAPI(
            runs=runs,
            jobs={11: [fixture_job(101)], 12: [fixture_job(102)]},
        )
        self.assertEqual(
            adapter.validate_exact_ci(api, not_before="2026-11-02T05:40:00Z"),
            {"pull_request": 1, "push": 1},
        )
        failures = [
            FixtureAPI(),
            FixtureAPI(runs=[runs[0]], jobs=api.jobs),
            FixtureAPI(runs=[runs[1]], jobs=api.jobs),
            # A GitHub run can report success in metadata while its job census is empty.
            # Zero-job or missing-step runs must never certify an independent review.
            FixtureAPI(runs=[runs[0], runs[1]], jobs={11: [], 12: [fixture_job(102)]}),
            FixtureAPI(runs=[runs[0], runs[1]], jobs={11: [fixture_job(101)], 12: []}),
            FixtureAPI(runs=[runs[0], runs[1]], jobs={11: [dict(fixture_job(101), steps=[])], 12: [fixture_job(102)]}),
            FixtureAPI(
                runs=[
                    fixture_run("pull_request", 11, status="action_required", conclusion="action_required"),
                    runs[1],
                ],
                jobs=api.jobs,
            ),
            FixtureAPI(
                runs=[
                    runs[0],
                    fixture_run("push", 12, status="action_required", conclusion="action_required"),
                ],
                jobs=api.jobs,
            ),
            FixtureAPI(
                runs=[fixture_run("pull_request", 11, head="0" * 40), runs[1]],
                jobs=api.jobs,
            ),
            FixtureAPI(
                runs=[runs[0], fixture_run("push", 12, head="0" * 40)],
                jobs=api.jobs,
            ),
            FixtureAPI(
                runs=[runs[0], runs[1]],
                jobs={11: [fixture_job(101, executed=False)], 12: [fixture_job(102)]},
            ),
            FixtureAPI(
                runs=[runs[0], runs[1]],
                jobs={11: [fixture_job(101)], 12: [fixture_job(102, executed=False)]},
            ),
            FixtureAPI(
                runs=[runs[0], runs[1]],
                jobs={11: [fixture_job(101, conclusion="failure")], 12: [fixture_job(102)]},
            ),
            FixtureAPI(
                runs=[runs[0], runs[1]],
                jobs={11: [fixture_job(101)], 12: [fixture_job(102, conclusion="failure")]},
            ),
        ]
        for api_case in failures:
            with self.subTest(runs=api_case.runs), self.assertRaises(ValueError):
                adapter.validate_exact_ci(api_case, not_before="2026-11-02T05:40:00Z")
        with self.assertRaisesRegex(ValueError, "predates"):
            adapter.validate_exact_ci(api, not_before="2026-11-02T05:55:00Z")

    def test_attestation_requires_one_unquoted_bot_comment_after_introduction(self):
        receipt = self.receipts[-1]
        key = (receipt["source"]["repository"], receipt["source"]["path"])
        expected = adapter.EXPECTED_RECEIPTS[key]
        markers = (
            StrictFixtureVerifier.RECEIPT_MARKER + expected["receipt_sha256"],
            StrictFixtureVerifier.INTRO_COMMIT_MARKER + expected["receipt_commit"],
            StrictFixtureVerifier.EVIDENCE_COMMIT_MARKER + expected["evidence_commit"],
            StrictFixtureVerifier.DECISION_MARKER,
        )
        body = "\n".join((
            StrictFixtureVerifier.ATTESTATION_BEGIN,
            *markers,
            StrictFixtureVerifier.ATTESTATION_END,
        ))

        def comment(user=None, content=body, comment_id=901, created="2026-11-02T05:10:00Z"):
            return {
                "id": comment_id,
                "user": user or {
                    "login": "Copilot",
                    "id": v4.BOT_ID,
                    "node_id": v4.BOT_NODE_ID,
                    "type": "Bot",
                },
                "issue_url": f"{v4.API_ROOT}/issues/8",
                "html_url": f"https://github.com/{v4.OWNER_REPOSITORY}/pull/8#issuecomment-{comment_id}",
                "body": content,
                "created_at": created,
            }

        old_git = v4._git
        v4._git = lambda *_args: "2026-11-02T05:00:00+00:00"
        try:
            good = comment()
            self.assertIs(
                adapter.verify_expected_comment(receipt, StrictFixtureVerifier, FixtureAPI([good]), "/unused"),
                good,
            )
            alias = comment(user={
                "login": "copilot-swe-agent[bot]",
                "id": v4.BOT_ID,
                "node_id": v4.BOT_NODE_ID,
                "type": "Bot",
            })
            self.assertIs(
                adapter.verify_expected_comment(receipt, StrictFixtureVerifier, FixtureAPI([alias]), "/unused"),
                alias,
            )
            duplicate_section = comment(content=body + "\n" + body)
            quoted = comment(content="> " + "\n> ".join(body.splitlines()))
            owner = comment(user={"login": "xbaconator9000x", "id": 343442676, "type": "User"})
            spoofed = comment(user={
                "login": "Copilot",
                "id": v4.BOT_ID + 1,
                "node_id": v4.BOT_NODE_ID,
                "type": "Bot",
            })
            duplicates = [good, comment(comment_id=902)]
            stale = comment(created="2026-11-02T04:59:59Z")
            for comments in ([], [duplicate_section], [quoted], duplicates, [owner], [spoofed]):
                with self.subTest(comments=comments), self.assertRaises(ValueError):
                    adapter.verify_expected_comment(
                        receipt, StrictFixtureVerifier, FixtureAPI(comments), "/unused"
                    )
            with self.assertRaisesRegex(ValueError, "predates"):
                adapter.verify_expected_comment(
                    receipt, StrictFixtureVerifier, FixtureAPI([stale]), "/unused"
                )
        finally:
            v4._git = old_git

    def test_analyst_evidence_authorship_is_distinct_from_copilot(self):
        receipt = copy.deepcopy(self.receipts[-1])
        receipt["target"]["evidence_commit"] = adapter.EVIDENCE_COMMIT
        files = {"evidence.md": b"independent source evidence", "dossier.json": b"source dossier"}
        receipt["review"]["authorship"] = {
            "dossier": {"path": "dossier.json", "sha256": hashlib.sha256(files["dossier.json"]).hexdigest()},
            "substantive_evidence": [{
                "path": "evidence.md",
                "sha256": hashlib.sha256(files["evidence.md"]).hexdigest(),
            }],
        }

        class CommitAPI:
            def __init__(self, author):
                self.author = author
                self.path = None

            def __call__(self, url):
                if "/commits?path=" in url:
                    self.path = parse_qs(urlparse(url).query)["path"][0]
                    return [{"sha": "a" * 40}]
                if url.endswith("/commits/" + "a" * 40):
                    return {
                        "sha": "a" * 40,
                        "files": [{"filename": self.path}],
                        "author": self.author,
                        "committer": {"login": "xbaconator9000x", "id": 343442676},
                    }
                raise AssertionError(url)

        old_git = v4._git
        old_check_output = adapter.subprocess.check_output
        with TemporaryDirectory() as root:
            for name, content in files.items():
                (Path(root) / name).write_bytes(content)

            def fake_git(_root, *args):
                if args[:2] == ("merge-base", "--is-ancestor"):
                    return ""
                raise AssertionError(args)

            def fake_check_output(args, **kwargs):
                if args[0:3] == ["git", "-C", str(Path(root).resolve())] and args[3] == "show":
                    return files[args[-1].split(":", 1)[1]]
                return old_check_output(args, **kwargs)

            v4._git = fake_git
            adapter.subprocess.check_output = fake_check_output
            try:
                adapter.verify_non_copilot_evidence_authorship(
                    receipt, CommitAPI({"login": "xbaconator9000x", "id": 343442676}), root
                )
                with self.assertRaisesRegex(ValueError, "Copilot cannot review"):
                    adapter.verify_non_copilot_evidence_authorship(
                        receipt,
                        CommitAPI({"login": "Copilot", "id": v4.BOT_ID}),
                        root,
                    )
                os.symlink(root, Path(root) / "alias", target_is_directory=True)
                unsafe = copy.deepcopy(receipt)
                unsafe["review"]["authorship"]["substantive_evidence"][0]["path"] = "alias/evidence.md"
                with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                    adapter.verify_non_copilot_evidence_authorship(
                        unsafe,
                        CommitAPI({"login": "xbaconator9000x", "id": 343442676}),
                        root,
                    )
            finally:
                v4._git = old_git
                adapter.subprocess.check_output = old_check_output


if __name__ == "__main__":
    unittest.main()

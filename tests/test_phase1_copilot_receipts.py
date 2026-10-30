import copy
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import phase1_copilot_receipts as receipts
from phase1_bulk_triage import canonical, digest, git_blob


class CopilotReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_root = self.root / "upstream"
        self.checkout = self.source_root / "pokefirered"
        self.repository_root = self.root / "repository"
        self.checkout.mkdir(parents=True)
        self.repository_root.mkdir()
        subprocess.run(["git", "-C", str(self.repository_root), "init", "-q"], check=True)
        subprocess.run([
            "git", "-C", str(self.repository_root), "config", "user.name", "Fixture Author"
        ], check=True)
        subprocess.run([
            "git", "-C", str(self.repository_root), "config", "user.email",
            "fixture-author@example.test",
        ], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "init", "-q"], check=True)
        (self.checkout / "src").mkdir()
        self.source = b"static int add(int a, int b)\n{\n    return a + b;\n}\n"
        self.second_source = b"static int negate(int value)\n{\n    return -value;\n}\n"
        self.license = b"Copyright and license terms for the pinned fixture.\n"
        (self.checkout / "src" / "sample.c").write_bytes(self.source)
        (self.checkout / "src" / "second.c").write_bytes(self.second_source)
        (self.checkout / "LICENSE").write_bytes(self.license)
        subprocess.run(["git", "-C", str(self.checkout), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.checkout), "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture",
        ], check=True)
        self.pin = subprocess.check_output(
            ["git", "-C", str(self.checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        self.old_pin = receipts.PINS["pret/pokefirered"]
        receipts.PINS["pret/pokefirered"] = self.pin
        self.addCleanup(self._restore_pin)
        self.head = "c" * 40
        self.repository = "xbaconator9000x/XGBA-ROM-Expansion"
        self.key = ("pret/pokefirered", "src/sample.c")
        self.second_key = ("pret/pokefirered", "src/second.c")
        self.dossier = {
            "provenance": {
                "repository": self.key[0],
                "pinned_revision": self.pin,
                "path": self.key[1],
                "git_blob_sha": git_blob(self.source),
                "source_content_sha256": hashlib.sha256(self.source).hexdigest(),
            },
            "review": {"semantic_signoff": False, "reviewer": None},
        }
        self.dossier_hash = digest(canonical(self.dossier))
        self.second_dossier = {
            "provenance": {
                "repository": self.second_key[0],
                "pinned_revision": self.pin,
                "path": self.second_key[1],
                "git_blob_sha": git_blob(self.second_source),
                "source_content_sha256": hashlib.sha256(self.second_source).hexdigest(),
            },
            "review": {"semantic_signoff": False, "reviewer": None},
        }
        self.second_dossier_hash = digest(canonical(self.second_dossier))
        self.queue = {
            self.key: {
                "repo": self.key[0], "path": self.key[1],
                "blob_sha": git_blob(self.source), "evidence_sha256": self.dossier_hash,
            },
            self.second_key: {
                "repo": self.second_key[0], "path": self.second_key[1],
                "blob_sha": git_blob(self.second_source),
                "evidence_sha256": self.second_dossier_hash,
            }
        }
        self.dossiers = {self.key: self.dossier, self.second_key: self.second_dossier}
        (self.repository_root / "review").mkdir()
        dossier_bytes = b'{"reviewed_item":"pret/pokefirered/src/sample.c"}\n'
        evidence_bytes = b"Independent source observations for the fixture.\n"
        second_dossier_bytes = b'{"reviewed_item":"pret/pokefirered/src/second.c"}\n'
        second_evidence_bytes = b"Independent observations for the second fixture.\n"
        (self.repository_root / "review" / "dossier.json").write_bytes(dossier_bytes)
        (self.repository_root / "review" / "evidence.txt").write_bytes(evidence_bytes)
        (self.repository_root / "review" / "second-dossier.json").write_bytes(second_dossier_bytes)
        (self.repository_root / "review" / "second-evidence.txt").write_bytes(second_evidence_bytes)
        subprocess.run(["git", "-C", str(self.repository_root), "add", "review/dossier.json", "review/evidence.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Evidence checkpoint"], check=True)
        self.evidence_commit = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self.authorship = {
            self.key: [
            {
                "path": "review/dossier.json",
                "sha256": hashlib.sha256(dossier_bytes).hexdigest(),
                "commit_sha": self.evidence_commit,
            },
            {
                "path": "review/evidence.txt",
                "sha256": hashlib.sha256(evidence_bytes).hexdigest(),
                "commit_sha": self.evidence_commit,
            },
            ],
            self.second_key: [
                {
                    "path": "review/second-dossier.json",
                    "sha256": hashlib.sha256(second_dossier_bytes).hexdigest(),
                    "commit_sha": self.evidence_commit,
                },
                {
                    "path": "review/second-evidence.txt",
                    "sha256": hashlib.sha256(second_evidence_bytes).hexdigest(),
                    "commit_sha": self.evidence_commit,
                },
            ],
        }
        self.second_evidence_commit = None
        self.receipt = self._make_receipt()
        self.github_responses = {}
        self.committed_receipts = []

    def _restore_pin(self):
        receipts.PINS["pret/pokefirered"] = self.old_pin

    def _source_ref(self, path, data):
        return {
            "repository": "pret/pokefirered",
            "revision": self.pin,
            "path": path,
            "git_blob_sha1": git_blob(data),
            "source_sha256": hashlib.sha256(data).hexdigest(),
        }

    def _make_receipt(self, key=None):
        key = self.key if key is None else key
        source = self.source if key == self.key else self.second_source
        dossier_hash = self.dossier_hash if key == self.key else self.second_dossier_hash
        authorship = self.authorship[key]
        lines = len(source.splitlines())
        return {
            "schema": receipts.SCHEMA,
            "source": self._source_ref(key[1], source),
            "machine_dossier_sha256": dossier_hash,
            "review": {
                "decision": "APPROVED",
                "semantic_rationale": "The complete pinned implementation and its call contract were reviewed.",
                "findings": [{
                    "claim": (
                        "The helper returns the sum of its two integer arguments."
                        if key == self.key else
                        "The helper returns the negation of its integer argument."
                    ),
                    "source_lines": [1, 3],
                }],
                "whole_file_coverage": {
                    "scope": "WHOLE_FILE",
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "source_lines": lines,
                    "reviewed_line_ranges": [[1, lines]],
                },
                "dependency_closure": {
                    "status": "COMPLETE",
                    "rationale": "The translation unit has no external declarations or includes.",
                    "dependencies": [],
                },
                "licensing": {
                    "status": "CLEARED",
                    "rationale": "The pinned repository license terms were reviewed for this item.",
                    "evidence": [self._source_ref("LICENSE", self.license)],
                },
                "evidence_distinctions": {
                    "source": {
                        "status": "VERIFIED",
                        "source_sha256": hashlib.sha256(source).hexdigest(),
                    },
                    "synthetic": {"status": "NOT_CLAIMED", "reason": "No synthetic result is claimed."},
                    "compiled_native": {"status": "NOT_RUN", "reason": "No native build result is claimed."},
                    "runtime_gameplay": {"status": "NOT_RUN", "reason": "No runtime result is claimed."},
                    "save_restart": {"status": "NOT_APPLICABLE", "reason": "This fixture has no save behavior."},
                    "physical_flash": {"status": "NOT_CLAIMED", "reason": "No hardware result is claimed."},
                },
                "objections": [],
                "authorship": {
                    "dossier": {k: v for k, v in authorship[0].items() if k != "commit_sha"},
                    "substantive_evidence": [
                        {k: v for k, v in authorship[1].items() if k != "commit_sha"}
                    ],
                },
            },
            "target": {
                "repository": self.repository,
                "pull_number": 8,
                "evidence_commit": (
                    self.evidence_commit if key == self.key else self.second_evidence_commit
                ),
                "receipt_path": "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl",
            },
            "attestation": {
                "mode": "conversation_comment",
                "receipt_sha256": "",
            },
        }

    def _commit_receipt(self, receipt):
        body_hash = receipts.receipt_digest(receipt)
        receipt["attestation"]["receipt_sha256"] = body_hash
        register = self.repository_root / receipt["target"]["receipt_path"]
        register.parent.mkdir(parents=True, exist_ok=True)
        receipt_line = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        previous = register.read_text(encoding="utf-8") if register.exists() else ""
        if receipt_line in previous.splitlines():
            return self.head
        register.write_text(previous + receipt_line + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repository_root), "add", receipt["target"]["receipt_path"]], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Add semantic receipt"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        intro_date = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "show", "-s", "--format=%cI", self.head],
            text=True,
        ).strip()
        intro_time = datetime.datetime.fromisoformat(intro_date)
        comment_id = 810000 + len(self.committed_receipts)
        evidence_sha = receipt["target"]["evidence_commit"]
        body = "\n".join((
            receipts.RECEIPT_MARKER + body_hash,
            receipts.INTRO_COMMIT_MARKER + self.head,
            receipts.EVIDENCE_COMMIT_MARKER + evidence_sha,
            receipts.DECISION_MARKER,
        ))
        self.committed_receipts.append({
            "receipt": receipt,
            "digest": body_hash,
            "intro": self.head,
            "created_at": (intro_time + datetime.timedelta(seconds=1)).isoformat(),
            "comment_id": comment_id,
            "body": body,
        })
        self._refresh_github_responses()
        return self.head

    def _add_unrelated_commit(self):
        extra = self.repository_root / "review" / "later-note.txt"
        extra.write_text("A later unrelated change.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repository_root), "add", "review/later-note.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Later unrelated change"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _commit_second_evidence(self):
        subprocess.run([
            "git", "-C", str(self.repository_root), "add",
            "review/second-dossier.json", "review/second-evidence.txt",
        ], check=True)
        subprocess.run([
            "git", "-C", str(self.repository_root), "commit", "-qm", "Second independent evidence",
        ], check=True)
        self.second_evidence_commit = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        for item in self.authorship[self.second_key]:
            item["commit_sha"] = self.second_evidence_commit
        self._refresh_github_responses()

    def _commit_second_evidence_with_rewritten_register(self):
        register = self.repository_root / self.receipt["target"]["receipt_path"]
        original_lines = register.read_text(encoding="utf-8").splitlines()
        register.write_text(original_lines[0] + " " + "\n", encoding="utf-8")
        subprocess.run([
            "git", "-C", str(self.repository_root), "add",
            "review/second-dossier.json", "review/second-evidence.txt",
            self.receipt["target"]["receipt_path"],
        ], check=True)
        subprocess.run([
            "git", "-C", str(self.repository_root), "commit", "-qm",
            "Second evidence rewrites earlier receipt",
        ], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _amend_introduction_with_extra_file(self):
        subprocess.run(
            ["git", "-C", str(self.repository_root), "reset", "--soft", "HEAD^"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        (self.repository_root / "review" / "unexpected.txt").write_text(
            "An unreviewed extra edit.\n", encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.repository_root), "add", "review/unexpected.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repository_root), "commit", "-qm", "Receipt with extra edit"],
            check=True,
        )
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _foreign_commit(self):
        tree = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", f"{self.evidence_commit}^{{tree}}"],
            text=True,
        ).strip()
        return subprocess.check_output(
            ["git", "-C", str(self.repository_root), "commit-tree", tree, "-m", "Foreign evidence"],
            text=True,
        ).strip()

    def _rebase_receipt_introduction(self):
        old_introduction = self.head
        receipt_path = self.receipt["target"]["receipt_path"]
        register_bytes = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "show", f"{old_introduction}:{receipt_path}"],
        )
        subprocess.run(
            ["git", "-C", str(self.repository_root), "reset", "--hard", self.evidence_commit],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        (self.repository_root / "review" / "before-rebased-receipt.txt").write_text(
            "An intervening commit changes the receipt ancestry.\n", encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.repository_root), "add", "review/before-rebased-receipt.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Intervening commit"], check=True)
        register = self.repository_root / receipt_path
        register.parent.mkdir(parents=True, exist_ok=True)
        register.write_bytes(register_bytes)
        subprocess.run(["git", "-C", str(self.repository_root), "add", receipt_path], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Rebased receipt introduction"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _remove_receipt_after_introduction(self):
        register = self.repository_root / self.receipt["target"]["receipt_path"]
        register.unlink()
        subprocess.run(
            ["git", "-C", str(self.repository_root), "add", "-u", self.receipt["target"]["receipt_path"]],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Remove receipt"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _remove_later_appended_receipt(self):
        register = self.repository_root / self.receipt["target"]["receipt_path"]
        lines = register.read_text(encoding="utf-8").splitlines()
        register.write_text(lines[0] + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repository_root), "add", self.receipt["target"]["receipt_path"]], check=True)
        subprocess.run(["git", "-C", str(self.repository_root), "commit", "-qm", "Remove appended receipt"], check=True)
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        self._refresh_github_responses()

    def _seal(self, receipt=None):
        receipt = self.receipt if receipt is None else receipt
        subprocess.run([
            "git", "-C", str(self.repository_root), "reset", "--hard", self.evidence_commit
        ], check=True, stdout=subprocess.DEVNULL)
        self.head = self.evidence_commit
        self.committed_receipts = []
        return self._commit_receipt(receipt)

    def _refresh_github_responses(self):
        self.github_responses = {
            f"https://api.github.com/repos/{self.repository}/pulls/8": {
                "user": {"login": "xbaconator9000x"},
                "head": {"sha": self.head},
            },
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100&page=1": [],
            f"https://api.github.com/repos/{self.repository}/pulls/8/reviews?per_page=100&page=2": [],
            f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1": [
                {
                    "id": item["comment_id"],
                    "user": {"login": "Copilot"},
                    "issue_url": f"https://api.github.com/repos/{self.repository}/issues/8",
                    "html_url": f"https://github.com/{self.repository}/pull/8#issuecomment-{item['comment_id']}",
                    "created_at": item["created_at"],
                    "body": item["body"],
                }
                for item in self.committed_receipts
            ],
            f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=2": [],
            f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100&page=1": {
                "workflow_runs": [{
                    "id": 900001,
                    "name": "Phase 1 consolidated PR checks",
                    "event": "pull_request",
                    "head_sha": self.head,
                    "status": "completed",
                    "conclusion": "success",
                    "referenced_workflows": [{
                        "path": f"{self.repository}/.github/workflows/phase1-census.yml@{self.head}",
                    }],
                    "pull_requests": [{
                        "number": 8,
                        "head": {"sha": self.head},
                    }],
                }],
            },
            f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100&page=2": {
                "workflow_runs": [],
            },
        }
        api_root = f"https://api.github.com/repos/{self.repository}"
        files_by_commit = {}
        for entries in self.authorship.values():
            for item in entries:
                query = urlencode({
                    "path": item["path"], "sha": item["commit_sha"], "per_page": 1,
                })
                self.github_responses[f"{api_root}/commits?{query}"] = [
                    {"sha": item["commit_sha"]}
                ]
                files_by_commit.setdefault(item["commit_sha"], []).append(
                    {"filename": item["path"]}
                )
        for commit_sha, files in files_by_commit.items():
            self.github_responses[f"{api_root}/commits/{commit_sha}"] = {
                "sha": commit_sha,
                "parents": [],
                "author": {"login": "xbaconator9000x"},
                "committer": {"login": "xbaconator9000x"},
                "files": files,
            }

    def _validate(self, receipt=None, github_api=None):
        return receipts.validate_receipt(
            self.receipt if receipt is None else receipt,
            queue=self.queue,
            dossiers=self.dossiers,
            source_root=self.source_root,
            expected_head=self.head,
            repository_root=self.repository_root,
            repository=self.repository,
            github_api=github_api or self.github_responses.__getitem__,
        )

    @staticmethod
    def _noise_records(first_id, count):
        return [{"id": first_id + index, "user": {"login": "other"}} for index in range(count)]

    def test_real_post_receipt_git_sha_validates_without_self_reference(self):
        self._seal()
        committed_head = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"], text=True
        ).strip()
        parent = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "rev-parse", "HEAD^"], text=True
        ).strip()
        self.assertEqual(self.head, committed_head)
        self.assertEqual(parent, self.evidence_commit)
        self.assertNotEqual(self.head, self.evidence_commit)
        key, problems = self._validate()
        self.assertEqual(key, self.key)
        self.assertEqual(problems, [])

    def test_two_receipts_remain_valid_after_later_receipt_and_unrelated_commit(self):
        self._seal()
        first = copy.deepcopy(self.receipt)
        self._commit_second_evidence()
        second = self._make_receipt(self.second_key)
        self._commit_receipt(second)
        self._add_unrelated_commit()
        self.assertEqual(self._validate(first), (self.key, []))
        self.assertEqual(self._validate(second), (self.second_key, []))

    def test_paginated_attestations_find_page_two_and_share_cached_snapshots(self):
        self._seal()
        first = copy.deepcopy(self.receipt)
        self._commit_second_evidence()
        second = self._make_receipt(self.second_key)
        self._commit_receipt(second)
        self._add_unrelated_commit()
        api_root = f"https://api.github.com/repos/{self.repository}"
        comments_one = f"{api_root}/issues/8/comments?per_page=100&page=1"
        comments_two = f"{api_root}/issues/8/comments?per_page=100&page=2"
        comments_three = f"{api_root}/issues/8/comments?per_page=100&page=3"
        reviews_one = f"{api_root}/pulls/8/reviews?per_page=100&page=1"
        reviews_two = f"{api_root}/pulls/8/reviews?per_page=100&page=2"
        self.github_responses[comments_one] = self._noise_records(100000, 100)
        self.github_responses[comments_two] = [
            {
                "id": item["comment_id"],
                "user": {"login": "Copilot"},
                "issue_url": f"{api_root}/issues/8",
                "html_url": f"https://github.com/{self.repository}/pull/8#issuecomment-{item['comment_id']}",
                "created_at": item["created_at"],
                "body": item["body"],
            }
            for item in self.committed_receipts
        ]
        self.github_responses[comments_three] = []
        self.github_responses[reviews_one] = self._noise_records(200000, 100)
        self.github_responses[reviews_two] = []
        calls = {}

        def counted_api(url):
            calls[url] = calls.get(url, 0) + 1
            return self.github_responses[url]

        api = receipts.GitHubAPICache(counted_api)
        self.assertEqual(self._validate(first, api), (self.key, []))
        snapshot_calls = {
            url: count for url, count in calls.items()
            if "/reviews?" in url or "/comments?" in url or "/actions/runs?" in url
        }
        snapshot_collection_count = len(api.collections)
        self.assertEqual(self._validate(second, api), (self.second_key, []))
        self.assertEqual(
            snapshot_calls,
            {
                url: count for url, count in calls.items()
                if "/reviews?" in url or "/comments?" in url or "/actions/runs?" in url
            },
        )
        self.assertEqual(len(api.collections), snapshot_collection_count)
        self.assertIn(comments_two, api.responses)
        self.assertIn(reviews_two, api.responses)

    def test_duplicate_attestations_across_pages_are_rejected(self):
        self._seal()
        api_root = f"https://api.github.com/repos/{self.repository}"
        comments_one = f"{api_root}/issues/8/comments?per_page=100&page=1"
        comments_two = f"{api_root}/issues/8/comments?per_page=100&page=2"
        original = self.github_responses[comments_one][0]
        self.github_responses[comments_one] = self._noise_records(100000, 99) + [original]
        duplicate = copy.deepcopy(original)
        duplicate["id"] += 1
        duplicate["html_url"] = f"https://github.com/{self.repository}/pull/8#issuecomment-{duplicate['id']}"
        self.github_responses[comments_two] = [duplicate]
        self.assertTrue(self._validate()[1])

    def test_short_attestation_page_does_not_hide_later_records(self):
        self._seal()
        api_root = f"https://api.github.com/repos/{self.repository}"
        comments_one = f"{api_root}/issues/8/comments?per_page=100&page=1"
        comments_two = f"{api_root}/issues/8/comments?per_page=100&page=2"
        comments_three = f"{api_root}/issues/8/comments?per_page=100&page=3"
        attestation = self.github_responses[comments_one][0]
        self.github_responses[comments_one] = self._noise_records(100000, 30)
        self.github_responses[comments_two] = [attestation]
        self.github_responses[comments_three] = []
        key, problems = self._validate()
        self.assertEqual(key, self.key)
        self.assertEqual(problems, [])

    def test_missing_or_rate_limited_attestation_page_fails_closed(self):
        self._seal()
        api_root = f"https://api.github.com/repos/{self.repository}"
        comments_one = f"{api_root}/issues/8/comments?per_page=100&page=1"
        comments_two = f"{api_root}/issues/8/comments?per_page=100&page=2"
        self.github_responses[comments_one] = self._noise_records(100000, 100)
        self.github_responses.pop(comments_two, None)
        self.assertTrue(self._validate()[1])

        def rate_limited(url):
            if url == comments_two:
                raise RuntimeError("rate limit")
            return self.github_responses[url]

        self.assertTrue(self._validate(github_api=rate_limited)[1])

    def test_receipt_introduction_commit_with_extra_file_is_rejected(self):
        self._seal()
        self._amend_introduction_with_extra_file()
        key, problems = self._validate()
        self.assertEqual(key, self.key)
        self.assertTrue(problems)

    def test_receipt_with_foreign_evidence_ancestry_is_rejected(self):
        bad = copy.deepcopy(self.receipt)
        bad["target"]["evidence_commit"] = self._foreign_commit()
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_receipt_rebased_onto_new_introduction_commit_requires_new_attestation(self):
        self._seal()
        self._rebase_receipt_introduction()
        self.assertTrue(self._validate()[1])

    def test_removing_a_receipt_after_introduction_is_rejected(self):
        self._seal()
        self._remove_receipt_after_introduction()
        self.assertTrue(self._validate()[1])

    def test_removing_another_appended_receipt_is_rejected(self):
        self._seal()
        self._commit_second_evidence()
        self._commit_receipt(self._make_receipt(self.second_key))
        self._remove_later_appended_receipt()
        self.assertTrue(self._validate()[1])

    def test_duplicate_source_receipts_are_rejected(self):
        self._seal()
        duplicate = copy.deepcopy(self.receipt)
        duplicate["review"]["semantic_rationale"] += " Duplicate identity."
        self._commit_receipt(duplicate)
        self.assertTrue(self._validate()[1])

    def test_second_evidence_commit_cannot_rewrite_prior_receipt(self):
        self._seal()
        self._commit_second_evidence_with_rewritten_register()
        self.assertTrue(self._validate()[1])

    def test_receipt_register_missing_or_foreign_target_is_rejected(self):
        self._seal()
        register = self.repository_root / self.receipt["target"]["receipt_path"]
        register.unlink()
        self.assertTrue(self._validate()[1])
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["target"]["repository"] = "elsewhere/another-repo"
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_missing_or_forged_signature_is_rejected(self):
        self._seal()
        missing = copy.deepcopy(self.receipt)
        del missing["attestation"]
        self.assertTrue(self._validate(missing)[1])
        forged = copy.deepcopy(self.receipt)
        forged["attestation"]["receipt_sha256"] = "0" * 64
        self.assertTrue(self._validate(forged)[1])

    def test_stale_source_dossier_and_head_hashes_are_rejected(self):
        self._seal()
        for field, value in (("source_sha256", "0" * 64),):
            bad = copy.deepcopy(self.receipt)
            bad["source"][field] = value
            self._seal(bad)
            self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["machine_dossier_sha256"] = "0" * 64
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["target"]["evidence_commit"] = "d" * 40
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_incomplete_scope_and_dependencies_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["whole_file_coverage"]["reviewed_line_ranges"] = [[1, 2]]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["dependency_closure"]["status"] = "INCOMPLETE"
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_author_conflict_is_rejected(self):
        self._seal()
        pull_url = f"https://api.github.com/repos/{self.repository}/pulls/8"
        self.github_responses[pull_url]["user"]["login"] = "copilot"
        self.assertTrue(self._validate()[1])

    def test_copilot_authored_dossier_is_rejected_even_when_pr_author_is_other(self):
        self._seal()
        commit_url = (
            f"https://api.github.com/repos/{self.repository}/commits/"
            f"{self.evidence_commit}"
        )
        self.github_responses[commit_url]["author"]["login"] = "copilot-swe-agent[bot]"
        self.assertEqual(
            self.github_responses[
                f"https://api.github.com/repos/{self.repository}/pulls/8"
            ]["user"]["login"],
            "xbaconator9000x",
        )
        self.assertTrue(self._validate()[1])

    def test_stale_dossier_or_substantive_evidence_file_hash_is_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["authorship"]["dossier"]["sha256"] = "0" * 64
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        self._seal()
        evidence_file = self.repository_root / "review" / "evidence.txt"
        evidence_file.write_text("Changed substantive evidence.\n", encoding="utf-8")
        self.assertTrue(self._validate()[1])

    def test_missing_reviewer_identity_is_rejected(self):
        self._seal()
        comment_url = f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1"
        self.github_responses[comment_url][0]["user"] = {}
        self.assertTrue(self._validate()[1])

    def test_conversation_comment_attestation_rejects_wrong_author_duplicate_or_early_comment(self):
        comment_url = f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1"
        self._seal()
        self.github_responses[comment_url][0]["user"]["login"] = "someone-else"
        self.assertTrue(self._validate()[1])
        self._seal()
        self.github_responses[comment_url].append(copy.deepcopy(self.github_responses[comment_url][0]))
        self.assertTrue(self._validate()[1])
        self._seal()
        intro_date = subprocess.check_output(
            ["git", "-C", str(self.repository_root), "show", "-s", "--format=%cI", self.head],
            text=True,
        ).strip()
        self.github_responses[comment_url][0]["created_at"] = intro_date
        self.assertTrue(self._validate()[1])

    def test_missing_conversation_comment_is_rejected(self):
        self._seal()
        comment_url = f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1"
        self.github_responses[comment_url] = []
        self.assertTrue(self._validate()[1])

    def test_conversation_comment_requires_exact_receipt_and_commit_markers(self):
        comment_url = f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1"
        for marker in (
            receipts.RECEIPT_MARKER + "0" * 64,
            receipts.INTRO_COMMIT_MARKER + "d" * 40,
            receipts.EVIDENCE_COMMIT_MARKER + "e" * 40,
            receipts.DECISION_MARKER,
        ):
            with self.subTest(marker=marker):
                self._seal()
                body = self.github_responses[comment_url][0]["body"]
                if marker == receipts.DECISION_MARKER:
                    body = body.replace(marker, "XGBA-Phase1-Decision: NEEDS_REVIEW")
                elif marker.startswith(receipts.RECEIPT_MARKER):
                    body = body.replace(receipts.RECEIPT_MARKER + receipts.receipt_digest(self.receipt), marker)
                elif marker.startswith(receipts.INTRO_COMMIT_MARKER):
                    body = body.replace(
                        receipts.INTRO_COMMIT_MARKER + self.head, marker,
                    )
                else:
                    body = body.replace(
                        receipts.EVIDENCE_COMMIT_MARKER + self.evidence_commit, marker,
                    )
                self.github_responses[comment_url][0]["body"] = body
                self.assertTrue(self._validate()[1])

    def test_malformed_source_identity_is_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["source"]["repository"] = []
        self._seal(bad)
        key, problems = self._validate(bad)
        self.assertIsNone(key)
        self.assertTrue(problems)

    def test_unpinned_dependency_bytes_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        dependency = self._source_ref("LICENSE", self.license)
        dependency["git_blob_sha1"] = "0" * 40
        bad["review"]["dependency_closure"]["dependencies"] = [dependency]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_unresolved_licensing_or_objections_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["licensing"]["status"] = "PENDING"
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["objections"] = [{"status": "OPEN", "resolution": ""}]
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_ci_only_and_unsupported_runtime_claims_are_rejected(self):
        self._seal()
        bad = copy.deepcopy(self.receipt)
        bad["review"]["evidence_distinctions"]["runtime_gameplay"] = {
            "status": "CI_ONLY", "reason": "CI passed."
        }
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])
        bad = copy.deepcopy(self.receipt)
        bad["review"]["evidence_distinctions"]["runtime_gameplay"] = {
            "status": "VERIFIED",
            "artifacts": [{
                "kind": "runtime_trace",
                "uri": "https://example.test/test.log",
                "sha256": "a" * 64,
            }],
        }
        self._seal(bad)
        self.assertTrue(self._validate(bad)[1])

    def test_claimed_non_source_artifacts_are_rejected_without_byte_verifier(self):
        kinds = {
            "synthetic": "synthetic_test",
            "compiled_native": "build_artifact",
            "runtime_gameplay": "runtime_trace",
            "save_restart": "save_image",
            "physical_flash": "physical_flash_capture",
        }
        for uri, digest in (
            ("https://missing.example/artifact.bin", "a" * 64),
            ("https://example.test/wrong-bytes.bin", "b" * 64),
            ("https://example.test/stale-artifact.bin", "c" * 64),
        ):
            for category, kind in kinds.items():
                with self.subTest(uri=uri, category=category):
                    bad = copy.deepcopy(self.receipt)
                    bad["review"]["evidence_distinctions"][category] = {
                        "status": "VERIFIED",
                        "artifacts": [{"kind": kind, "uri": uri, "sha256": digest}],
                    }
                    self._seal(bad)
                    self.assertTrue(self._validate(bad)[1])

    def test_exact_head_run_must_include_census_workflow(self):
        self._seal()
        run_url = f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100&page=1"
        self.github_responses[run_url]["workflow_runs"][0]["referenced_workflows"] = []
        self.assertTrue(self._validate()[1])

    def test_unsuccessful_exact_head_validation_is_rejected(self):
        self._seal()
        run_url = f"https://api.github.com/repos/{self.repository}/actions/runs?head_sha={self.head}&per_page=100&page=1"
        self.github_responses[run_url]["workflow_runs"][0]["conclusion"] = "failure"
        self.assertTrue(self._validate()[1])
        self._seal()
        self.github_responses[run_url]["workflow_runs"][0]["pull_requests"][0]["number"] = 9
        self.assertTrue(self._validate()[1])

    def test_hash_without_explicit_review_decision_is_rejected(self):
        self._seal()
        comment_url = f"https://api.github.com/repos/{self.repository}/issues/8/comments?per_page=100&page=1"
        self.github_responses[comment_url][0]["body"] = receipts.RECEIPT_MARKER + receipts.receipt_digest(self.receipt)
        self.assertTrue(self._validate()[1])


if __name__ == "__main__":
    unittest.main()

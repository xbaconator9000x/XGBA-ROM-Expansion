"""Fail-closed tests for the trusted Phase 1 pull-request CI context."""

import unittest

from tools.verify_phase1_ci_context import validate_event


HEAD_SHA = "a" * 40
REPOSITORY = "xbaconator9000x/XGBA-ROM-Expansion"


def pull_request_event():
    return {
        "repository": {"full_name": REPOSITORY},
        "pull_request": {
            "number": 37,
            "head": {"sha": HEAD_SHA},
        },
    }


class Phase1CIContextTests(unittest.TestCase):
    def test_exact_pull_request_head_and_scope_pass(self):
        self.assertEqual(
            validate_event("pull_request", pull_request_event(), HEAD_SHA, REPOSITORY),
            [],
        )

    def test_synthetic_merge_or_unrelated_checkout_sha_fails(self):
        issues = validate_event(
            "pull_request", pull_request_event(), "d" * 40, REPOSITORY
        )
        self.assertTrue(any("does not equal PR head" in issue for issue in issues))

    def test_missing_pull_request_scope_fails_closed(self):
        event = pull_request_event()
        del event["pull_request"]
        issues = validate_event("pull_request", event, HEAD_SHA, REPOSITORY)
        self.assertIn("pull_request event scope is missing", issues)

    def test_wrong_event_and_repository_scope_fail_closed(self):
        issues = validate_event(
            "pull_request_target",
            pull_request_event(),
            HEAD_SHA,
            "another-owner/another-repository",
        )
        self.assertIn("workflow event must be pull_request", issues)
        self.assertIn(
            "event repository scope does not match GITHUB_REPOSITORY", issues
        )


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import os
import re
import textwrap
import unittest
from pathlib import Path
from unittest import mock


WORKFLOW = Path(__file__).parents[1] / ".github/workflows/phase1-copilot-chain.yml"


def dispatcher_source():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^        run: \|\n(?P<body>(?:^          .*(?:\n|$))+)",
        workflow,
    )
    if not match:
        raise AssertionError("dispatcher heredoc not found")
    lines = match.group("body").splitlines()
    if lines[0].strip() != "python3 - <<'PY'" or lines[-1].strip() != "PY":
        raise AssertionError("dispatcher heredoc boundaries changed")
    return textwrap.dedent("\n".join(lines[1:-1])) + "\n"


def run_dispatcher(token, urlopen=None):
    source = dispatcher_source()
    output = io.StringIO()
    with mock.patch.dict(
        os.environ,
        {"REPO": "xbaconator9000x/XGBA-ROM-Expansion", "GH_TOKEN": token},
        clear=True,
    ), contextlib.redirect_stdout(output):
        if urlopen is None:
            with mock.patch("urllib.request.urlopen") as mocked:
                status = execute(source)
                return status, output.getvalue(), mocked
        with mock.patch("urllib.request.urlopen", side_effect=urlopen) as mocked:
            status = execute(source)
            return status, output.getvalue(), mocked


def execute(source):
    try:
        exec(compile(source, str(WORKFLOW), "exec"), {"__name__": "__main__"})
    except SystemExit as exc:
        return exc.code
    return None


class DispatcherRegressionTests(unittest.TestCase):
    def test_embedded_python_compiles(self):
        compile(dispatcher_source(), str(WORKFLOW), "exec")

    def test_literal_escaped_newline_is_rejected(self):
        source = dispatcher_source()
        marker = (
            'detail=exc.read().decode("utf-8","replace")[:1200]\n'
            "        print("
        )
        self.assertIn(marker, source)
        corrupted = source.replace(marker, marker.replace("\n", r"\n", 1), 1)
        with self.assertRaises(SyntaxError):
            compile(corrupted, str(WORKFLOW), "exec")

    def test_missing_token_exits_without_network_or_comment(self):
        status, output, mocked = run_dispatcher("")
        self.assertEqual(status, 0)
        self.assertIn("DRY RUN: missing XGBA_COPILOT_DISPATCH_PAT", output)
        mocked.assert_not_called()

    def test_incomplete_exact_head_ci_never_posts(self):
        head = "a" * 40

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                return io.BytesIO(
                    json.dumps(
                        {"state": "open", "draft": True, "head": {"sha": head}}
                    ).encode()
                )
            if "/actions/runs?" in request.full_url:
                return io.BytesIO(
                    json.dumps(
                        {
                            "total_count": 1,
                            "workflow_runs": [
                                {
                                    "event": "push",
                                    "status": "completed",
                                    "conclusion": "success",
                                    "head_sha": head,
                                }
                            ]
                        }
                    ).encode()
                )
            self.fail(f"unexpected API request: {request.full_url}")

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("STOP: exact-head CI incomplete", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))

    def test_unreceipted_dispatch_waits_without_comment_creation(self):
        head = "b" * 40
        dispatch = {
            "body": "XGBA_AUTO_PACKAGE_V2 DISPATCH 4 HEAD " + head,
            "created_at": "2026-11-07T00:00:00Z",
            "user": {"login": "xbaconator9000x"},
        }

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                payload = {"state": "open", "draft": True, "head": {"sha": head}}
            elif "/actions/runs?" in request.full_url:
                payload = {
                    "total_count": 2,
                    "workflow_runs": [
                        {
                            "event": event,
                            "status": "completed",
                            "conclusion": "success",
                            "head_sha": head,
                        }
                        for event in ("push", "pull_request")
                    ]
                }
            elif request.full_url.endswith("/issues/27"):
                payload = {"comments": 1}
            elif "/issues/27/comments?" in request.full_url:
                payload = [dispatch]
            else:
                self.fail(f"unexpected API request: {request.full_url}")
            return io.BytesIO(json.dumps(payload).encode())

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("WAIT: dispatched package 4", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))


    def test_spoofed_copilot_username_cannot_advance_queue(self):
        head = "c" * 40
        prior = "d" * 40
        dispatch = {
            "body": "XGBA_AUTO_PACKAGE_V2 DISPATCH 4 HEAD " + prior,
            "created_at": "2026-11-07T00:00:00Z",
            "user": {"login": "xbaconator9000x"},
        }
        spoof = {
            "body": "XGBA_AUTO_PACKAGE_V2 COMPLETE 4 " + head,
            "created_at": "2026-11-07T01:00:00Z",
            "user": {"login": "copilot", "id": 999, "type": "User"},
        }

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                payload = {"state": "open", "draft": True, "head": {"sha": head}}
            elif "/actions/runs?" in request.full_url:
                payload = {"total_count": 2, "workflow_runs": [
                    {"event": event, "status": "completed",
                     "conclusion": "success", "head_sha": head}
                    for event in ("push", "pull_request")
                ]}
            elif request.full_url.endswith("/issues/27"):
                payload = {"comments": 2}
            elif "/issues/27/comments?" in request.full_url:
                payload = [dispatch, spoof]
            else:
                self.fail(f"unexpected API request: {request.full_url}")
            return io.BytesIO(json.dumps(payload).encode())

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("WAIT: dispatched package 4", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))



    def test_manual_copilot_assignment_blocks_new_dispatch(self):
        head = "e" * 40
        manual = {
            "body": "@copilot Continue existing pinned review package on PR27",
            "user": {"login": "xbaconator9000x"},
        }

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                payload = {"state": "open", "draft": True, "head": {"sha": head}}
            elif "/actions/runs?" in request.full_url:
                payload = {"total_count": 2, "workflow_runs": [
                    {"event": event, "status": "completed",
                     "conclusion": "success", "head_sha": head}
                    for event in ("push", "pull_request")
                ]}
            elif request.full_url.endswith("/issues/27"):
                payload = {"comments": 1}
            elif "/issues/27/comments?" in request.full_url:
                payload = [manual]
            else:
                self.fail(f"unexpected API request: {request.full_url}")
            return io.BytesIO(json.dumps(payload).encode())

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("STOP: manual Copilot assignment exists", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))


    def test_receipt_requires_exact_structured_body_and_head(self):
        source = dispatcher_source()
        self.assertIn('re.fullmatch(re.escape(marker)+r" COMPLETE "', source)
        self.assertIn('r" HEAD "+re.escape(head)', source)
        self.assertNotIn('(marker+" COMPLETE "+str(number)) in c.get("body","")', source)
        marker = "XGBA_AUTO_PACKAGE_V2"
        number = 4
        head = "a" * 40
        pattern = re.escape(marker) + r" COMPLETE " + str(number) + r" HEAD " + re.escape(head)
        self.assertIsNotNone(re.fullmatch(pattern, f"{marker} COMPLETE 4 HEAD {head}"))
        for forged in (
            f"prefix {marker} COMPLETE 4 HEAD {head}",
            f"{marker} COMPLETE 4 HEAD {head} trailing",
            f"{marker} COMPLETE 4 HEAD {'b' * 40}",
            f"{marker} COMPLETE 40 HEAD {head}",
            f"{marker} COMPLETE 4 {head}",
        ):
            with self.subTest(forged=forged):
                self.assertIsNone(re.fullmatch(pattern, forged))

    def test_overfull_ci_run_inventory_fails_closed(self):
        head = "f" * 40

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                payload = {"state": "open", "draft": True, "head": {"sha": head}}
            elif "/actions/runs?" in request.full_url:
                payload = {"total_count": 101, "workflow_runs": [
                    {"event": event, "status": "completed",
                     "conclusion": "success", "head_sha": head}
                    for event in ("push", "pull_request")
                ]}
            else:
                self.fail(f"unexpected API request: {request.full_url}")
            return io.BytesIO(json.dumps(payload).encode())

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("CI run inventory missing, truncated or exceeds one page", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))

    def test_overfull_comment_inventory_fails_closed(self):
        head = "f" * 40

        def fake_urlopen(request, timeout):
            self.assertEqual(request.get_method(), "GET")
            if request.full_url.endswith("/pulls/27"):
                payload = {"state": "open", "draft": True, "head": {"sha": head}}
            elif "/actions/runs?" in request.full_url:
                payload = {"total_count": 2, "workflow_runs": [
                    {"event": event, "status": "completed",
                     "conclusion": "success", "head_sha": head}
                    for event in ("push", "pull_request")
                ]}
            elif request.full_url.endswith("/issues/27"):
                payload = {"comments": 201}
            else:
                self.fail(f"unexpected API request: {request.full_url}")
            return io.BytesIO(json.dumps(payload).encode())

        status, output, mocked = run_dispatcher("test-token", fake_urlopen)
        self.assertEqual(status, 0)
        self.assertIn("discussion exceeds inspected comment window", output)
        self.assertTrue(all(call.args[0].get_method() == "GET" for call in mocked.call_args_list))


if __name__ == "__main__":
    unittest.main()

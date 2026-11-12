"""Unit tests for public tracked-tree privacy check; synthetic data only."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "repository_privacy_audit.py"
spec = importlib.util.spec_from_file_location("repository_privacy_audit", PATH)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class PublicRepositoryPrivacyChecks(unittest.TestCase):
    def test_rejects_synthetic_credentials_without_printing_them(self):
        sample = "prefix " + "gh" + "p_" + "A" * 35
        self.assertIn(("github-access-token", 1),
                      audit.audit_bytes("docs/demo.md", sample.encode()))

    def test_rejects_synthetic_api_key_and_private_pem(self):
        key = "sk-" + "proj-" + "B" * 40
        self.assertIn(("openai-api-key", 1),
                      audit.audit_bytes("tools/demo.py", key.encode()))
        pem = "-----BEGIN " + "PRIVATE KEY-----\n" + "C" * 64
        self.assertIn(("private-key", 1),
                      audit.audit_bytes("docs/demo.md", pem.encode()))

    def test_rejects_transcribed_chat_or_private_operational_narrative(self):
        dialogue = "User" + ": please export everything\n" + "Assistant" + ": done\n"
        categories = {kind for kind, _ in audit.audit_bytes("a.md", dialogue.encode())}
        self.assertIn("private-conversation-marker", categories)
        history = "billing " + "screenshot" + " from old workflow"
        categories = {kind for kind, _ in audit.audit_bytes("a.md", history.encode())}
        self.assertIn("personal-chat-session", categories)

    def test_rejects_contact_details_not_example_or_bot_addresses(self):
        address = "staff" + "@" + "example.net"
        self.assertIn(("potential-email-address", 1),
                      audit.audit_bytes("a.md", address.encode()))
        good = "example" + "@" + "example.com"
        self.assertNotIn("potential-email-address",
                         {kind for kind, _ in audit.audit_bytes("a.md", good.encode())})

    def test_catches_untracked_credentials_only_when_added(self):
        self.assertTrue(audit.FORBIDDEN_FILE.search("configs/.env"))
        self.assertTrue(audit.FORBIDDEN_FILE.search("keys/private.pem"))
        self.assertFalse(audit.FORBIDDEN_FILE.search("tests/test_xgba_guest.py"))

    def test_functional_task_goals_are_not_confused_with_chat_transcripts(self):
        code = 'def prompt_for(task): return {"prompt": task.goal}'
        self.assertEqual([], audit.audit_bytes("tools/dispatcher.py", code.encode()))

    def test_readme_intro_in_required_order(self):
        readme = "\n".join((
            "## What XGBA is", "## Goals", "## Potential implications",
            "## AI disclosure",
            "I am developing XGBA with the help of AI for coding and logging purposes.",
            "## Development history and verified results", "R6–R27 verified",
        ))
        self.assertEqual([], audit.check_readme(readme))
        self.assertNotEqual([], audit.check_readme(readme.replace("## Goals", "")))

    def test_retired_copilot_dispatch_sources_cannot_return(self):
        self.assertIn("tools/xgba_autonomous_product.py",
                      audit.RETIRED_DISPATCH_FILES)
        self.assertIn(".github/workflows/phase1-copilot-chain.yml",
                      audit.RETIRED_DISPATCH_FILES)
        self.assertNotIn("integration/mgba/xgba_mgba_device.c",
                         audit.RETIRED_DISPATCH_FILES)

    def test_binary_files_are_not_decoded_as_utf8(self):
        self.assertEqual([], audit.audit_bytes("img/a.png", b"\x89PNG\x00\x88"))


if __name__ == "__main__":
    unittest.main()

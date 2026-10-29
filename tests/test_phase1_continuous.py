"""Regression tests for the fail-closed Phase 1 evidence queue controller.

Run with: python3 -m unittest discover -s tests -p test_phase1_continuous.py
"""
import importlib.util
from pathlib import Path
import unittest


TARGET = Path(__file__).resolve().parents[1] / "tools" / "phase1_continuous.py"
SPEC = importlib.util.spec_from_file_location("phase1_continuous", TARGET)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class FakeSnapshot:
    def __init__(self):
        self.fingerprint = "pinned-fixture-v1"
        self.queue = [{}] * 1200
        self.total = 3
        self.fail_unit = None

    def packet(self, index):
        if index == self.fail_unit:
            raise RuntimeError("Injected full disk or corrupt dossier")
        return {
            "unit": index + 1,
            "first_file": index * worker.CHUNK + 1,
            "last_file": min((index + 1) * worker.CHUNK, len(self.queue)),
            "verified_files": min(worker.CHUNK, len(self.queue) - index * worker.CHUNK),
            "input_fingerprint": self.fingerprint,
            "packet_sha256": "fixture-%d" % index,
            "evidence_class": "REVERIFIED_CANDIDATE_DOSSIERS_ONLY",
            "independent_semantic_approvals": 0,
            "phase1_approved": False,
        }


class MemoryStore:
    def __init__(self, snapshot):
        self.state = worker.initial_state(snapshot)
        self.writes = 0
        self.fail_after_save_number = None

    def load(self, snapshot):
        return self.state, str(self.writes)

    def save(self, state, previous_sha):
        assert str(self.writes) == previous_sha
        self.writes += 1
        if self.fail_after_save_number == self.writes:
            # Mimics a killed process directly after the server commits.
            raise KeyboardInterrupt("simulated runner crash after durable checkpoint")
        return str(self.writes)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = FakeSnapshot()
        self.store = MemoryStore(self.snapshot)

    def execute(self, limit=3):
        return worker.perform(self.snapshot, self.store, limit, "test-run")

    def test_verify_chunks_in_order_and_complete_only_on_receipts(self):
        outcome, amount, state = self.execute()
        self.assertEqual((outcome, amount), ("COMPLETE", 3))
        self.assertEqual([x["status"] for x in state["units"]], ["VERIFIED"] * 3)
        self.assertTrue(worker.verify_state(self.snapshot, state))
        self.assertFalse(state["approval_claim"])

    def test_failure_never_skips_next_chunk(self):
        self.snapshot.fail_unit = 1
        outcome, amount, state = self.execute()
        self.assertEqual((outcome, amount), ("RETRY", 1))
        self.assertEqual([x["status"] for x in state["units"]], ["VERIFIED", "RETRY", "PENDING"])
        self.assertEqual([x["attempts"] for x in state["units"]], [1, 1, 0])
        self.snapshot.fail_unit = None
        outcome, amount, state = self.execute()
        self.assertEqual((outcome, amount), ("COMPLETE", 2))
        self.assertEqual([x["attempts"] for x in state["units"]], [1, 2, 1])

    def test_three_failures_block_queue_and_preserve_gap(self):
        self.snapshot.fail_unit = 0
        self.assertEqual(self.execute()[0], "RETRY")
        self.assertEqual(self.execute()[0], "RETRY")
        outcome, amount, state = self.execute()
        self.assertEqual((outcome, amount), ("BLOCKED", 0))
        self.assertEqual([x["status"] for x in state["units"]], ["BLOCKED", "PENDING", "PENDING"])
        self.assertEqual(state["units"][0]["attempts"], 3)
        self.snapshot.fail_unit = None
        self.assertEqual(self.execute()[0], "BLOCKED")

    def test_resume_running_unit_after_crash(self):
        self.store.fail_after_save_number = 1
        with self.assertRaises(KeyboardInterrupt):
            self.execute()
        self.assertEqual([x["status"] for x in self.store.state["units"]], ["RUNNING", "PENDING", "PENDING"])
        self.store.fail_after_save_number = None
        outcome, count, state = self.execute()
        self.assertEqual((outcome, count), ("COMPLETE", 3))
        self.assertEqual(state["units"][0]["attempts"], 2)

    def test_later_verified_receipt_does_not_cover_gap(self):
        state = worker.initial_state(self.snapshot)
        state["units"][2] = {"status": "VERIFIED", "attempts": 1,
                             "receipt": self.snapshot.packet(2), "error": None}
        with self.assertRaisesRegex(RuntimeError, "after unfinished"):
            worker.verify_state(self.snapshot, state)

    def test_tampered_receipt_rejected(self):
        self.execute()
        self.store.state["units"][0]["receipt"]["packet_sha256"] = "tampered"
        with self.assertRaisesRegex(RuntimeError, "altered verified receipt"):
            worker.verify_state(self.snapshot, self.store.state)

    def test_changed_pins_or_count_require_reconciliation(self):
        self.execute()
        self.snapshot.fingerprint = "changed-source-pins"
        with self.assertRaisesRegex(RuntimeError, "schema or pinned evidence changed"):
            worker.verify_state(self.snapshot, self.store.state)

    def test_running_item_with_receipt_is_invalid(self):
        state = worker.initial_state(self.snapshot)
        state["units"][0]["receipt"] = self.snapshot.packet(0)
        with self.assertRaisesRegex(RuntimeError, "Unverified chunk contains receipt"):
            worker.verify_state(self.snapshot, state)


if __name__ == "__main__":
    unittest.main()

"""Fail-closed host log-observer evidence controls."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_frontend_log_observers",
    ROOT / "tools/phase1_mgba_frontend_log_observers.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = (
    "compiler diagnostics\n"
    "PHASE1_MGBA_FRONTEND_LOG_WITNESS "
    + json.dumps(runner.EXPECTED_OUTPUT, separators=(",", ":"), sort_keys=True)
    + "\n"
)


class TestFrontendLogObserverEvidence(unittest.TestCase):
    def test_positive_result(self):
        result = runner.parse_output(GOOD)
        self.assertEqual(result["evidence_class"], "compiled_pinned_source_host_sink")
        self.assertFalse(result["native_frontend_runtime_observed"])
        self.assertFalse(result["persistence_acknowledgment"])

    def assert_mutation_rejected(self, key, value):
        result = copy.deepcopy(runner.EXPECTED_OUTPUT)
        result[key] = value
        output = "PHASE1_MGBA_FRONTEND_LOG_WITNESS " + json.dumps(result) + "\n"
        with self.assertRaises(ValueError):
            runner.parse_output(output)

    def test_reject_claimed_native_frontend(self):
        self.assert_mutation_rejected("native_frontend_runtime_observed", True)

    def test_reject_fabricated_persistence_acknowledgment(self):
        self.assert_mutation_rejected("persistence_acknowledgment", True)

    def test_reject_claimed_stock_gameplay(self):
        self.assert_mutation_rejected("stock_gameplay", True)

    def test_reject_claimed_physical_flash(self):
        self.assert_mutation_rejected("physical_flash", True)

    def test_reject_missing_standard_stdout_observation(self):
        self.assert_mutation_rejected("standard_stdout_exact", False)

    def test_reject_missing_gui_file_observation(self):
        self.assert_mutation_rejected("gui_file_exact", False)

    def test_reject_invented_gui_write_retry(self):
        self.assert_mutation_rejected("gui_positive_short_retries", 1)

    def test_reject_absent_sink_write(self):
        self.assert_mutation_rejected("gui_missing_sink_writes", 1)

    def test_reject_filter_bypass(self):
        self.assert_mutation_rejected("gui_filter_suppressed_writes", 1)

    def test_reject_false_reopen_recovery(self):
        self.assert_mutation_rejected("gui_recovery_file_exact", False)

    def test_reject_wrong_reopen_path_or_mode(self):
        self.assert_mutation_rejected("gui_reopen_arguments_exact", False)

    def test_reject_malformed_json(self):
        with self.assertRaises(ValueError):
            runner.parse_output(
                "PHASE1_MGBA_FRONTEND_LOG_WITNESS {not-json}\n"
            )

    def test_reject_duplicate_result(self):
        line = GOOD.splitlines()[-1]
        with self.assertRaises(ValueError):
            runner.parse_output(line + "\n" + line + "\n")

    def test_reject_duplicate_json_key(self):
        output = (
            'PHASE1_MGBA_FRONTEND_LOG_WITNESS '
            '{"native_frontend_runtime_observed":false,'
            '"native_frontend_runtime_observed":true}\n'
        )
        with self.assertRaises(ValueError):
            runner.parse_output(output)

    def test_reject_missing_result(self):
        with self.assertRaises(ValueError):
            runner.parse_output("no witness output\n")

    def test_reject_extra_result_field(self):
        result = copy.deepcopy(runner.EXPECTED_OUTPUT)
        result["semantic_approval"] = True
        with self.assertRaises(ValueError):
            runner.parse_output(
                "PHASE1_MGBA_FRONTEND_LOG_WITNESS "
                + json.dumps(result)
                + "\n"
            )

    def test_reject_wrong_source_signature(self):
        with self.assertRaises(ValueError):
            runner.extract_function("void other(void) {}", "void target(void)")

    def test_reject_ambiguous_source_signature(self):
        with self.assertRaises(ValueError):
            runner.extract_function(
                "void target(void) {}\nvoid target(void) {}",
                "void target(void)",
            )

    def test_reject_unbalanced_source_function(self):
        with self.assertRaises(ValueError):
            runner.extract_function(
                "void target(void) { if (1) { return; }",
                "void target(void)",
            )

    def test_extract_exact_nested_function(self):
        source = "void target(void) { if (1) { return; } }\nint after;"
        self.assertEqual(
            runner.extract_function(source, "void target(void)"),
            "void target(void) { if (1) { return; } }",
        )

    def test_matrix_has_no_native_or_durability_claim(self):
        matrix = runner.expected_matrix()
        contract = matrix["execution_contract"]
        self.assertFalse(contract["native_qt_or_console_frontend_execution"])
        self.assertFalse(contract["persistence_or_power_loss_evidence"])
        self.assertFalse(contract["independent_semantic_approval"])
        self.assertEqual(len(matrix["source_records"]), 4)

    def test_matrix_source_pin_mutation_changes_contract(self):
        matrix = runner.expected_matrix()
        matrix["source_records"][0]["git_blob"] = "0" * 40
        self.assertNotEqual(matrix, runner.expected_matrix())

    def test_matrix_verifier_rejects_stale_pin(self):
        matrix = runner.expected_matrix()
        matrix["pinned_revision"] = "0" * 40
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as stream:
            json.dump(matrix, stream)
            stream.flush()
            with self.assertRaises(ValueError):
                runner.verify_matrix(ROOT, stream.name)


if __name__ == "__main__":
    unittest.main()

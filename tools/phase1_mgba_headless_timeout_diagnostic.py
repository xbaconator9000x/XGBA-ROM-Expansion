#!/usr/bin/env python3
"""Verify the bounded headless timeout and Qt feasibility handoff."""
import argparse
import importlib.util
import json
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-headless-timeout-diagnostic-20261106.json"
)
BASE_TOOL = "tools/phase1_mgba_frontend_runtime_feasibility.py"
SOURCE_PATHS = (
    "src/platform/headless-main.c",
    "src/gba/core.c",
    "src/gba/gba.c",
    "src/core/core.c",
    "src/platform/qt/CoreController.cpp",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _base_runner(root):
    spec = importlib.util.spec_from_file_location(
        "phase1_mgba_frontend_runtime_feasibility",
        Path(root) / BASE_TOOL,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_diagnostic(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    base = _base_runner(root)
    records = {
        row["path"]: row for row in base.expected_matrix()["source_records"]
    }
    return {
        "schema": "phase1.mgba.headless-timeout-diagnostic.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "machine_dossier": {
            "path": base.DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "source_records": [
            {
                key: records[path][key]
                for key in (
                    "path", "git_blob", "full_source_sha256",
                    "canonical_dossier_row_sha256", "license",
                )
            }
            for path in SOURCE_PATHS
        ],
        "headless_source_diagnosis": {
            "signal_handler": "SIGINT only",
            "default_gba_exit_swi": 3,
            "run_loop_condition": "_dispatchExiting remains false until a shutdown/SWI callback",
            "timeout_signal_effect": (
                "A TERM-based timeout does not invoke the installed SIGINT handler; "
                "the process can be terminated before unloadROM/deinit."
            ),
            "synthetic_rom_observation_from_prior_attempt": (
                "Repeated GBA BIOS SWI 00 messages; intended shutdown/save path not reached."
            ),
            "headless_autoloads_file_save": False,
            "gba_savedata_initial_vfile_is_null": True,
            "implication": (
                "Even a controlled headless shutdown does not establish a normal "
                "file-backed .sav save/reopen lifecycle on this caller path."
            ),
        },
        "prior_actual_headless_attempt": {
            "pinned_headless_build_reported_success": True,
            "process_launched": True,
            "save_or_shutdown_reached": False,
            "exact_command_retained": False,
            "exact_exit_status": None,
            "exact_runtime_seconds": None,
            "stdout_or_stderr_artifact_retained": False,
            "reproducible_binary_retained": False,
            "reason_missing": (
                "The earlier temporary checkout/build/logs were not retained in this "
                "sandbox; do not infer an exit code or duration from the word timeout."
            ),
        },
        "bounded_signal_controls": [
            {
                "class": "synthetic_host_timeout_control",
                "command": (
                    "/usr/bin/time -f 'outer_elapsed_seconds=%e\\ntime_exit=%x' "
                    "timeout --preserve-status -s TERM 0.40s python3 -u -c "
                    "'import signal,time; signal.signal(signal.SIGINT, lambda *_: "
                    "print(\"SIGINT_HANDLER_RAN\", flush=True)); "
                    "print(\"CONTROL_STARTED\", flush=True); time.sleep(30)'"
                ),
                "elapsed_seconds": 0.40,
                "shell_exit_status": 143,
                "stdout_lines": ["CONTROL_STARTED"],
                "interpretation": (
                    "TERM terminates the controlled process; its SIGINT handler does "
                    "not run. This demonstrates timeout signal semantics only."
                ),
                "mGBA_process": False,
            },
            {
                "class": "synthetic_host_signal_control",
                "command": (
                    "/usr/bin/time -f 'outer_elapsed_seconds=%e\\ntime_exit=%x' "
                    "timeout --preserve-status -s INT 0.40s python3 -u -c "
                    "'import signal,time; signal.signal(signal.SIGINT, lambda *_: "
                    "print(\"SIGINT_HANDLER_RAN\", flush=True) or "
                    "(_ for _ in ()).throw(SystemExit(0))); "
                    "print(\"CONTROL_STARTED\", flush=True); time.sleep(30)'"
                ),
                "elapsed_seconds": 0.40,
                "shell_exit_status": 0,
                "stdout_lines": ["CONTROL_STARTED", "SIGINT_HANDLER_RAN"],
                "interpretation": (
                    "The matching SIGINT control invokes its installed handler."
                ),
                "mGBA_process": False,
            },
        ],
        "qt_build_diagnosis": {
            "prior_build_attempts": [
                {
                    "configuration": "BUILD_GL=OFF",
                    "result": "FAILED",
                    "observed": "ShaderSelector undeclared during compilation",
                },
                {
                    "configuration": "BUILD_GL=ON after installing libepoxy-dev",
                    "result": "FAILED",
                    "observed": (
                        "link failed with unresolved ShaderSelector Qt "
                        "meta-object/vtable symbols"
                    ),
                },
            ],
            "frontend_executable_produced": False,
            "build_logs_retained": False,
            "new_qt_build_reproduced": False,
            "latest_push_workflow": {
                "run_id": 42062070815,
                "job_id": 127366220708,
                "head_sha": "03785a6c029188bccfe6c13907a61da0b3c7d544",
                "conclusion": "cancelled",
                "cancelled_at": (
                    "Install native Qt6 Core for SaveConverter witness; Actions "
                    "log ended while downloading Qt/graphics dependencies, at "
                    "libspa-0.2-modules"
                ),
                "meaning": (
                    "Job started at 16:12:20Z and was cancelled at 16:32:35Z, "
                    "while the 20-minute job was still downloading dependencies. "
                    "No Qt frontend compile/link step ran; do not treat this as "
                    "a Qt frontend build failure."
                ),
            },
        },
        "execution_contract": {
            "actual_headless_timeout_reproduced": False,
            "synthetic_signal_controls_executed": True,
            "actual_mgba_frontend_fault_injection": False,
            "headless_save_lifecycle_observed": False,
            "frontend_native_execution_observed": False,
            "cold_process_sav_reopen_observed": False,
            "logger_delivery_observed": False,
            "missing_logger_control_repeated": False,
            "dirty_to_clean_is_persistence_acknowledgment": False,
            "durable_persistence_or_power_loss_evidence": False,
            "stock_gameplay": False,
            "physical_flash": False,
            "independent_semantic_approval": False,
            "gate_or_approval_state_changed": False,
        },
        "unresolved": [
            "Rebuild the exact pinned headless binary with a retained command, output, exit code, and elapsed time.",
            "Use a ROM/BIOS path that reaches the configured shutdown SWI or send SIGINT and verify cleanup runs.",
            "Use a caller that actually opens a file-backed .sav before testing reopen; headless autoload is absent.",
            "Reproduce the Qt frontend build with retained configure/build logs and resolve the ShaderSelector compile/link blocker.",
            "Inject real backend write/sync failure and observe frontend return, callback, and log behavior.",
        ],
        "distribution_notice": (
            "Source identities refer to pinned MPL-2.0 files already covered by the "
            "frontend feasibility verifier. Preserve MPL-2.0 and repository license "
            "notices in combined distributions; this report copies no upstream source."
        ),
    }


def validate_payload(payload, root=None):
    require(payload == expected_diagnostic(root),
            "headless timeout diagnostic differs from the fail-closed contract")
    require(payload["status"] == "NEEDS_EVIDENCE" and
            payload["overall"] == "FAIL_INCOMPLETE",
            "unobserved headless/frontend behavior cannot be marked complete")
    return True


def verify_checkout(checkout, root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    base = _base_runner(root)
    base.verify_checkout(checkout, root)
    payload = json.loads((root / MATRIX).read_text(encoding="utf-8"))
    validate_payload(payload, root)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", help="exact pinned mGBA checkout")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root)
    payload = json.loads((root / MATRIX).read_text(encoding="utf-8"))
    validate_payload(payload, root)
    if args.checkout:
        verify_checkout(args.checkout, root)
    print(json.dumps({
        "pinned_revision": PIN,
        "synthetic_signal_controls": len(payload["bounded_signal_controls"]),
        "actual_headless_timeout_reproduced": False,
        "headless_save_lifecycle_observed": False,
        "status": payload["status"],
        "overall": payload["overall"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

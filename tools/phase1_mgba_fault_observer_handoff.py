#!/usr/bin/env python3
"""Verify the bounded pinned mGBA save-fault observer handoff."""
import argparse
import importlib.util
import json
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-fault-to-observer-handoff-20261105.json"
)
CALLBACK_TOOL = "tools/phase1_mgba_vfs_fd_callback_native.py"
CALLBACK_WORKPAPER = (
    "docs/phase1-review-readiness/"
    "mgba-gba-savedata-callback-failure-20261102.md"
)
CROSS_BACKEND_WORKPAPER = (
    "docs/phase1-review-readiness/"
    "mgba-cross-backend-save-observability-20261105.md"
)
PLATFORM_WORKPAPER = (
    "docs/phase1-review-readiness/"
    "mgba-platform-save-observer-closure-20261105.md"
)

PATH_OBJECTIONS = [
    {
        "id": "savedata_callback",
        "status": "RESOLVED_SOURCE_ONLY",
        "sources": [
            "src/gba/savedata.c",
            "src/gba/gba.c",
            "src/core/scripting.c",
            "src/script/stdlib.c",
            "include/mgba/core/interface.h",
        ],
        "result": "failed_sync_can_clear_dirty_and_emit_savedataUpdated",
        "meaning": "save_data_changed_not_persistence_acknowledgment",
        "execution": "prior_pinned_linux_host_failure_witness",
        "objection": "No persistence receipt is returned by this callback; host callback observation is not a frontend presentation result.",
    },
    {
        "id": "core_sync_info_log",
        "status": "RESOLVED_SOURCE_ONLY",
        "sources": [
            "src/gba/savedata.c",
            "src/core/log.c",
            "src/util/vfs/vfs-fd.c",
        ],
        "result": "failed_sync_emits_INFO_Savedata_failed_to_sync",
        "meaning": "native_test_logger_received_message_not_frontend_visibility",
        "execution": "pinned_linux_host_logger_capture_with_controlled_msync_EIO",
        "objection": "The captured test logger is not Qt, SDL, libretro, Python, or a headless user session.",
    },
    {
        "id": "shutdown_and_teardown",
        "status": "RESOLVED_SOURCE_ONLY",
        "sources": [
            "src/gba/savedata.c",
            "src/gba/gba.c",
            "src/gba/core.c",
            "src/core/core.c",
            "include/mgba/core/thread.h",
            "src/util/vfs/vfs-fd.c",
            "src/util/vfs/vfs-file.c",
        ],
        "result": "unmap_and_core_unload_do_not_propagate_persistence_result",
        "meaning": "close_status_and_sync_status_are_not_core_shutdown_acknowledgments",
        "execution": "prior_source_closure_and_host_teardown_witnesses",
        "objection": "The contract is resolved at these pinned call sites; it does not prove actual disk persistence or platform durability.",
    },
    {
        "id": "qt",
        "status": "NEEDS_EVIDENCE",
        "sources": [
            "src/platform/qt/CoreController.cpp",
            "src/platform/qt/LogController.cpp",
            "src/platform/qt/LogView.cpp",
            "src/platform/qt/Window.cpp",
            "src/platform/qt/CoreManager.cpp",
            "src/platform/qt/main.cpp",
        ],
        "result": "INFO_filter_and_logPosted_route_are_source_reviewed",
        "meaning": "INFO_is_not_the_Qt_ERROR_dialog_condition",
        "execution": "not_executed_in_Qt_frontend",
        "objection": "Actual Qt filter state, logPosted delivery, configured sinks, and visible UI response remain unobserved.",
    },
    {
        "id": "sdl",
        "status": "NEEDS_EVIDENCE",
        "sources": ["src/platform/sdl/main.c", "src/core/log.c"],
        "result": "default_logLevel_excludes_INFO_configuration_may_change_it",
        "meaning": "source_condition_only",
        "execution": "not_executed_in_SDL_frontend",
        "objection": "No SDL run observed effective configuration, stdout/file sink, or user visibility.",
    },
    {
        "id": "libretro",
        "status": "NEEDS_EVIDENCE",
        "sources": [
            "src/platform/libretro/libretro.c",
            "src/platform/libretro/libretro.h",
            "src/core/log.c",
        ],
        "result": "RETRO_LOG_INFO_is_forwarded_only_with_optional_host_log_interface",
        "meaning": "conditional_callback_not_save_success",
        "execution": "not_executed_in_libretro_frontend",
        "objection": "No libretro frontend/host interface negotiation or log callback invocation was observed.",
    },
    {
        "id": "python",
        "status": "NEEDS_EVIDENCE",
        "sources": [
            "src/platform/python/core.c",
            "src/platform/python/core.h",
            "src/platform/python/mgba/core.py",
            "src/platform/python/log.c",
            "src/platform/python/mgba/log.py",
            "src/platform/python/_builder.py",
        ],
        "result": "logger_is_optional_and_NullLogger_suppresses_output",
        "meaning": "installation_dependent_log_consumer",
        "execution": "not_executed_in_Python_binding",
        "objection": "No installed default Python logger, callback behavior, or consumer output was observed.",
    },
    {
        "id": "headless",
        "status": "NEEDS_EVIDENCE",
        "sources": ["src/platform/headless-main.c", "src/core/log.c"],
        "result": "standard_logger_configures_logToStdout_default_true",
        "meaning": "configuration_and_source_route_only",
        "execution": "not_executed_in_headless_process",
        "objection": "No headless process captured the failed-sync log or its exit status under failure.",
    },
]

WITNESS = {
    "source_pin": PIN,
    "source_files": [
        {
            "path": "src/gba/savedata.c",
            "git_blob_sha": "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
            "source_sha256": "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
            "dossier_row_sha256": "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
            "license": "MPL-2.0",
            "role": "original_sync_failure_call_site",
        },
        {
            "path": "src/util/vfs/vfs-fd.c",
            "git_blob_sha": "2535bd0fb76740745ae038d5523ead28658f1035",
            "source_sha256": "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
            "dossier_row_sha256": "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
            "license": "MPL-2.0",
            "role": "complete_original_posix_fd_vfile_translation_unit",
        },
        {
            "path": "src/core/log.c",
            "git_blob_sha": "39d6db88cad3ca6f521a532c114b6488adb77279",
            "source_sha256": "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
            "dossier_row_sha256": "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
            "license": "MPL-2.0",
            "role": "original_logger_dispatch_function_bodies",
        },
    ],
    "function_sha256": {
        "GBASavedataClean": "3fc3989ccac6c04fa32780fcffcb5cd49ff22ff306826e569c85d52647f701bb",
        "mLogGetThreadLogger": "3d970d27d308e3254cf4378e700a0a976312ef1338350788cd3da6c9dad78991",
        "mLogGetContext": "741c7b1d0d604d083ec96cec49dfadf59826794d37ea8bb6c2412f3cad82b0bf",
        "mLogSetDefaultLogger": "9b2a934daaf6a20a3f6815e83acab6be9e564b3323421522a4a403772d019597",
        "mLog": "7de1b3df9d9db21bb6a537dd3d7c7089f1728795eb06f1eecc2ed851d858b523",
    },
    "source_file": "src/core/log.c",
    "source_file_git_blob": "39d6db88cad3ca6f521a532c114b6488adb77279",
    "source_file_sha256": "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
    "source_dossier_row_sha256": "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
    "backend": "pinned_POSIX_fd_VFile_msync_MS_ASYNC",
    "fault": "controlled_test_wrapper_returns_EIO",
    "executed_original_bodies": [
        "GBASavedataClean",
        "mLogGetThreadLogger",
        "mLogGetContext",
        "mLogSetDefaultLogger",
        "mLog",
    ],
    "native_class": "compiled_linux_host_source_extraction",
    "logger": "test_capture_callback_not_platform_frontend",
    "observed": "one_INFO_log_with_exact_sync_failure_message",
    "persistence_result": "not_observed",
    "persistence_acknowledgment": False,
    "frontend_runtime_observed": False,
    "physical_flash_or_power_loss_evidence": False,
    "stock_game_or_save_file_claim": False,
}

MUTATION_CONTROLS = [
    "failed_sync_cannot_be_relabelled_persistence_success",
    "absent_frontend_logger_cannot_be_claimed_observed",
    "stale_upstream_revision_rejected",
    "wrong_native_backend_rejected",
    "fabricated_persistence_acknowledgment_rejected",
    "non_observed_frontend_delivery_rejected",
    "source_pin_and_dossier_row_mismatch_rejected",
    "sync_failure_log_level_or_message_mutation_rejected",
]


def expected_matrix():
    return {
        "schema": "phase1.mgba.fault-to-observer-handoff.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "source_inventory": "reuses_already_pinned_sources_only_no_new_frontend_inventory",
        "prior_workpapers": [
            CALLBACK_WORKPAPER,
            CROSS_BACKEND_WORKPAPER,
            PLATFORM_WORKPAPER,
        ],
        "native_witness": WITNESS,
        "path_objections": PATH_OBJECTIONS,
        "mutation_controls": MUTATION_CONTROLS,
        "limitations": {
            "actual_frontend_log_visibility_observed": False,
            "core_shutdown_persistence_acknowledgment": False,
            "actual_persistence_result_observed": False,
            "physical_flash_or_power_loss_evidence": False,
            "stock_game_or_save_file_claim": False,
            "semantic_approval": False,
        },
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_matrix_payload(matrix):
    require(matrix == expected_matrix(),
            "fault-to-observer matrix differs from the pinned contract")
    statuses = {item["status"] for item in matrix["path_objections"]}
    require(statuses <= {"RESOLVED_SOURCE_ONLY", "NEEDS_EVIDENCE"},
            "unsupported observer disposition status")
    return True


def load_callback_runner(root):
    path = root / CALLBACK_TOOL
    spec = importlib.util.spec_from_file_location(
        "phase1_mgba_vfs_fd_callback_native", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_source_verifier(root, path):
    spec = importlib.util.spec_from_file_location(path.stem, root / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(source_root, repo_root, matrix_path, checkout_identity=False):
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    validate_matrix_payload(matrix)
    for workpaper in matrix["prior_workpapers"]:
        require((Path(repo_root) / workpaper).is_file(),
                "missing reused evidence workpaper: " + workpaper)
    callback = load_callback_runner(Path(repo_root))
    sources, *_ = callback.verify_sources(Path(source_root), checkout_identity)
    cross = load_source_verifier(
        Path(repo_root), Path("tools/phase1_mgba_cross_backend_observability.py")
    )
    cross.verify_sources(
        Path(source_root), Path(repo_root), Path(repo_root) / cross.MATRIX,
        checkout_identity,
    )
    platform = load_source_verifier(
        Path(repo_root), Path("tools/phase1_mgba_platform_observer_closure.py")
    )
    platform.verify_sources(
        Path(source_root), Path(repo_root), Path(repo_root) / platform.MATRIX,
        checkout_identity,
    )
    for item in WITNESS["source_files"]:
        path = item["path"]
        require(callback.FILES[path] == (
            item["git_blob_sha"], item["source_sha256"]
        ), "source identity differs from native handoff: " + path)
        require(callback.DOSSIER_ROWS[path] == item["dossier_row_sha256"],
                "dossier row differs from native handoff: " + path)
        require("Mozilla Public" in sources[path] and "License, v. 2.0." in
                sources[path], "missing pinned MPL-2.0 notice: " + path)
    require(
        WITNESS["source_dossier_row_sha256"] ==
        callback.DOSSIER_ROWS[WITNESS["source_file"]],
        "core logger dossier row differs from handoff",
    )
    require(
        WITNESS["function_sha256"]["GBASavedataClean"] ==
        callback.CLEAN_BODY_SHA256,
        "savedata function hash differs from native handoff",
    )
    require(
        set(callback.LOGGER_FUNCTION_HASHES.values()) ==
        {WITNESS["function_sha256"][name] for name in (
            "mLogGetThreadLogger", "mLogGetContext",
            "mLogSetDefaultLogger", "mLog",
        )},
        "logger function hashes differ from native handoff",
    )
    return matrix


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkout", help="exact pinned mGBA checkout")
    source.add_argument("--source-dir", help="individually fetched pinned source tree")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--matrix", default=MATRIX)
    args = parser.parse_args()
    root = Path(args.root)
    matrix_path = Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = root / matrix_path
    matrix = verify(
        args.checkout or args.source_dir, root, matrix_path, bool(args.checkout)
    )
    print("PHASE1_MGBA_FAULT_OBSERVERS paths=%d native_log_witness=%s frontends=%d" % (
        len(matrix["path_objections"]),
        matrix["native_witness"]["native_class"],
        sum(path["id"] in {"qt", "sdl", "libretro", "python", "headless"}
            for path in matrix["path_objections"]),
    ))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify pinned mGBA platform save-error observer dispositions."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-platform-save-observer-closure-20261105.json"
)

SOURCE_FILES = {
    "src/platform/headless-main.c": (
        "61110b1e84a25f702b5e7d158887d93b150e1b66",
        "51687802777b8e831622e28fbd278782084e4c0d65e1ba28b7c1dec4e5617c68",
        "7cd9f22ce4878d5f9cab92adbe4b26a011a3fd6fbce9f21f7e20668be5c16e4e",
        "scoped_headless_logger_and_shutdown_path",
        ((125, "mStandardLoggerConfig(&_logger, &core->config);"),
         (126, "mLogSetDefaultLogger(&_logger.d);"),
         (128, "struct mCoreCallbacks callbacks = {0};"),
         (232, "core->unloadROM(core);"),
         (250, "core->deinit(core);"),
         (262, "return cleanExit ? _exitCode : uncleanExit;")),
    ),
    "src/platform/3ds/main.c": (
        "ac638465d5ffe662be176b70444536019b63e323",
        "a4dd625a15738a730af7232e5e2f7b449a034c65572433c250cebccdc4236c2a",
        "6259457d76fb6b7b0d27f8bd043dac2ee50cab683be91242b6393116bd802410",
        "scoped_shared_gui_runner_integration",
        ((923, "struct mGUIRunner runner = {"),
         (1077, "mGUIInit(&runner, \"3ds\");"),
         (1104, "mGUIRun(&runner, initialPath);"),
         (1109, "mGUIDeinit(&runner);")),
    ),
    "src/platform/3ds/3ds-vfs.c": (
        "88297e9cd1dd76ea005ca3e77243b48332d453a1",
        "92b090e4f221af314cca3848f93a846dc297ac4a064e3395afa4fdbfe3f76b89",
        "9e0d63b3ca620b4e4bda8f3ddf0d317285563844ae66282e7c7cce1ccdcc02ec",
        "scoped_vfile_error_return_path",
        ((92, "FSFILE_Close(vf3d->handle);"),
         (94, "return true;"),
         (129, "Result res = FSFILE_Write(vf3d->handle, &sizeWritten, vf3d->offset, buffer, size, FS_WRITE_FLUSH | FS_WRITE_UPDATE_TIME);"),
         (151, "static void _vf3dUnmap(struct VFile* vf, void* memory, size_t size) {"),
         (154, "FSFILE_Write(vf3d->handle, &sizeWritten, 0, memory, size, FS_WRITE_FLUSH | FS_WRITE_UPDATE_TIME);"),
         (170, "static bool _vf3dSync(struct VFile* vf, void* buffer, size_t size) {"),
         (175, "return R_SUCCEEDED(res);"),
         (177, "FSFILE_Flush(vf3d->handle);"),
         (178, "return true;")),
    ),
    "src/platform/psp2/main.c": (
        "ad07bc9da57a97d4f74cd6da918a420dec490786",
        "102f52f87169d0229e111df12e740de549e23ca07d5391ca4192bb3709dc436d",
        "51137b46ebc80c06a0ab85029146f7753b44124e4ef89aa001517b32b96975b0",
        "scoped_shared_gui_runner_integration",
        ((239, ".gameUnloaded = mPSP2UnloadROM,"),
         (259, "mGUIInit(&runner, \"psvita\");"),
         (288, "mGUIRun(&runner, initialPath);"),
         (294, "mGUIDeinit(&runner);")),
    ),
    "src/platform/psp2/sce-vfs.c": (
        "a98e9943dc23db1592ccbf2b29ea34ffc10c1b73",
        "720c19792d4e770b9114404e9018c05dab27bd7a91faf7f15f77f667fb68ac4c",
        "47a00ee75dd48fc7ba02dd5021141702c55173149aa4ab9891e0494270b56a29",
        "scoped_vfile_error_return_path",
        ((92, "bool _vfsceClose(struct VFile* vf) {"),
         (94, "sceIoSyncByFd(vfsce->fd, 0);"),
         (95, "return sceIoClose(vfsce->fd) >= 0;"),
         (129, "static void _vfsceUnmap(struct VFile* vf, void* memory, size_t size) {"),
         (133, "sceIoWrite(vfsce->fd, memory, size);"),
         (135, "sceIoSyncByFd(vfsce->fd, 0);"),
         (153, "bool _vfsceSync(struct VFile* vf, void* buffer, size_t size) {"),
         (161, "return sceIoSyncByFd(vfsce->fd, 0) >= 0;")),
    ),
    "src/platform/switch/main.c": (
        "ad012f89135a5321c486cfdc7cee4d08e646487e",
        "817c38e1b8f9af252adbec8b34f2ea0057bb61fa9f35c1c91c97e841b7b64bd6",
        "d75e55081585dff480e781ed638962b911e5ba1ad1c32d6d28143592666ed7a2",
        "scoped_shared_gui_runner_integration",
        ((1053, ".gameUnloaded = _gameUnloaded,"),
         (1064, "mGUIInit(&runner, \"switch\");"),
         (1099, "mGUIRun(&runner, argv[1]);"),
         (1104, "mGUIDeinit(&runner);")),
    ),
    "src/platform/wii/main.c": (
        "1003a8d9e578a48ba7dbfdea956e2086e9e1b868",
        "c3c43ed2ee06e606935c98750a67a061e182e197cea27094926a8dfbaede91e1",
        "35ce854e6393f6ef9eb6de2ad27f78df15a1ecae178a9f71c975db89ecb99958",
        "scoped_shared_gui_runner_integration",
        ((601, ".gameUnloaded = _gameUnloaded,"),
         (610, "mGUIInit(&runner, \"wii\");"),
         (664, "mGUIRun(&runner, argv[1]);"),
         (671, "mGUIDeinit(&runner);")),
    ),
    "src/platform/windows/vfs-w32.c": (
        "b160bc5885731600e0f186723af3686dc4e9a8be",
        "3b06ecda404b0593bd06f0992d42ed758094e502246ee6ca78b7c5269c8b26c5",
        "89dd2e7917aa707a311a5a4dc7217e921699aa4eb7c57aa78e3c2830394ec24d",
        "identity_only_vdir_wrapper_not_vfile_backend",
        ((109, "struct VFile* _vdwOpenFile(struct VDir* vd, const char* path, int mode) {"),
         (119, "struct VFile* file = VFileOpen(combined, mode);")),
    ),
    "src/feature/gui/gui-runner.c": (
        "c119e22f7e725234143163bd132fb767a8955ef4",
        "79d53c4a4490a45e6fdf30dd80a3249f697c6f9be6c23ec7cf85cdc9ddd36f67",
        "cb0ea10bf3911810e514062548d5048730e00f16536b86f765a4fabc958e9f2d",
        "scoped_shared_logger_and_shutdown_contract",
        ((212, "void mGUIInit(struct mGUIRunner* runner, const char* port) {"),
         (239, "mCoreConfigGetIntValue(&runner->config, \"logLevel\", &logger.logLevel);"),
         (244, "logger.vf = VFileOpen(path, O_CREAT | O_WRONLY | O_APPEND);"),
         (245, "mLogSetDefaultLogger(&logger.d);"),
         (299, "static void _log(struct mLogger* logger, int category, enum mLogLevel level, const char* format, va_list args) {"),
         (301, "if (!guiLogger->vf) {"),
         (304, "if (!(guiLogger->logLevel & level)) {"),
         (315, "if (guiLogger->vf->write(guiLogger->vf, log2, len) < 0) {"),
         (321, "if (guiLogger->vf->write(guiLogger->vf, log2, len) < 0) {"),
         (326, "#ifdef GEKKO"),
         (327, "puts(log2);"),
         (732, "runner->core->unloadROM(runner->core);"),
         (752, "runner->core->deinit(runner->core);"),
         (758, 'mLOG(GUI_RUNNER, INFO, "Game stopped!");')),
    ),
    "src/feature/gui/gui-runner.h": (
        "9f64ed1c7297ed3bc92deb2734e53c05b26eabde",
        "d2ae4d5136bac430bcbfca1833fc6a9edef6d2d39b4c85def5e90bd41760ab4f",
        "c49c66eecb3683c9e6010b1741d0522356e842ec953f5fad327bdf75ccf9737e",
        "scoped_gui_lifecycle_callback_contract",
        ((86, "void (*gameLoaded)(struct mGUIRunner*);"),
         (87, "void (*gameUnloaded)(struct mGUIRunner*);"),
         (102, "void mGUIRun(struct mGUIRunner*, const char* path);")),
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "scoped_compile_time_vfile_backend_dispatch",
        ((22, "struct VFile* VFileOpen(const char* path, int flags) {"),
         (23, "#ifdef ENABLE_VFS_FILE"),
         (47, "#elif defined(PSP2)"),
         (71, "#elif defined(ENABLE_VFS_3DS)"),
         (99, "#elif defined(ENABLE_VFS_FD)"),
         (101, "#else")),
    ),
}

PATH_DISPOSITIONS = [
    {
        "id": "headless",
        "entry_source": "src/platform/headless-main.c",
        "shared_sources": [],
        "observer_route": "standard_logger_configured_from_core_config_with_logToStdout_default_true",
        "shutdown_route": "core_unload_and_deinit_are_called_without_a_save_persistence_result",
        "classification": "conditional_log_route_no_persistence_acknowledgment",
        "selected_vfile_backend": "unproven_by_this_frontend_source",
    },
    {
        "id": "3ds",
        "entry_source": "src/platform/3ds/main.c",
        "shared_sources": [
            "src/feature/gui/gui-runner.c",
            "src/feature/gui/gui-runner.h",
            "src/util/vfs.c",
            "src/platform/3ds/3ds-vfs.c",
        ],
        "observer_route": "shared_gui_log_file_conditioned_on_logLevel_and_logger_vfile",
        "shutdown_route": "mGUI_runner_calls_unload_and_deinit_without_persistence_status",
        "classification": "conditional_log_and_backend_status_partly_discarded",
        "selected_vfile_backend": "3ds_only_if_ENABLE_VFS_3DS_branch_is_selected",
    },
    {
        "id": "3ds_vfile",
        "entry_source": "src/platform/3ds/3ds-vfs.c",
        "shared_sources": ["src/util/vfs.c"],
        "observer_route": "buffered_sync_returns_fs_result_but_not_short_count; unmap_and_unbuffered_flush_errors_discarded",
        "shutdown_route": "void_unmap_and_always_true_close_provide_no_failure_status",
        "classification": "mixed_sync_return_and_discarded_unmap_close_failures",
        "selected_vfile_backend": "3ds_only_if_ENABLE_VFS_3DS_branch_is_selected",
    },
    {
        "id": "psp2",
        "entry_source": "src/platform/psp2/main.c",
        "shared_sources": [
            "src/feature/gui/gui-runner.c",
            "src/feature/gui/gui-runner.h",
            "src/util/vfs.c",
            "src/platform/psp2/sce-vfs.c",
        ],
        "observer_route": "shared_gui_log_file_conditioned_on_logLevel_and_logger_vfile",
        "shutdown_route": "mGUI_runner_calls_unload_and_deinit_without_persistence_status",
        "classification": "conditional_log_and_backend_status_partly_discarded",
        "selected_vfile_backend": "psp2_only_if_PSP2_branch_is_reached",
    },
    {
        "id": "psp2_vfile",
        "entry_source": "src/platform/psp2/sce-vfs.c",
        "shared_sources": ["src/util/vfs.c"],
        "observer_route": "buffered_sync_requires_exact_pwrite_and_sync; unmap_and_close_discard_sync_result",
        "shutdown_route": "unmap_is_void; close_reports_only_close_result_not_preceding_sync_result",
        "classification": "mixed_sync_return_and_discarded_unmap_close_failures",
        "selected_vfile_backend": "psp2_only_if_PSP2_branch_is_reached",
    },
    {
        "id": "switch",
        "entry_source": "src/platform/switch/main.c",
        "shared_sources": [
            "src/feature/gui/gui-runner.c",
            "src/feature/gui/gui-runner.h",
            "src/util/vfs.c",
        ],
        "observer_route": "shared_gui_log_file_conditioned_on_logLevel_and_logger_vfile",
        "shutdown_route": "mGUI_runner_calls_unload_and_deinit_without_persistence_status",
        "classification": "conditional_log_route_no_persistence_acknowledgment",
        "selected_vfile_backend": "unproven_without_target_build_configuration",
    },
    {
        "id": "wii",
        "entry_source": "src/platform/wii/main.c",
        "shared_sources": [
            "src/feature/gui/gui-runner.c",
            "src/feature/gui/gui-runner.h",
            "src/util/vfs.c",
        ],
        "observer_route": "shared_gui_log_file_conditioned_on_logLevel_and_logger_vfile_plus_GEKKO_stdout",
        "shutdown_route": "mGUI_runner_calls_unload_and_deinit_without_persistence_status",
        "classification": "conditional_log_route_no_persistence_acknowledgment",
        "selected_vfile_backend": "unproven_without_target_build_configuration",
    },
    {
        "id": "windows_vdir",
        "entry_source": "src/platform/windows/vfs-w32.c",
        "shared_sources": ["src/util/vfs.c"],
        "observer_route": "not_a_frontend_logger_or_vfile_backend",
        "shutdown_route": "not_implemented_in_this_vdir_wrapper",
        "classification": "identity_only_wrapper_delegates_file_open_to_vfileopen",
        "selected_vfile_backend": "unproven_by_this_wrapper",
    },
]

SHARED_CONTRACT = {
    "gui_logger": {
        "level_filter": "configured_logLevel_must_include_message_level",
        "missing_vfile": "message_dropped_before_any_sink",
        "write_handling": "negative_write_attempts_reopen_but_second_open_is_not_null_checked; positive_short_write_is_not_detected",
        "wii_stdout": "puts_is_compiled_only_under_GEKKO_and_is_reached_after_gui_logger_vfile_and_level_checks",
        "meaning": "log_delivery_is_not_a_persistence_acknowledgment_or_on_screen_notification",
    },
    "gui_shutdown": {
        "order": ["optional_autosave_state", "core_unloadROM", "core_deinit", "Game_stopped_INFO_log"],
        "result": "mGUIRun_is_void_and_shutdown_does_not_propagate_a_save_persistence_result",
        "callback_distinction": "gameLoaded_and_gameUnloaded_are_lifecycle_callbacks_not_savedataUpdated_persistence_receipts",
    },
    "vfile_dispatch": {
        "source": "src/util/vfs.c",
        "selection": "compile_time_preprocessor_order_selects_VFile_backend",
        "unproven": "actual_target_build_definitions_for_Switch_Wii_and_console_configurations_not_verified_here",
    },
}

LIMITS = {
    "evidence_class": "pinned_source_only",
    "native_platform_runtime_observed": False,
    "real_frontend_log_display_observed": False,
    "real_save_failure_injected_on_platform": False,
    "physical_flash_or_power_loss_evidence": False,
    "semantic_approval": False,
}


def expected_matrix():
    return {
        "schema": "phase1.mgba.platform-save-observer-closure.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob_sha": DOSSIER_BLOB,
            "sha256": DOSSIER_SHA256,
        },
        "reviewed_new_files": [
            {
                "path": path,
                "git_blob_sha": values[0],
                "source_sha256": values[1],
                "dossier_row_sha256": values[2],
                "license": "MPL-2.0",
                "review_scope": values[3],
                "anchors": [
                    {"line": line, "contains": needle}
                    for line, needle in values[4]
                ],
            }
            for path, values in SOURCE_FILES.items()
        ],
        "platform_paths": PATH_DISPOSITIONS,
        "shared_contract": SHARED_CONTRACT,
        "limits": LIMITS,
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(source_root, *args, input_bytes=None):
    return subprocess.check_output(
        ["git", "-C", str(source_root), *args],
        input=input_bytes,
        stderr=subprocess.DEVNULL,
    ).decode().strip()


def validate_matrix_payload(matrix):
    require(matrix == expected_matrix(), "platform observer matrix differs from the pinned contract")
    return True


def verify_sources(source_root, repo_root, matrix_path, checkout_identity=False):
    source_root = Path(source_root)
    repo_root = Path(repo_root)
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    validate_matrix_payload(matrix)
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA checkout revision")

    for path, (blob, source_sha, _, _, anchors) in SOURCE_FILES.items():
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned source tree blob changed: " + path)
        raw = (source_root / path).read_bytes()
        require(subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", "--stdin"], input=raw
        ).decode().strip() == blob, "source Git blob mismatch: " + path)
        require(hashlib.sha256(raw).hexdigest() == source_sha,
                "source full-byte SHA-256 mismatch: " + path)
        normalized = " ".join(raw.decode("utf-8").split())
        require("Mozilla Public" in normalized and "License, v. 2.0." in normalized,
                "missing MPL-2.0 notice: " + path)
        lines = raw.decode("utf-8").splitlines()
        for line_number, needle in anchors:
            require(line_number <= len(lines) and needle in lines[line_number - 1],
                    "source anchor changed: %s:%d" % (path, line_number))

    dossier_path = repo_root / DOSSIER
    raw_dossier = dossier_path.read_bytes()
    require(git(repo_root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned machine dossier Git blob changed")
    require(hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "pinned machine dossier full-byte SHA-256 changed")
    dossier_rows = {}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    path not in SOURCE_FILES):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(
                hashlib.sha256(canonical).hexdigest() == SOURCE_FILES[path][2] and
                provenance.get("git_blob_sha") == SOURCE_FILES[path][0] and
                provenance.get("source_content_sha256") == SOURCE_FILES[path][1],
                "pinned dossier row identity changed: " + path,
            )
            require(path not in dossier_rows, "duplicate pinned dossier row: " + path)
            dossier_rows[path] = True
    require(set(dossier_rows) == set(SOURCE_FILES),
            "pinned dossier does not cover every newly reviewed source")
    return matrix


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkout", help="exact pinned mGBA checkout")
    source.add_argument(
        "--source-dir",
        help="directory with individually fetched files; does not attest tree identity",
    )
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--matrix", default=MATRIX)
    args = parser.parse_args()
    repo_root = Path(args.root)
    matrix_path = Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = repo_root / matrix_path
    result = verify_sources(
        args.checkout or args.source_dir, repo_root, matrix_path, bool(args.checkout)
    )
    print("PHASE1_MGBA_PLATFORM_OBSERVERS files=%d paths=%d evidence=%s" % (
        len(result["reviewed_new_files"]), len(result["platform_paths"]),
        result["limits"]["evidence_class"],
    ))


if __name__ == "__main__":
    main()

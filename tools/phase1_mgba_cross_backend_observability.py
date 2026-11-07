#!/usr/bin/env python3
"""Verify pinned mGBA cross-backend save-error observer evidence."""
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
    "mgba-cross-backend-save-observability-20261105.json"
)
LICENSE_IDENTITY = (
    "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
    "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85",
    "b23d241b38f5808b3714b8f4f5d255db9a47e3ab9b114972bcc7e042bc92acf0",
)

FILES = {
    "src/core/core.c": (
        "17edcde68b8d4f0885c6c6ddd17c4e6ca64701f8",
        "94b5dc1cec2d9b157ef2933681c644a6dfb43dcebe9f6b887d68b104ac640ea5",
        "6e453bae6a2dd590ac92ce6f86821a8e342dcc34f9f762836152bdad9b49e989",
    ),
    "include/mgba/core/interface.h": (
        "b5ffa3049749b9141aa09fc3693bf758a13f4e13",
        "da6ea4e344c46be5943859a24c0149c12a803b3e951c07140cc795cab09651de",
        "093b18935d1a1968f5ce81caa23611a578cc8810a03bde39f3e3f55d0d6b2830",
    ),
    "include/mgba/core/thread.h": (
        "7164f6409cc9aec8df893df64d495a6f38b9c3f7",
        "c055b87b8e2bd1b255641cef4a1bc9f1d06125d785395b47a4c8ecfb9c9857d7",
        "2965deaa47903417eecf6eb10d041692b38d3561f156ff6576ebb4209b35756d",
    ),
    "src/platform/qt/CoreController.h": (
        "3b7d8bafb7202b66e326221890e2c68655d1be72",
        "3618b5e08c89274b89fa03683840ac79c8aeadc9e7f8ab87a20c65ac58a215a4",
        "2276f54d6a154f7e2ac2973b5f7ffe229e776caaf94aca15cf2ff49d814596e0",
    ),
    "src/platform/qt/CoreManager.cpp": (
        "459846c61103b77645a4170ebd784599cb4cbe79",
        "1961c67b62916f301b76620a01a30479d79fe2c807d47990753914a8cef3d753",
        "6e8985a122d48aa5ddd00854c325bd87bb16ff30f49425a4500a8b09fb45edcc",
    ),
    "src/platform/qt/LogController.cpp": (
        "526cdb9a4054698a0047379613c63fa64efad47d",
        "cb9e77b62ae0752495badb6942f3aec846b2fc0b1db6c33be96a8235d4d16299",
        "96796da1768502b3567e311199957f5890452d635f1d4e0bc6d0ff27391ea100",
    ),
    "src/platform/qt/main.cpp": (
        "d0ea3cb178dd2eb70d8ebbd7308a469d3eded1a2",
        "a4244173f58fcd1c8f7b72356bacf0b2a70055adcdc4b8fed08e850d415a89fd",
        "063560feab649a1d40893ea1e0c1378c2c2ce67d22fcbb7a528c45573f5ac581",
    ),
    "src/platform/libretro/libretro.h": (
        "2f174837012e7bec32868a2fcf49fe425f1a83a9",
        "7e61792e17843954a71bf52b2e88c571baa07436519fa708ed487785a109ceb8",
        "3015f7cef9977a6df63538db43bc1c6cfbbd33ed5a71945829f1e456e4f02778",
    ),
    "src/platform/python/_builder.py": (
        "f18a3c95e39d5f52c3f442d5f6ce09cf160a5b7f",
        "c453544bda4b1839bb830c945ba36ff1604a9c937d1648d4a03255f60b36fbb2",
        "994dbf44d938851d6e5952ba994da9beceb7eea2de7cd5284b7056cd4806c8e0",
    ),
    "src/platform/python/core.c": (
        "6d7c1c855a713508d7548737f9337e5e7e9d2afb",
        "f16f45c8435db5d17d452144cc2d30f25b228bf6cb961dc7e18b4c30eebbf971",
        "96ffdc818f85bd5889eded1052250c2838329261e03db942cc7ca410b550f331",
    ),
    "src/platform/python/core.h": (
        "5e6f23be0f9146bc1f250d7d7085281e21dfed33",
        "493805da23f4d40ae858ed0eeec7b41d7226965ac59834bd937d8febd4a2f34d",
        "e28581e12e1d809f394e38ee895bcff4b162716a903d1098f3071c39ebcf8f82",
    ),
    "src/platform/python/mgba/core.py": (
        "22965b3f9c75c03b9156457aee73d89f3f202d10",
        "3813a0c572cacbd76d1bc39596044dbd6c09479b338897a6d854dfb855a2aa43",
        "e3b17a509aa350fc5c90bb330d897d0ba4b8254f53990da25afed8e0b4f0e4bc",
    ),
    "src/core/log.c": (
        "39d6db88cad3ca6f521a532c114b6488adb77279",
        "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
        "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
    ),
    "src/platform/python/log.c": (
        "ed3d3f35bc5c979cdf749ea2c746788e7efc9d6a",
        "f14f5048c48db01e6289a0ccc1823c7055160aac569dfb12faefbe6ae962a0ad",
        "25ac6434b72711e09e24af95dffe5d06bb46452e9e1be0300ad25d4b3c690121",
    ),
    "src/platform/python/mgba/log.py": (
        "fb2e73cc833ec5ecd7a3f5b3a5d1330a86a6f1b2",
        "0887ca618f5702c8e8948bf7f3ab8d8ce132a57dbfc40f50202917b0e4b9ad07",
        "747793fe1c07a5902f51de0302aa38e28a1de630e17a05982f5e7328364319da",
    ),
    "src/platform/qt/LogView.cpp": (
        "c34e79e354c7bb50c52fc6ef4be8b14f41aa2496",
        "c433122251bc31b8153e6988ddbe7baf7a7617ab55077af1f4ae605831c622c5",
        "ef66505b6849722f60b5507ab8313079db835045169b041bc0a4a50d43530b9e",
    ),
}

ANCHORS = {
    "src/core/core.c": ((135, "core->unloadROM(core);"), (257, "bool mCoreAutoloadSave")),
    "include/mgba/core/interface.h": ((49, "shutdown"), (51, "savedataUpdated")),
    "include/mgba/core/thread.h": ((107, "void mCoreThreadEnd"),),
    "src/platform/qt/CoreController.h": ((228, "void stopping();"), (230, "void failed();")),
    "src/platform/qt/CoreManager.cpp": (
        (155, "Failed to open save file; in-game saves cannot be updated."),
        (159, "core->deinit(core);"),
    ),
    "src/platform/qt/LogController.cpp": (
        (62, '"logPosted"'),
        (120, "level == mLOG_ERROR"),
        (125, "emit logPosted"),
    ),
    "src/platform/qt/main.cpp": ((146, "int ret = application.exec();"), (147, "if (ret != 0)")),
    "src/platform/libretro/libretro.h": (
        (3877, "retro_unload_game(void);"),
        (3883, "retro_get_memory_data(unsigned id);"),
    ),
    "src/platform/python/_builder.py": ((65, "ffi.cdef"),),
    "src/platform/python/core.c": (
        (10, "mCorePythonCallbackCreate"),
        (13, "callbacks->videoFrameEnded"),
        (14, "callbacks->coreCrashed"),
    ),
    "src/platform/python/core.h": ((10, "mCorePythonCallbackCreate"),),
    "src/platform/python/mgba/core.py": (
        (88, "class CoreCallbacks"),
        (93, "self.core_crashed = []"),
        (131, "self._core.addCoreCallbacks"),
        (161, "core = ffi.gc(native, native.deinit)"),
    ),
    "src/core/log.c": (
        (73, "void mLogSetDefaultLogger"),
        (114, "void mLog("),
        (234, "void _mCoreStandardLog"),
        (257, "if (stdlog->logToStdout)"),
    ),
    "src/platform/python/log.c": (
        (8, "static void _pyLogShim"),
        (15, "struct mLogger* mLoggerPythonCreate"),
    ),
    "src/platform/python/mgba/log.py": (
        (12, "def install_default(logger):"),
        (42, "lib.mLogSetDefaultLogger(logger._native)"),
        (44, "def log(self, category, level, message):"),
    ),
    "src/platform/qt/LogView.cpp": (
        (51, "connect(log, &LogController::logPosted"),
        (67, "void LogView::postLog"),
    ),
}

LICENSES = {
    path: (
        "MIT" if path == "src/platform/libretro/libretro.h" else
        "MPL-2.0 via root LICENSE; no embedded notice"
        if path == "src/platform/python/_builder.py" else
        "MPL-2.0"
    )
    for path in FILES
}

REUSED_SOURCES = (
    (
        "include/mgba-util/vfs.h",
        "docs/phase1-review-readiness/mgba-vfs-fd-teardown-errors-20261104.md",
    ),
    (
        "src/util/vfs/vfs-fd.c",
        "docs/phase1-review-readiness/mgba-vfs-fd-teardown-errors-20261104.md",
    ),
    (
        "src/util/vfs/vfs-file.c",
        "docs/phase1-review-readiness/mgba-vfs-stdio-save-teardown-20261104.md",
    ),
    (
        "src/gba/savedata.c",
        "docs/phase1-review-readiness/mgba-vfs-fd-teardown-errors-20261104.md",
    ),
    (
        "src/gba/gba.c",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/gba/core.c",
        "docs/phase1-review-readiness/mgba-vfs-fd-teardown-errors-20261104.md",
    ),
    (
        "src/core/scripting.c",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/script/stdlib.c",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/platform/qt/CoreController.cpp",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/platform/qt/Window.cpp",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/platform/sdl/main.c",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
    (
        "src/platform/libretro/libretro.c",
        "docs/phase1-review-readiness/mgba-gba-savedata-callback-failure-20261102.md",
    ),
)

UNREVIEWED_IDENTIFIED = (
    "src/platform/headless-main.c",
    "src/platform/3ds/main.c",
    "src/platform/3ds/3ds-vfs.c",
    "src/platform/psp2/main.c",
    "src/platform/psp2/sce-vfs.c",
    "src/platform/switch/main.c",
    "src/platform/wii/main.c",
    "src/platform/windows/vfs-w32.c",
)

EDGE_CONTRACTS = {
    "fd_sync_to_savedata_clean": ("discarded", "prior_native_failure", "false", "none", True),
    "stdio_sync_to_savedata_clean": ("discarded", "prior_native_failure", "false", "none", True),
    "fd_unmap_close_to_core_shutdown": ("discarded", "prior_native_failure", "failure", "none", True),
    "stdio_unmap_close_to_core_shutdown": ("discarded", "prior_native_failure", "failure", "none", True),
    "dirty_to_clean_script_event": (
        "propagated", "prior_native_failure", "one_event", "save_data_changed_not_persistence_ack", True
    ),
    "core_shutdown_return_channel": ("discarded", "source_review_only", "void", "none", False),
    "qt_host_shutdown": ("discarded", "source_review_only", "void", "none", False),
    "sdl_host_shutdown": ("discarded", "source_review_only", "void", "none", False),
    "libretro_host_shutdown": ("discarded", "source_review_only", "void", "memory_api_only", False),
    "python_host_shutdown": ("discarded", "source_review_only", "void", "none", False),
    "qt_sync_warning_log": (
        "conditional", "source_review_only", "info_message",
        "qt_logPosted_if_info_enabled", False
    ),
    "sdl_sync_warning_log": (
        "conditional", "source_review_only", "info_message",
        "conditional_stdout_or_file", False
    ),
    "libretro_sync_warning_log": (
        "conditional", "source_review_only", "info_message",
        "conditional_RETRO_LOG_INFO_callback", False
    ),
    "python_sync_warning_log": (
        "conditional", "source_review_only", "info_message",
        "optional_python_logger", False
    ),
    "other_platforms": ("unproven", "not_executed", "unknown", "unknown", False),
}

FAILURE_CONTROLS = {
    "fd_async_sync_eio": ("false", "discarded", "none", "failure async_ms=1 fsync=2 rtc=0 dirty=0 retried=0 fsync_error=1"),
    "fd_unmap_sync_eio": ("failure", "discarded", "none", "sync_failure"),
    "fd_close_eio": ("failure", "discarded", "none", "close_failure"),
    "stdio_flush_eio": ("false", "discarded", "none", "injected_flush"),
    "stdio_unmap_short_write": ("partial", "discarded", "none", "mapped_short_unmap"),
    "stdio_close_eio": ("failure", "discarded", "none", "unload_close_error"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def validate_matrix_payload(matrix):
    require(matrix.get("schema") == "phase1.mgba.cross-backend-save-observability.v1",
            "wrong matrix schema")
    require(matrix.get("repository") == "mgba-emu/mgba" and
            matrix.get("pinned_revision") == PIN,
            "wrong repository or pinned revision")
    dossier = matrix.get("machine_dossier", {})
    require(dossier == {
        "path": DOSSIER,
        "git_blob_sha": DOSSIER_BLOB,
        "sha256": DOSSIER_SHA256,
    }, "wrong or stale machine dossier identity")
    require(matrix.get("license_artifact") == {
        "path": "LICENSE",
        "git_blob_sha": LICENSE_IDENTITY[0],
        "sha256": LICENSE_IDENTITY[1],
        "dossier_row_sha256": LICENSE_IDENTITY[2],
        "license": "MPL-2.0",
    }, "wrong repository-level license identity")

    files = matrix.get("reviewed_new_files")
    require(isinstance(files, list) and len(files) == 16,
            "new-source review must contain exactly 16 files")
    by_path = {}
    for item in files:
        path = item.get("path")
        require(path in FILES and path not in by_path,
                "unknown or duplicate new source file")
        blob, source_sha, row_sha = FILES[path]
        require(item == {
            "path": path,
            "git_blob_sha": blob,
            "source_sha256": source_sha,
            "dossier_row_sha256": row_sha,
            "license": LICENSES[path],
            "review_disposition": "reviewed_source_only",
            "anchors": [
                {"line": line, "contains": needle}
                for line, needle in ANCHORS[path]
            ],
        }, "source pin, license, disposition, or anchor mismatch: " + str(path))
        by_path[path] = item
    require(set(by_path) == set(FILES), "new source inventory is incomplete")

    reused = matrix.get("reused_prior_sources")
    require(isinstance(reused, list), "missing reused-source inventory")
    expected_reused = [
        {"path": path, "evidence_workpaper": workpaper, "status": "prior_pin_reused"}
        for path, workpaper in REUSED_SOURCES
    ]
    require(reused == expected_reused, "reused prior source scope changed")
    require(matrix.get("identified_but_unreviewed") == list(UNREVIEWED_IDENTIFIED),
            "identified-but-unreviewed platform paths changed")

    edges = matrix.get("edges")
    require(isinstance(edges, list) and len(edges) == len(EDGE_CONTRACTS),
            "edge inventory is incomplete")
    seen = set()
    for edge in edges:
        edge_id = edge.get("id")
        require(edge_id in EDGE_CONTRACTS and edge_id not in seen,
                "unknown or duplicate observer edge")
        classification, execution, failure_result, host_status, injected = (
            EDGE_CONTRACTS[edge_id]
        )
        require(edge.get("classification") == classification,
                "invented propagation classification: " + edge_id)
        require(edge.get("execution") == execution,
                "incorrect execution disposition: " + edge_id)
        require(edge.get("failure_result") == failure_result,
                "contradictory failure result: " + edge_id)
        require(edge.get("host_status") == host_status,
                "invented host-facing status: " + edge_id)
        require(edge.get("injected_failure") is injected,
                "failure injection disposition mismatch: " + edge_id)
        require(edge.get("persistence_success_claim") is False,
                "failure evidence cannot claim persistence success: " + edge_id)
        refs = edge.get("source_refs")
        require(isinstance(refs, list) and refs and
                all(ref in FILES or ref in {p for p, _ in REUSED_SOURCES}
                    for ref in refs),
                "edge cites an unpinned source: " + edge_id)
        if classification == "propagated":
            require(edge_id == "dirty_to_clean_script_event",
                    "unexpected propagated observer edge")
            require(host_status == "save_data_changed_not_persistence_ack",
                    "save-data callback cannot acknowledge persistence")
        if classification == "conditional":
            require(edge_id in {
                        "qt_sync_warning_log",
                        "sdl_sync_warning_log",
                        "libretro_sync_warning_log",
                        "python_sync_warning_log",
                    } and execution == "source_review_only" and not injected,
                    "conditional logger route cannot claim runtime observation")
        if execution == "not_executed":
            require(classification in ("not_executed", "unproven"),
                    "unexecuted path cannot claim observed propagation")
        seen.add(edge_id)
    require(seen == set(EDGE_CONTRACTS), "observer edge coverage is incomplete")

    controls = matrix.get("injected_failure_controls")
    require(isinstance(controls, list) and len(controls) == len(FAILURE_CONTROLS),
            "failure-control matrix is incomplete")
    control_ids = set()
    for control in controls:
        control_id = control.get("id")
        require(control_id in FAILURE_CONTROLS and control_id not in control_ids,
                "unknown or duplicate injected-failure control")
        backend_result, caller_result, host_status, evidence_case = (
            FAILURE_CONTROLS[control_id]
        )
        require(control == {
            "id": control_id,
            "injected": True,
            "backend_result": backend_result,
            "caller_result": caller_result,
            "host_status": host_status,
            "persistence_success_claim": False,
            "execution": "prior_native_witness",
            "evidence_case": evidence_case,
        }, "false success or altered failure control: " + control_id)
        control_ids.add(control_id)
    require(control_ids == set(FAILURE_CONTROLS),
            "injected-failure controls are incomplete")

    require(matrix.get("claims") == {
        "core_shutdown_error_returned": False,
        "frontend_persistence_error_status_returned": False,
        "sync_failure_info_log_in_source": True,
        "savedata_updated_means_persistence_succeeded": False,
        "physical_flash_or_power_loss_evidence": False,
    }, "unsupported observable-status or durability claim")
    return True


def verify_sources(source_root, repo_root, matrix_path, checkout_identity=False):
    source_root = Path(source_root)
    repo_root = Path(repo_root)
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA checkout revision")

    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    validate_matrix_payload(matrix)
    for _, workpaper in REUSED_SOURCES:
        require((repo_root / workpaper).is_file(),
                "missing reused-source evidence workpaper: " + workpaper)

    for path, (blob, source_sha, _) in FILES.items():
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned source tree blob changed: " + path)
        raw = (source_root / path).read_bytes()
        require(subprocess.check_output(
            ["git", "hash-object", "--stdin"], input=raw
        ).decode().strip() == blob, "source Git blob mismatch: " + path)
        require(hashlib.sha256(raw).hexdigest() == source_sha,
                "source full-byte SHA-256 mismatch: " + path)
        normalized = " ".join(raw.decode("utf-8").split())
        if LICENSES[path] == "MPL-2.0":
            require("Mozilla Public" in normalized and "License, v. 2.0." in normalized,
                    "missing MPL-2.0 notice: " + path)
        elif LICENSES[path] == "MPL-2.0 via root LICENSE; no embedded notice":
            require(path == "src/platform/python/_builder.py",
                    "unexpected source without its own MPL notice")
        else:
            require("Permission is hereby granted, free of charge" in normalized and
                    "The RetroArch team" in normalized,
                    "missing pinned libretro header MIT notice")
        lines = raw.decode("utf-8").splitlines()
        for line_number, needle in ANCHORS[path]:
            require(line_number <= len(lines) and needle in lines[line_number - 1],
                    "source anchor changed: %s:%d" % (path, line_number))

    license_path = source_root / "LICENSE"
    license_bytes = license_path.read_bytes()
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD:LICENSE") == LICENSE_IDENTITY[0],
                "pinned repository LICENSE blob changed")
    else:
        require(subprocess.check_output(
            ["git", "-C", str(repo_root), "hash-object", "--stdin"],
            input=license_bytes,
        ).decode().strip() == LICENSE_IDENTITY[0],
                "pinned repository LICENSE blob changed")
    require(hashlib.sha256(license_bytes).hexdigest() == LICENSE_IDENTITY[1] and
            license_bytes.startswith(b"Mozilla Public License Version 2.0"),
            "pinned repository LICENSE bytes changed")

    dossier_path = repo_root / DOSSIER
    raw_dossier = dossier_path.read_bytes()
    require(git(repo_root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "machine dossier Git blob changed")
    require(hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "machine dossier full-byte SHA-256 changed")
    rows = {}
    license_row_seen = False
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            if path == "LICENSE":
                require(hashlib.sha256(canonical).hexdigest() == LICENSE_IDENTITY[2] and
                        provenance.get("git_blob_sha") == LICENSE_IDENTITY[0] and
                        provenance.get("source_content_sha256") is None,
                        "repository LICENSE dossier row changed")
                require(not license_row_seen, "duplicate repository LICENSE dossier row")
                license_row_seen = True
                continue
            if path not in FILES:
                continue
            require(hashlib.sha256(canonical).hexdigest() == FILES[path][2],
                    "canonical dossier row changed: " + path)
            require(provenance.get("git_blob_sha") == FILES[path][0] and
                    provenance.get("source_content_sha256") == FILES[path][1],
                    "dossier source identity changed: " + path)
            require(path not in rows, "duplicate canonical dossier row: " + path)
            rows[path] = True
    require(set(rows) == set(FILES),
            "machine dossier does not cover all 16 newly reviewed files")
    require(license_row_seen, "machine dossier does not cover repository LICENSE")
    return matrix


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkout", help="exact pinned mGBA checkout")
    source.add_argument(
        "--source-dir",
        help="directory with individually fetched pinned files; does not attest tree identity",
    )
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--matrix", default=MATRIX)
    args = parser.parse_args()
    repo_root = Path(args.root)
    matrix_path = Path(args.matrix)
    if not matrix_path.is_absolute():
        matrix_path = repo_root / matrix_path
    source_root = args.checkout or args.source_dir
    result = verify_sources(
        source_root, repo_root, matrix_path, bool(args.checkout)
    )
    print("PHASE1_MGBA_CROSS_BACKEND reviewed_new_files=%d edges=%d injected_controls=%d" % (
        len(result["reviewed_new_files"]), len(result["edges"]),
        len(result["injected_failure_controls"])
    ))


if __name__ == "__main__":
    main()

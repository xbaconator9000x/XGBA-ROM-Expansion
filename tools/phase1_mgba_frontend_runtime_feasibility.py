#!/usr/bin/env python3
"""Verify pinned-source provenance and fail-closed frontend runtime status."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-frontend-runtime-feasibility-20261106.json"
)

SOURCES = {
    "src/platform/headless-main.c": (
        "61110b1e84a25f702b5e7d158887d93b150e1b66",
        "51687802777b8e831622e28fbd278782084e4c0d65e1ba28b7c1dec4e5617c68",
        "7cd9f22ce4878d5f9cab92adbe4b26a011a3fd6fbce9f21f7e20668be5c16e4e",
        "reviewed_for_runtime_feasibility",
        "Headless shutdown calls unloadROM and deinit; no save autoload call is present.",
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
        "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
        "reviewed_for_runtime_feasibility",
        "Core loadSave delegates to GBALoadSave; temporary save returns a placeholder true.",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
        "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
        "reviewed_for_runtime_feasibility",
        "Savedata initializes without a VFile; teardown and dirty-clear callback are distinct paths.",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
        "reused_identity_only",
        "Previously source-reviewed; exact identity reused, not reassigned as a new review.",
    ),
    "src/core/core.c": (
        "17edcde68b8d4f0885c6c6ddd17c4e6ca64701f8",
        "94b5dc1cec2d9b157ef2933681c644a6dfb43dcebe9f6b887d68b104ac640ea5",
        "6e453bae6a2dd590ac92ce6f86821a8e342dcc34f9f762836152bdad9b49e989",
        "reviewed_for_runtime_feasibility",
        "File-based save helpers and autoload entry point inspected; headless caller not found.",
    ),
    "src/core/log.c": (
        "39d6db88cad3ca6f521a532c114b6488adb77279",
        "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
        "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
        "reused_identity_only",
        "Previously source-reviewed logger dispatch dependency; no new runtime claim.",
    ),
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
        "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
        "reused_identity_only",
        "Previously source-reviewed POSIX VFile dependency; no new fault injection.",
    ),
    "src/core/directories.c": (
        "2337f5d47c8db428c62da13afa2743afa6d83f1e",
        "a878d5eada8bf7443061d571f6cdd998d1f19934381278cca415275dc245d0f4",
        "d589bb948b805041abe73209873e21525b69ef9fc92e6e3a501cacc4e83658dd",
        "reused_identity_only",
        "Directory/open-suffix dependency identity only; not a new whole-file review.",
    ),
    "src/platform/qt/CoreController.cpp": (
        "183cea418a70963bd5332ef66bdff54a0dcccd46",
        "8ca7ca7b26fa030ef76322085a6f634b5e3ca4fd40a4e6549b6a12abace260b2",
        "1cbedd6e36f387b7c579bcea8c77bed82e9c3e8b18954974847c647dcf8b0f28",
        "reviewed_for_runtime_feasibility",
        "Qt save-open/load and core deinit paths inspected; frontend did not build.",
    ),
    "src/platform/qt/LogController.cpp": (
        "526cdb9a4054698a0047379613c63fa64efad47d",
        "cb9e77b62ae0752495badb6942f3aec846b2fc0b1db6c33be96a8235d4d16299",
        "96796da1768502b3567e311199957f5890452d635f1d4e0bc6d0ff27391ea100",
        "reviewed_for_runtime_feasibility",
        "Qt filter and conditional stdout/file sinks inspected; no frontend delivery observed.",
    ),
}

ANCHORS = {
    "src/platform/headless-main.c": {
        232: "core->unloadROM(core);",
        250: "core->deinit(core);",
    },
    "src/gba/core.c": {
        656: "return GBALoadSave(core->board, vf);",
        661: "GBASavedataMask(&gba->memory.savedata, vf, false);",
    },
    "src/gba/gba.c": {
        87: "GBASavedataInit(&gba->memory.savedata, NULL);",
        172: "GBASavedataDeinit(&gba->memory.savedata);",
        174: "gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);",
        969: "GBASavedataClean(&gba->memory.savedata, gba->video.frameCounter);",
        1005: "if (callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty) {",
    },
    "src/core/core.c": {
        245: "struct VFile* vf = VFileOpen(path, O_CREAT | O_RDWR);",
        257: "bool mCoreAutoloadSave(struct mCore* core) {",
    },
    "src/platform/qt/CoreController.cpp": {
        235: "m_threadContext.core->deinit(m_threadContext.core);",
        1289: "VFile* save = mDirectorySetOpenSuffix(",
        1291: "if (!m_threadContext.core->loadSave(m_threadContext.core, save)) {",
    },
    "src/platform/qt/LogController.cpp": {
        106: "if (!mLogFilterTest(&m_filter, category, static_cast<mLogLevel>(level))) {",
        109: "if (m_logToStdout || m_logToFile) {",
        125: "emit logPosted(level, category, string);",
    },
}


def expected_matrix():
    return {
        "schema": "phase1.mgba.frontend-runtime-feasibility.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "source_records": [
            {
                "path": path,
                "git_blob": values[0],
                "full_source_sha256": values[1],
                "canonical_dossier_row_sha256": values[2],
                "license": "MPL-2.0",
                "review_scope": values[3],
                "finding": values[4],
                "anchors": [
                    {"line": line, "contains": needle}
                    for line, needle in ANCHORS.get(path, {}).items()
                ],
            }
            for path, values in SOURCES.items()
        ],
        "source_observations": [
            {
                "path": "headless_savedata_lifecycle",
                "status": "SOURCE_ONLY",
                "finding": (
                    "headless-main.c calls unloadROM and deinit, but does not call "
                    "mCoreAutoloadSave or mCoreLoadSaveFile; GBA initialization "
                    "starts savedata with a NULL VFile"
                ),
                "fault_injection_observed": False,
                "cold_process_sav_reopen_observed": False,
            },
            {
                "path": "qt_save_and_log_consumers",
                "status": "SOURCE_ONLY",
                "finding": (
                    "Qt opens a configured save suffix and closes it when loadSave "
                    "fails; its INFO log route depends on filtering and configured "
                    "stdout/file sinks"
                ),
                "fault_injection_observed": False,
                "frontend_ui_or_log_delivery_observed": False,
                "cold_process_sav_reopen_observed": False,
            },
            {
                "path": "savedata_callback_and_teardown",
                "status": "SOURCE_ONLY",
                "finding": (
                    "savedataUpdated follows dirty-to-clean transition; it is not "
                    "a persistence acknowledgment, and teardown return values are "
                    "not surfaced as a save-success result"
                ),
                "fault_injection_observed": False,
                "durable_persistence_observed": False,
            },
        ],
        "runtime_attempts": {
            "headless": {
                "build": "SUCCEEDED",
                "execution": "TIMED_OUT_BEFORE_SAVE_LIFECYCLE",
                "observation": (
                    "Synthetic BIOS/ROM repeatedly logged GBA BIOS SWI 00; the "
                    "intended save and shutdown path was not reached."
                ),
                "native_frontend_process_launched": True,
                "save_failure_or_shutdown_observed": False,
                "fault_injection": False,
                "save_file_reopen": False,
            },
            "qt": {
                "build": "FAILED",
                "attempts": [
                    {
                        "configuration": "BUILD_GL=OFF",
                        "failure": "ShaderSelector undeclared during compilation",
                    },
                    {
                        "configuration": "BUILD_GL=ON",
                        "failure": (
                            "link failed with unresolved ShaderSelector Qt "
                            "meta-object/vtable symbols"
                        ),
                    },
                ],
                "frontend_executable_produced": False,
                "native_frontend_execution": False,
                "fault_injection": False,
                "save_file_reopen": False,
            },
            "sdl": {
                "build": "NOT_ATTEMPTED",
                "execution": "NOT_ATTEMPTED",
                "native_frontend_execution": False,
                "fault_injection": False,
                "save_file_reopen": False,
            },
        },
        "execution_contract": {
            "pinned_source_and_dossier_verified": True,
            "headless_executable_compiled": True,
            "headless_process_launched": True,
            "headless_save_lifecycle_observed": False,
            "qt_frontend_compiled": False,
            "qt_frontend_executed": False,
            "sdl_frontend_executed": False,
            "actual_frontend_fault_injection": False,
            "frontend_save_failure_or_log_delivery_observed": False,
            "cold_process_sav_reopen_observed": False,
            "dirty_to_clean_is_persistence_acknowledgment": False,
            "durable_persistence_or_power_loss_evidence": False,
            "stock_gameplay": False,
            "physical_flash": False,
            "independent_semantic_approval": False,
            "gate_or_approval_state_changed": False,
        },
        "unresolved": [
            "Build and run a pinned frontend on a supported Qt or SDL environment.",
            "Inject a real frontend save I/O/sync failure and observe its UI, logs, callbacks, and return status.",
            "Exercise shutdown/unmap/close behavior and cold-process reopen of an actual .sav.",
            "Distinguish successful host writes from durable storage and physical Flash behavior.",
        ],
        "distribution_notice": (
            "Pinned mGBA source files carry MPL-2.0 notices. Preserve those notices "
            "and the repository license in combined distributions; this report "
            "contains provenance and findings, not copied upstream source."
        ),
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *args):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args],
        stderr=subprocess.DEVNULL,
    ).decode().strip()


def validate_matrix_payload(matrix):
    require(matrix == expected_matrix(),
            "runtime-feasibility matrix differs from the fail-closed contract")
    require(matrix["status"] == "NEEDS_EVIDENCE" and
            matrix["overall"] == "FAIL_INCOMPLETE",
            "unobserved frontend behavior cannot be marked complete")
    return True


def _dossier_rows(root):
    rows = {}
    with gzip.open(root / DOSSIER, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    path not in SOURCES):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(path not in rows, "duplicate pinned dossier row: " + path)
            rows[path] = (
                hashlib.sha256(canonical).hexdigest(),
                provenance.get("git_blob_sha"),
                provenance.get("source_content_sha256"),
            )
    return rows


def verify_checkout(checkout, root):
    checkout = Path(checkout)
    root = Path(root)
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "checkout is not the exact pinned mGBA revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "pinned mGBA source tree identity changed")
    raw_dossier = (root / DOSSIER).read_bytes()
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB and
            hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "compressed source dossier identity changed")
    rows = _dossier_rows(root)
    require(set(rows) == set(SOURCES),
            "pinned dossier does not contain every selected source row")
    for path, values in SOURCES.items():
        blob, source_hash, row_hash = values[:3]
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned Git blob mismatch: " + path)
        raw = (checkout / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == source_hash,
                "pinned full-source SHA-256 mismatch: " + path)
        require(rows[path] == (row_hash, blob, source_hash),
                "pinned dossier row/source identity mismatch: " + path)
        text = raw.decode("utf-8")
        require("Mozilla Public" in text and "License, v. 2.0." in text,
                "source MPL-2.0 notice missing: " + path)
        for line, needle in ANCHORS.get(path, {}).items():
            lines = text.splitlines()
            require(line <= len(lines) and needle in lines[line - 1],
                    "pinned source anchor mismatch: %s:%d" % (path, line))
    headless = (checkout / "src/platform/headless-main.c").read_text(
        encoding="utf-8"
    )
    require("mCoreAutoloadSave(" not in headless and
            "mCoreLoadSaveFile(" not in headless,
            "headless save-load caller presence contradicts the recorded finding")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, help="exact pinned mGBA checkout")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root)
    matrix_path = root / MATRIX
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    validate_matrix_payload(matrix)
    verify_checkout(args.checkout, root)
    print(
        "PHASE1_MGBA_FRONTEND_RUNTIME_FEASIBILITY "
        + json.dumps({
            "pinned_revision": PIN,
            "reviewed_sources": sum(
                value[3] == "reviewed_for_runtime_feasibility"
                for value in SOURCES.values()
            ),
            "reused_identity_only": sum(
                value[3] == "reused_identity_only"
                for value in SOURCES.values()
            ),
            "headless_process_launched": True,
            "frontend_save_failure_runtime_observed": False,
            "status": "NEEDS_EVIDENCE",
            "overall": "FAIL_INCOMPLETE",
        }, sort_keys=True)
    )


if __name__ == "__main__":
    main()

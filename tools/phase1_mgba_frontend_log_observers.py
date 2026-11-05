#!/usr/bin/env python3
"""Compile pinned mGBA save-failure logging into bounded host sink witnesses."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-frontend-log-observers-20261105.json"
)
HARNESS = "tests/phase1_mgba_frontend_log_observers.c"
SOURCES = {
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
    ),
    "include/mgba/internal/defines.h": (
        "67b8ec8fd2f51ee2c0c6231443af752158397b03",
        "167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b",
        "05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2",
    ),
    "src/core/log.c": (
        "39d6db88cad3ca6f521a532c114b6488adb77279",
        "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
        "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
    ),
    "src/feature/gui/gui-runner.c": (
        "c119e22f7e725234143163bd132fb767a8955ef4",
        "79d53c4a4490a45e6fdf30dd80a3249f697c6f9be6c23ec7cf85cdc9ddd36f67",
        "cb0ea10bf3911810e514062548d5048730e00f16536b86f765a4fabc958e9f2d",
    ),
}

FUNCTIONS = {
    "src/gba/savedata.c": (
        ("void GBASavedataClean(struct GBASavedata* savedata, uint32_t frameCount)",
         "PHASE1_INSERT_PINNED_GBA_SAVEDATA_CLEAN"),
    ),
    "include/mgba/internal/defines.h": (
        ("static inline bool mSavedataClean(int* dirty, uint32_t* dirtAge, uint32_t frameCount)",
         "PHASE1_INSERT_PINNED_M_SAVEDATA_CLEAN"),
    ),
    "src/core/log.c": (
        ("struct mLogger* mLogGetThreadLogger(void)",
         "PHASE1_INSERT_PINNED_MLOG_GET_THREAD"),
        ("struct mLogger* mLogGetContext(void)",
         "PHASE1_INSERT_PINNED_MLOG_GET_CONTEXT"),
        ("void mLogSetDefaultLogger(struct mLogger* logger)",
         "PHASE1_INSERT_PINNED_MLOG_SET_DEFAULT"),
        ("void mLog(int category, enum mLogLevel level, const char* format, ...)",
         "PHASE1_INSERT_PINNED_MLOG"),
        ("void _mCoreStandardLog(struct mLogger* logger, int category, enum mLogLevel level, const char* format, va_list args)",
         "PHASE1_INSERT_PINNED_STANDARD_LOG"),
    ),
    "src/feature/gui/gui-runner.c": (
        ("static void _log(struct mLogger* logger, int category, enum mLogLevel level, const char* format, va_list args)",
         "PHASE1_INSERT_PINNED_GUI_LOG"),
    ),
}

SYMBOLS = {
    "PHASE1_PINNED_STANDARD_LOG_SYMBOL": "_mCoreStandardLog",
    "PHASE1_PINNED_GUI_LOG_SYMBOL": "_log",
}

OUTPUT_PATTERN = re.compile(r"^PHASE1_MGBA_FRONTEND_LOG_WITNESS (\{.*\})$")
EXPECTED_OUTPUT = {
    "evidence_class": "compiled_pinned_source_host_sink",
    "native_frontend_runtime_observed": False,
    "sync_failure_calls": 1,
    "standard_stdout_exact": True,
    "standard_file_exact": True,
    "gui_file_exact": True,
    "gui_filter_suppressed_writes": 0,
    "gui_missing_sink_writes": 0,
    "gui_negative_write_calls": 1,
    "gui_negative_write_closes": 1,
    "gui_negative_reopen_calls": 1,
    "gui_reopen_arguments_exact": True,
    "gui_recovery_file_exact": True,
    "gui_positive_short_calls": 1,
    "gui_positive_short_retries": 0,
    "persistence_acknowledgment": False,
    "stock_gameplay": False,
    "physical_flash": False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *args, input_bytes=None):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args],
        input=input_bytes,
        stderr=subprocess.DEVNULL,
    ).decode().strip()


def extract_function(source, signature):
    require(source.count(signature) == 1,
            "missing or ambiguous pinned function: " + signature)
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced pinned function: " + signature)


def expected_matrix():
    return {
        "schema": "phase1.mgba.frontend-log-observers.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "source_records": [
            {
                "path": path,
                "git_blob": identities[0],
                "full_source_sha256": identities[1],
                "canonical_dossier_row_sha256": identities[2],
                "license": "MPL-2.0",
                "review_scope": (
                    "exact function bodies compiled as a bounded host witness; "
                    "not a complete independent whole-file review"
                ),
            }
            for path, identities in SOURCES.items()
        ],
        "paths": [
            {
                "name": "core_savedata_to_standard_logger",
                "source_functions": [
                    "GBASavedataClean",
                    "mSavedataClean",
                    "mLog",
                    "mLogGetContext",
                    "_mCoreStandardLog",
                ],
                "host_observation": "exact failure INFO text at stdout and mock log VFile",
                "frontend_ui_observed": False,
            },
            {
                "name": "core_savedata_to_gui_runner_file_logger",
                "source_functions": [
                    "GBASavedataClean",
                    "mSavedataClean",
                    "mLog",
                    "_log",
                ],
                "host_observation": (
                    "exact failure INFO text in mock log VFile; filter, absent "
                    "sink, negative-write recovery, and positive short-write controls"
                ),
                "frontend_ui_observed": False,
            },
        ],
        "execution_contract": {
            "actual_pinned_function_bodies_compiled": True,
            "mock_vfile_sync_failure": True,
            "native_linux_host_execution": True,
            "native_qt_or_console_frontend_execution": False,
            "real_emulator_or_gameplay": False,
            "persistence_or_power_loss_evidence": False,
            "physical_flash_evidence": False,
            "independent_semantic_approval": False,
        },
        "distribution_notice": (
            "The extracted mGBA source functions retain their MPL-2.0 notices "
            "in source provenance; this combined test harness is distributed "
            "with that licensing caveat and is not an upstream mGBA modification."
        ),
    }


def verify_matrix(root, matrix_path):
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    require(matrix == expected_matrix(), "frontend observer matrix differs from the pinned contract")
    return matrix


def verify_sources(source_root, root, checkout_identity):
    source_root = Path(source_root)
    root = Path(root)
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
    sources = {}
    for path, (blob, digest, _) in SOURCES.items():
        raw = (source_root / path).read_bytes()
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned source tree blob changed: " + path)
        require(git(source_root, "hash-object", "--stdin", input_bytes=raw) == blob,
                "pinned source Git blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        normalized = " ".join(raw.decode("utf-8").split())
        require("Mozilla Public" in normalized and "License, v. 2.0." in normalized,
                "missing MPL-2.0 notice: " + path)
        sources[path] = raw.decode("utf-8")

    dossier_path = root / DOSSIER
    raw_dossier = dossier_path.read_bytes()
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned dossier Git blob changed")
    require(hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "pinned dossier compressed SHA-256 changed")
    found = {}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path not in SOURCES
            ):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(
                hashlib.sha256(canonical).hexdigest() == SOURCES[path][2]
                and provenance.get("git_blob_sha") == SOURCES[path][0]
                and provenance.get("source_content_sha256") == SOURCES[path][1],
                "pinned dossier row identity changed: " + path,
            )
            require(path not in found, "duplicate pinned dossier row: " + path)
            found[path] = True
    require(set(found) == set(SOURCES), "pinned dossier is missing an observer source row")
    return sources


def compile_harness(sources, harness_path, output_path):
    harness = Path(harness_path).read_text(encoding="utf-8")
    for path, functions in FUNCTIONS.items():
        for signature, marker in functions:
            body = extract_function(sources[path], signature)
            require(harness.count(marker) == 1, "missing or duplicate harness marker: " + marker)
            harness = harness.replace(marker, body)
    for marker, symbol in SYMBOLS.items():
        require(harness.count(marker) == 1, "missing or duplicate symbol marker: " + marker)
        harness = harness.replace(marker, symbol)
    with tempfile.TemporaryDirectory(prefix="mgba-frontend-log-") as directory:
        generated = Path(directory) / "witness.c"
        generated.write_text(harness, encoding="utf-8")
        command = [
            "cc", "-std=c11", "-D_GNU_SOURCE", "-DDISABLE_THREADING",
            "-Wall", "-Wextra", "-Werror", str(generated), "-o", str(output_path),
        ]
        built = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=60)
        require(built.returncode == 0, "native host witness compilation failed:\n" + built.stdout)
    return harness


def parse_output(output):
    lines = [line for line in output.splitlines() if line.startswith("PHASE1_MGBA_FRONTEND_LOG_WITNESS ")]
    require(len(lines) == 1, "native host witness must emit exactly one result")
    match = OUTPUT_PATTERN.fullmatch(lines[0])
    require(match is not None, "malformed native host witness JSON")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate native host witness JSON key")
            result[key] = value
        return result

    try:
        result = json.loads(match.group(1), object_pairs_hook=unique_keys)
    except json.JSONDecodeError as error:
        raise ValueError("malformed native host witness JSON") from error
    require(result == EXPECTED_OUTPUT, "native host witness result differs from the bounded contract")
    return result


def reject_source_mutations(sources):
    savedata = sources["src/gba/savedata.c"]
    mutations = (
        savedata.replace(
            '"Savedata failed to sync!"', '"Savedata synced"', 1
        ),
        savedata.replace(
            'mLOG(GBA_SAVE, INFO, "Savedata failed to sync!");',
            'mLOG(GBA_SAVE, INFO, "Savedata synced");',
            1,
        ),
    )
    rejected = 0
    for mutated in mutations:
        require(mutated != savedata, "source mutation control did not alter source")
        try:
            require(
                hashlib.sha256(mutated.encode()).hexdigest()
                == SOURCES["src/gba/savedata.c"][1],
                "pinned source SHA-256 changed: src/gba/savedata.c",
            )
        except ValueError:
            rejected += 1
    require(rejected == 2, "expected two source-level false-success mutations to be rejected")
    for path, functions in FUNCTIONS.items():
        for signature, _ in functions:
            try:
                extract_function(sources[path], signature + " absent")
            except ValueError:
                rejected += 1
    require(rejected == 10, "expected function extraction mutations to fail closed")
    return rejected


def run_witness(source_root, root, harness_path, matrix_path, checkout_identity):
    root = Path(root)
    verify_matrix(root, matrix_path)
    sources = verify_sources(source_root, root, checkout_identity)
    source_mutations_rejected = reject_source_mutations(sources)
    with tempfile.TemporaryDirectory(prefix="mgba-frontend-log-bin-") as directory:
        binary = Path(directory) / "witness"
        compile_harness(sources, harness_path, binary)
        executed = subprocess.run([str(binary)], text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=20)
    require(executed.returncode == 0, "native host witness failed:\n" + executed.stdout)
    result = parse_output(executed.stdout)
    print(json.dumps({
        "schema": "phase1.mgba.frontend-log-observers.result.v1",
        "pinned_revision": PIN,
        "source_records": len(SOURCES),
        "source_mutations_rejected": source_mutations_rejected,
        "native_linux_host_execution": True,
        "native_frontend_runtime_observed": False,
        "observations": result,
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, help="exact pinned mGBA checkout")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--harness", default=HARNESS)
    parser.add_argument("--matrix", default=MATRIX)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    harness = Path(args.harness)
    if not harness.is_absolute():
        harness = root / harness
    matrix = Path(args.matrix)
    if not matrix.is_absolute():
        matrix = root / matrix
    run_witness(args.checkout, root, harness, matrix, True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify and execute pinned SDL savestate caller bodies with host fixtures."""

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
RECEIPT = "docs/phase1-review-readiness/mgba-sdl-restore-caller-20261109.json"
HARNESS = "tests/phase1_mgba_sdl_restore_caller.c"
SOURCES = {
    "src/platform/sdl/main.c": (
        "91f22bd593d4952076c2a9a11da5a8d6951db2a8",
        "8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b",
        "9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c",
        "PARTIAL_SDL_RUNSTATE_LOAD_OWNERSHIP_AND_ERROR_PROPAGATION",
        "COMPILED_EXTRACTED_LOADSTATE_AND_MSDLRUN_WITH_HOST_CORE_THREAD_VFILE_AND_AUDIO_FIXTURES",
    ),
    "include/mgba/core/serialize.h": (
        "177a7871aa2761c0b478256ce16c7015a36b0fb8",
        "c1301365f7f24c8842e84b51324cc419e5ea01843f5366e9edbbf1cdf40f5c49",
        "4e61192f417f79c7210d2aae3132db1afbedff078fc1e6779b8944ec07bc38b7",
        "PARTIAL_SAVESTATE_RTC_FLAG_INTERFACE",
        "PINNED_HEADER_COMPILED_FOR_SAVESTATE_RTC_FLAG",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
        "PARTIAL_VFILE_CLOSE_INTERFACE",
        "PINNED_VFILE_ABI_HEADER_COMPILED; VFILEOPEN_IS_HOST_FIXTURE",
    ),
}
FUNCTIONS = {
    "static void _loadState(struct mCoreThread* thread) {":
        "225885c26162aa29ac8ce4dffff3a1a6801dde8da093e3e6cdd5c7e145e9f679",
    "int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {":
        "2aa802c9eefdf2fc70580f8d61c81cfa884aee5d790c420bbc931c65167fab1d",
}
EXPECTED_LINES = (
    "PHASE1_SDL_CASE loader_failure mcore=0 msdlrun=0 ignored=1 "
    "state_closed=1 global_cleared=1 runloop=1",
    "PHASE1_SDL_CASE loader_success mcore=1 msdlrun=0 state_closed=1 "
    "global_cleared=1 runloop=1",
    "PHASE1_SDL_CASE open_failure callback=0 close=0 runloop=1",
    "PHASE1_SDL_CASE retry failed_close=1 success_close=1 "
    "global_cleared=1",
)
TERMINAL = "PHASE1_SDL_RESTORE_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")
FILE_FINDINGS = {
    "src/platform/sdl/main.c": (
        "The pinned SDL callback discards mCoreLoadStateNamed's bool. mSDLRun "
        "runs the callback, clears the global state pointer and closes the opened "
        "VFile before proceeding to the runloop; failure to open skips callback "
        "and close, while either load result is not propagated by this path."
    ),
    "include/mgba/core/serialize.h": (
        "The pinned declaration supplies the SAVESTATE_RTC value passed by the "
        "original SDL callback; this witness does not execute the core serializer."
    ),
    "include/mgba-util/vfs.h": (
        "The pinned VFile interface supplies the close callback contract; the "
        "witness substitutes VFileOpen and its close target."
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *command):
    return subprocess.check_output(
        ["git", "-C", str(root), *command], text=True, stderr=subprocess.DEVNULL
    ).strip()


def extract_block(source, signature):
    require(source.count(signature) == 1,
            "missing or ambiguous SDL source anchor: " + signature)
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for offset in range(brace, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced SDL source block: " + signature)


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def expected_source_records():
    return [
        {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "review_scope": values[3],
            "execution_scope": values[4],
            "finding": FILE_FINDINGS[path],
        }
        for path, values in SOURCES.items()
        if path == "src/platform/sdl/main.c"
    ]


def expected_dependency_identities():
    return [
        {
            "path": path,
            "git_blob": SOURCES[path][0],
            "full_source_sha256": SOURCES[path][1],
            "canonical_dossier_row_sha256": SOURCES[path][2],
            "license": "MPL-2.0",
            "scope": "IDENTITY_ONLY_REUSED_DEPENDENCY_NOT_COUNTED_AS_REVIEW",
            "use": SOURCES[path][4],
        }
        for path in (
            "include/mgba/core/serialize.h",
            "include/mgba-util/vfs.h",
        )
    ]


def source_map(checkout, root):
    checkout = Path(checkout)
    root = Path(root)
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "upstream checkout is not the pinned revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "pinned upstream tree mismatch")
    dossier_path = root / DOSSIER
    raw_dossier = dossier_path.read_bytes()
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB and
            hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "compressed dossier identity mismatch")
    rows = {}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and path in SOURCES):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                require(path not in rows, "duplicate pinned dossier row: " + path)
                rows[path] = (
                    sha256(canonical),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                )
    require(set(rows) == set(SOURCES), "pinned SDL dossier inventory incomplete")
    sources = {}
    for path, (blob, digest, row_hash, _, _) in SOURCES.items():
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned Git blob mismatch: " + path)
        raw = (checkout / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 mismatch: " + path)
        require(rows[path] == (row_hash, blob, digest),
                "pinned dossier row/source mismatch: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "MPL-2.0 source notice missing: " + path)
        sources[path] = raw.decode("utf-8")
    return sources


def checked_bodies(sources):
    source = sources["src/platform/sdl/main.c"]
    bodies = {}
    for signature, expected_hash in FUNCTIONS.items():
        body = extract_block(source, signature)
        require(sha256(body) == expected_hash,
                "pinned SDL function body hash mismatch: " + signature)
        bodies[signature] = body
    require("mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC);" in
            bodies["static void _loadState(struct mCoreThread* thread) {"],
            "SDL load callback or flags changed")
    require("mCoreThreadRunFunction(&thread, _loadState);" in
            bodies["int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {"] and
            "_state = NULL;" in
            bodies["int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {"] and
            "state->close(state);" in
            bodies["int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {"],
            "SDL dispatch or VFile cleanup path changed")
    return bodies


def reject_source_mutations(bodies):
    cases = (
        ("static void _loadState(struct mCoreThread* thread) {",
         "mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC);",
         "return mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC);"),
        ("int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {",
         "mCoreThreadRunFunction(&thread, _loadState);", "/* dispatch omitted */"),
        ("int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {",
         "_state = NULL;", "/* global not cleared */"),
        ("int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {",
         "state->close(state);", "/* VFile close omitted */"),
    )
    for signature, before, after in cases:
        body = bodies[signature]
        require(body.count(before) == 1, "SDL source mutation anchor changed")
        if sha256(body.replace(before, after, 1)) == FUNCTIONS[signature]:
            raise ValueError("SDL source mutation escaped: " + signature)
    return len(cases)


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "SDL restore terminal marker missing or duplicated")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES, "SDL restore output differs from expected evidence")
    return {
        "loader_failure": {
            "mcore_result": False,
            "result_discarded_by_callback": True,
            "state_closed": True,
            "global_cleared": True,
            "runloop_reached": True,
        },
        "loader_success": {
            "mcore_result": True,
            "state_closed": True,
            "global_cleared": True,
            "runloop_reached": True,
        },
        "open_failure": {
            "callback_invoked": False,
            "state_closed": False,
            "runloop_reached": True,
        },
        "retry": {
            "retry_is_separate_msd_run_invocation": True,
            "failed_attempt_closed": True,
            "successful_attempt_closed": True,
            "global_cleared_between_attempts": True,
        },
    }


def reject_output_mutations(output):
    mutations = (
        output.replace("ignored=1", "ignored=0", 1),
        output.replace("state_closed=1", "state_closed=0", 1),
        output.replace("global_cleared=1", "global_cleared=0", 1),
        output.replace("runloop=1", "runloop=0", 1),
        output.replace("callback=0", "callback=1", 1),
        output.replace(TERMINAL, "", 1),
    )
    for mutated in mutations:
        try:
            parse_output(mutated)
        except ValueError:
            continue
        raise ValueError("contradictory SDL witness output escaped")
    return len(mutations)


def expected_receipt():
    expected_output = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    return {
        "schema": "phase1.mgba.sdl-restore-caller.v1",
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
        "independent_approvals": 0,
        "evidence_class": (
            "COMPILED_EXTRACTED_PINNED_SDL_MSDLRUN_AND_LOADSTATE_CALLBACK_"
            "WITH_HOST_LOADER_THREAD_AUDIO_AND_VFILE_FIXTURES"
        ),
        "source_records": expected_source_records(),
        "dependency_identities_reused": expected_dependency_identities(),
        "extracted_original_body_sha256": FUNCTIONS,
        "source_call_graph": [
            "mSDLRun -> VFileOpen(args->savestate, O_RDONLY); a non-NULL VFile is assigned to global _state.",
            "mSDLRun dispatches _loadState through mCoreThreadRunFunction; _loadState calls mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC) and discards the bool.",
            "After dispatch, mSDLRun clears _state and closes the opened state VFile before entering the runloop; open failure skips callback and close.",
            "SDL does not set SAVESTATE_SAVEDATA on this path. The core loader implementation and savedata callback remain covered only by prior receipts, not this caller witness.",
            "Prior PR13 libretro integration propagated the loader bool and closed its input VFile; prior restore-consumer package covered the core/GBA restore closure, while PR35 VFile work covered separate backend/allocation obligations.",
        ],
        "observations": parse_output(expected_output),
        "source_mutations_rejected": 4,
        "output_mutations_rejected": 6,
        "limitations": {
            "compiled_original_sdl_loadstate_callback": True,
            "compiled_original_msd_run_function": True,
            "pinned_vfile_and_serialize_headers": True,
            "core_loader": "HOST_RESULT_FIXTURE_NOT_PINNED_MCORE_IMPLEMENTATION",
            "core_thread_dispatch": "SYNCHRONOUS_HOST_FIXTURE",
            "vfileopen_and_close": "HOST_FIXTURE_NOT_NATIVE_BACKEND",
            "audio_and_runloop": "HOST_FIXTURES",
            "full_sdl_frontend_build_or_execution": False,
            "native_user_state_file": False,
            "native_filesystem_error_or_malformed_state": False,
            "natural_malformed_savestate": False,
            "durable_savestate_or_savedata": False,
            "stock_gameplay_or_physical_flash": False,
            "prior_libretro_caller_repeated": False,
            "prior_core_restore_consumer_repeated": False,
            "prior_pr35_vfile_backend_witness_repeated": False,
            "transitive_distribution_licensing_resolved": False,
        },
        "prior_evidence": {
            "libretro_caller": "docs/phase1-review-readiness/mgba-savestate-caller-integration-20261109.json",
            "qt_caller": "docs/phase1-review-readiness/mgba-qt-restore-caller-20261109.json",
            "core_restore_consumer": "docs/phase1-review-readiness/mgba-savestate-restore-consumer-20261109.json",
            "pr35_savedata_review": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json",
            "pr35_source_objection_receipts": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/source-objection-receipts.json",
            "pr35_vfile_wrapper_failure": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/vfile-wrapper-allocation-failure.json",
            "pr35_rewind_restore_map_failure": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/rewind-restore-map-failure.json",
            "overlap": "Reuses only pinned VFile and serializer header identities; the newly executed original code is the SDL callback plus mSDLRun caller body. PR13 libretro behavior, PR35 mCoreRewindRestore map-failure caller, and PR35 backend allocation tests are not repeated.",
        },
        "licensing": {
            "all_source_records_mpl_2_0": True,
            "upstream_modified": False,
            "transitive_distribution_licensing_resolved": False,
        },
    }


def verify_receipt(root):
    path = Path(root) / RECEIPT
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt == expected_receipt(),
            "SDL restore caller receipt differs from fail-closed contract")
    return receipt


def run(checkout, root, harness_path):
    sources = source_map(checkout, root)
    bodies = checked_bodies(sources)
    source_mutations = reject_source_mutations(bodies)
    output_mutations = reject_output_mutations(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    )
    receipt = verify_receipt(root)
    harness_path = Path(root) / harness_path
    harness = harness_path.read_text(encoding="utf-8")
    insertions = {
        "PHASE1_INSERT_PINNED_SDL_LOADSTATE": bodies[
            "static void _loadState(struct mCoreThread* thread) {"
        ],
        "PHASE1_INSERT_PINNED_SDL_MSDLRUN": bodies[
            "int mSDLRun(struct mSDLRenderer* renderer, struct mArguments* args) {"
        ],
    }
    expanded = harness
    for marker, body in insertions.items():
        require(expanded.count(marker) == 1,
                "missing or ambiguous SDL harness insertion marker: " + marker)
        expanded = expanded.replace(marker, body, 1)
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-sdl-restore-") as temp:
        source_path = Path(temp) / "sdl_restore.c"
        binary_path = Path(temp) / "sdl_restore"
        source_path.write_text(expanded, encoding="utf-8")
        compiled = subprocess.run(
            ["cc", "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
             "-I", str(Path(checkout) / "include"), str(source_path),
             "-o", str(binary_path)],
            capture_output=True, text=True, timeout=60,
        )
        require(compiled.returncode == 0,
                "compiled SDL caller witness failed:\n" + compiled.stderr[-8000:])
        executed = subprocess.run(
            [str(binary_path)], capture_output=True, text=True, timeout=20
        )
        require(executed.returncode == 0,
                "SDL caller witness failed:\n" + executed.stdout + executed.stderr)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations == receipt["source_mutations_rejected"] and
                output_mutations == receipt["output_mutations_rejected"],
                "SDL witness does not match its receipt")
    print(
        f"PHASE1_MGBA_SDL_RESTORE_CALLER pinned={PIN} sources={len(SOURCES)} "
        f"source_mutations_rejected={source_mutations} "
        f"output_mutations_rejected={output_mutations}"
    )
    print(executed.stdout, end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--harness", default=HARNESS)
    args = parser.parse_args()
    run(args.checkout, args.root, args.harness)


if __name__ == "__main__":
    main()

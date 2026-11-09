#!/usr/bin/env python3
"""Verify pinned mGBA frontend-to-core savestate restore integration."""

import argparse
import gzip
import hashlib
import importlib.util
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
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-savestate-caller-integration-20261109.json"
)
BASE_HARNESS = "tests/phase1_mgba_savestate_restore_consumer.c"
BASE_HARNESS_SHA256 = "190c1445e41e8586a0e377a77d8a127f9d6d7fe06d18cd98832eaa7865449998"
HARNESS_SHA256 = "58586f959bf3d895d77542a5e6b17de053de303ab04aa9e162d001cb0768834b"

SOURCES = {
    "src/platform/libretro/libretro.c": (
        "12e79131c38e06a8ba46cef97e0872ec51544e38",
        "da8800c76929e25729573760b6180452cdefa824aa6df21b51c3566553ad67ac",
        "70da3c3b8a3280ad6d077f9998fc73d69b443505d2d13dfee3dae791105f5f18",
        "PARTIAL_CALLER_EXECUTION_AND_SERIALIZER_TRACE",
        "COMPILED_EXTRACTED_RETRO_UNSERIALIZE; SERIALIZER_CALLERS_SOURCE_TRACED",
    ),
    "src/platform/qt/CoreController.cpp": (
        "183cea418a70963bd5332ef66bdff54a0dcccd46",
        "8ca7ca7b26fa030ef76322085a6f634b5e3ca4fd40a4e6549b6a12abace260b2",
        "1cbedd6e36f387b7c579bcea8c77bed82e9c3e8b18954974847c647dcf8b0f28",
        "PARTIAL_CALLSITE_TRACE",
        "SOURCE_TRACED_QT_SAVEDATA_PRODUCER_AND_RESTORE_CALLER",
    ),
    "src/platform/sdl/main.c": (
        "91f22bd593d4952076c2a9a11da5a8d6951db2a8",
        "8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b",
        "9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c",
        "PARTIAL_CALLSITE_TRACE",
        "SOURCE_TRACED_SDL_RESTORE_RESULT_AND_VFILE_LIFETIME",
    ),
}

FUNCTIONS = {
    "retro_serialize_size": (
        "size_t retro_serialize_size(void)",
        "31c5a1d837287ede1ed1372d85a88d8ef5cfb06a3f8737027bbb83b599bedad0",
    ),
    "retro_serialize": (
        "bool retro_serialize(void* data, size_t size)",
        "c5ea2e7f21392a358406ce6b0c42ec04e48d2503e6c2f18e49e3d9513281fd0f",
    ),
    "retro_unserialize": (
        "bool retro_unserialize(const void* data, size_t size)",
        "64ad07d469c48944df1094bc180435c62169d8b422a72d58cd849746fe050dfd",
    ),
}

FILE_DEPENDENCIES = {
    "src/platform/libretro/libretro.c": [
        "retro_serialize_size and retro_serialize -> mCoreSaveStateNamed(SAVESTATE_SAVEDATA | SAVESTATE_RTC) -> savedataClone -> EXTDATA_SAVEDATA serialization",
        "retro_unserialize -> VFileFromConstMemory -> mCoreLoadStateNamed(SAVESTATE_RTC) -> mCoreExtractState -> extdata deserialize and restore callback",
        "retro_unserialize returns mCoreLoadStateNamed result and closes the temporary input VFile before returning",
    ],
    "src/platform/qt/CoreController.cpp": [
        "Default m_saveStateFlags include SAVESTATE_SAVEDATA; Qt named save calls mCoreSaveStateNamed with those flags",
        "Qt named and QIODevice load paths call mCoreLoadStateNamed with m_loadStateFlags and close the wrapped/opened input VFile after the call",
        "Qt emits frameAvailable/stateLoaded only when mCoreLoadStateNamed returns true; it captures a backup state before attempting the load",
    ],
    "src/platform/sdl/main.c": [
        "_loadState calls mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC) and ignores its bool result",
        "mSDLRun opens the optional state VFile, runs _loadState on the core thread, then closes the VFile regardless of load result",
        "SDL load path does not set SAVESTATE_SAVEDATA; savedata extdata writeback is therefore false when an item is present",
    ],
}

FILE_OBJECTIONS = {
    "src/platform/libretro/libretro.c": (
        "Only the extracted retro_unserialize body is compiled with the existing extracted core/restore closure and pinned VFile memory translation unit. "
        "retro_serialize bodies and the complete libretro frontend are not executed; host fixtures and in-memory input do not establish native libretro behavior."
    ),
    "src/platform/qt/CoreController.cpp": (
        "Qt callsites and default flags are source-traced only; Qt, QIODevice, core-thread scheduling, signals, backup recovery and frontend error reporting are not executed."
    ),
    "src/platform/sdl/main.c": (
        "SDL callsites are source-traced only; SDL event/runtime behavior, native filesystem errors, reporting and gameplay are not executed."
    ),
}

SOURCE_CLOSURE = [
    "The libretro producer bodies call mCoreSaveStateNamed with SAVESTATE_SAVEDATA | SAVESTATE_RTC; the pinned core serializer creates EXTDATA_SAVEDATA only when savedataClone returns nonzero bytes.",
    "The libretro consumer constructs VFileFromConstMemory, calls mCoreLoadStateNamed with SAVESTATE_RTC, closes the input VFile, and returns the core loader result.",
    "The flags passed by libretro omit SAVESTATE_SAVEDATA, so a present GBA savedata item follows the existing deferred mask/unmask path rather than immediate writeback.",
    "The exact extracted libretro caller was compiled with the already-pinned mCoreLoadStateNamed, extdata parser, GBA restore/SRAM functions and complete pinned VFile memory translation unit; the full libretro frontend was not compiled.",
    "Valid core bytes with absent, short-header or short-payload extdata reach the loader through the libretro caller; the pinned core path ignores extdata parse failure and can return true without restoring savedata.",
    "A short fixed-size core state makes mCoreLoadStateNamed return false; retro_unserialize propagates false and still closes its input VFile.",
    "A valid savedata extdata item reaches the GBA callback; the SAVESTATE_SAVEDATA-omitting writeback false transfers the temporary restore VFile to GBASavedataMask, and unmask applies and closes it.",
    "Qt's default named-save flags include SAVESTATE_SAVEDATA, while its load path reports success through stateLoaded and closes the input VFile; the Qt source is not executed here.",
    "SDL and headless load paths pass flags without SAVESTATE_SAVEDATA and ignore the loader result; both source paths close their input VFiles. Headless identity and callsite are already recorded by the prior PR #13 restore-consumer receipt.",
]

EXPECTED_LINES = (
    "PHASE1_CALLER_CASE absent result=1 input_vfiles=1 input_closed=1 "
    "restore_vfiles=0 save_unchanged=1 clean=1",
    "PHASE1_CALLER_CASE malformed result=1 input_closed=1 "
    "restore_vfiles=0 save_unchanged=1 clean=1",
    "PHASE1_CALLER_CASE short_state result=0 input_closed=1 "
    "restore_vfiles=0 save_unchanged=1 clean=1",
    "PHASE1_CALLER_CASE valid_retry result=1 input_closed=1 "
    "restore_vfiles=1 restore_closed_after_unmask=1 save_match=1 clean=1",
)
TERMINAL = "PHASE1_SAVESTATE_CALLER_INTEGRATION_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *command):
    return subprocess.check_output(
        ["git", "-C", str(root), *command], text=True
    ).strip()


def load_restore_runner(root):
    path = root / "tools/phase1_mgba_savestate_restore_consumer.py"
    spec = importlib.util.spec_from_file_location(
        "phase1_mgba_savestate_restore_consumer", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        }
        for path, values in SOURCES.items()
    ]


def verify_sources(checkout, root, restore, old):
    source_map = restore.verify_sources(checkout, root, old)
    for path, (blob, digest, _, _, _) in SOURCES.items():
        raw = (checkout / path).read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned source tree blob changed: " + path)
        require(hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw
        ).hexdigest() == blob, "pinned source Git blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 notice: " + path)
        source_map[path] = raw.decode("utf-8")

    dossier = root / DOSSIER
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB and
            hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256,
            "pinned machine dossier identity changed")
    expected = {
        path: (values[2], values[0], values[1])
        for path, values in SOURCES.items()
    }
    found = {path: [] for path in SOURCES}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and
                    path in found):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                found[path].append((
                    hashlib.sha256(canonical).hexdigest(),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                ))
    require(found == {path: [value] for path, value in expected.items()},
            "pinned dossier rows changed or are ambiguous")
    for name, (signature, digest) in FUNCTIONS.items():
        old.validate_body(source_map["src/platform/libretro/libretro.c"],
                          signature, digest)
    verify_callsite_contracts(source_map)
    return source_map


def verify_callsite_contracts(source_map):
    libretro = source_map["src/platform/libretro/libretro.c"]
    qt = source_map["src/platform/qt/CoreController.cpp"]
    sdl = source_map["src/platform/sdl/main.c"]
    required = (
        ("libretro producer flag", "mCoreSaveStateNamed(core, vfm, SAVESTATE_SAVEDATA | SAVESTATE_RTC);", libretro),
        ("libretro restore flags", "mCoreLoadStateNamed(core, vfm, SAVESTATE_RTC)", libretro),
        ("libretro input close", "vfm->close(vfm);", libretro),
        ("Qt default savedata producer flag", "m_saveStateFlags(SAVESTATE_SCREENSHOT | SAVESTATE_SAVEDATA | SAVESTATE_CHEATS | SAVESTATE_RTC)", qt),
        ("Qt named restore caller", "mCoreLoadStateNamed(context->core, vf, controller->m_loadStateFlags)", qt),
        ("Qt input close", "vf->close(vf);", qt),
        ("SDL restore caller", "mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC);", sdl),
        ("SDL input close", "state->close(state);", sdl),
    )
    for label, anchor, source in required:
        require(anchor in source, "pinned caller contract changed: " + label)


def reject_source_mutations(source_map, old):
    source = source_map["src/platform/libretro/libretro.c"]
    signature, digest = FUNCTIONS["retro_unserialize"]
    body = old.validate_body(source, signature, digest)
    mutations = (
        ("SAVESTATE_RTC", "SAVESTATE_RTC | SAVESTATE_SAVEDATA"),
        ("vfm->close(vfm);", "UNUSED(vfm);"),
        ("return success;", "return true;"),
    )
    rejected = 0
    for before, after in mutations:
        require(body.count(before) == 1, "source mutation anchor changed")
        try:
            old.validate_body(body.replace(before, after, 1), signature, digest)
        except ValueError:
            rejected += 1
    require(rejected == len(mutations), "a pinned caller mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "caller integration witness lacks a unique terminal marker")
    require(tuple(output[:-len(TERMINAL)].splitlines()) == EXPECTED_LINES,
            "caller integration witness output changed")
    return {
        "absent_extdata": {
            "libretro_return": True,
            "input_vfile_created_and_closed": True,
            "restore_vfiles_created": 0,
            "savedata_unchanged": True,
            "cleanup_balanced": True,
        },
        "malformed_extdata": {
            "libretro_return": True,
            "input_vfile_closed": True,
            "restore_vfiles_created": 0,
            "savedata_unchanged": True,
            "cleanup_balanced": True,
        },
        "short_core_state": {
            "libretro_return": False,
            "input_vfile_closed": True,
            "restore_vfiles_created": 0,
            "failure_propagated": True,
            "cleanup_balanced": True,
        },
        "valid_extdata_after_malformed_retry": {
            "libretro_return": True,
            "input_vfile_closed": True,
            "restore_vfiles_created": 1,
            "restore_vfile_closed_by_unmask": True,
            "savedata_matches": True,
            "cleanup_balanced": True,
        },
    }


def reject_output_mutations(output):
    mutations = (
        output.replace("input_closed=1", "input_closed=0", 1),
        output.replace("restore_vfiles=0", "restore_vfiles=1", 1),
        output.replace("result=0", "result=1", 1),
        output.replace("restore_closed_after_unmask=1", "restore_closed_after_unmask=0", 1),
        output.replace("save_match=1", "save_match=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for mutated in mutations:
        try:
            parse_output(mutated)
        except ValueError:
            continue
        raise ValueError("caller integration output mutation escaped")
    return len(mutations)


def verify_receipt(root, restore, receipt_path=None):
    receipt_path = receipt_path or root / RECEIPT
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.savestate-caller-integration.v1" and
            receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "caller integration receipt schema or source pin changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "caller integration receipt must remain non-approving")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "caller integration machine dossier identity changed")
    require(receipt.get("source_records") == expected_source_records(),
            "caller integration per-file source records changed")
    require(receipt.get("function_body_sha256") == {
        name: values[1] for name, values in FUNCTIONS.items()
    }, "caller integration function-body hashes changed")
    require(receipt.get("file_dependencies") == FILE_DEPENDENCIES and
            receipt.get("per_file_objections") == FILE_OBJECTIONS,
            "caller integration dependency or objection inventory changed")
    require(receipt.get("source_closure") == SOURCE_CLOSURE,
            "caller integration source closure changed")
    expected = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    require(receipt.get("observations") == parse_output(expected),
            "caller integration observations changed")
    require(receipt.get("source_mutations_rejected") == 3 and
            receipt.get("output_mutations_rejected") == 6,
            "caller integration mutation control counts changed")
    require(receipt.get("prior_evidence_inventory") == {
        "pr13_restore_consumer": {
            "path": "docs/phase1-review-readiness/mgba-savestate-restore-consumer-20261109.json",
            "source_records": 19,
            "overlap": "Core restore, extdata parse, GBA callback and memory VFile behavior; headless caller source-traced only.",
            "distinct_gap": "No production Qt, SDL or libretro caller is executed.",
        },
        "pr13_clone_and_gba_clone_receipts": [
            "docs/phase1-review-readiness/mgba-core-savestate-clone-caller-20261108.json",
            "docs/phase1-review-readiness/mgba-gba-clone-vfile-allocation-20261108.json",
        ],
        "pr13_other_file_save_callers": [
            "docs/phase1-review-readiness/mgba-core-loadsave-allocation-recovery-20261107.json",
            "docs/phase1-review-readiness/mgba-core-autoload-save-ownership-20261107.json",
        ],
        "pr35_savedata_review": {
            "path": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json",
            "git_blob": "e3a1d80c489f5b557748a8250131fce289ac878a",
            "overlap": "Pinned savedata/backend source review; no mCoreLoadStateNamed frontend execution.",
        },
        "pr35_source_objection_receipts": {
            "path": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/source-objection-receipts.json",
            "git_blob": "a10d2c14dbc45d7453b03166dfab5ccc3ac04d48",
            "overlap": "The mcore-consumer-closure and frontend callback outcome objections remain NEEDS_EVIDENCE; this packet adds bounded caller tracing and one host execution, not a full frontend closure.",
        },
        "pr35_vfile_wrapper_failure": {
            "path": "PR #35 semantic-snapshots/independent-reviews/copilot-mgba-savedata/vfile-wrapper-allocation-failure.json",
            "git_blob": "a0373c0af36fa74911f8ca18c63c14d64533f0f4",
            "overlap": "VFileMemChunk constructor allocation boundary; no savestate restore caller execution.",
        },
    }, "caller integration PR13/PR35 nonoverlap inventory changed")
    require(receipt.get("limitations") == {
        "compiled_unchanged_extracted_libretro_retro_unserialize": True,
        "compiled_core_and_gba_restore_closure_reused_from_prior_receipt": True,
        "compiled_pinned_complete_vfile_memory_translation_unit": True,
        "qt_caller_source_traced_not_executed": True,
        "sdl_caller_source_traced_not_executed": True,
        "libretro_serializer_producer_source_traced_not_executed": True,
        "host_memory_input_and_savedata_vfiles": True,
        "host_allocator_and_mapping_shims": True,
        "native_libretro_or_gui_frontend_executed": False,
        "naturally_malformed_user_savestate_observed": False,
        "durable_savestate_or_sav_persistence_tested": False,
        "stock_gameplay_or_physical_flash_tested": False,
        "transitive_distribution_licensing_resolved": False,
    }, "caller integration evidence limitations changed")
    require(receipt.get("licensing") == {
        "source_notices": "All three newly inventoried frontend source files carry MPL-2.0 notices; the reused core closure's prior receipt records MPL-2.0 for its 19 files.",
        "upstream_modified": False,
        "transitive_distribution_licensing_resolved": False,
    }, "caller integration licensing boundary changed")
    require(receipt.get("nonoverlap") == {
        "distinct_from_prior_restore_consumer": True,
        "new_executed_caller": "src/platform/libretro/libretro.c::retro_unserialize",
        "prior_core_restore_closure_reused": True,
        "new_source_traced_callers": [
            "src/platform/qt/CoreController.cpp",
            "src/platform/sdl/main.c",
        ],
        "no_prior_mCoreLoadStateNamed_caller_execution": True,
    }, "caller integration nonoverlap declaration changed")
    require(restore.verify_receipt(root, None)["overall"] == "FAIL_INCOMPLETE",
            "prior restore-consumer receipt no longer validates")
    return receipt


def run(command, timeout=90):
    return subprocess.run(
        command, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    root = Path(__file__).resolve().parents[1]
    restore = load_restore_runner(root)
    old = restore.load_source_helpers(root)
    receipt = verify_receipt(root, restore)
    require(git(checkout, "rev-parse", "HEAD") == PIN and
            git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA revision or tree")
    source_map = verify_sources(checkout, root, restore, old)
    source_mutations = reject_source_mutations(source_map, old)
    expected_output = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    output_mutations = reject_output_mutations(expected_output)
    harness = args.harness.read_text(encoding="utf-8")
    require(hashlib.sha256(harness.encode("utf-8")).hexdigest() == HARNESS_SHA256,
            "caller integration harness SHA-256 changed")
    require(hashlib.sha256(
        (root / BASE_HARNESS).read_bytes()
    ).hexdigest() == BASE_HARNESS_SHA256,
            "prior pinned restore harness identity changed")
    base_marker = "PHASE1_INSERT_PINNED_RESTORE_FUNCTIONS"
    base = (root / BASE_HARNESS).read_text(encoding="utf-8")
    require(base.count(base_marker) == 1, "prior restore harness marker changed")
    bodies = []
    for name, (path, signature, digest, kind) in restore.FUNCTIONS.items():
        if kind == "declaration":
            body = old.validate_declaration(source_map[path], signature, digest)
        else:
            body = old.validate_body(source_map[path], signature, digest)
        if name not in ("VFileMemChunk", "headless main"):
            bodies.append(body)
    base = base.replace(base_marker, "\n\n".join(bodies), 1)
    base = base.replace("int main(void) {",
                        "int prior_restore_consumer_main(void) {", 1)
    caller_body = old.validate_body(
        source_map["src/platform/libretro/libretro.c"],
        FUNCTIONS["retro_unserialize"][0],
        FUNCTIONS["retro_unserialize"][1],
    )
    caller_marker = "PHASE1_INSERT_PINNED_LIBRETRO_UNSERIALIZE"
    require(harness.count(caller_marker) == 1,
            "libretro caller extraction marker changed")
    expanded = base + "\n" + harness.replace(
        caller_marker, caller_body, 1
    )

    with tempfile.TemporaryDirectory(
            prefix="xgba-mgba-savestate-caller-integration-") as temp:
        temp = Path(temp)
        expanded_source = temp / "caller-integration.c"
        binary = temp / "caller-integration"
        expanded_source.write_text(expanded, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            str(expanded_source), str(checkout / "src/util/vfs/vfs-mem.c"),
            "-Wl,--wrap=malloc", "-Wl,--wrap=free",
            "-Wl,--wrap=VFileMemChunk",
            "-Wl,--wrap=VFileFromConstMemory", "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned caller integration compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned caller integration failed:\n" + executed.stdout)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations == receipt["source_mutations_rejected"] and
                output_mutations == receipt["output_mutations_rejected"],
                "caller integration runtime differs from its receipt")
        print(
            "PHASE1_SAVESTATE_CALLER_INTEGRATION "
            f"pinned={PIN} new_sources={len(receipt['source_records'])} "
            f"source_mutations_rejected={source_mutations} "
            f"output_mutations_rejected={output_mutations}"
        )
        print(executed.stdout, end="")


if __name__ == "__main__":
    main()

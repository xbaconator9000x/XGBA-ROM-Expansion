#!/usr/bin/env python3
"""Verify and execute the pinned mGBA core savedata teardown ownership path."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
RECEIPT = ROOT / "docs/phase1-review-readiness/mgba-core-teardown-ownership-20261109.json"
HARNESS = ROOT / "tests/phase1_mgba_core_teardown_ownership.c"
EXPECTED_LINES = (
    "PHASE1_CORE_TEARDOWN_CASE normal sync_calls=1 sync_errors=0 "
    "unmap_calls=1 close_calls=1 close_errors=0 savedata_refs_cleared=1 "
    "board_freed=1 core_freed=1 fd_open_after_production=0 "
    "wrapper_survives=0 harness_cleanup_close=0 production_retry=0 trace=SUC",
    "PHASE1_CORE_TEARDOWN_CASE sync_and_close_failure sync_calls=1 "
    "sync_errors=1 unmap_calls=1 close_calls=1 close_errors=1 "
    "savedata_refs_cleared=1 board_freed=1 core_freed=1 "
    "fd_open_after_production=1 wrapper_survives=1 "
    "harness_cleanup_close=1 production_retry=0 trace=SUC",
)

spec = importlib.util.spec_from_file_location(
    "phase1_mgba_vfs_fd_teardown_native",
    ROOT / "tools/phase1_mgba_vfs_fd_teardown_native.py",
)
teardown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(teardown)

FUNCTIONS = (
    ("src/gba/savedata.c", "size_t GBASavedataSize(const struct GBASavedata* savedata)",
     teardown.BODY_HASHES["size"]),
    ("src/gba/savedata.c", "void GBASavedataDeinit(struct GBASavedata* savedata)",
     teardown.BODY_HASHES["deinit"]),
    ("src/gba/savedata.c", "void GBASavedataUnmask(struct GBASavedata* savedata)",
     teardown.BODY_HASHES["unmask"]),
    ("src/gba/gba.c", "void GBAUnloadROM(struct GBA* gba)",
     teardown.BODY_HASHES["unload_rom"]),
    ("src/gba/gba.c", "void GBADestroy(struct GBA* gba)",
     teardown.BODY_HASHES["gba_destroy"]),
    ("src/gba/core.c", "static void _GBACoreDeinit(struct mCore* core)",
     teardown.BODY_HASHES["gba_core_deinit"]),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_receipt(path=RECEIPT):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "phase1.mgba.core-teardown-ownership.v1",
            "core teardown receipt schema changed")
    require(receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "core teardown source pin changed")
    require(receipt.get("machine_dossier") == {
        "path": teardown.DOSSIER,
        "git_blob": teardown.DOSSIER_BLOB,
        "compressed_sha256": teardown.DOSSIER_SHA256,
    }, "core teardown dossier identity changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "core teardown receipt must remain non-approving")
    return receipt


def verify_sources(source_root, checkout_identity):
    if checkout_identity:
        require(teardown.git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
        require(teardown.git(source_root, "rev-parse", "HEAD^{tree}") == TREE,
                "wrong pinned mGBA source tree")
    source_paths = {
        "include/mgba-util/vfs.h", "src/util/vfs/vfs-fd.c",
        "src/gba/savedata.c", "src/gba/gba.c", "src/gba/core.c",
    }
    sources = {}
    for path in source_paths:
        git_blob, sha256 = teardown.FILES[path]
        source_path = source_root / path
        raw = source_path.read_bytes()
        actual_blob = subprocess.check_output(
            ["git", "hash-object", "--stdin"], input=raw
        ).decode().strip()
        require(actual_blob == git_blob,
                "pinned source blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == sha256,
                "pinned source SHA-256 changed: " + path)
        if checkout_identity:
            require(teardown.git(source_root, "rev-parse", "HEAD:" + path) ==
                    git_blob, "pinned source tree blob changed: " + path)
        sources[path] = raw.decode("utf-8")

    dossier_path = ROOT / teardown.DOSSIER
    require(teardown.git(ROOT, "hash-object", teardown.DOSSIER) ==
            teardown.DOSSIER_BLOB, "pinned dossier Git blob changed")
    dossier_bytes = dossier_path.read_bytes()
    require(hashlib.sha256(dossier_bytes).hexdigest() ==
            teardown.DOSSIER_SHA256, "pinned dossier SHA-256 changed")
    observed_rows = set()
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    path not in source_paths):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(hashlib.sha256(canonical).hexdigest() ==
                    teardown.DOSSIER_ROWS[path],
                    "canonical dossier row changed: " + path)
            require(provenance.get("git_blob_sha") ==
                    teardown.FILES[path][0] and
                    provenance.get("source_content_sha256") ==
                    teardown.FILES[path][1],
                    "dossier source pin changed: " + path)
            observed_rows.add(path)
    require(observed_rows == source_paths,
            "dossier does not cover the POSIX core teardown closure")

    bodies = {}
    for path, signature, digest in FUNCTIONS:
        bodies[(path, signature)] = teardown.extract_function(
            sources[path], signature, digest)
    require("core->deinit = _GBACoreDeinit;" in sources["src/gba/core.c"],
            "pinned GBA core no longer registers the tested deinit callback")
    require("GBADestroy(core->board);" in bodies[
        ("src/gba/core.c", "static void _GBACoreDeinit(struct mCore* core)")],
            "core deinit no longer owns GBA board destruction")
    require("GBAUnloadROM(gba);" in bodies[
        ("src/gba/gba.c", "void GBADestroy(struct GBA* gba)")],
            "GBA destroy no longer owns ROM/savedata teardown")
    require("gba->memory.savedata.realVf->close(" in bodies[
        ("src/gba/gba.c", "void GBAUnloadROM(struct GBA* gba)")],
            "GBA unload close path changed")
    receipt = load_receipt()
    expected_records = {
        "src/gba/core.c", "src/gba/gba.c", "src/gba/savedata.c",
        "src/util/vfs/vfs-fd.c", "include/mgba-util/vfs.h",
    }
    records = receipt.get("source_records", [])
    require({record.get("path") for record in records} == expected_records,
            "core teardown source closure changed")
    for record in records:
        path = record["path"]
        require(record.get("git_blob") == teardown.FILES[path][0] and
                record.get("full_source_sha256") == teardown.FILES[path][1] and
                record.get("canonical_dossier_row_sha256") ==
                teardown.DOSSIER_ROWS[path] and
                record.get("license") == "MPL-2.0" and
                record.get("whole_file_semantic_coverage") is False and
                record.get("substantive_objection"),
                "core teardown source record is incomplete: " + path)
    require(receipt.get("function_sha256") == {
        signature: digest for _, signature, digest in FUNCTIONS
    }, "core teardown function hashes changed")
    return sources, bodies


def reject_source_mutations(sources):
    cases = (
        (FUNCTIONS[5], "GBADestroy(core->board);", "GBADestroy(NULL);"),
        (FUNCTIONS[4], "GBAUnloadROM(gba);", "(void) gba;"),
        (FUNCTIONS[3],
         "gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);",
         "return;"),
    )
    rejected = 0
    for function, original, replacement in cases:
        path, signature, digest = function
        body = teardown.extract_function(sources[path], signature, digest)
        require(body.count(original) == 1,
                "core teardown mutation anchor changed: " + original)
        changed = body.replace(original, replacement, 1)
        try:
            teardown.extract_function(changed, signature, digest)
        except ValueError:
            rejected += 1
    require(rejected == len(cases), "a core teardown source mutation escaped")
    return rejected


def parse_output(output):
    require(output.splitlines() == [*EXPECTED_LINES, "PHASE1_CORE_TEARDOWN_DONE"],
            "production core teardown observations changed: " +
            repr(output.splitlines()))
    return {
        "cases": ["normal", "sync_and_close_failure"],
        "core_deinit_has_error_return": False,
        "savedata_refs_cleared_before_board_free": True,
        "close_failure_orphans_backend_wrapper_from_production_owner": True,
        "production_retry_after_close_failure": False,
        "harness_only_close_retry": True,
        "page_cache_or_durable_save_claim": False,
    }


def reject_output_mutations(output):
    changes = (
        output.replace("sync_errors=1", "sync_errors=0", 1),
        output.replace("close_errors=1", "close_errors=0", 1),
        output.replace("savedata_refs_cleared=1", "savedata_refs_cleared=0", 1),
        output.replace("board_freed=1 core_freed=1", "board_freed=0 core_freed=1", 1),
        output.replace("fd_open_after_production=1", "fd_open_after_production=0", 1),
        output.replace("wrapper_survives=1", "wrapper_survives=0", 1),
        output.replace("harness_cleanup_close=1", "harness_cleanup_close=0", 1),
        output.replace("production_retry=0", "production_retry=1", 1),
        output.replace("trace=SUC", "trace=SCU", 1),
        output.replace("PHASE1_CORE_TEARDOWN_DONE\n", "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("a core teardown output mutation escaped")
    return len(changes)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    source_root = (args.checkout or args.source_dir).resolve()
    tree_identity_verified = bool(args.checkout)
    sources, bodies = verify_sources(source_root, tree_identity_verified)
    source_mutations_rejected = reject_source_mutations(sources)

    fixture = HARNESS.read_text(encoding="utf-8")
    fixture_sha256 = hashlib.sha256(fixture.encode()).hexdigest()
    receipt = load_receipt()
    require(receipt.get("harness_sha256") == fixture_sha256,
            "core teardown fixture hash differs from the receipt")
    markers = {
        "PHASE1_INSERT_PINNED_SAVEDATA_SIZE": bodies[
            ("src/gba/savedata.c", FUNCTIONS[0][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_DEINIT": bodies[
            ("src/gba/savedata.c", FUNCTIONS[1][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_UNMASK": bodies[
            ("src/gba/savedata.c", FUNCTIONS[2][1])],
        "PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM": bodies[
            ("src/gba/gba.c", FUNCTIONS[3][1])],
        "PHASE1_INSERT_PINNED_GBA_DESTROY": bodies[
            ("src/gba/gba.c", FUNCTIONS[4][1])],
        "PHASE1_INSERT_PINNED_GBA_CORE_DEINIT": bodies[
            ("src/gba/core.c", FUNCTIONS[5][1])],
    }
    expanded = fixture
    for marker, body in markers.items():
        require(expanded.count(marker) == 1,
                "core teardown extraction marker changed: " + marker)
        expanded = expanded.replace(marker, body)

    compiler = "gcc"
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-core-teardown-") as temp:
        temp = Path(temp)
        source_path = temp / "core-teardown.c"
        binary = temp / "core-teardown"
        source_path.write_text(expanded, encoding="utf-8")
        command = [
            compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-DENABLE_VFS_FD", "-I", str(source_root / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(source_root / "src/util/vfs/vfs-fd.c"),
            str(source_path), "-Wl,--wrap=close", "-Wl,--wrap=msync",
            "-Wl,--wrap=munmap", "-Wl,--wrap=free", "-o", str(binary),
        ]
        compiled = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=90)
        require(compiled.returncode == 0,
                "pinned core teardown compile failed:\n" + compiled.stdout)
        executed = subprocess.run([str(binary)], text=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=30)
        require(executed.returncode == 0,
                "pinned core teardown execution failed:\n" + executed.stdout)
        output = executed.stdout
        observations = parse_output(output)
        output_mutations_rejected = reject_output_mutations(output)
        binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "evidence_class": "PINNED_MGBA_CORE_POSIX_SAVEDATA_TEARDOWN_OWNERSHIP",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "source_tree_identity_verified": tree_identity_verified,
        "source_mutations_rejected": source_mutations_rejected,
        "output_mutations_rejected": output_mutations_rejected,
        "harness_sha256": fixture_sha256,
        "binary_sha256": binary_sha256,
        "compile_command": command,
        "original_posix_fd_translation_unit_compiled": True,
        "compiled_extracted_original_functions": [
            signature for _, signature, _ in FUNCTIONS
        ],
        "full_gba_and_core_translation_units_compiled": False,
        "secondary_gba_deinit_routines": "host no-op fixtures",
        "close_error": "linker-injected EIO before the real close syscall",
        "close_retry": "harness-held VFile pointer only after production owner teardown",
        "observations": observations,
        "raw_output": output.splitlines(),
        "native_linux_syscalls_exercised": ["mmap", "msync", "munmap", "close"],
        "durable_sav_persistence_tested": False,
        "native_frontend_or_gameplay_tested": False,
        "physical_flash_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_CORE_TEARDOWN_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

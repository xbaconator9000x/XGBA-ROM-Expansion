#!/usr/bin/env python3
"""Verify and execute pinned mGBA POSIX savedata growth failure behavior."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
RECEIPT = ROOT / "docs/phase1-review-readiness/mgba-posix-truncate-failure-20261109.json"
HARNESS = ROOT / "tests/phase1_mgba_posix_truncate_failure.c"
MEMORY_HEADER = "include/mgba/internal/gba/memory.h"
MEMORY_HEADER_IDENTITY = (
    "0aad912613e726560d06bbdbf6061986e69e5842",
    "fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41",
    "6d4aad1e87edf5e5e07bc6af2af6f36c396f1a5530518ca575a765e3640dea8e",
)

spec = importlib.util.spec_from_file_location(
    "phase1_mgba_core_teardown_ownership",
    ROOT / "tools/phase1_mgba_core_teardown_ownership.py",
)
core_teardown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_teardown)
source_tools = core_teardown.teardown

FUNCTIONS = (
    ("src/gba/savedata.c",
     "static void _ashesToAshes(struct mTiming* timing, void* user, uint32_t cyclesLate)",
     source_tools.BODY_HASHES["ashes"]),
    ("src/gba/savedata.c",
     "size_t GBASavedataSize(const struct GBASavedata* savedata)",
     source_tools.BODY_HASHES["size"]),
    ("src/gba/savedata.c",
     "void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf)",
     source_tools.BODY_HASHES["init"]),
    ("src/gba/savedata.c",
     "void GBASavedataDeinit(struct GBASavedata* savedata)",
     source_tools.BODY_HASHES["deinit"]),
    ("src/gba/savedata.c",
     "void GBASavedataUnmask(struct GBASavedata* savedata)",
     source_tools.BODY_HASHES["unmask"]),
    ("src/gba/savedata.c",
     "void GBASavedataForceType(struct GBASavedata* savedata, enum GBASavedataType type)",
     source_tools.BODY_HASHES["force_type"]),
    ("src/gba/savedata.c",
     "void GBASavedataInitSRAM(struct GBASavedata* savedata)",
     "d9b4d85db33cea2da5073208f512fe3c82d8f7450c1d074baeff37c79a29efbc"),
    ("src/gba/gba.c",
     "bool GBALoadSave(struct GBA* gba, struct VFile* sav)",
     "cfbfe0068178dbc3c1ed8e8a034ed861cfc0deb777e32bcc48979ad710732b73"),
    ("src/gba/core.c",
     "static bool _GBACoreLoadSave(struct mCore* core, struct VFile* vf)",
     "0e348b801d98712108765d16b23ce7faa2ab2b9382011cf1d521d543b053c4de"),
    ("src/gba/gba.c", "void GBAUnloadROM(struct GBA* gba)",
     source_tools.BODY_HASHES["unload_rom"]),
    ("src/util/vfs/vfs-fd.c",
     "static void _vfdTruncate(struct VFile* vf, size_t size)",
     "bbd51fc63433dea4d80803391db2632dac4b8f5a9b00e6cffe44939f362400c5"),
)

EXPECTED_LINES = (
    "PHASE1_POSIX_TRUNCATE_CASE success caller_return=1 "
    "truncate_events=SRC file_size=32768 initial_byte=42 fill=FF "
    "cleanup=original_GBAUnloadROM signal=none",
    "PHASE1_POSIX_TRUNCATE_CASE injected_EIO caller_return=unreturned "
    "truncate_events=E signal=SIGBUS automatic_retry=0 "
    "cleanup=child_process_exit",
    "PHASE1_POSIX_TRUNCATE_CASE recovery_after_EIO caller_return=1 "
    "truncate_events=SRC file_size=32768 initial_byte=42 fill=FF "
    "cleanup=original_GBAUnloadROM signal=none",
    "PHASE1_POSIX_TRUNCATE_CASE injected_ENOSPC caller_return=unreturned "
    "truncate_events=N signal=SIGBUS automatic_retry=0 "
    "cleanup=child_process_exit",
    "PHASE1_POSIX_TRUNCATE_CASE recovery_after_ENOSPC caller_return=1 "
    "truncate_events=SRC file_size=32768 initial_byte=42 fill=FF "
    "cleanup=original_GBAUnloadROM signal=none",
    "PHASE1_POSIX_TRUNCATE_DONE",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def load_receipt(path=RECEIPT):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "phase1.mgba.posix-truncate-failure.v1",
            "POSIX truncate receipt schema changed")
    require(
        receipt.get("repository") == "mgba-emu/mgba" and
        receipt.get("pinned_revision") == PIN and
        receipt.get("pinned_tree") == TREE,
        "POSIX truncate source pin changed",
    )
    require(receipt.get("machine_dossier") == {
        "path": source_tools.DOSSIER,
        "git_blob": source_tools.DOSSIER_BLOB,
        "compressed_sha256": source_tools.DOSSIER_SHA256,
    }, "POSIX truncate dossier identity changed")
    require(
        receipt.get("status") == "NEEDS_EVIDENCE" and
        receipt.get("overall") == "FAIL_INCOMPLETE" and
        receipt.get("independent_approvals") == 0,
        "POSIX truncate receipt must remain non-approving",
    )
    return receipt


def verify_memory_header(source_root, checkout_identity):
    blob, source_sha, row_sha = MEMORY_HEADER_IDENTITY
    source_path = source_root / MEMORY_HEADER
    raw = source_path.read_bytes()
    actual_blob = subprocess.check_output(
        ["git", "hash-object", "--stdin"], input=raw
    ).decode().strip()
    require(actual_blob == blob and hashlib.sha256(raw).hexdigest() == source_sha,
            "pinned GBA memory header identity changed")
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD:" + MEMORY_HEADER) == blob,
                "pinned GBA memory header tree blob changed")

    dossier_path = ROOT / source_tools.DOSSIER
    found = False
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    provenance.get("path") != MEMORY_HEADER):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(hashlib.sha256(canonical).hexdigest() == row_sha,
                    "canonical GBA memory header dossier row changed")
            require(
                provenance.get("git_blob_sha") == blob and
                provenance.get("source_content_sha256") == source_sha,
                "GBA memory header dossier pin changed",
            )
            found = True
            break
    require(found, "pinned GBA memory header dossier row is absent")
    require(re.search(r"^\s*GBA_SIZE_SRAM\s*=\s*(?:0x0*8000|32768)\s*,?",
                      raw.decode("utf-8"), re.MULTILINE) is not None,
            "pinned SRAM size constant changed")
    return raw.decode("utf-8")


def verify_sources(source_root, checkout_identity):
    sources, _ = core_teardown.verify_sources(source_root, checkout_identity)
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD^{tree}") == TREE,
                "wrong pinned mGBA source tree")
    sources[MEMORY_HEADER] = verify_memory_header(
        source_root, checkout_identity)
    bodies = {}
    for path, signature, digest in FUNCTIONS:
        bodies[(path, signature)] = source_tools.extract_function(
            sources[path], signature, digest)

    require("core->loadSave = _GBACoreLoadSave;" in sources["src/gba/core.c"],
            "pinned core no longer registers the tested savedata callback")
    require("GBASavedataForceType(&gba->memory.savedata, type);" in bodies[
        ("src/gba/gba.c", "bool GBALoadSave(struct GBA* gba, struct VFile* sav)")],
            "pinned GBALoadSave type-dispatch path changed")
    require("savedata->vf->truncate(savedata->vf, GBA_SIZE_SRAM);" in bodies[
        ("src/gba/savedata.c", "void GBASavedataInitSRAM(struct GBASavedata* savedata)")],
            "pinned SRAM growth no longer calls VFile truncate")
    require("ftruncate(vfd->fd, size);" in bodies[
        ("src/util/vfs/vfs-fd.c", "static void _vfdTruncate(struct VFile* vf, size_t size)")],
            "pinned POSIX truncate call changed")

    receipt = load_receipt()
    expected_records = {
        "include/mgba-util/vfs.h",
        MEMORY_HEADER,
        "src/util/vfs/vfs-fd.c",
        "src/gba/savedata.c",
        "src/gba/gba.c",
        "src/gba/core.c",
    }
    records = receipt.get("source_records", [])
    require({record.get("path") for record in records} == expected_records,
            "POSIX truncate source closure changed")
    for record in records:
        path = record["path"]
        if path == MEMORY_HEADER:
            expected = MEMORY_HEADER_IDENTITY
        else:
            expected = (*source_tools.FILES[path],
                        source_tools.DOSSIER_ROWS[path])
        require(
            record.get("git_blob") == expected[0] and
            record.get("full_source_sha256") == expected[1] and
            record.get("canonical_dossier_row_sha256") == expected[2] and
            record.get("license") == "MPL-2.0" and
            record.get("whole_file_semantic_coverage") is False and
            record.get("reused_identity") is True and
            record.get("substantive_objection"),
            "POSIX truncate source record is incomplete: " + path,
        )
    require(receipt.get("distinct_scope", {}).get("new_original_files") == 0,
            "reused original source identities must not be recounted")
    require(receipt.get("function_sha256") == {
        signature: digest for _, signature, digest in FUNCTIONS
    }, "POSIX truncate function hashes changed")
    return sources, bodies


def reject_source_mutations(sources):
    cases = (
        (
            FUNCTIONS[10],
            "ftruncate(vfd->fd, size);",
            "return;",
        ),
        (
            FUNCTIONS[6],
            "savedata->vf->truncate(savedata->vf, GBA_SIZE_SRAM);",
            "savedata->data = NULL;",
        ),
        (
            FUNCTIONS[7],
            "GBASavedataForceType(&gba->memory.savedata, type);",
            "return false;",
        ),
    )
    rejected = 0
    for function, original, replacement in cases:
        path, signature, digest = function
        body = source_tools.extract_function(sources[path], signature, digest)
        require(body.count(original) == 1,
                "POSIX truncate mutation anchor changed: " + original)
        changed = body.replace(original, replacement, 1)
        try:
            source_tools.extract_function(changed, signature, digest)
        except ValueError:
            rejected += 1
    require(rejected == len(cases),
            "a POSIX truncate source mutation escaped")
    return rejected


def parse_output(output):
    require(output.splitlines() == list(EXPECTED_LINES),
            "POSIX truncate observations changed: " + repr(output.splitlines()))
    return {
        "normal_growth_returned_true_and_cleaned_up": True,
        "injected_eio_and_enospc_each_reached_sigbus": True,
        "truncate_failure_propagated_to_gba_loadsave": False,
        "automatic_retry_after_failure": False,
        "separate_retry_after_fault_removal_succeeded": True,
        "durability_claim": False,
    }


def reject_output_mutations(output):
    changes = (
        output.replace("truncate_events=SRC", "truncate_events=SRCX", 1),
        output.replace("caller_return=unreturned", "caller_return=0", 1),
        output.replace("truncate_events=E", "truncate_events=S", 1),
        output.replace("truncate_events=N", "truncate_events=S", 1),
        output.replace("signal=SIGBUS", "signal=none", 1),
        output.replace("automatic_retry=0", "automatic_retry=1", 1),
        output.replace("file_size=32768", "file_size=1", 1),
        output.replace("PHASE1_POSIX_TRUNCATE_DONE\n", "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("a POSIX truncate output mutation escaped")
    return len(changes)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    require(sys.platform.startswith("linux"),
            "native POSIX truncate witness requires Linux")
    source_root = (args.checkout or args.source_dir).resolve()
    checkout_identity = bool(args.checkout)
    sources, bodies = verify_sources(source_root, checkout_identity)
    source_mutations_rejected = reject_source_mutations(sources)

    fixture = HARNESS.read_text(encoding="utf-8")
    fixture_sha256 = hashlib.sha256(fixture.encode()).hexdigest()
    receipt = load_receipt()
    require(receipt.get("harness_sha256") == fixture_sha256,
            "POSIX truncate fixture hash differs from the receipt")
    markers = {
        "PHASE1_INSERT_PINNED_ASHES": bodies[
            ("src/gba/savedata.c", FUNCTIONS[0][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_SIZE": bodies[
            ("src/gba/savedata.c", FUNCTIONS[1][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_INIT": bodies[
            ("src/gba/savedata.c", FUNCTIONS[2][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_DEINIT": bodies[
            ("src/gba/savedata.c", FUNCTIONS[3][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_UNMASK": bodies[
            ("src/gba/savedata.c", FUNCTIONS[4][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_FORCE_TYPE": bodies[
            ("src/gba/savedata.c", FUNCTIONS[5][1])],
        "PHASE1_INSERT_PINNED_SAVEDATA_INIT_SRAM": bodies[
            ("src/gba/savedata.c", FUNCTIONS[6][1])],
        "PHASE1_INSERT_PINNED_GBA_LOAD_SAVE": bodies[
            ("src/gba/gba.c", FUNCTIONS[7][1])],
        "PHASE1_INSERT_PINNED_GBA_CORE_LOAD_SAVE": bodies[
            ("src/gba/core.c", FUNCTIONS[8][1])],
        "PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM": bodies[
            ("src/gba/gba.c", FUNCTIONS[9][1])],
    }
    expanded = fixture
    for marker, body in markers.items():
        token = marker + "\n"
        require(expanded.count(token) == 1,
                "POSIX truncate extraction marker changed: " + marker)
        expanded = expanded.replace(token, body + "\n", 1)

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-posix-truncate-") as temp:
        temp = Path(temp)
        source_path = temp / "posix-truncate.c"
        binary = temp / "posix-truncate"
        source_path.write_text(expanded, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-D_POSIX_MAPPED_FILES=1",
            "-DENABLE_VFS_FD", "-I", str(source_root / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(source_root / "src/util/vfs/vfs-fd.c"),
            str(source_path), "-Wl,--wrap=ftruncate", "-o", str(binary),
        ]
        compiled = subprocess.run(
            command, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=90,
        )
        require(compiled.returncode == 0,
                "pinned POSIX truncate compile failed:\n" + compiled.stdout)
        executed = subprocess.run(
            [str(binary)], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=30,
        )
        require(executed.returncode == 0,
                "pinned POSIX truncate execution failed:\n" + executed.stdout)
        output = executed.stdout
        observations = parse_output(output)
        output_mutations_rejected = reject_output_mutations(output)
        binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "evidence_class":
            "COMPILED_PINNED_GBA_LOADSAVE_AND_POSIX_VFILE_WITH_HOST_FTRUNCATE_INJECTION",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "source_tree_identity_verified": checkout_identity,
        "new_original_files": 0,
        "source_mutations_rejected": source_mutations_rejected,
        "output_mutations_rejected": output_mutations_rejected,
        "harness_sha256": fixture_sha256,
        "binary_sha256": binary_sha256,
        "compile_command": command,
        "original_posix_fd_translation_unit_compiled": True,
        "compiled_extracted_original_functions": [
            signature for _, signature, _ in FUNCTIONS
        ],
        "full_gba_core_and_savedata_translation_units_compiled": False,
        "ftruncate_fault": "linker-injected EIO or ENOSPC before the real syscall",
        "savedata_type_precondition":
            "Host fixture seeds the existing configured SRAM type before core loadSave.",
        "sigbus_isolated_in_child_process": True,
        "normal_cleanup": "Original GBAUnloadROM body after successful initialization.",
        "recovery": "Separate invocation after fault injection is disabled.",
        "observations": observations,
        "raw_output": output.splitlines(),
        "natural_storage_failure_observed": False,
        "durable_sav_persistence_tested": False,
        "native_frontend_or_gameplay_tested": False,
        "physical_flash_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_POSIX_TRUNCATE_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

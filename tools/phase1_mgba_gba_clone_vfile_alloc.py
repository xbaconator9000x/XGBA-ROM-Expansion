#!/usr/bin/env python3
"""Execute the pinned GBA savedata-clone VFile allocation failure path."""
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
    "mgba-gba-clone-vfile-allocation-20261108.json"
)
OLD_RUNNER = "tools/phase1_mgba_core_savestate_clone.py"
NEW_SOURCES = {
    "src/util/vfs/vfs-mem.c": (
        "048194e2dd2d0b3b395a852d2092c694663c88a2",
        "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b",
        "3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce",
        "COMPILED_PINNED_VFILE_MEMORY_BACKEND_TRANSLATION_UNIT",
    ),
    "include/mgba/internal/gba/gba.h": (
        "65e994dc63a304cc9fb207536f09bb2c8a6cf3e5",
        "b50fc8ae1467f9ac1c6be3ba8452e22027571ff5c886695edb9be529d7962d4e",
        "d6e61894ce31db089d3fd04e64e0938d1e689fb6c7498a8056fced405bf2bba0",
        "COMPILED_GBA_BOARD_AND_MEMORY_LAYOUT",
    ),
    "include/mgba/internal/gba/memory.h": (
        "0aad912613e726560d06bbdbf6061986e69e5842",
        "fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41",
        "6d4aad1e87edf5e5e07bc6af2af6f36c396f1a5530518ca575a765e3640dea8e",
        "COMPILED_GBA_MEMORY_AND_SAVEDATA_SIZE_CONSTANTS",
    ),
    "include/mgba/internal/gba/savedata.h": (
        "6227be25e8c9d2c1cc14c06ded34389b96138577",
        "30481cada83cc0e3a88b55298f3081cc660e18e55ca7f5a57356e6f2a75224dc",
        "eaee2c8bdb65c51e4f40daeb80af916f57ed430c48c88286562363f687ca6de9",
        "COMPILED_GBA_SAVEDATA_LAYOUT",
    ),
    "include/mgba/gba/interface.h": (
        "6edb38e6bf3161e28f3130b49b5598fc5d21884a",
        "d75c2c6bdcef009197252dcfbe059ae61084b137eeab677f818a837e3226038d",
        "44cd0490e58f1be562051dd1f5ce1240245573f3dc24e447df4176a2c2a1f1a2",
        "COMPILED_GBA_SAVEDATA_TYPE_ENUM",
    ),
    "include/mgba-util/math.h": (
        "f7b3269c9d51967765379b951ba6f43d24c61865",
        "04f5ee1686f4b30744d4e62caef4cf16f2f4b80682b88a87e7e18cf117fd421e",
        "87d819c03b064e4665a27b5563f4a7261cfcdad051913229884d4f72cfd813f9",
        "COMPILED_VFILE_MEMORY_BACKEND_MATH_DEPENDENCY",
    ),
    "include/mgba-util/memory.h": (
        "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
        "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
        "COMPILED_VFILE_MEMORY_BACKEND_MEMORY_API",
    ),
}

SIZE_BODY_SHA256 = (
    "9f3e0774073a8f44195f2b1b8c2d4c20977dedd1eb8c4d7ec4c1c42e467b02d1"
)
VFILE_FROM_MEMORY_SIGNATURE = (
    "struct VFile* VFileFromMemory(void* mem, size_t size)"
)
VFILE_FROM_MEMORY_BODY_SHA256 = (
    "1a711858436bda76766b74512e60ef0c7af3d20600c65d62739edcb813d485fd"
)
HARNESS_SHA256 = (
    "87469ae8736f08dc6a51d123a20e166f4ca8912f94676ed55da1b20e67c290b9"
)
TERMINAL = "PHASE1_GBA_CLONE_DONE\n"
EXPECTED_LINES = (
    "PHASE1_GBA_CLONE_CASE success caller_return=1 "
    "callback_clone_result=32768 "
    "wrapper_alloc_attempts=1 wrapper_alloc_failures=0 wrapper_frees=1 "
    "clone_buffer_frees=1 savedata_present=1 payload_match=1",
    "PHASE1_GBA_CLONE_CASE wrapper_allocation_failure caller_return=1 "
    "callback_clone_result=0 "
    "wrapper_alloc_attempts=1 wrapper_alloc_failures=1 wrapper_frees=0 "
    "clone_buffer_frees=1 savedata_present=0",
    "PHASE1_GBA_CLONE_CASE retry_after_wrapper_failure caller_return=1 "
    "callback_clone_result=32768 "
    "wrapper_alloc_attempts=1 wrapper_alloc_failures=0 wrapper_frees=1 "
    "clone_buffer_frees=1 savedata_present=1 payload_match=1",
)
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *command):
    return subprocess.check_output(
        ["git", "-C", str(root), *command], text=True
    ).strip()


def load_old_runner(root):
    path = root / OLD_RUNNER
    spec = importlib.util.spec_from_file_location(
        "phase1_mgba_core_savestate_clone_dependency", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_source_records(old):
    records = old.expected_source_records()
    scopes = {
        "src/gba/core.c": "COMPILED_EXTRACTED_ORIGINAL_GBA_CLONE_CALLBACK",
        "src/gba/savedata.c": (
            "COMPILED_EXTRACTED_ORIGINAL_GBA_SAVEDATA_SIZE_AND_CLONE"
        ),
    }
    for record in records:
        if record["path"] in scopes:
            record["execution_scope"] = scopes[record["path"]]
        if record["path"] == "src/gba/savedata.c":
            record["function_body_sha256"]["GBASavedataSize"] = (
                SIZE_BODY_SHA256
            )
    for path, values in NEW_SOURCES.items():
        record = {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "execution_scope": values[3],
        }
        existing = next(
            (item for item in records if item["path"] == path), None
        )
        if existing:
            existing.update(record)
        else:
            records.append(record)
    for record in records:
        if record["path"] == "src/util/vfs/vfs-mem.c":
            record["function_body_sha256"] = {
                "VFileFromMemory": VFILE_FROM_MEMORY_BODY_SHA256
            }
    return records


def verify_new_sources(checkout, old_sources, old):
    sources = {}
    for path, (blob, digest, _, _) in NEW_SOURCES.items():
        raw = (checkout / path).read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned source tree blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        require(subprocess.check_output(
            ["git", "-C", str(checkout), "hash-object", str(checkout / path)],
            text=True,
        ).strip() == blob, "pinned source Git blob changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 source notice: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier = root / DOSSIER
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "machine-dossier Git blob changed")
    require(hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256,
            "machine-dossier SHA-256 changed")
    expected = {
        path: (values[2], values[0], values[1])
        for path, values in NEW_SOURCES.items()
    }
    found = {path: [] for path in NEW_SOURCES}
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

    size_body = old_sources["src/gba/savedata.c"]
    old.validate_body(
        size_body,
        "size_t GBASavedataSize(const struct GBASavedata* savedata)",
        SIZE_BODY_SHA256,
        ("case GBA_SAVEDATA_SRAM:", "return savedata->vf->size(savedata->vf);"),
    )
    memory_body = old.validate_body(
        sources["src/util/vfs/vfs-mem.c"],
        VFILE_FROM_MEMORY_SIGNATURE,
        VFILE_FROM_MEMORY_BODY_SHA256,
        ("if (!mem || !size)", "malloc(sizeof(struct VFileMem))",
         "if (!vfm)", "return &vfm->d;"),
    )
    require(memory_body.index("if (!vfm)") < memory_body.index("return &vfm->d;"),
            "pinned memory VFile allocation guard changed")

    core = old_sources["src/gba/core.c"]
    old.validate_body(
        core, old.GBA_CLONE_SIGNATURE, old.GBA_CLONE_BODY_SHA256,
        ("struct GBA* gba = core->board;", "struct VFile* vf = VFileFromMemory(*sram, size);",
         "if (!vf)", "if (!success)", "return size;"),
    )
    savedata = old_sources["src/gba/savedata.c"]
    old.validate_body(
        savedata, old.GBA_SAVEDATA_CLONE_SIGNATURE,
        old.GBA_SAVEDATA_CLONE_BODY_SHA256,
        ("case GBA_SAVEDATA_SRAM:", "return out->write(out, savedata->data, GBA_SIZE_SRAM) == GBA_SIZE_SRAM;"),
    )

    gba_header = sources["include/mgba/internal/gba/gba.h"]
    memory_header = sources["include/mgba/internal/gba/memory.h"]
    savedata_header = sources["include/mgba/internal/gba/savedata.h"]
    require("struct GBAMemory memory;" in gba_header and
            "struct GBASavedata savedata;" in memory_header and
            "enum GBASavedataType type;" in savedata_header and
            "uint8_t* data;" in savedata_header and
            "struct VFile* vf;" in savedata_header,
            "pinned GBA-to-savedata type/layout closure changed")
    require("GBA_SAVEDATA_SRAM = 1" in
            sources["include/mgba/gba/interface.h"] and
            "GBA_SIZE_SRAM = 0x00008000" in memory_header,
            "pinned SRAM type or size changed")
    return sources


def reject_source_mutations(old_sources, new_sources, old):
    cases = (
        (old_sources["src/gba/core.c"], old.GBA_CLONE_SIGNATURE,
         old.GBA_CLONE_BODY_SHA256, "if (!vf) {", "if (vf) {"),
        (new_sources["src/util/vfs/vfs-mem.c"],
         VFILE_FROM_MEMORY_SIGNATURE, VFILE_FROM_MEMORY_BODY_SHA256,
         "if (!vfm) {", "if (false) {"),
        (old_sources["src/core/serialize.c"], old.MCORE_SAVE_SIGNATURE,
         old.MCORE_SAVE_BODY_SHA256, "if (size) {", "if (true) {"),
        (old_sources["src/gba/savedata.c"],
         "size_t GBASavedataSize(const struct GBASavedata* savedata)",
         SIZE_BODY_SHA256, "return GBA_SIZE_SRAM;", "return 0;"),
    )
    rejected = 0
    for source, signature, digest, before, after in cases:
        body = old.extract_function(source, signature)
        require(body.count(before) == 1, "mutation anchor changed: " + before)
        changed = body.replace(before, after, 1)
        try:
            old.validate_body(changed, signature, digest)
        except ValueError:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "GBA clone witness lacks a unique terminal marker")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES,
            "GBA clone witness differs from expected observations")
    return {
        "successful_clone": {
            "mcore_caller_return": True,
            "callback_clone_size": 32768,
            "vfile_wrapper_allocation_failures": 0,
            "vfile_wrapper_freed": True,
            "clone_buffer_freed_by_extdata": True,
            "savedata_extdata_present": True,
            "payload_matches": True,
        },
        "injected_vfile_wrapper_allocation_failure": {
            "mcore_caller_return": True,
            "callback_clone_size": 0,
            "vfile_wrapper_allocation_failures": 1,
            "vfile_wrapper_freed": False,
            "clone_buffer_freed_by_gba_callback": True,
            "savedata_extdata_present": False,
        },
        "retry_after_wrapper_failure": {
            "mcore_caller_return": True,
            "callback_clone_size": 32768,
            "vfile_wrapper_allocation_failures": 0,
            "vfile_wrapper_freed": True,
            "clone_buffer_freed_by_extdata": True,
            "savedata_extdata_present": True,
            "payload_matches": True,
        },
    }


def reject_output_mutations(output):
    changes = (
        output.replace("caller_return=1", "caller_return=0", 1),
        output.replace("wrapper_alloc_failures=1", "wrapper_alloc_failures=0", 1),
        output.replace("clone_buffer_frees=1", "clone_buffer_frees=0", 1),
        output.replace("savedata_present=0", "savedata_present=1", 1),
        output.replace("payload_match=1", "payload_match=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("GBA clone output mutation escaped")
    return len(changes)


def verify_receipt(root, old, receipt_path=None):
    receipt_path = receipt_path or root / RECEIPT
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.gba-clone-vfile-allocation.v1" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE and
            receipt.get("repository") == "mgba-emu/mgba",
            "GBA clone receipt schema or source pin changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "GBA clone receipt must remain non-approving")
    require(receipt.get("evidence_class") ==
            "COMPILED_EXTRACTED_MCORE_SAVESTATE_CALLER_AND_GBA_SAVEDATA_"
            "CLONE_CALLBACK_WITH_PINNED_VFILE_MEMORY_BACKEND_AND_HOST_"
            "ALLOCATOR_FAULT_INJECTION",
            "GBA clone evidence class changed")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "machine-dossier identity changed")
    require(receipt.get("source_records") == expected_source_records(old),
            "GBA clone source records changed")
    require(receipt.get("observations") == parse_output(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    ), "GBA clone observations changed")
    require(receipt.get("call_graph") == [
        "Pinned mCoreSaveStateNamed calls the harness-bound original _GBACoreSavedataClone callback for SAVESTATE_SAVEDATA.",
        "The callback obtains the pinned GBA_SAVEDATA_SRAM size and allocates its clone buffer.",
        "The callback calls the compiled pinned VFileFromMemory implementation with that buffer.",
        "A host linker wrapper fails exactly the VFileMem wrapper allocation after observing the clone-buffer allocation.",
        "The original callback frees the clone buffer, clears the output pointer, and returns zero when VFileFromMemory returns NULL.",
        "The pinned mCore caller omits EXTDATA_SAVEDATA on the zero result but still returns true for the state-only output.",
        "A separate retry with fault injection disabled completes the original clone and serializes the matching payload.",
    ], "GBA clone call graph changed")
    require(receipt.get("fault_injection") == {
        "boundary": "malloc(sizeof(struct VFileMem)) inside original VFileFromMemory",
        "host_control": (
            "Failure is armed only after the actual callback's "
            "GBA_SIZE_SRAM clone-buffer allocation."
        ),
        "negative_control": (
            "Normal wrapper allocation and close; subsequent retry after one "
            "failed wrapper allocation."
        ),
        "natural_os_allocation_failure_observed": False,
    }, "GBA clone fault-injection description changed")
    require(receipt.get("source_mutations_rejected") == 4 and
            receipt.get("output_mutations_rejected") == 6,
            "GBA clone mutation controls changed")
    expected_flags = {
        "original_mcore_savestate_caller_compiled": True,
        "original_gba_savedata_clone_callback_executed": True,
        "original_gba_savedata_size_and_clone_executed": True,
        "original_vfile_from_memory_executed": True,
        "pinned_vfile_memory_translation_unit_compiled": True,
        "host_wrapper_allocation_fault_injected": True,
        "natural_os_allocation_failure_observed": False,
        "full_mgba_core_compiled": False,
        "native_mgba_frontend_executed": False,
        "savestate_frontend_roundtrip_tested": False,
        "durable_persistence_tested": False,
        "sav_interoperability_tested": False,
        "stock_gameplay_tested": False,
        "physical_flash_tested": False,
    }
    require(receipt.get("evidence_flags") == expected_flags,
            "GBA clone evidence limits changed")
    require(receipt.get("prior_witness_nonoverlap") == {
        "previous_receipt": (
            "docs/phase1-review-readiness/"
            "mgba-core-savestate-clone-caller-20261108.json"
        ),
        "previous_case": (
            "mCoreSaveStateNamed caller supplied a test callback returning zero"
        ),
        "new_case": (
            "original _GBACoreSavedataClone -> GBASavedataClone -> "
            "VFileFromMemory wrapper allocation failure"
        ),
        "distinct_failure_injection_boundary": True,
    }, "GBA clone nonoverlap inventory changed")
    return receipt


def run(command, timeout=90):
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    root = Path(__file__).resolve().parents[1]
    old = load_old_runner(root)
    receipt = verify_receipt(root, old)
    require(git(checkout, "rev-parse", "HEAD") == PIN and
            git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA revision or tree")
    old_sources, _ = old.verify_sources(checkout)
    new_sources = verify_new_sources(checkout, old_sources, old)
    source_mutations_rejected = reject_source_mutations(
        old_sources, new_sources, old
    )
    output_mutations_rejected = reject_output_mutations(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    )

    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "GBA clone harness SHA-256 changed")
    expanded = harness.decode("utf-8")
    marker = "PHASE1_INSERT_PINNED_GBA_CLONE_FUNCTIONS"
    require(expanded.count(marker) == 1,
            "GBA clone extraction marker changed")
    serialize = old_sources["src/core/serialize.c"]
    function_bodies = [
        old.validate_declaration(
            serialize, old.EXTDATA_HEADER_SIGNATURE,
            old.EXTDATA_HEADER_SHA256,
        ),
        old.validate_body(
            serialize, old.MCORE_SAVE_SIGNATURE,
            old.MCORE_SAVE_BODY_SHA256,
        ),
        *[
            old.validate_body(serialize, signature, digest)
            for name, (signature, digest) in old.EXTDATA_BODIES.items()
            if name != "mStateExtdataDeserialize"
        ],
        old.extract_function(
            serialize, old.EXTDATA_BODIES["mStateExtdataDeserialize"][0]
        ),
        old.extract_function(
            old_sources["src/gba/core.c"], old.GBA_CLONE_SIGNATURE
        ),
        old.extract_function(
            old_sources["src/gba/savedata.c"],
            "size_t GBASavedataSize(const struct GBASavedata* savedata)",
        ),
        old.extract_function(
            old_sources["src/gba/savedata.c"],
            old.GBA_SAVEDATA_CLONE_SIGNATURE,
        ),
    ]
    expanded = expanded.replace(marker, "\n\n".join(function_bodies), 1)

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-gba-clone-") as temp:
        temp = Path(temp)
        expanded_source = temp / "gba-clone.c"
        binary = temp / "gba-clone"
        expanded_source.write_text(expanded, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            str(expanded_source),
            str(checkout / "src/util/vfs/vfs-mem.c"),
            "-Wl,--wrap=malloc", "-Wl,--wrap=free", "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned GBA clone witness compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned GBA clone witness failed:\n" + executed.stdout)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                output_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "GBA clone runtime differs from its receipt")
        print(
            "PHASE1_GBA_CLONE_VFILE_ALLOC_WITNESS "
            f"pinned={PIN} sources={len(receipt['source_records'])} "
            f"source_mutations_rejected={source_mutations_rejected} "
            f"output_mutations_rejected={output_mutations_rejected}"
        )
        print(executed.stdout, end="")


if __name__ == "__main__":
    main()

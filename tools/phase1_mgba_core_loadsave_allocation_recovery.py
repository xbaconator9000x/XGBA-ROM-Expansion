#!/usr/bin/env python3
"""Compile the pinned mCore save caller through the POSIX VFile allocation path."""
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

SOURCES = {
    "src/core/core.c": (
        "17edcde68b8d4f0885c6c6ddd17c4e6ca64701f8",
        "94b5dc1cec2d9b157ef2933681c644a6dfb43dcebe9f6b887d68b104ac640ea5",
        "6e453bae6a2dd590ac92ce6f86821a8e342dcc34f9f762836152bdad9b49e989",
        "COMPILED_EXTRACTED_CALLER_BODY",
    ),
    "include/mgba/core/core.h": (
        "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
        "e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9",
        "0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87",
        "TRACED_INTERFACE_NARROW_FIXTURE",
    ),
    "src/core/scripting.c": (
        "7ccb51e897685ce24b37dabc76beb27427331b4f",
        "8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1",
        "9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8",
        "TRACED_SCRIPT_ENTRY_NOT_COMPILED",
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "COMPILED_ORIGINAL_TRANSLATION_UNIT",
    ),
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
        "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
        "COMPILED_ORIGINAL_TRANSLATION_UNIT",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/string.h": (
        "bc29e28d71bbb4cbb51261a9ded26399c019fb2e",
        "80434f7f78cf6fa0bb60a7d3fcc4fe2ee09acf8ac14295a8c9e5c9a6a8715a9d",
        "6c046cb5d36c75862236163fb73973c308d6f61d1c93470e5ce69fc1940ccc77",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/vector.h": (
        "c837379e2102ca6535db2b292233bd4983c3532c",
        "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
        "6a1179a47870dc93b443eff57599611d1b8d43d87560de25863a9e5805d83eb7",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
        "5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070",
        "COMPILED_INTERFACE",
    ),
}

CALLER_SIGNATURE = (
    "bool mCoreLoadSaveFile(struct mCore* core, const char* path, bool temporary)"
)
CALLER_BODY_SHA256 = "623abab0e9024f839ebd661ae941e1bc386280db728beff527394d3d46328efe"
SCRIPT_BINDING = (
    "mSCRIPT_DECLARE_STRUCT_METHOD(mCore, BOOL, loadSaveFile, "
    "mCoreLoadSaveFile, 2, CHARP, path, BOOL, temporary);"
)
DISPATCH_SIGNATURE = "struct VFile* VFileOpen(const char* path, int flags)"
DISPATCH_BODY_SHA256 = "e41233c9f3694959554a63cb8ef2a2fdb456f245a11b26e79a533ff1e1c7a137"
OPEN_SIGNATURE = "struct VFile* VFileOpenFD(const char* path, int flags)"
OPEN_BODY_SHA256 = "1e166c42b6f3ae8a3c1f8b9886e5a00dd1282645dfd37c720c83b1ac1f31ff3e"
FROM_FD_SIGNATURE = "struct VFile* VFileFromFD(int fd)"
FROM_FD_BODY_SHA256 = "13cb910fdbbafbe0712bc985e9f1be0b03f01cd5a61c31173879e491ca3fef63"
HARNESS_SHA256 = "1df8b54ba01b8e41d29910fcd0fff6e55513c002b265ae1753bf558a4f693f46"
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-core-loadsave-allocation-recovery-20261107.json"
)
TERMINAL = "PHASE1_CALLER_DONE\n"
MPL_NOTICE = re.compile(
    rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\."
)
EXPECTED_LINES = (
    "PHASE1_CALLER_CASE normal caller_return=1 open_attempts=1 "
    "successful_opens=1 allocation_attempts=1 allocation_failures=0 "
    "save_callbacks=1 close_calls=1 target_fd_open=0",
    "PHASE1_CALLER_CASE allocation_failure caller_return=0 open_attempts=1 "
    "successful_opens=1 allocation_attempts=1 allocation_failures=1 "
    "save_callbacks=0 close_calls=0 leaked_fd_open=1",
    "PHASE1_CALLER_CASE retry failure_return=0 retry_return=1 "
    "open_attempts=2 successful_opens=2 allocation_attempts=2 "
    "allocation_failures=1 save_callbacks=1 close_calls=1 "
    "leaked_first_fd_open=1 retry_fd_closed=1",
    "PHASE1_CALLER_CASE open_failure caller_return=0 open_attempts=1 "
    "successful_opens=0 allocation_attempts=0 allocation_failures=0 "
    "save_callbacks=0 errno=ENOENT",
)
OBJECTION_NOTES = [
    "The malloc failure is injected by a host linker wrapper, not observed as a naturally occurring OS allocation failure.",
    "The exact pinned mCoreLoadSaveFile body and original VFile dispatcher/backend are compiled, but the complete mGBA core and frontend are not.",
    "The caller body is compiled against a narrow test mCore fixture; include/mgba/core/core.h is source-verified but not compiled into this harness.",
    "The save callback is a controlled fixture. The injected-failure assertion verifies the original caller returns before invoking it; the retry callback only closes the returned VFile.",
    "The leaked descriptor is observed with fcntl in the same process, then explicitly closed by harness cleanup; this is not durable-storage, .sav interoperability, gameplay, or physical Flash evidence.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


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


def validate_body(source, signature, digest, anchors):
    body = extract_function(source, signature)
    require(hashlib.sha256(body.encode()).hexdigest() == digest,
            "pinned function body hash changed: " + signature)
    for anchor in anchors:
        require(body.count(anchor) == 1,
                "pinned function anchor missing or ambiguous: " + anchor)
    return body


def expected_source_records():
    records = []
    for path, values in SOURCES.items():
        record = {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "execution_scope": values[3],
        }
        if path == "src/core/core.c":
            record["function_body_sha256"] = CALLER_BODY_SHA256
        records.append(record)
    return records


def verify_sources(checkout):
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "wrong pinned mGBA revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA source tree")
    sources = {}
    for path, (blob, digest, _, _) in SOURCES.items():
        file_path = checkout / path
        raw = file_path.read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned tree blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        require(subprocess.check_output(
            ["git", "-C", str(checkout), "hash-object", str(file_path)],
            text=True,
        ).strip() == blob, "pinned source Git blob changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 source notice: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier_path = root / DOSSIER
    require(dossier_path.is_file(), "pinned machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned machine-dossier Git blob changed")
    dossier_bytes = dossier_path.read_bytes()
    require(hashlib.sha256(dossier_bytes).hexdigest() == DOSSIER_SHA256,
            "pinned machine-dossier compressed SHA-256 changed")

    expected_rows = {
        path: (values[2], values[0], values[1])
        for path, values in SOURCES.items()
    }
    found = {path: [] for path in SOURCES}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
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
    require(found == {path: [value] for path, value in expected_rows.items()},
            "pinned dossier rows changed or are ambiguous")

    validate_body(
        sources["src/core/core.c"], CALLER_SIGNATURE, CALLER_BODY_SHA256,
        ("VFileOpen(path, O_CREAT | O_RDWR)", "if (!vf)",
         "return false;", "return core->loadSave(core, vf);"),
    )
    require(sources["src/core/scripting.c"].count(SCRIPT_BINDING) == 1,
            "pinned script-to-core save binding changed")
    validate_body(
        sources["src/util/vfs.c"], DISPATCH_SIGNATURE,
        DISPATCH_BODY_SHA256,
        ("#elif defined(ENABLE_VFS_FD)", "return VFileOpenFD(path, flags);"),
    )
    validate_body(
        sources["src/util/vfs/vfs-fd.c"], OPEN_SIGNATURE, OPEN_BODY_SHA256,
        ("int fd = open(path, flags, 0666);", "return VFileFromFD(fd);"),
    )
    validate_body(
        sources["src/util/vfs/vfs-fd.c"], FROM_FD_SIGNATURE,
        FROM_FD_BODY_SHA256,
        ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
         "if (!vfd) {\n\t\treturn 0;\n\t}"),
    )
    require("bool (*loadSave)(struct mCore*, struct VFile*);" in
            sources["include/mgba/core/core.h"],
            "pinned mCore save callback declaration changed")
    return sources


def reject_source_mutations(sources):
    body = extract_function(sources["src/core/core.c"], CALLER_SIGNATURE)
    cases = (
        ("if (!vf) {\n\t\treturn false;\n\t}",
         "if (!vf) {\n\t\treturn true;\n\t}"),
        ("return core->loadSave(core, vf);", "return false;"),
        ("return core->loadTemporarySave(core, vf);", "return false;"),
    )
    rejected = 0
    for before, after in cases:
        require(body.count(before) == 1,
                "caller source mutation anchor changed")
        mutated = body.replace(before, after, 1)
        try:
            validate_body(
                mutated, CALLER_SIGNATURE, CALLER_BODY_SHA256,
                ("VFileOpen(path, O_CREAT | O_RDWR)", "if (!vf)",
                 "return false;", "return core->loadSave(core, vf);"),
            )
        except ValueError:
            rejected += 1
    require(rejected == len(cases),
            "a caller source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "caller witness lacks a unique terminal marker")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES,
            "caller witness output differs from the pinned contract")
    return {
        "normal_caller": {
            "caller_return": True,
            "open_attempts": 1,
            "successful_opens": 1,
            "allocation_attempts": 1,
            "allocation_failures": 0,
            "save_callbacks": 1,
            "close_calls": 1,
            "target_fd_open": False,
        },
        "allocation_failure": {
            "caller_return": False,
            "open_attempts": 1,
            "successful_opens": 1,
            "allocation_attempts": 1,
            "allocation_failures": 1,
            "save_callbacks": 0,
            "close_calls": 0,
            "leaked_fd_open": True,
        },
        "retry_after_allocation_failure": {
            "failure_return": False,
            "retry_return": True,
            "open_attempts": 2,
            "successful_opens": 2,
            "allocation_attempts": 2,
            "allocation_failures": 1,
            "save_callbacks": 1,
            "close_calls": 1,
            "leaked_first_fd_open": True,
            "retry_fd_closed": True,
        },
        "open_failure_control": {
            "caller_return": False,
            "open_attempts": 1,
            "successful_opens": 0,
            "allocation_attempts": 0,
            "allocation_failures": 0,
            "save_callbacks": 0,
            "errno": "ENOENT",
        },
    }


def verify_receipt(path):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.core-loadsave-allocation-recovery.v1" and
            receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "caller recovery receipt pin/schema changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "caller recovery receipt approval status changed")
    require(receipt.get("source_records") == expected_source_records(),
            "caller recovery source identities or scopes changed")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "caller recovery dossier identity changed")
    expected_call_graph = [
        "mCore.loadSaveFile script binding -> mCoreLoadSaveFile",
        "mCoreLoadSaveFile -> VFileOpen(path, O_CREAT | O_RDWR)",
        "VFileOpen -> VFileOpenFD for ENABLE_VFS_FD",
        "VFileOpenFD -> POSIX open -> VFileFromFD",
        "VFileFromFD -> fstat -> malloc(sizeof(struct VFileFD))",
        "allocation failure -> VFileFromFD returns NULL without closing fd",
        "mCoreLoadSaveFile sees NULL -> returns false before save callback",
    ]
    require(receipt.get("call_graph") == expected_call_graph,
            "caller recovery call graph changed")
    require(receipt.get("evidence_class") ==
            "COMPILED_EXTRACTED_PINNED_CORE_CALLER_AND_ORIGINAL_POSIX_VFILE_"
            "WITH_HOST_ALLOCATOR_INJECTION" and
            receipt.get("objection_notes") == OBJECTION_NOTES,
            "caller recovery evidence class or objection notes changed")
    require(receipt.get("observations") == parse_output(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    ), "caller recovery receipt observations changed")
    require(receipt.get("source_mutations_rejected") == 3 and
            receipt.get("output_mutations_rejected") == 6,
            "caller recovery negative controls changed")
    for field in ("native_mgba_frontend_executed",
                  "real_gba_savedata_callback_executed",
                  "natural_os_allocation_failure_observed",
                  "durable_persistence_tested", "sav_interoperability_tested",
                  "stock_gameplay_tested", "physical_flash_tested"):
        require(receipt.get(field) is False,
                "caller recovery receipt overstates evidence: " + field)
    require(receipt.get("host_allocator_fault_injection") is True and
            receipt.get("compiled_original_dispatcher") is True and
            receipt.get("compiled_original_fd_backend") is True and
            receipt.get("compiled_original_caller_body") is True and
            receipt.get("caller_core_struct_is_narrow_fixture") is True,
            "caller recovery evidence class changed")
    return receipt


def reject_output_mutations(output):
    changes = (
        output.replace("save_callbacks=0 close_calls=0 leaked_fd_open=1",
                       "save_callbacks=1 close_calls=1 leaked_fd_open=0", 1),
        output.replace("caller_return=0 open_attempts=1",
                       "caller_return=1 open_attempts=1", 1),
        output.replace("failure_return=0 retry_return=1",
                       "failure_return=1 retry_return=1", 1),
        output.replace("leaked_first_fd_open=1 retry_fd_closed=1",
                       "leaked_first_fd_open=0 retry_fd_closed=1", 1),
        output.replace("allocation_attempts=0 allocation_failures=0 "
                       "save_callbacks=0 errno=ENOENT",
                       "allocation_attempts=1 allocation_failures=0 "
                       "save_callbacks=0 errno=ENOENT", 1),
        output.replace(TERMINAL, "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("caller recovery evidence mutation escaped")
    return len(changes)


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
    receipt = verify_receipt(root / RECEIPT)
    sources = verify_sources(checkout)
    source_mutations_rejected = reject_source_mutations(sources)

    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "caller recovery harness SHA-256 changed")
    marker = "PHASE1_INSERT_PINNED_MCORE_LOADSAVEFILE"
    require(harness.count(marker.encode()) == 1,
            "pinned caller extraction marker changed")
    caller_body = extract_function(sources["src/core/core.c"], CALLER_SIGNATURE)
    expanded_harness = harness.replace(marker.encode(), caller_body.encode())

    with tempfile.TemporaryDirectory(
            prefix="xgba-mgba-core-loadsave-allocation-") as temp:
        temp = Path(temp)
        expanded_source = temp / "caller-allocation-recovery.c"
        binary = temp / "caller-allocation-recovery"
        expanded_source.write_bytes(expanded_harness)
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-DENABLE_VFS", "-DENABLE_VFS_FD", "-ffunction-sections",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(checkout / "src/util/vfs.c"),
            str(checkout / "src/util/vfs/vfs-fd.c"),
            str(expanded_source),
            "-Wl,--wrap=malloc", "-Wl,--wrap=open", "-Wl,--wrap=close",
            "-Wl,--gc-sections", "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned caller/backend witness compile failed:\n" +
                compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned caller/backend witness failed:\n" + executed.stdout)
        observations = parse_output(executed.stdout)
        output_mutations_rejected = reject_output_mutations(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                output_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "execution or negative controls disagree with receipt")
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "schema": "phase1.mgba.core-loadsave-allocation-recovery.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "evidence_class": (
            "COMPILED_EXTRACTED_PINNED_CORE_CALLER_AND_ORIGINAL_POSIX_VFILE_"
            "WITH_HOST_ALLOCATOR_INJECTION"
        ),
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "source_records": expected_source_records(),
        "call_graph": receipt["call_graph"],
        "observations": observations,
        "objection_notes": OBJECTION_NOTES,
        "source_mutations_rejected": source_mutations_rejected,
        "output_mutations_rejected": output_mutations_rejected,
        "host_allocator_fault_injection": True,
        "natural_os_allocation_failure_observed": False,
        "compiled_original_caller_body": True,
        "compiled_original_dispatcher": True,
        "compiled_original_fd_backend": True,
        "caller_core_struct_is_narrow_fixture": True,
        "real_gba_savedata_callback_executed": False,
        "native_mgba_frontend_executed": False,
        "durable_persistence_tested": False,
        "sav_interoperability_tested": False,
        "stock_gameplay_tested": False,
        "physical_flash_tested": False,
        "compile_command": command,
        "compiled_artifact_sha256": artifact_sha256,
        "raw_output": executed.stdout.splitlines(),
    }
    print("PHASE1_CORE_LOADSAVE_ALLOC_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

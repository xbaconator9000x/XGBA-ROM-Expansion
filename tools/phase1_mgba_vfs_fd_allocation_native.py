#!/usr/bin/env python3
"""Compile and exercise pinned POSIX VFile allocation-failure ownership."""
import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
SOURCE = "src/util/vfs/vfs-fd.c"
SOURCE_BLOB = "2535bd0fb76740745ae038d5523ead28658f1035"
SOURCE_SHA256 = "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44"
DISPATCH_SOURCE = "src/util/vfs.c"
DISPATCH_BLOB = "3158c52659a83333cb23aeb0dd7ea4bba35908fc"
DISPATCH_SHA256 = "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06"
DISPATCH_ROW_SHA256 = "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2"
DISPATCH_BODY_SHA256 = "e41233c9f3694959554a63cb8ef2a2fdb456f245a11b26e79a533ff1e1c7a137"
VFS_HEADER = "include/mgba-util/vfs.h"
VFS_HEADER_BLOB = "6c9bd299153af4c3c9cd5487f2425a2481331ee5"
VFS_HEADER_SHA256 = "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656"
VFS_HEADER_ROW_SHA256 = "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd"
STRING_HEADER = "include/mgba-util/string.h"
STRING_HEADER_BLOB = "bc29e28d71bbb4cbb51261a9ded26399c019fb2e"
STRING_HEADER_SHA256 = "80434f7f78cf6fa0bb60a7d3fcc4fe2ee09acf8ac14295a8c9e5c9a6a8715a9d"
STRING_HEADER_ROW_SHA256 = "6c046cb5d36c75862236163fb73973c308d6f61d1c93470e5ce69fc1940ccc77"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROW_SHA256 = "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942"
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-vfs-fd-allocation-failure-20261107.json"
)
DISPATCH_SIGNATURE = "struct VFile* VFileOpen(const char* path, int flags)"
OPEN_SIGNATURE = "struct VFile* VFileOpenFD(const char* path, int flags)"
OPEN_BODY_SHA256 = "1e166c42b6f3ae8a3c1f8b9886e5a00dd1282645dfd37c720c83b1ac1f31ff3e"
FROM_FD_SIGNATURE = "struct VFile* VFileFromFD(int fd)"
FROM_FD_BODY_SHA256 = "13cb910fdbbafbe0712bc985e9f1be0b03f01cd5a61c31173879e491ca3fef63"
HARNESS_SHA256 = "9423b95512c3ee0ecb57a60da6ed174f8c96f60fe6636122359dee7777f0110f"
DONE = "PHASE1_ALLOC_DONE\n"
EXPECTED_LINES = (
    "PHASE1_ALLOC_CASE success caller_return=1 open_calls=1 "
    "allocation_attempts=1 allocation_failures=0 close_calls=1 "
    "fd_open_after_close=0",
    "PHASE1_ALLOC_CASE allocation_failure caller_return=0 open_calls=1 "
    "allocation_attempts=1 allocation_failures=1 close_calls=0 "
    "fd_open_after_return=1",
    "PHASE1_ALLOC_CASE open_failure caller_return=0 open_calls=1 "
    "allocation_attempts=0 allocation_failures=0 errno=ENOENT",
)


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


def verify_source(checkout, source_path, check_tree):
    if check_tree:
        require(git(checkout, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
        require(git(checkout, "rev-parse", "HEAD:" + SOURCE) == SOURCE_BLOB,
                "pinned source tree blob changed")
    raw = source_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256,
            "pinned VFile source SHA-256 changed")
    require(subprocess.check_output(
        ["git", "hash-object", str(source_path)], text=True
    ).strip() == SOURCE_BLOB, "pinned VFile source Git blob changed")

    root = Path(__file__).resolve().parents[1]
    dossier = root / DOSSIER
    require(dossier.is_file(), "pinned machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "machine-dossier Git blob changed")
    dossier_bytes = dossier.read_bytes()
    require(hashlib.sha256(dossier_bytes).hexdigest() == DOSSIER_SHA256,
            "machine-dossier compressed SHA-256 changed")
    expected_rows = {
        DISPATCH_SOURCE: (
            DISPATCH_ROW_SHA256, DISPATCH_BLOB, DISPATCH_SHA256
        ),
        SOURCE: (DOSSIER_ROW_SHA256, SOURCE_BLOB, SOURCE_SHA256),
        VFS_HEADER: (
            VFS_HEADER_ROW_SHA256, VFS_HEADER_BLOB, VFS_HEADER_SHA256
        ),
        STRING_HEADER: (
            STRING_HEADER_ROW_SHA256, STRING_HEADER_BLOB, STRING_HEADER_SHA256
        ),
    }
    matches = {path: [] for path in expected_rows}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and
                    provenance.get("path") in expected_rows):
                path = provenance["path"]
                row_hash = hashlib.sha256(json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()).hexdigest()
                matches[path].append((
                    row_hash, provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                ))
    require(matches == {
        path: [expected] for path, expected in expected_rows.items()
    }, "pinned machine-dossier source rows changed or are ambiguous")

    for path, blob, digest in (
        (DISPATCH_SOURCE, DISPATCH_BLOB, DISPATCH_SHA256),
        (VFS_HEADER, VFS_HEADER_BLOB, VFS_HEADER_SHA256),
        (STRING_HEADER, STRING_HEADER_BLOB, STRING_HEADER_SHA256),
    ):
        dependency = checkout / path
        require(hashlib.sha256(dependency.read_bytes()).hexdigest() == digest,
                "pinned compile dependency SHA-256 changed: " + path)
        require(subprocess.check_output(
            ["git", "hash-object", str(dependency)], text=True
        ).strip() == blob,
            "pinned compile dependency Git blob changed: " + path)

    source = raw.decode("utf-8")
    dispatch = (checkout / DISPATCH_SOURCE).read_text(encoding="utf-8")
    validate_body(
        dispatch, DISPATCH_SIGNATURE, DISPATCH_BODY_SHA256,
        ("#elif defined(ENABLE_VFS_FD)", "return VFileOpenFD(path, flags);"),
    )
    validate_body(
        source, OPEN_SIGNATURE, OPEN_BODY_SHA256,
        ("int fd = open(path, flags, 0666);", "return VFileFromFD(fd);"),
    )
    validate_body(
        source, FROM_FD_SIGNATURE, FROM_FD_BODY_SHA256,
        ("if (fstat(fd, &stat) < 0 || (stat.st_mode & S_IFDIR)) {",
         "close(fd);", "struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
         "if (!vfd) {\n\t\treturn 0;\n\t}"),
    )
    return source


def reject_source_mutations(source):
    body = extract_function(source, FROM_FD_SIGNATURE)
    cases = (
        ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
         "struct VFileFD* vfd = NULL;"),
        ("if (!vfd) {\n\t\treturn 0;\n\t}",
         "if (!vfd) {\n\t\tclose(fd);\n\t\treturn 0;\n\t}"),
        ("close(fd);\n\t\treturn 0;",
         "return 0;"),
    )
    rejected = 0
    for original, replacement in cases:
        require(body.count(original) == 1,
                "allocation-branch mutation anchor changed")
        changed = body.replace(original, replacement, 1)
        try:
            validate_body(
                changed, FROM_FD_SIGNATURE, FROM_FD_BODY_SHA256,
                ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
                 "if (!vfd) {\n\t\treturn 0;\n\t}"),
            )
        except ValueError:
            rejected += 1
    require(rejected == len(cases),
            "a pinned allocation-ownership mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(DONE) and output.count(DONE) == 1,
            "allocation witness lacks a unique terminal marker")
    lines = output[:-len(DONE)].splitlines()
    require(tuple(lines) == EXPECTED_LINES,
            "allocation witness output differs from the pinned contract")
    return {
        "normal_open_and_close": {
            "caller_return": True,
            "open_calls": 1,
            "allocation_attempts": 1,
            "allocation_failures": 0,
            "close_calls": 1,
            "fd_open_after_close": False,
        },
        "injected_allocation_failure": {
            "caller_return": False,
            "open_calls": 1,
            "allocation_attempts": 1,
            "allocation_failures": 1,
            "close_calls": 0,
            "fd_open_after_return": True,
        },
        "open_failure_control": {
            "caller_return": False,
            "open_calls": 1,
            "allocation_attempts": 0,
            "allocation_failures": 0,
            "errno": "ENOENT",
        },
    }


def verify_receipt(path):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "phase1.mgba.vfs-fd-allocation-failure.v1",
            "allocation receipt schema changed")
    require(receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "allocation receipt upstream pin changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "allocation receipt approval status changed")
    source_record = receipt.get("source_record", {})
    require(source_record.get("path") == SOURCE and
            source_record.get("git_blob") == SOURCE_BLOB and
            source_record.get("full_source_sha256") == SOURCE_SHA256 and
            source_record.get("canonical_dossier_row_sha256") ==
            DOSSIER_ROW_SHA256 and
            source_record.get("body_sha256") == {
                OPEN_SIGNATURE: OPEN_BODY_SHA256,
                FROM_FD_SIGNATURE: FROM_FD_BODY_SHA256,
            } and
            source_record.get("license") == "MPL-2.0",
            "allocation receipt source identity or license changed")
    dependencies = receipt.get("dependency_records", [])
    require(receipt.get("callsite_record") == {
        "path": DISPATCH_SOURCE,
        "git_blob": DISPATCH_BLOB,
        "full_source_sha256": DISPATCH_SHA256,
        "canonical_dossier_row_sha256": DISPATCH_ROW_SHA256,
        "body_sha256": DISPATCH_BODY_SHA256,
        "license": "MPL-2.0",
        "review_scope": (
            "Pinned VFileOpen POSIX dispatcher callsite; not whole-file review."
        ),
    }, "allocation receipt caller identity changed")
    expected_dependencies = [
        {
            "path": VFS_HEADER,
            "git_blob": VFS_HEADER_BLOB,
            "full_source_sha256": VFS_HEADER_SHA256,
            "canonical_dossier_row_sha256": VFS_HEADER_ROW_SHA256,
            "license": "MPL-2.0",
            "review_scope": (
                "Pinned VFile callback/API declarations used by the compiled "
                "source closure; not whole-file review."
            ),
        },
        {
            "path": STRING_HEADER,
            "git_blob": STRING_HEADER_BLOB,
            "full_source_sha256": STRING_HEADER_SHA256,
            "canonical_dossier_row_sha256": STRING_HEADER_ROW_SHA256,
            "license": "MPL-2.0",
            "review_scope": (
                "Pinned string declarations included by the original VFile "
                "dispatcher; not whole-file review."
            ),
        },
    ]
    require(dependencies == expected_dependencies,
            "allocation receipt dependency identity changed")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "allocation receipt dossier identity changed")
    require(receipt.get("evidence_class") ==
            "COMPILED_PINNED_POSIX_VFILE_WITH_HOST_ALLOCATOR_INJECTION" and
            receipt.get("observations") == parse_output(
                "\n".join(EXPECTED_LINES) + "\n" + DONE
            ), "allocation receipt execution observations changed")
    require(receipt.get("call_graph") == [
        "caller invokes VFileOpen(path, flags)",
        "VFileOpen selects VFileOpenFD for ENABLE_VFS_FD",
        "VFileOpenFD calls host open(path, flags, 0666)",
        "VFileOpenFD passes returned descriptor to VFileFromFD",
        "VFileFromFD validates descriptor with fstat",
        "VFileFromFD attempts malloc(sizeof(struct VFileFD))",
        "on allocation failure VFileFromFD returns NULL without closing fd",
    ], "allocation receipt call graph changed")
    require(receipt.get("source_mutations_rejected") == 3 and
            receipt.get("output_mutations_rejected") == 5,
            "allocation receipt negative controls changed")
    for field in ("native_mgba_frontend_executed",
                  "naturally_observed_allocation_failure",
                  "stock_gameplay_tested", "sav_interoperability_tested",
                  "durable_persistence_tested", "physical_flash_tested"):
        require(receipt.get(field) is False,
                "allocation receipt overstates evidence: " + field)
    require(receipt.get("compiled_original_translation_unit") is True and
            receipt.get("host_allocator_fault_injection") is True,
            "allocation receipt execution class changed")
    return receipt


def reject_output_mutations(output):
    cases = (
        output.replace("allocation_failures=1", "allocation_failures=0", 1),
        output.replace("close_calls=0 fd_open_after_return=1",
                       "close_calls=1 fd_open_after_return=0", 1),
        output.replace("allocation_attempts=0 allocation_failures=0 errno=ENOENT",
                       "allocation_attempts=1 allocation_failures=0 errno=ENOENT", 1),
        output.replace("PHASE1_ALLOC_DONE\n", "", 1),
        output + "PHASE1_ALLOC_DONE\n",
    )
    for changed in cases:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("allocation evidence mutation escaped")
    return len(cases)


def run(command, timeout=90):
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = (args.checkout or args.source_dir).resolve()
    check_tree = bool(args.checkout)
    source_path = checkout / SOURCE
    root = Path(__file__).resolve().parents[1]
    receipt = verify_receipt(root / RECEIPT)
    if check_tree:
        require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
                "pinned mGBA source tree changed")
    source = verify_source(checkout, source_path, check_tree)
    source_mutations_rejected = reject_source_mutations(source)

    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "allocation witness harness changed")
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-vfs-allocation-") as temp:
        binary = Path(temp) / "vfs-fd-allocation"
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-DENABLE_VFS", "-DENABLE_VFS_FD", "-ffunction-sections",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(checkout / DISPATCH_SOURCE), str(source_path),
            str(args.harness.resolve()),
            "-Wl,--wrap=malloc", "-Wl,--wrap=open", "-Wl,--wrap=close",
            "-Wl,--gc-sections",
            "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned POSIX VFile allocation harness compile failed:\n" +
                compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned POSIX VFile allocation harness failed:\n" +
                executed.stdout)
        observations = parse_output(executed.stdout)
        evidence_mutations_rejected = reject_output_mutations(executed.stdout)
        require(observations == receipt["observations"],
                "runtime output differs from committed allocation receipt")
        require(source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                evidence_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "runtime negative-control count differs from receipt")
        binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "schema": "phase1.mgba.vfs-fd-allocation-failure.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "evidence_class": "COMPILED_PINNED_POSIX_VFILE_WITH_HOST_ALLOCATOR_INJECTION",
        "source_record": {
            "path": SOURCE,
            "git_blob": SOURCE_BLOB,
            "full_source_sha256": SOURCE_SHA256,
            "canonical_dossier_row_sha256": DOSSIER_ROW_SHA256,
            "license": "MPL-2.0",
            "body_sha256": {
                OPEN_SIGNATURE: OPEN_BODY_SHA256,
                FROM_FD_SIGNATURE: FROM_FD_BODY_SHA256,
            },
            "review_scope": (
                "Bounded VFileOpenFD-to-VFileFromFD descriptor ownership "
                "on allocation failure; not whole-file review."
            ),
        },
        "callsite_record": {
            "path": DISPATCH_SOURCE,
            "git_blob": DISPATCH_BLOB,
            "full_source_sha256": DISPATCH_SHA256,
            "canonical_dossier_row_sha256": DISPATCH_ROW_SHA256,
            "body_sha256": DISPATCH_BODY_SHA256,
            "license": "MPL-2.0",
            "review_scope": (
                "Pinned VFileOpen POSIX dispatcher callsite; not whole-file review."
            ),
        },
        "dependency_records": [
            {
                "path": VFS_HEADER,
                "git_blob": VFS_HEADER_BLOB,
                "full_source_sha256": VFS_HEADER_SHA256,
                "canonical_dossier_row_sha256": VFS_HEADER_ROW_SHA256,
                "license": "MPL-2.0",
                "review_scope": (
                    "Pinned VFile callback/API declarations used by the compiled "
                    "source closure; not whole-file review."
                ),
            },
            {
                "path": STRING_HEADER,
                "git_blob": STRING_HEADER_BLOB,
                "full_source_sha256": STRING_HEADER_SHA256,
                "canonical_dossier_row_sha256": STRING_HEADER_ROW_SHA256,
                "license": "MPL-2.0",
                "review_scope": (
                    "Pinned string declarations included by the original VFile "
                    "dispatcher; not whole-file review."
                ),
            },
        ],
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "call_graph": [
            "caller invokes VFileOpen(path, flags)",
            "VFileOpen selects VFileOpenFD for ENABLE_VFS_FD",
            "VFileOpenFD calls host open(path, flags, 0666)",
            "VFileOpenFD passes returned descriptor to VFileFromFD",
            "VFileFromFD validates descriptor with fstat",
            "VFileFromFD attempts malloc(sizeof(struct VFileFD))",
            "on allocation failure VFileFromFD returns NULL without closing fd",
        ],
        "objection_notes": [
            "Allocation failure is deterministically injected by linker-wrapped host malloc; it is not a naturally observed memory-pressure event.",
            "The pinned VFileOpen dispatcher and POSIX vfs-fd.c translation unit are compiled; the complete mGBA core and frontend are not part of this harness.",
            "The descriptor-open observation is process-local on the test host and does not establish save corruption or user-visible behavior.",
            "The witness covers Linux/POSIX mapped-file compilation only; other platform VFile backends are not inferred.",
        ],
        "observations": observations,
        "source_mutations_rejected": source_mutations_rejected,
        "output_mutations_rejected": evidence_mutations_rejected,
        "compiled_original_translation_unit": True,
        "native_mgba_frontend_executed": False,
        "host_allocator_fault_injection": True,
        "naturally_observed_allocation_failure": False,
        "stock_gameplay_tested": False,
        "sav_interoperability_tested": False,
        "durable_persistence_tested": False,
        "physical_flash_tested": False,
        "compiled_artifact_sha256": binary_sha256,
        "compile_command": command,
        "raw_output": executed.stdout.splitlines(),
    }
    print("PHASE1_VFS_ALLOC_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

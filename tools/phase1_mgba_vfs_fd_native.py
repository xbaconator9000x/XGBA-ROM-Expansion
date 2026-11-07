#!/usr/bin/env python3
"""Compile and execute pinned mGBA Linux fd-VFile and savedata-cleanup paths."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FILES = {
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "include/mgba/internal/defines.h": (
        "67b8ec8fd2f51ee2c0c6231443af752158397b03",
        "167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
    ),
    "include/mgba-util/vector.h": (
        "c837379e2102ca6535db2b292233bd4983c3532c",
        "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
    ),
}
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROWS = {
    "src/util/vfs/vfs-fd.c": "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
    "src/gba/savedata.c": "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
    "src/gba/gba.c": "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
    "include/mgba/internal/defines.h": "05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2",
}
CLEAN_SIGNATURE = (
    "void GBASavedataClean(struct GBASavedata* savedata, uint32_t frameCount)"
)
CLEAN_BODY_SHA256 = "3fc3989ccac6c04fa32780fcffcb5cd49ff22ff306826e569c85d52647f701bb"
DIRTY_HELPER_SIGNATURE = (
    "static inline bool mSavedataClean(int* dirty, uint32_t* dirtAge, "
    "uint32_t frameCount)"
)
DIRTY_HELPER_SHA256 = "c34a3ce89da1f2e1823314ea38692d471a762746aa4d9d020c2faa50263d9fcb"
FRAME_ENDED_SIGNATURE = "void GBAFrameEnded(struct GBA* gba)"
FRAME_ENDED_SHA256 = "79da6a49b3bdb7101a950cef81837a5f18d2f1bda6294fa3ffe589ae25679942"
DEINIT_SIGNATURE = "void GBASavedataDeinit(struct GBASavedata* savedata)"
DEINIT_SHA256 = "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2"
FIXTURE_SHA256 = "0669521df7e63cbe3e21a461e37fc1bc46ff802e9594c977830cf063f06c8374"
CASE_LINES = (
    re.compile(r"^PHASE1_VFS_CASE mappings shared_child=(\d+) private_child=(\d+)$"),
    re.compile(
        r"^PHASE1_VFS_CASE cleanup async_ms=(\d+) sync_ms=(\d+) "
        r"fsync=(\d+) rtc=(\d+) dirty=(-?\d+) age=(\d+)$"
    ),
    re.compile(
        r"^PHASE1_VFS_CASE failure async_ms=(\d+) fsync=(\d+) "
        r"rtc=(\d+) dirty=(-?\d+) retried=(\d+) fsync_error=(\d+)$"
    ),
    re.compile(r"^PHASE1_VFS_CASE close active_mapping_survives=(\d+)$"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, *, timeout=60, cwd=None, input_text=None):
    return subprocess.run(
        command, cwd=cwd, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout
    )


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


def verify_sources(source_root, checkout_identity):
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
    verified = {}
    for path, (blob, digest) in FILES.items():
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned tree blob changed: " + path)
        source_path = source_root / path
        source = source_path.read_bytes()
        blob_hash = subprocess.check_output(
            ["git", "hash-object", str(source_path)], text=True
        ).strip()
        require(blob_hash == blob, "pinned source blob changed: " + path)
        require(hashlib.sha256(source).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        verified[path] = source.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier = root / DOSSIER
    require(dossier.is_file(), "pinned compressed machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "machine-dossier Git blob changed")
    dossier_bytes = dossier.read_bytes()
    require(hashlib.sha256(dossier_bytes).hexdigest() == DOSSIER_SHA256,
            "machine-dossier compressed SHA-256 changed")
    rows = {}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and
                    path in DOSSIER_ROWS):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                require(hashlib.sha256(canonical).hexdigest() ==
                        DOSSIER_ROWS[path],
                        "machine-dossier row digest changed: " + path)
                require(provenance.get("git_blob_sha") == FILES[path][0] and
                        provenance.get("source_content_sha256") == FILES[path][1],
                        "machine-dossier source provenance changed: " + path)
                require(path not in rows,
                        'duplicate pinned machine-dossier row: ' + path)
                rows[path] = True
    require(set(rows) == set(DOSSIER_ROWS),
            "machine dossier does not contain every pinned dependency row")

    clean = validate_body(
        verified["src/gba/savedata.c"], CLEAN_SIGNATURE, CLEAN_BODY_SHA256,
        ("mSavedataClean(&savedata->dirty, &savedata->dirtAge, frameCount)",
         "savedata->vf->sync(savedata->vf, savedata->data, size)"),
    )
    validate_body(
        verified["src/gba/savedata.c"], DEINIT_SIGNATURE, DEINIT_SHA256,
        ("savedata->vf->unmap(savedata->vf, savedata->data, size)",
         "savedata->vf = NULL;"),
    )
    validate_body(
        verified["src/gba/gba.c"], FRAME_ENDED_SIGNATURE, FRAME_ENDED_SHA256,
        ("GBASavedataClean(&gba->memory.savedata, gba->video.frameCounter);",
         "callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty"),
    )
    validate_body(
        verified["include/mgba/internal/defines.h"],
        DIRTY_HELPER_SIGNATURE, DIRTY_HELPER_SHA256,
        ("frameCount - *dirtAge > mSAVEDATA_CLEANUP_THRESHOLD",
         "*dirty = 0;"),
    )
    require(clean.count("savedata->vf->sync(savedata->vf, savedata->data, size)") == 1,
            "cleanup sync callback anchor is not unique")
    return verified, clean


def reject_source_mutations(sources):
    cases = (
        ("src/util/vfs/vfs-fd.c", "mmapFlags = MAP_SHARED;",
         "mmapFlags = MAP_PRIVATE;"),
        ("src/util/vfs/vfs-fd.c", "MS_ASYNC", "MS_SYNC"),
        ("src/gba/savedata.c",
         "savedata->vf->sync(savedata->vf, savedata->data, size)",
         "savedata->vf->close(savedata->vf)"),
    )
    rejected = 0
    for path, original, replacement in cases:
        source = sources[path]
        require(source.count(original) == 1,
                "source mutation anchor is not unique: " + original)
        mutated = source.replace(original, replacement, 1).encode()
        if hashlib.sha256(mutated).hexdigest() != FILES[path][1]:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    marker = "PHASE1_VFS_DONE\n"
    require(output.endswith(marker) and output.count(marker) == 1,
            "native VFile output missing unique terminal marker")
    lines = output[:-len(marker)].splitlines()
    require(len(lines) == len(CASE_LINES),
            "native VFile output has missing or extra case records")
    values = []
    for line, pattern in zip(lines, CASE_LINES):
        match = pattern.fullmatch(line)
        require(match is not None, "malformed native VFile case record")
        values.append(tuple(int(value) for value in match.groups()))
    require(values[0] == (165, 34),
            "cross-process shared/private mapping visibility changed")
    require(values[1] == (1, 1, 0, 1, 0, 100),
            "cleanup threshold or VFile sync/unmap observation changed")
    require(values[2] == (1, 2, 0, 0, 0, 1),
            "failed sync, retry, or fsync evidence changed")
    require(values[3] == (1,),
            "closing the VFile unexpectedly invalidated its live mapping")
    return {
        "shared_map_child_byte": values[0][0],
        "private_map_child_byte": values[0][1],
        "cleanup_ms_async_calls": values[1][0],
        "unmap_ms_sync_calls": values[1][1],
        "fsync_calls": values[1][2],
        "cleanup_rtc_write_calls": values[1][3],
        "dirty_after_cleanup": values[1][4],
        "dirty_age_frame": values[1][5],
        "failed_cleanup_async_calls": values[2][0],
        "explicit_fsync_calls": values[2][1],
        "failed_cleanup_rtc_writes": values[2][2],
        "failed_cleanup_dirty": values[2][3],
        "failed_cleanup_retries": values[2][4],
        "fsync_error_propagated": bool(values[2][5]),
        "mapping_survived_vfile_close": bool(values[3][0]),
    }


def reject_evidence_mutations(output):
    cases = (
        output.replace("shared_child=165", "shared_child=164", 1),
        output.replace(" cleanup ", " cleanup-extra ", 1),
        output.replace("async_ms=1", "async_ms=0", 1),
        output.replace("active_mapping_survives=1",
                       "active_mapping_survives=0", 1),
        output.replace("failure async_ms=1", "failure async_ms=0", 1),
        output.replace("fsync_error=1", "fsync_error=0", 1),
    )
    for changed in cases:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("native VFile evidence mutation escaped")
    return len(cases)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    source_root = (args.checkout or args.source_dir).resolve()
    tree_identity_verified = bool(args.checkout)
    sources, clean_body = verify_sources(source_root, tree_identity_verified)
    source_mutations_rejected = reject_source_mutations(sources)

    fixture = args.harness.read_text(encoding="utf-8")
    fixture_digest = hashlib.sha256(fixture.encode()).hexdigest()
    require(fixture_digest == FIXTURE_SHA256,
            "native VFile fixture SHA-256 changed")
    marker = "PHASE1_INSERT_PINNED_GBASAVEDATACLEAN"
    require(fixture.count(marker) == 1, "harness extraction marker drift")
    expanded = fixture.replace(marker, clean_body)

    compiler = "gcc"
    macro_probe = run(
        [compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-dM", "-E",
         "-x", "c", "-"],
        input_text="#include <unistd.h>\n#include <sys/mman.h>\n",
    )
    require(macro_probe.returncode == 0 and
            re.search(r"^#define _POSIX_MAPPED_FILES \d+L?$",
                      macro_probe.stdout, re.M),
            "native compiler does not provide the POSIX mapped-file backend")
    mapped_files_macro = re.search(
        r"^#define _POSIX_MAPPED_FILES (\d+L?)$", macro_probe.stdout, re.M
    ).group(1)

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-vfs-fd-") as directory:
        directory = Path(directory)
        source_path = directory / "vfs-fd-native.c"
        binary = directory / "vfs-fd-native"
        source_path.write_text(expanded, encoding="utf-8")
        actual_compile_command = [
            compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-DENABLE_VFS_FD",
            "-I", str(source_root / "include"), "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", str(source_root / "src/util/vfs/vfs-fd.c"),
            str(source_path), "-Wl,--wrap=msync", "-Wl,--wrap=fsync",
            "-o", str(binary),
        ]
        compiled = run(actual_compile_command, timeout=90)
        require(compiled.returncode == 0,
                "pinned native VFile harness compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned native VFile harness failed:\n" + executed.stdout)
        output = executed.stdout
        observations = parse_output(output)
        evidence_mutations_rejected = reject_evidence_mutations(output)
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "class": "PINNED_MGBA_LINUX_FD_VFILE_SAVEDATA_CLEANUP_NATIVE",
        "mgba_commit": PIN,
        "source_tree_identity_verified": tree_identity_verified,
        "source_git_blobs": {path: value[0] for path, value in FILES.items()},
        "source_sha256": {path: value[1] for path, value in FILES.items()},
        "machine_dossier_blob": DOSSIER_BLOB,
        "machine_dossier_sha256": DOSSIER_SHA256,
        "machine_dossier_row_sha256": DOSSIER_ROWS,
        "gbasavedataclean_body_sha256": CLEAN_BODY_SHA256,
        "mSavedataClean_body_sha256": DIRTY_HELPER_SHA256,
        "GBAFrameEnded_body_sha256": FRAME_ENDED_SHA256,
        "GBASavedataDeinit_body_sha256": DEINIT_SHA256,
        "fixture_sha256": fixture_digest,
        "original_vfs_fd_translation_unit_compiled": True,
        "original_GBASavedataClean_body_executed": True,
        "original_mSavedataClean_inline_helper_executed": True,
        "GBAFrameEnded_caller_compiled": False,
        "posix_mapped_files_macro": mapped_files_macro,
        "compiler_version": subprocess.check_output(
            [compiler, "--version"], text=True
        ).splitlines()[0],
        "compile_command": actual_compile_command,
        "artifact_sha256": artifact_sha256,
        "source_mutations_rejected": source_mutations_rejected,
        "evidence_mutations_rejected": evidence_mutations_rejected,
        "observations": observations,
        "raw_output": output.splitlines(),
        "real_vfile_fd_backend": True,
        "real_temporary_files": True,
        "power_loss_durability_tested": False,
        "stock_gameplay_tested": False,
        "sav_restart_tested": False,
        "physical_flash_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_VFS_FD_EVIDENCE " + json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

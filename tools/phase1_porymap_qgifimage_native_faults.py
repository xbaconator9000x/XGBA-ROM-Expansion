#!/usr/bin/env python3
"""Compile pinned QtGifImage/GIFLIB and exercise bounded native fault cases."""
import argparse
import gzip
import hashlib
import json
import os
import shlex
import subprocess
import zipfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
DOSSIER_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
DOSSIER_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"
GIFLIB = "src/vendor/QtGifImage/3rdParty/giflib/"
QTGIF = "src/vendor/QtGifImage/gifimage/"
NATIVE_SOURCE_PATHS = (
    QTGIF + "qgifimage.cpp",
    QTGIF + "qgifimage.h",
    QTGIF + "qgifimage_p.h",
    QTGIF + "qgifglobal.h",
    GIFLIB + "dgif_lib.c",
    GIFLIB + "egif_lib.c",
    GIFLIB + "gif_err.c",
    GIFLIB + "gif_hash.c",
    GIFLIB + "gif_hash.h",
    GIFLIB + "gifalloc.c",
    GIFLIB + "quantize.c",
    GIFLIB + "gif_lib.h",
    GIFLIB + "gif_lib_private.h",
    GIFLIB + "COPYING",
)
GIFLIB_SOURCES = (
    "dgif_lib.c", "egif_lib.c", "gif_err.c", "gif_hash.c",
    "gifalloc.c", "quantize.c",
)
SOURCE_ROLES = {
    QTGIF + "qgifimage.cpp": "Complete QtGifImage codec implementation and focal error-result/close ownership paths.",
    QTGIF + "qgifimage.h": "Public QGifImage API exercised by the native harness.",
    QTGIF + "qgifimage_p.h": "Private frame state and codec method declarations.",
    QTGIF + "qgifglobal.h": "QtGifImage import/export macro used by the native build.",
    GIFLIB + "dgif_lib.c": "Decoder open/slurp/close implementations and error cleanup.",
    GIFLIB + "egif_lib.c": "Encoder open/spew/close implementations and early returns.",
    GIFLIB + "gif_err.c": "GIFLIB error strings linked into original codec build.",
    GIFLIB + "gif_hash.c": "GIFLIB encoder hash-table implementation.",
    GIFLIB + "gif_hash.h": "GIFLIB hash-table dependency included by its private header.",
    GIFLIB + "gifalloc.c": "GIFLIB image, extension, and color-map allocation/free helpers.",
    GIFLIB + "quantize.c": "Palette quantization source included by the pinned qmake target.",
    GIFLIB + "gif_lib.h": "GIFLIB public declarations and result/error constants.",
    GIFLIB + "gif_lib_private.h": "GIFLIB private declarations shared by decoder/encoder sources.",
    GIFLIB + "COPYING": "GIFLIB notice bytes; no legal compliance conclusion.",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True
    ).strip()


def source_function(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start:pos + 1]
    raise ValueError("unclosed source function: " + marker)


def verify_source_contract(sources):
    qgif = sources[QTGIF + "qgifimage.cpp"]
    dgif = sources[GIFLIB + "dgif_lib.c"]
    egif = sources[GIFLIB + "egif_lib.c"]
    pub = source_function(qgif, "bool QGifImage::save(QIODevice *device)")
    load = source_function(qgif, "bool QGifImage::load(QIODevice *device)")
    private_save = source_function(qgif, "bool QGifImagePrivate::save(QIODevice *device) const")
    private_load = source_function(qgif, "bool QGifImagePrivate::load(QIODevice *device)")
    spew = source_function(egif, "EGifSpew(GifFileType *GifFileOut)")
    slurp = source_function(dgif, "DGifSlurp(GifFileType *GifFile)")
    giflib_notice = sources[GIFLIB + "COPYING"]

    required = (
        ("public save uses bitwise OR", "device->openMode() | QIODevice::WriteOnly" in pub),
        ("public load uses bitwise OR", "device->openMode() | QIODevice::ReadOnly" in load),
        ("private save calls but ignores EGifSpew result",
         "EGifSpew(gifFile);" in private_save and
         "if (EGifSpew" not in private_save and
         private_save.rfind("return true;") > private_save.index("EGifSpew(gifFile);")),
        ("private load returns on slurp error before close",
         "if (DGifSlurp(gifFile) == GIF_ERROR)\n        return false;" in private_load and
         private_load.index("return false;") < private_load.index("DGifCloseFile(gifFile);")),
        ("GIFLIB spew has early error returns before its close",
         "if (EGifPutScreenDesc" in spew and
         spew.index("return (GIF_ERROR);") < spew.index("EGifCloseFile(GifFileOut)") and
         "if (EGifCloseFile(GifFileOut) == GIF_ERROR)" in spew),
        ("GIFLIB slurp error returns do not close the file",
         "if (DGifGetRecordType(GifFile, &RecordType) == GIF_ERROR)\n"
         "            return (GIF_ERROR);" in slurp and
         "return (GIF_ERROR);" in slurp and "DGifCloseFile" not in slurp),
        ("GIFLIB close frees saved images and private state",
         "GifFreeSavedImages(GifFile);" in dgif and
         "free((char *)GifFile->Private);" in dgif),
        ("QtGifImage/GIFLIB notices are present as separate bytes",
         "Copyright (c) 2013 Debao Zhang" in qgif and
         "Permission is hereby granted" in qgif and
         "Copyright (c) 1997  Eric S. Raymond" in giflib_notice and
         "Permission is hereby granted" in giflib_notice and
         "THE SOFTWARE IS PROVIDED" in giflib_notice),
    )
    for label, valid in required:
        require(valid, "pinned source contract changed: " + label)
    return [label for label, _ in required]


def load_rows(workpack):
    raw_archive = workpack.read_bytes()
    require(digest(raw_archive) == WORKPACK_SHA256, "workpack ZIP hash mismatch")
    with zipfile.ZipFile(workpack) as archive:
        compressed = archive.read(DOSSIER_MEMBER)
    require(digest(compressed) == DOSSIER_SHA256,
            "compressed candidate dossier hash mismatch")
    rows = {}
    for raw_row in gzip.decompress(compressed).splitlines():
        row = json.loads(raw_row)
        provenance = row.get("provenance", {})
        if provenance.get("repository") != "huderlem/porymap":
            continue
        if provenance.get("pinned_revision") != PIN:
            continue
        path = provenance.get("path")
        if path in NATIVE_SOURCE_PATHS:
            require(path not in rows, "duplicate pinned candidate row: " + path)
            rows[path] = (row, digest(raw_row))
    require(set(rows) == set(NATIVE_SOURCE_PATHS),
            "native source candidate rows incomplete")
    return rows


def verify_candidate_row(path, row, source_data):
    provenance = row.get("provenance", {})
    review = row.get("review", {})
    require(provenance.get("repository") == "huderlem/porymap" and
            provenance.get("pinned_revision") == PIN and
            provenance.get("path") == path,
            "candidate identity mismatch: " + path)
    require(provenance.get("git_blob_sha") == git_blob_sha(source_data),
            "candidate Git blob mismatch: " + path)
    sha = provenance.get("source_content_sha256")
    require(not sha or sha == digest(source_data),
            "candidate source SHA-256 mismatch: " + path)
    require(review.get("semantic_signoff") is False and
            review.get("reviewer") is None,
            "candidate inventory now carries semantic approval: " + path)


def git_blob_sha(data):
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def source_records(root, rows):
    records = []
    sources = {}
    for path in NATIVE_SOURCE_PATHS:
        data = (root / path).read_bytes()
        row, row_sha = rows[path]
        verify_candidate_row(path, row, data)
        require(git(root, "hash-object", path) == git_blob_sha(data),
                "Git object and computed blob differ: " + path)
        records.append({
            "path": path,
            "git_blob_sha1": git_blob_sha(data),
            "full_source_sha256": digest(data),
            "candidate_row_sha256": row_sha,
            "whole_file_scope": SOURCE_ROLES[path],
            "candidate_source_sha256_present": bool(
                row.get("provenance", {}).get("source_content_sha256")
            ),
            "inventory_status": row.get("review", {}).get("status"),
            "disposition": "NEEDS_EVIDENCE",
        })
        sources[path] = data.decode("utf-8")
    return records, sources


def source_mutation_controls(sources):
    mutations = (
        (QTGIF + "qgifimage.cpp", "device->openMode() | QIODevice::WriteOnly",
         "device->openMode() & QIODevice::WriteOnly"),
        (QTGIF + "qgifimage.cpp", "device->openMode() | QIODevice::ReadOnly",
         "device->openMode() & QIODevice::ReadOnly"),
        (QTGIF + "qgifimage.cpp", "EGifSpew(gifFile);",
         "if (EGifSpew(gifFile) == GIF_ERROR) return false;"),
        (QTGIF + "qgifimage.cpp",
         "if (DGifSlurp(gifFile) == GIF_ERROR)\n        return false;",
         "if (DGifSlurp(gifFile) == GIF_ERROR) {\n"
         "        DGifCloseFile(gifFile);\n        return false;\n    }"),
        (GIFLIB + "egif_lib.c", "if (EGifCloseFile(GifFileOut) == GIF_ERROR)",
         "if (0 && EGifCloseFile(GifFileOut) == GIF_ERROR)"),
        (GIFLIB + "dgif_lib.c", "if (DGifGetRecordType(GifFile, &RecordType) == GIF_ERROR)\n"
         "            return (GIF_ERROR);",
         "if (DGifGetRecordType(GifFile, &RecordType) == GIF_ERROR)\n"
         "            return GIF_OK;"),
        (GIFLIB + "dgif_lib.c", "int\nDGifSlurp(GifFileType *GifFile)",
         "int\nDGifSlurp(PHASE1_MUTATION)"),
        (GIFLIB + "COPYING", "Permission is hereby granted",
         "PHASE1_MUTATED_NOTICE"),
    )
    rejected = 0
    for path, old, new in mutations:
        source = sources[path]
        require(old in source, "source mutation anchor missing: " + path)
        changed = dict(sources)
        changed[path] = source.replace(old, new, 1)
        try:
            verify_source_contract(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + path + ":" + old)
    return rejected


def candidate_mutation_controls(rows):
    path = QTGIF + "qgifimage.cpp"
    row = rows[path][0]
    # Use the pinned source identity without re-opening unrelated files.
    provenance = row["provenance"]
    synthetic = b"candidate mutation fixture"
    correct_blob = git_blob_sha(synthetic)
    test_row = {
        "provenance": {
            "repository": provenance["repository"],
            "pinned_revision": provenance["pinned_revision"],
            "path": path,
            "git_blob_sha": correct_blob,
            "source_content_sha256": digest(synthetic),
        },
        "review": {"semantic_signoff": False, "reviewer": None},
    }
    mutations = (
        lambda r: {**r, "provenance": {**r["provenance"],
                                      "pinned_revision": "deadbeef"}},
        lambda r: {**r, "provenance": {**r["provenance"], "path": "wrong"}},
        lambda r: {**r, "provenance": {**r["provenance"],
                                      "git_blob_sha": "0" * 40}},
        lambda r: {**r, "provenance": {**r["provenance"],
                                      "source_content_sha256": "0" * 64}},
        lambda r: {**r, "review": {"semantic_signoff": True, "reviewer": None}},
        lambda r: {**r, "review": {"semantic_signoff": False,
                                   "reviewer": "unverified"}},
    )
    rejected = 0
    for mutate in mutations:
        try:
            verify_candidate_row(path, mutate(test_row), synthetic)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("candidate row mutation escaped")
    return rejected


def compile_and_run(root, build_dir, harness):
    build_dir.mkdir(parents=True, exist_ok=True)
    log_path = build_dir / "compile-and-run.log"
    log_parts = []

    def run(command, env=None):
        rendered = shlex.join([str(part) for part in command])
        log_parts.append("$ " + rendered)
        proc = subprocess.run(command, cwd=root, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log_parts.append(proc.stdout)
        if proc.returncode:
            log_path.write_text("\n".join(log_parts))
            raise ValueError("native QtGifImage command failed: " + rendered)

    cflags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "Qt6Gui", "Qt6Core"], text=True
    ))
    libs = shlex.split(subprocess.check_output(
        ["pkg-config", "--libs", "Qt6Gui", "Qt6Core"], text=True
    ))
    qgif_root = root / QTGIF
    giflib_root = root / GIFLIB
    objects = []
    for source_name in GIFLIB_SOURCES:
        source = giflib_root / source_name
        obj = build_dir / (source_name + ".o")
        run(["cc", "-std=gnu99", "-fPIC", "-O0", "-g", "-I", str(giflib_root),
             "-c", str(source), "-o", str(obj)])
        objects.append(str(obj))
    library = build_dir / "libporymap_giflib.so"
    run(["cc", "-shared", *objects, "-o", str(library)])
    binary = build_dir / "phase1-qgifimage-native-faults"
    wraps = [
        "DGifOpen", "DGifSlurp", "DGifCloseFile",
        "EGifOpen", "EGifSpew",
    ]
    command = [
        "g++", "-std=c++17", "-fPIC", "-O0", "-g", "-DGIFIMAGE_NO_LIB",
        "-I", str(qgif_root), "-I", str(giflib_root), *cflags,
        str(harness), str(qgif_root / "qgifimage.cpp"),
        "-L", str(build_dir), "-lporymap_giflib",
        *["-Wl,--wrap=" + symbol for symbol in wraps],
        "-Wl,--export-dynamic", "-Wl,-rpath," + str(build_dir),
        *libs, "-ldl", "-o", str(binary),
    ]
    run(command)
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["LD_LIBRARY_PATH"] = str(build_dir) + os.pathsep + env.get(
        "LD_LIBRARY_PATH", ""
    )
    run([str(binary)], env)
    log_path.write_text("\n".join(log_parts))
    result_lines = [
        line.split("=", 1)[1]
        for line in log_parts[-1].splitlines()
        if line.startswith("PHASE1_QTGIF_NATIVE=")
    ]
    require(len(result_lines) == 1, "native harness result missing or duplicated")
    result = json.loads(result_lines[0])
    verify_native_observations(result)
    return result, log_path


def verify_native_observations(native):
    expected = {
        "status": "PASS_NATIVE_BOUNDED_WITNESS",
        "positive_save": True,
        "positive_egif_spew_result": 1,
        "positive_egif_close_calls": 1,
        "positive_load": True,
        "positive_frames": 1,
        "positive_dgif_slurp_result": 1,
        "positive_dgif_close_calls": 1,
        "truncated_load_returned_false": True,
        "truncated_dgif_slurp_result": 0,
        "truncated_dgif_close_calls": 0,
        "injected_egif_spew_result": 0,
        "injected_save_returned_true": True,
        "injected_egif_close_calls": 0,
        "write_only_load_entered_dgif_open": True,
        "read_only_save_returned_true": True,
        "read_only_egif_spew_result": 0,
        "read_only_egif_close_calls": 0,
        "allocation_leak_measured": False,
    }
    for key, value in expected.items():
        require(native.get(key) == value,
                "native witness result mismatch: " + key)
    require(native.get("positive_gif_bytes", 0) > 20,
            "native positive GIF output too short")
    require(native.get("injected_write_attempts", 0) > 0,
            "native failure device was not exercised")


def verify_report_boundary(report):
    require(report.get("all_file_dispositions") == "NEEDS_EVIDENCE" and
            report.get("independent_approvals") == 0 and
            report.get("source_pin") == PIN,
            "report promotes evidence or changes source pin")
    require(report.get("evidence_classes") == [
                "original_source_inspection",
                "compiled_original_qtgifimage_and_giflib_with_link_wrappers_and_symbol_interposition",
            ],
            "report evidence classes overstated")
    require(report.get("native_observations", {}).get(
                "allocation_leak_measured") is False,
            "report claims allocator leak measurement")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--workpack", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.porymap.resolve()
    require(git(root, "rev-parse", "HEAD") == PIN, "Porymap pin mismatch")

    rows = load_rows(args.workpack)
    records, sources = source_records(root, rows)
    source_findings = verify_source_contract(sources)
    source_negatives = source_mutation_controls(sources)
    receipt_negatives = candidate_mutation_controls(rows)
    native, log_path = compile_and_run(root, args.build_dir.resolve(),
                                       args.harness.resolve())

    report = {
        "schema": "phase1-porymap-qgifimage-native-fault-witness-v1",
        "source_pin": PIN,
        "candidate_workpack_sha256": WORKPACK_SHA256,
        "candidate_dossier_compressed_sha256": DOSSIER_SHA256,
        "source_records": records,
        "all_file_dispositions": "NEEDS_EVIDENCE",
        "independent_approvals": 0,
        "evidence_classes": [
            "original_source_inspection",
            "compiled_original_qtgifimage_and_giflib_with_link_wrappers_and_symbol_interposition",
        ],
        "source_findings": [
            {
                "id": "qiodevice-open-mode-or",
                "finding": "ReadOnly/WriteOnly mode predicates use bitwise OR; mismatched open modes reach the decoder/encoder path.",
                "status": "OBSERVED_NATIVE_BOUNDED",
            },
            {
                "id": "ignored-egif-spew-error",
                "finding": "QGifImage::save(QIODevice*) returns true after original EGifSpew returns GIF_ERROR on injected write failure.",
                "status": "OBSERVED_NATIVE_BOUNDED",
            },
            {
                "id": "giflib-close-ownership",
                "finding": "EGifSpew closes on its success path; its early error return skips that close. QGifImage load returns on DGifSlurp error before DGifCloseFile.",
                "status": "OBSERVED_NATIVE_BOUNDED",
            },
            {
                "id": "allocation-lifetime",
                "finding": "Close is not invoked on the exercised error paths; allocator leak magnitude or process-wide impact was not measured.",
                "status": "NEEDS_EVIDENCE",
            },
            {
                "id": "gui-and-real-file-runtime",
                "finding": "No full Porymap GUI, filesystem durability, long-run repetition, or user-facing failure handling was tested.",
                "status": "NEEDS_EVIDENCE",
            },
        ],
        "source_contracts_checked": source_findings,
        "native_observations": native,
        "negative_controls": {
            "source_mutations_rejected": source_negatives,
            "candidate_provenance_receipt_mutations_rejected": receipt_negatives,
            "native_result_positive_and_failure_controls_checked": True,
        },
        "log_path": str(log_path),
        "limits": [
            "Native means original pinned qgifimage.cpp and GIFLIB C sources compiled against system Qt6 Core/Gui, with link-time wrapper counters and controlled QIODevice fixtures.",
            "No vendored source was modified; link wrappers are test instrumentation.",
            "No allocation leak was claimed or measured.",
            "All per-file dispositions remain NEEDS_EVIDENCE; this is not independent semantic approval.",
        ],
    }
    verify_report_boundary(report)
    mutations = (
        {**report, "all_file_dispositions": "APPROVED"},
        {**report, "independent_approvals": 1},
        {**report, "source_pin": "deadbeef"},
        {**report, "native_observations": {
            **native, "allocation_leak_measured": True,
        }},
    )
    for changed in mutations:
        try:
            verify_report_boundary(changed)
        except ValueError:
            continue
        raise ValueError("report disposition/evidence mutation escaped")
    report["negative_controls"]["report_mutations_rejected"] = len(mutations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": "PASS_NATIVE_BOUNDED_WITNESS",
        "source_count": len(records),
        "native_observations": native,
        "negative_controls": report["negative_controls"],
        "report": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

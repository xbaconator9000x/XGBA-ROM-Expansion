#!/usr/bin/env python3
"""Verify the pinned Porymap QtGifImage/FEX source and build/license boundary."""
import argparse
import gzip
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
DOSSIER_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
DOSSIER_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"

NEW_PATHS = (
    "src/vendor/QtGifImage/gifimage/doc/qtgifimage.qdocconf",
    "src/vendor/QtGifImage/gifimage/doc/snippets/doc_src_qtgifimage.cpp",
    "src/vendor/QtGifImage/gifimage/doc/snippets/doc_src_qtgifimage.pro",
    "src/vendor/QtGifImage/gifimage/doc/src/examples.qdoc",
    "src/vendor/QtGifImage/gifimage/doc/src/index.qdoc",
    "src/vendor/QtGifImage/gifimage/doc/src/qtgifimage.qdoc",
    "src/vendor/QtGifImage/gifimage/doc/src/usage.qdoc",
    "src/vendor/QtGifImage/gifimage/gifimage.pro",
    "src/vendor/QtGifImage/gifimage/qtgifimage.pri",
    "src/vendor/QtGifImage/gifimage/qgifimage.cpp",
    "src/vendor/QtGifImage/gifimage/qgifimage.h",
    "src/vendor/QtGifImage/gifimage/qgifimage_p.h",
    "src/vendor/QtGifImage/gifimage/qgifglobal.h",
    "src/vendor/QtGifImage/src.pro",
    "src/vendor/QtGifImage/3rdParty/giflib.pri",
    "src/vendor/QtGifImage/3rdParty/giflib/AUTHORS",
    "src/vendor/QtGifImage/3rdParty/giflib/COPYING",
    "src/vendor/QtGifImage/3rdParty/giflib/README",
    "src/vendor/QtGifImage/3rdParty/giflib/dgif_lib.c",
    "src/vendor/QtGifImage/3rdParty/giflib/egif_lib.c",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_err.c",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_font.c",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_hash.c",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_hash.h",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_lib.h",
    "src/vendor/QtGifImage/3rdParty/giflib/gif_lib_private.h",
    "src/vendor/QtGifImage/3rdParty/giflib/gifalloc.c",
    "src/vendor/QtGifImage/3rdParty/giflib/quantize.c",
    "include/lib/fex/LICENSE",
    "include/lib/fex/README",
    "include/lib/fex/array.h",
    "include/lib/fex/array_value.h",
    "include/lib/fex/define_statement.h",
    "include/lib/fex/lexer.h",
    "include/lib/fex/parser.h",
    "src/lib/fex/LICENSE",
    "src/lib/fex/README",
    "src/lib/fex/lexer.cpp",
    "src/lib/fex/parser.cpp",
    "src/lib/fex/parser_util.cpp",
)

CONTEXT_PATHS = (
    "LICENSE.md",
    "porymap.pro",
    "src/core/parseutil.cpp",
    "src/ui/loadingscreen.cpp",
    "include/ui/loadingscreen.h",
    "src/ui/mapimageexporter.cpp",
    "include/ui/mapimageexporter.h",
    "include/lib/orderedmap.h",
    "include/lib/orderedjson.h",
    "src/lib/orderedjson.cpp",
)

QTGIF_PREFIX = "src/vendor/QtGifImage/"
GIFLIB_PREFIX = QTGIF_PREFIX + "3rdParty/giflib/"
FEX_PREFIXES = ("include/lib/fex/", "src/lib/fex/")
QTGIF_SOURCES = (
    "dgif_lib.c", "egif_lib.c", "gif_err.c", "gif_hash.c",
    "gifalloc.c", "quantize.c",
)
FEX_LICENSE_NOTICE = "MIT License"
GIFLIB_LICENSE_NOTICE = "Permission is hereby granted"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True
    ).strip()


def load_candidate_rows(workpack):
    require(sha256(workpack.read_bytes()) == WORKPACK_SHA256,
            "candidate workpack SHA-256 mismatch")
    with zipfile.ZipFile(workpack) as archive:
        compressed = archive.read(DOSSIER_MEMBER)
    require(sha256(compressed) == DOSSIER_SHA256,
            "compressed candidate dossier SHA-256 mismatch")
    rows = {}
    for raw in gzip.decompress(compressed).splitlines():
        row = json.loads(raw)
        provenance = row.get("provenance", {})
        if provenance.get("repository") != "huderlem/porymap":
            continue
        path = provenance.get("path")
        if path in NEW_PATHS or path in CONTEXT_PATHS:
            require(path not in rows, "duplicate candidate row: " + path)
            rows[path] = (row, sha256(raw))
    require(set(NEW_PATHS).issubset(rows), "candidate dossier file missing")
    require(set(CONTEXT_PATHS).issubset(rows), "context dossier file missing")
    return rows


def verify_candidate_row(path, row):
    provenance = row.get("provenance", {})
    review = row.get("review", {})
    require(provenance.get("repository") == "huderlem/porymap",
            "wrong source repository: " + path)
    require(provenance.get("pinned_revision") == PIN, "wrong source pin: " + path)
    require(provenance.get("path") == path, "wrong source path: " + path)
    require(not review.get("semantic_signoff"),
            "candidate inventory claims semantic approval: " + path)
    require(review.get("status") in (
                "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
                "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            ),
            "candidate inventory disposition changed: " + path)
    require(review.get("reviewer") is None,
            "candidate inventory has a reviewer receipt: " + path)


def verify_source_bytes(path, data, row):
    provenance = row.get("provenance", {})
    blob = hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()
    require(provenance.get("git_blob_sha") == blob,
            "original Git blob mismatch: " + path)
    file_sha = sha256(data)
    recorded_sha = provenance.get("source_content_sha256")
    if recorded_sha:
        require(recorded_sha == file_sha,
                "candidate source SHA-256 mismatch: " + path)
    return blob, file_sha, bool(recorded_sha)


def verify_file(root, path, candidate):
    row, row_sha = candidate
    verify_candidate_row(path, row)
    data = (root / path).read_bytes()
    blob, file_sha, recorded_sha = verify_source_bytes(path, data, row)
    require(git(root, "hash-object", path) == blob,
            "Git and computed object IDs differ: " + path)
    return {
        "path": path,
        "source_repository": "huderlem/porymap",
        "source_revision": PIN,
        "git_blob_sha1": blob,
        "full_source_sha256": file_sha,
        "candidate_row_sha256": row_sha,
        "candidate_source_sha256_present": recorded_sha,
        "original_inventory_status": row.get("review", {}).get("status"),
        "disposition": "NEEDS_EVIDENCE",
        "semantic_approval": False,
    }


def read(root, path):
    return (root / path).read_text(encoding="utf-8")


def verify_source_contract(root):
    project = read(root, "porymap.pro")
    gif_pri = read(root, "src/vendor/QtGifImage/gifimage/qtgifimage.pri")
    giflib_pri = read(root, "src/vendor/QtGifImage/3rdParty/giflib.pri")
    parseutil = read(root, "src/core/parseutil.cpp")
    qgif = read(root, QTGIF_PREFIX + "gifimage/qgifimage.cpp")
    parser_h = read(root, "include/lib/fex/parser.h")
    lexer_h = read(root, "include/lib/fex/lexer.h")
    parser_util = read(root, "src/lib/fex/parser_util.cpp")

    require("src/vendor/QtGifImage/gifimage/qtgifimage.pri" in project,
            "Porymap application no longer includes QtGifImage")
    require("src/lib/fex/lexer.cpp" in project and
            "src/lib/fex/parser.cpp" in project,
            "FEX parser/lexer source build edge changed")
    require("src/lib/fex/parser_util.cpp" not in project,
            "FEX parser_util.cpp build status changed; reevaluate closure")
    require("parser_util.h" not in parser_h + lexer_h + project,
            "FEX parser_util.h edge unexpectedly appeared")
    require(not (root / "include/lib/fex/parser_util.h").exists(),
            "FEX parser_util.h now exists; reevaluate orphan-source finding")
    require('#include "lib/fex/parser_util.h"' in parser_util,
            "FEX parser_util.cpp dependency changed")
    require("fex::Parser" in parseutil and "fex::Lexer" in parseutil,
            "Porymap FEX caller edge changed")
    require("orderedmap.h" in parser_h,
            "FEX ordered-map dependency changed")

    require("qgifimage.cpp" in gif_pri and "giflib.pri" in gif_pri,
            "QtGifImage implementation/GIFLIB edge changed")
    for source in QTGIF_SOURCES:
        require(source in giflib_pri, "GIFLIB build source missing: " + source)
    require("gif_font.c" not in giflib_pri,
            "GIFLIB font source build status changed")
    require((root / (GIFLIB_PREFIX + "gif_font.c")).is_file(),
            "tracked but unbuilt GIFLIB font source disappeared")
    for caller in ("src/ui/loadingscreen.cpp", "src/ui/mapimageexporter.cpp"):
        require("qgifimage.h" in read(root, caller),
                "QtGifImage caller edge changed: " + caller)

    require(FEX_LICENSE_NOTICE in read(root, "include/lib/fex/LICENSE"),
            "FEX notice text changed")
    require((root / "include/lib/fex/LICENSE").read_bytes() ==
            (root / "src/lib/fex/LICENSE").read_bytes(),
            "duplicated FEX license notices differ")
    require((root / "include/lib/fex/README").read_bytes() ==
            (root / "src/lib/fex/README").read_bytes(),
            "duplicated FEX READMEs differ")
    require(GIFLIB_LICENSE_NOTICE in read(root, GIFLIB_PREFIX + "COPYING"),
            "GIFLIB notice text changed")
    for path in (
        "src/vendor/QtGifImage/gifimage/qgifimage.cpp",
        "src/vendor/QtGifImage/gifimage/qgifimage.h",
        "src/vendor/QtGifImage/gifimage/qgifimage_p.h",
        "src/vendor/QtGifImage/gifimage/qgifglobal.h",
    ):
        notice = read(root, path)
        require("Permission is hereby granted" in notice and
                "included in all copies or substantial portions" in notice,
                "QtGifImage source notice changed: " + path)
    require("GNU LESSER GENERAL PUBLIC LICENSE" in read(root, "LICENSE.md"),
            "Porymap root license notice changed")
    require("QIODevice::WriteOnly" in qgif and "QIODevice::ReadOnly" in qgif,
            "QtGifImage device mode checks changed; reevaluate source objection")
    require("device->openMode() | QIODevice::WriteOnly" in qgif and
            "device->openMode() | QIODevice::ReadOnly" in qgif,
            "QtGifImage open-mode predicates changed; reevaluate source objection")
    return {
        "qtgifimage_in_application_build": True,
        "giflib_sources_in_application_build": list(QTGIF_SOURCES),
        "gif_font_c_in_source_tree_but_not_project_build": True,
        "fex_lexer_parser_in_application_build": True,
        "fex_parser_util_cpp_not_in_application_build": True,
        "fex_parser_util_header_absent": True,
        "fex_parser_util_cpp_includes_missing_header": True,
        "fex_orderedmap_dependency": "include/lib/orderedmap.h",
        "qtgifimage_callers": [
            "src/ui/loadingscreen.cpp", "src/ui/mapimageexporter.cpp",
        ],
        "source_only_qgifimage_mode_predicate_observation": (
            "Pinned source uses bitwise OR in the ReadOnly/WriteOnly mode "
            "checks; save also ignores EGifSpew's result and leaves "
            "EGifCloseFile commented out, while a DGifSlurp error returns "
            "before DGifCloseFile. These are source observations, not runtime evidence."
        ),
        "distribution_notice_scope": (
            "Porymap root LGPL notice; embedded QtGifImage MIT-style notices; "
            "GIFLIB COPYING notice; duplicate FEX MIT notices. No legal conclusion."
        ),
    }


def classify(path):
    if path.endswith(("LICENSE", "COPYING")):
        return "license_notice"
    if "/doc/" in path or path.endswith(("README", "README.md", "AUTHORS")):
        return "documentation_or_provenance"
    if path.endswith((".pri", ".pro")):
        return "build_definition"
    if path.startswith(FEX_PREFIXES):
        return "fex_parser_source"
    if path.startswith(GIFLIB_PREFIX):
        return "giflib_source"
    return "qtgifimage_source"


def file_role(path):
    roles = {
        "qtgifimage.qdocconf": "Qt documentation build configuration",
        "doc_src_qtgifimage.cpp": "QtGifImage documentation example code",
        "doc_src_qtgifimage.pro": "documentation-example qmake target",
        "examples.qdoc": "QtGifImage examples documentation",
        "index.qdoc": "QtGifImage documentation landing page",
        "usage.qdoc": "QtGifImage usage documentation",
        "gifimage.pro": "standalone QtGifImage module/documentation target",
        "qtgifimage.pri": "Porymap QtGifImage source/header inclusion fragment",
        "qgifimage.cpp": "QGifImage frame loading, decoding, and encoding implementation",
        "qgifimage.h": "public QGifImage API and frame operations",
        "qgifimage_p.h": "private QGifImage state and implementation declarations",
        "qgifglobal.h": "QtGifImage symbol export/import definitions",
        "src.pro": "QtGifImage subdirectory qmake project",
        "giflib.pri": "GIFLIB include and compiled-source manifest",
        "AUTHORS": "GIFLIB author attribution",
        "COPYING": "GIFLIB license notice",
        "README": "vendored subsystem usage/provenance documentation",
        "dgif_lib.c": "GIF input/decode implementation",
        "egif_lib.c": "GIF output/encode implementation",
        "gif_err.c": "GIFLIB error strings and error-code helpers",
        "gif_font.c": "GIFLIB font data/helpers; tracked but omitted from qmake source list",
        "gif_hash.c": "GIFLIB hash-table implementation",
        "gif_hash.h": "GIFLIB hash-table declarations",
        "gif_lib.h": "GIFLIB public types and API declarations",
        "gif_lib_private.h": "GIFLIB private types and implementation declarations",
        "gifalloc.c": "GIFLIB allocation and deallocation helpers",
        "quantize.c": "GIF palette quantization implementation",
        "LICENSE": "FEX MIT license text",
        "array.h": "FEX array/initializer representation",
        "array_value.h": "FEX array value and value-pair representation",
        "define_statement.h": "FEX define-statement representation",
        "lexer.h": "FEX lexer interface and token definitions",
        "parser.h": "FEX parser interface and parsed array representation",
        "lexer.cpp": "FEX source lexer implementation",
        "parser.cpp": "FEX source parser implementation",
        "parser_util.cpp": "unbuilt FEX parser utility implementation",
    }
    if path.endswith("qtgifimage.qdoc"):
        return "QtGifImage class/API documentation"
    return roles.get(Path(path).name, "vendored documentation or provenance record")


def file_objection(path, component):
    if component == "license_notice":
        return ("Notice text is verified, but a complete distribution manifest, "
                "downstream notice bundle, and independent legal review are absent.")
    if component == "documentation_or_provenance":
        return ("This file is inventoried and hash-bound; its exact upstream "
                "provenance and license coverage are not inferred from neighboring files.")
    if component == "build_definition":
        return ("Build inclusion is traced only through the pinned qmake edges; "
                "standalone module packaging and all platform configurations are unverified.")
    if component == "fex_parser_source":
        return ("Whole-file identity and the parser call edge are recorded, but "
                "parser correctness, malformed-input behavior, and runtime use are untested.")
    if component == "giflib_source":
        return ("Whole-file identity and the qmake source list are recorded; "
                "GIF behavior, error-path cleanup, and non-Linux builds are untested.")
    if path.endswith("/qgifimage.cpp"):
        return ("Pinned source uses bitwise OR in device-mode tests, ignores the "
                "GIF writer result, and has unclosed decoder error paths; no runtime "
                "reproduction or fix is included in this license/build package.")
    return ("Whole-file identity and QtGifImage call/build edges are recorded; "
            "GIF error handling and runtime behavior are untested.")


def license_status(path, component):
    if path.endswith(("LICENSE", "COPYING")):
        return "license text inventoried and hash-bound; no legal conclusion"
    if component == "fex_parser_source":
        return ("duplicate FEX MIT notice files are present; per-file license "
                "reach and distribution obligations are not adjudicated")
    if component in ("giflib_source", "qtgifimage_source"):
        return ("vendored notice is present in the subsystem; per-file "
                "license reach and distribution obligations are not adjudicated")
    return ("no file-specific license conclusion; neighboring notices are not "
            "assumed to cover this file")


def caller_edges(path, component):
    if path.endswith(("LICENSE", "COPYING", "README", "README.md", "AUTHORS")):
        return [
            "provenance/license documentation only; not a compiled caller or target",
            "notice scope is not treated as an independent legal conclusion",
        ]
    if path.startswith("include/lib/fex/") or path.startswith("src/lib/fex/"):
        if path.endswith("parser_util.cpp"):
            return [
                "src/lib/fex/parser_util.cpp includes absent include/lib/fex/parser_util.h",
                "not listed in porymap.pro; no compiled application caller established",
            ]
        return [
            "porymap.pro -> src/lib/fex/lexer.cpp and parser.cpp",
            "src/core/parseutil.cpp -> fex::Lexer/fex::Parser",
            "include/lib/fex/parser.h -> include/lib/orderedmap.h",
        ]
    if path.startswith(GIFLIB_PREFIX):
        return [
            "src/vendor/QtGifImage/gifimage/qtgifimage.pri -> "
            "src/vendor/QtGifImage/3rdParty/giflib.pri",
            "giflib.pri compiles six listed C files; gif_font.c is not listed",
            "giflib API is consumed by QtGifImage qgifimage.cpp",
        ]
    if path == "src/vendor/QtGifImage/3rdParty/giflib.pri":
        return [
            "included by src/vendor/QtGifImage/gifimage/qtgifimage.pri",
            "lists six compiled GIFLIB C files and omits tracked gif_font.c",
        ]
    if path.startswith(QTGIF_PREFIX + "gifimage/doc/"):
        return [
            "documentation/snippet source; not a Porymap application build input",
            "QtGifImage qmake documentation/standalone targets not runtime-tested",
        ]
    if path.endswith((".pri", ".pro")):
        return [
            "porymap.pro includes gifimage/qtgifimage.pri",
            "qtgifimage.pri includes giflib.pri and qgifimage.cpp",
            "standalone module project files are not separately built here",
        ]
    return [
        "porymap.pro -> QtGifImage qmake inclusion",
        "qgifimage.h callers: src/ui/loadingscreen.cpp and "
        "src/ui/mapimageexporter.cpp",
    ]


def assert_rejected(mutator, row, expected_path, source_bytes):
    changed = mutator(dict(row))
    try:
        verify_candidate_row(expected_path, changed)
        verify_source_bytes(expected_path, source_bytes, changed)
    except ValueError:
        return True
    return False


def verify_report_boundary(report):
    require(report.get("all_dispositions") == "NEEDS_EVIDENCE",
            "report promotes unresolved evidence")
    require(report.get("independent_semantic_approvals") == 0,
            "report fabricates semantic approval")
    require(report.get("legal_conclusion_made") is False,
            "report makes a legal conclusion")
    require("Source and qmake closure only." in report.get("evidence_boundary", ""),
            "report overstates evidence boundary")
    require(report.get("full_gui_verified") is not True and
            report.get("gif_runtime_verified") is not True,
            "report mislabels source/build evidence as runtime evidence")
    records = report.get("per_file_records", [])
    require(len(records) == report.get("new_complete_source_file_count"),
            "per-file record count changed")
    require(all(row.get("disposition") == "NEEDS_EVIDENCE" and
                row.get("semantic_approval") is False and
                row.get("new_file_counted") is True
                for row in records),
            "per-file handoff promotes or omits a source disposition")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--workpack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.porymap.resolve()
    require(git(root, "rev-parse", "HEAD") == PIN, "Porymap pin mismatch")

    candidates = load_candidate_rows(args.workpack)
    source_controls = []
    records = []
    for path in NEW_PATHS:
        record = verify_file(root, path, candidates[path])
        record["component"] = classify(path)
        record["full_file_role"] = file_role(path)
        record["whole_file_scope"] = file_objection(path, record["component"])
        record["license_status"] = license_status(path, record["component"])
        record["caller_dependency_edges"] = caller_edges(path, record["component"])
        record["unresolved_objections"] = [record["whole_file_scope"]]
        record["source_sha256_matches_pinned_git_blob"] = True
        record["candidate_archive_sha256"] = WORKPACK_SHA256
        record["candidate_dossier_compressed_sha256"] = DOSSIER_SHA256
        record["new_file_counted"] = True
        records.append(record)
        changed = (root / path).read_bytes() + b"\nphase1-source-mutation\n"
        try:
            verify_source_bytes(path, changed, candidates[path][0])
        except ValueError:
            pass
        else:
            raise ValueError("source mutation escaped: " + path)
        source_controls.append(path)

    context = []
    for path in CONTEXT_PATHS:
        record = verify_file(root, path, candidates[path])
        record["disposition"] = "REUSED_CONTEXT_NOT_RECENSUSED"
        record["new_file_counted"] = False
        context.append(record)
    source_edges = verify_source_contract(root)

    sample_path = "src/vendor/QtGifImage/gifimage/qgifimage.cpp"
    sample_row = candidates[sample_path][0]
    sample_bytes = (root / sample_path).read_bytes()
    row_controls = [
        lambda r: {**r, "provenance": {**r.get("provenance", {}),
                                      "pinned_revision": "deadbeef"}},
        lambda r: {**r, "provenance": {**r.get("provenance", {}),
                                      "path": "wrong/path"}},
        lambda r: {**r, "review": {**r.get("review", {}),
                                    "semantic_signoff": True}},
        lambda r: {**r, "review": {**r.get("review", {}),
                                    "reviewer": "unverified"}},
        lambda r: {**r, "review": {**r.get("review", {}),
                                    "status": "APPROVED"}},
        lambda r: {**r, "provenance": {**r.get("provenance", {}),
                                      "git_blob_sha": "0" * 40}},
        lambda r: {**r, "provenance": {**r.get("provenance", {}),
                                      "source_content_sha256": "0" * 64}},
    ]
    require(all(assert_rejected(m, sample_row, sample_path, sample_bytes)
                for m in row_controls),
            "candidate row mutation escaped")
    require(sha256(args.workpack.read_bytes() + b"mutation") != WORKPACK_SHA256,
            "workpack mutation control failed")
    with zipfile.ZipFile(args.workpack) as archive:
        compressed_dossier = archive.read(DOSSIER_MEMBER)
    require(sha256(compressed_dossier + b"mutation") != DOSSIER_SHA256,
            "dossier mutation control failed")

    result = {
        "schema": "phase1-porymap-vendored-dependency-license-closure-v1",
        "porymap_pin": PIN,
        "workpack_sha256": WORKPACK_SHA256,
        "candidate_dossier_compressed_sha256": DOSSIER_SHA256,
        "new_complete_source_file_count": len(records),
        "all_dispositions": "NEEDS_EVIDENCE",
        "independent_semantic_approvals": 0,
        "legal_conclusion_made": False,
        "build_and_dependency_edges": source_edges,
        "per_file_records": records,
        "reused_context_not_recensused": context,
        "negative_controls": {
            "source_byte_mutations_rejected": len(source_controls),
            "candidate_row_mutations_rejected": len(row_controls),
            "workpack_sha256_mutation_rejected": True,
            "compressed_dossier_sha256_mutation_rejected": True,
            "source_file_paths_mutated": source_controls,
        },
        "evidence_boundary": (
            "Source and qmake closure only. A successful pinned full-app build "
            "establishes compilation/linking in that CI environment, not GIF "
            "runtime correctness, GUI behavior, distribution compliance, or gameplay."
        ),
    }
    verify_report_boundary(result)
    evidence_mutations = [
        {**result, "all_dispositions": "APPROVED"},
        {**result, "independent_semantic_approvals": 1},
        {**result, "legal_conclusion_made": True},
        {**result, "gif_runtime_verified": True},
        {**result, "per_file_records": [
            {**records[0], "disposition": "APPROVED"}, *records[1:]
        ]},
        {**result, "per_file_records": [
            {**records[0], "semantic_approval": True}, *records[1:]
        ]},
    ]
    for changed in evidence_mutations:
        try:
            verify_report_boundary(changed)
        except ValueError:
            continue
        raise ValueError("evidence-boundary mutation escaped")
    result["negative_controls"]["evidence_boundary_mutations_rejected"] = len(
        evidence_mutations
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "result": "PASS_SOURCE_PROVENANCE_AND_BUILD_BOUNDARY",
        "new_complete_source_file_count": len(records),
        "negative_controls": result["negative_controls"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

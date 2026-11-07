#!/usr/bin/env python3
"""Verify pinned OrderedJson identities, source contracts, and native Qt behavior."""

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
DOSSIER_GZIP_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
LIBRARY = {
    "include/lib/orderedjson.h": {
        "blob": "cb5139d37d955f2469ebd2eaaf089668b82884fe",
        "sha256": "06af4ab35f09263aa213673dbdca5640b840fddfb22f7e8fc35dc41ad91fdaa2",
        "row": "100dc0dba8d6682f8eb1d6b5df2cf8a3ce1543d63c1640d61aca9322034aae56",
    },
    "src/lib/orderedjson.cpp": {
        "blob": "4d3a460c652541371a01132116e508db8c4c872c",
        "sha256": "a6acaf57872aa3bfc2fc98b02b743e550bead19cc85cf298c642c50a5f3f75ae",
        "row": "ce04fbf6b06f98a91b74cf82c962fb0eca90ffe26396cae32480e8ac00015793",
    },
    "include/lib/orderedmap.h": {
        "blob": "33fcfc50609722b10ae45eaa847be540c7c72d13",
        "sha256": "0f3e331b6be95f8f07047f88a649ce1275ffe16c04b5c21bd300e965c8ac2f18",
        "row": "1c67b737d5d7b4b1c7d2b250066b0dacb5b98950ef15693c6cc8b613a1a99a1e",
    },
}
CONTEXT = {
    "porymap.pro": {
        "blob": "53d8055ecfe5d88afb6f183b82d4a3472727ad4f",
        "sha256": "cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996",
        "row": "93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2",
    },
    "src/core/parseutil.cpp": {
        "blob": "a1c3e69daed3f04d7ed64e1a34bd95db56137ae2",
        "sha256": "7c9e4028c74555c7b27b7fb6e3d255f406d8303277989887f69ddf8a44ece441",
        "row": "8a86894dbbd710bfecfd5af86c87dc3392b9878756636608010b39569d5aed33",
    },
    "src/project.cpp": {
        "blob": "d43b0949303433111d4478ad76117c2b3445dd13",
        "sha256": "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
        "row": "b6b90abf56f02452537a9b096fa191ead9ee7360dd19d72c6f5486834bed02d7",
    },
    "src/ui/prefab.cpp": {
        "blob": "0baebee4f5bcaf5baa6b2bdac3d5791e140c558f",
        "sha256": "f377fd58124377eb38d805e72be937bd71ed5c54b751063650b9825973653581",
        "row": "60b944205115267daf86e0c2b95fff25bf325c0487b2f85b419177743187c33a",
    },
    "src/ui/regionmapeditor.cpp": {
        "blob": "a96de606cc18469b558b1acfc7c787432b8dcfb4",
        "sha256": "43f433c1754cd25d4691491567e7be9ff48e47e89c485eb917a5b26e2e1eb4e2",
        "row": "36d435c647bbf00a5028ca29d80acf9356d9bd5dba8aac5771cd7be8c4a7a6b5",
    },
    "LICENSE.md": {
        "blob": "65c5ca88a67c30becee01c5a8816d964b03862f9",
        "sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
        "row": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
    },
}
ALL = {**LIBRARY, **CONTEXT}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def source_contract(sources):
    header = sources["include/lib/orderedjson.h"]
    implementation = sources["src/lib/orderedjson.cpp"]
    orderedmap = sources["include/lib/orderedmap.h"]
    parseutil = sources["src/core/parseutil.cpp"]
    build = sources["porymap.pro"]
    project = sources["src/project.cpp"]
    prefab = sources["src/ui/prefab.cpp"]
    regionmap = sources["src/ui/regionmapeditor.cpp"]
    license_text = sources["LICENSE.md"]

    required = (
        (header, "static Json parse(const QString & in,"),
        (header, "void dump(QFile *file)"),
        (implementation, "static auto iter = m_value.find(key);"),
        (implementation, "data[std::move(key)] = parse_json(depth + 1);"),
        (implementation, "if (parser.i != in.size())"),
        (implementation, "case QJsonValue::Double: return value.toInt();"),
        (orderedmap, "class ordered_map"),
        (orderedmap, "return try_emplace(std::forward<K>(key)).first.value();"),
        (parseutil, "*out = OrderedJson::parse(jsonTxt, error).object_items();"),
        (build, "src/lib/orderedjson.cpp"),
        (build, "include/lib/orderedjson.h"),
        (project, "OrderedJsonDoc jsonDoc"),
        (prefab, "OrderedJsonDoc jsonDoc"),
        (regionmap, "poryjson::Json::parse"),
        (license_text, "GNU LESSER GENERAL PUBLIC LICENSE"),
        (header, "Copyright (c) 2013 Dropbox, Inc."),
        (orderedmap, "MIT License"),
    )
    for source, token in required:
        require(token in source, "pinned source contract missing: " + token)

    lookup = implementation[
        implementation.index("const Json & JsonObject::operator[]"):
        implementation.index("const Json & JsonArray::operator[]")
    ]
    require("static auto iter = m_value.find(key);" in lookup and
            "return (iter == m_value.end()) ? static_null() : (*iter).second;" in lookup,
            "JsonObject lookup behavior changed; reevaluate the cross-object iterator finding")

    reader_start = parseutil.index("bool ParseUtil::tryParseOrderedJsonFile")
    reader_end = parseutil.index("\n}", reader_start) + 2
    reader = parseutil[reader_start:reader_end]
    require("OrderedJson::parse(jsonTxt, error).object_items()" in reader,
            "OrderedJson file reader no longer uses the pinned parse contract")
    require("is_object" not in reader,
            "OrderedJson file reader now validates the top-level type")
    require("if (error && !error->isEmpty())" in reader,
            "OrderedJson file reader error propagation changed")

    parser = implementation[
        implementation.index("Json Json::parse(const QString &in"):
    ]
    require("parser.consume_garbage();" in parser and "if (parser.i != in.size())" in parser,
            "trailing-input rejection contract changed")
    return reader


def dossier_rows(package_bytes):
    require(sha256(package_bytes) == WORKPACK_SHA256, "candidate workpack ZIP hash mismatch")
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        compressed = archive.read("evidence/candidate_review_dossiers.jsonl.gz")
    require(sha256(compressed) == DOSSIER_GZIP_SHA256, "candidate dossier archive hash mismatch")

    expected_paths = set(ALL)
    found = {}
    for line in gzip.decompress(compressed).splitlines():
        row = json.loads(line)
        provenance = row.get("provenance", {})
        path = provenance.get("path")
        if provenance.get("repository") != "huderlem/porymap" or path not in expected_paths:
            continue
        found[path] = (row, sha256(line))
    require(set(found) == expected_paths, "missing or duplicate original candidate-dossier rows")

    for path, expected in ALL.items():
        row, row_hash = found[path]
        provenance = row["provenance"]
        require(provenance["pinned_revision"] == PIN, "dossier pin mismatch: " + path)
        require(provenance["git_blob_sha"] == expected["blob"], "dossier blob mismatch: " + path)
        require(row_hash == expected["row"], "dossier row hash mismatch: " + path)
        require(row["review"]["status"] in (
            "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
        ), "unexpected candidate disposition: " + path)
    return found


def validate_identity(path, data, dossier, expected):
    if isinstance(data, str):
        data = data.encode("utf-8")
    row, row_hash = dossier[path]
    provenance = row["provenance"]
    serialized_row = json.dumps(
        row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return (
        path in expected
        and git_blob(data) == expected[path]["blob"]
        and sha256(data) == expected[path]["sha256"]
        and provenance["repository"] == "huderlem/porymap"
        and provenance["path"] == path
        and provenance["pinned_revision"] == PIN
        and provenance["git_blob_sha"] == expected[path]["blob"]
        and provenance["source_content_sha256"] in (None, expected[path]["sha256"])
        and row["review"]["status"] in (
            "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
        )
        and sha256(serialized_row) == row_hash
        and row_hash == expected[path]["row"]
    )


def check_native_output(output):
    require(output.count("PHASE1_ORDEREDJSON_RESULT ") == 1, "native result missing or duplicated")
    expected = (
        "PHASE1_ORDEREDJSON_RESULT malformed=reject trailing=reject comments=explicit "
        "duplicate=last-value-first-position root-array=valid-empty-object-view "
        "qjson-double=truncated static-lookup=first-object"
    )
    require(expected in output, "unexpected native OrderedJson behavior")
    require("PHASE1_ORDEREDJSON_FATAL" not in output, "native OrderedJson harness failed")


def mutation_controls(sources, dossier, workpack_bytes):
    rejected = 0

    for changed_archive in (workpack_bytes[:-1], workpack_bytes + b"mutation"):
        try:
            dossier_rows(changed_archive)
        except (ValueError, zipfile.BadZipFile):
            rejected += 1
        else:
            raise ValueError("candidate archive mutation escaped")

    def must_reject(mutated):
        nonlocal rejected
        try:
            source_contract(mutated)
        except (ValueError, KeyError):
            rejected += 1
        else:
            raise ValueError("source mutation escaped contract checks")

    mutation = dict(sources)
    mutation["src/lib/orderedjson.cpp"] = mutation["src/lib/orderedjson.cpp"].replace(
        "static auto iter = m_value.find(key);", "auto iter = m_value.find(key);", 1
    )
    must_reject(mutation)

    mutation = dict(sources)
    mutation["src/lib/orderedjson.cpp"] = mutation["src/lib/orderedjson.cpp"].replace(
        "if (parser.i != in.size())", "if (parser.i == in.size())", 1
    )
    must_reject(mutation)

    mutation = dict(sources)
    mutation["src/core/parseutil.cpp"] = mutation["src/core/parseutil.cpp"].replace(
        "OrderedJson::parse(jsonTxt, error).object_items()", "OrderedJson::parse(jsonTxt, error)", 1
    )
    must_reject(mutation)

    mutation = dict(sources)
    mutation["porymap.pro"] = mutation["porymap.pro"].replace("src/lib/orderedjson.cpp", "", 1)
    must_reject(mutation)

    for field, value in (
        ("git_blob_sha", "0" * 40),
        ("source_content_sha256", "0" * 64),
    ):
        row, row_hash = dossier["src/lib/orderedjson.cpp"]
        altered = json.loads(json.dumps(row))
        altered["provenance"][field] = value
        mutated_hash = sha256(json.dumps(
            altered, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8"))
        require(not validate_identity(
            "src/lib/orderedjson.cpp",
            sources["src/lib/orderedjson.cpp"],
            {"src/lib/orderedjson.cpp": (altered, mutated_hash)},
            {"src/lib/orderedjson.cpp": LIBRARY["src/lib/orderedjson.cpp"]},
        ), "identity mutation escaped: " + field)
        rejected += 1

    row, row_hash = dossier["include/lib/orderedjson.h"]
    altered = json.loads(json.dumps(row))
    altered["review"]["status"] = "COPILOT_REVIEWED"
    mutated_hash = sha256(json.dumps(
        altered, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8"))
    require(not validate_identity(
        "include/lib/orderedjson.h",
        sources["include/lib/orderedjson.h"],
        {"include/lib/orderedjson.h": (altered, mutated_hash)},
        {"include/lib/orderedjson.h": LIBRARY["include/lib/orderedjson.h"]},
    ), "candidate status mutation escaped")
    rejected += 1
    require(not validate_identity(
        "include/lib/orderedjson.h",
        sources["include/lib/orderedjson.h"],
        {"include/lib/orderedjson.h": (row, "0" * 64)},
        {"include/lib/orderedjson.h": LIBRARY["include/lib/orderedjson.h"]},
    ), "dossier row hash mutation escaped")
    rejected += 1

    must_reject({**sources, "include/lib/orderedmap.h": ""})
    return rejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workpack", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    require(args.verify_only or args.output is not None, "--output is required for native execution")
    workpack = args.workpack or Path(__file__).resolve().parents[1] / "imports/XGBA_Phase1_v1.5_Complete_Workpack.zip"

    if not args.verify_only:
        revision = subprocess.check_output(
            ["git", "-C", str(args.porymap), "rev-parse", "HEAD"], text=True
        ).strip()
        require(revision == PIN, "pinned Porymap revision mismatch")

    sources = {}
    for path, expected in ALL.items():
        data = (args.porymap / path).read_bytes()
        require(git_blob(data) == expected["blob"], "original Git blob mismatch: " + path)
        require(sha256(data) == expected["sha256"], "full-byte SHA-256 mismatch: " + path)
        sources[path] = data.decode("utf-8")

    workpack_bytes = workpack.read_bytes()
    dossier = dossier_rows(workpack_bytes)
    reader = source_contract(sources)
    source_negatives = mutation_controls(sources, dossier, workpack_bytes)
    require("return true;" in reader, "reader success result missing")

    if args.verify_only:
        print(json.dumps({
            "source_records_verified": len(LIBRARY),
            "context_records_verified": len(CONTEXT),
            "source_mutations_rejected": source_negatives,
            "native_executed": False,
            "status": "SOURCE_AND_PROVENANCE_CHECKS_PASS",
        }, sort_keys=True))
        return

    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True
    ).split()
    executable = args.output.with_name("phase1_porymap_orderedjson_contract")
    compile_result = subprocess.run(
        [
            "g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
            "-I" + str(args.porymap / "include/lib"),
            str(args.harness), str(args.porymap / "src/lib/orderedjson.cpp"),
            "-o", str(executable),
        ] + flags,
        text=True,
        capture_output=True,
    )
    require(compile_result.returncode == 0, "native compile failed: " + compile_result.stderr[-4000:])
    run = subprocess.run([str(executable.resolve())], text=True, capture_output=True)
    require(
        run.returncode == 0,
        "native harness failed: stdout=" + run.stdout[-2000:] + " stderr=" + run.stderr[-2000:],
    )
    check_native_output(run.stdout)
    transcript_negatives = 0
    for changed in (
        run.stdout.replace("trailing=reject", "trailing=accept"),
        run.stdout.replace("duplicate=last-value-first-position", "duplicate=first-value"),
        run.stdout.replace("root-array=valid-empty-object-view", "root-array=error"),
        run.stdout.replace("static-lookup=first-object", "static-lookup=per-object"),
    ):
        try:
            check_native_output(changed)
        except ValueError:
            transcript_negatives += 1
        else:
            raise ValueError("native transcript mutation escaped")

    record = {
        "class": "PINNED_PORYMAP_ORDEREDJSON_SEMANTIC_CONTRACT",
        "porymap_pin": PIN,
        "native_original_source_executed": True,
        "native_framework": "Qt6Core",
        "native_transcript": run.stdout.strip(),
        "source_records": [
            {
                "path": path,
                "git_blob_sha1": details["blob"],
                "full_source_sha256": details["sha256"],
                "candidate_dossier_row_sha256": details["row"],
                "disposition": "NEEDS_EVIDENCE",
                "whole_file_semantic_approval": False,
            }
            for path, details in LIBRARY.items()
        ],
        "source_mutations_rejected": source_negatives,
        "transcript_mutations_rejected": transcript_negatives,
        "findings": [
            "JsonObject::operator[] caches a function-static iterator into the first object's map; subsequent object lookups reuse it.",
            "ParseUtil::tryParseOrderedJsonFile assigns object_items() without checking the parsed top-level type, so valid arrays/scalars become empty objects with no parse error.",
            "Json::fromQJsonValue converts every QJsonValue::Double through toInt(), truncating fractional values.",
            "Parsing rejects truncated/trailing input; COMMENTS mode explicitly accepts comments; duplicate keys replace the value without changing the first insertion position.",
        ],
        "caller_and_license_limits": [
            "Porymap parse/save callers are pinned source context, not full GUI execution.",
            "The original candidate dossier is machine triage, not a semantic receipt.",
            "Embedded Dropbox/json11 and Tessil/MIT notices are distinct from the Porymap root LGPL license; no distribution-compliance conclusion is made.",
            "OrderedMap operations outside the exercised ordering and replacement contract remain unreviewed.",
        ],
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "native_executed": True,
        "source_records": len(LIBRARY),
        "source_mutations_rejected": source_negatives,
        "transcript_mutations_rejected": transcript_negatives,
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

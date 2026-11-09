#!/usr/bin/env python3
"""Verify partial source evidence for second-packet mGBA translation and SQLite files."""

import copy
import gzip
import hashlib
import json
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/phase1-review-readiness"
HANDOFF = BASE / "analyst-second-packet-mgba-special-sources-112-127-129-20261104.json"
PACKET = BASE / "packet-0100-0199.json"
PACKET_BLOB = "3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REPOSITORY = "mgba-emu/mgba"
DOSSIER_PATH = ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_RECEIPT = BASE / "machine-dossier-byte-reconciliation-0000-0199-20261030.json"
PRIOR_INDEX = BASE / "second-packet-partial-handoff-index-20261030.json"
INDICES = list(range(112, 128)) + [129]
SQLITE_PATH = "src/third-party/sqlite3/sqlite3.c"
SQLITE_OBSERVATIONS = [
    "The full amalgamation identifies SQLite version 3.51.1 and upstream Fossil source check-in 281fc0e9afc38674b9b0991943b9e9d1e64c.",
    "The source contains its own copyright disclaimer/public-domain blessing and embeds sqlite3.h; it is a single translation unit containing many SQLite modules.",
    "This checkout defines SQLITE_OMIT_LOAD_EXTENSION and SQLITE_ENABLE_LOCKING_STYLE near the amalgamation prefix.",
]
SQLITE_UNRESOLVED = [
    "Confirm configured system-versus-bundled provider, compile options, toolchain ABI, and downstream packaging in each supported build.",
    "Review SQLite's complete implementation and security/update provenance independently; the full byte stream was pinned and structurally scanned, not semantically dispositioned.",
    "Assess bundled SQLite and MPL-covered mGBA code in each combined distribution; this handoff is not legal advice or a combined-license clearance.",
]
DEPENDENCY_IDENTITIES = {
    "LICENSE": ("14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e", "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85"),
    "CMakeLists.txt": ("834e9fd9ceb94a972941fb7b12494270702601e8", "6dd68feaebc479a02606b14be889e7c966949aa6aa5a4c52f601861c5d369a31"),
    "src/platform/qt/CMakeLists.txt": ("fc0c46c19dfb91ed1bfc5c681c7fe0885540db79", "9bf8a6adaf3863648bca2997d427ea096f4de28e96fb93926d7066d5e60f4d8a"),
    "src/platform/qt/main.cpp": ("d0ea3cb178dd2eb70d8ebbd7308a469d3eded1a2", "a4244173f58fcd1c8f7b72356bacf0b2a70055adcdc4b8fed08e850d415a89fd"),
    "src/feature/sqlite3/no-intro.h": ("ba3bc128f9b503245646d66bc9c1198f1c7cf003", "976ba64af399cd79ff0971e0288b509d41adbfe6743d2a144c1cf1cc54db5a8b"),
    "src/feature/sqlite3/no-intro.c": ("8b0474c8c96fed98c97dddf36bf8c34c22df2923", "ae935793035e8d879da1f0fb1249c75805b5a25d0ea380275d468572cb8b9314"),
    "src/platform/qt/GBAApp.cpp": ("755a0f94a2af4ff57dd2e8008e16a45c2ee80ee5", "715ba0cfc15443524f4023a9d1fb54431676e0ce77e228faeb7ea2feb024a7bd"),
    "src/third-party/sqlite3/sqlite3.h": ("76c567d050a0e148af0fb8c619731057f86e83f9", "4340a24cda7bc436d62459c3c5237f67b9ab716ddca872faf8052d0ce0d97119"),
}
DEPENDENCY_ANCHOR_SHA256 = {
    "LICENSE": "e3b7ea5f2e8afc8e1491606561ef911d3b647713b5a2feea611ffd212d8ca50f",
    "CMakeLists.txt": "e57aeae346d558f86d96ebffc847e621067e4a9af6243a7968df52d59094a2cd",
    "src/platform/qt/CMakeLists.txt": "f281bff3e4062f6377cc32642f981009cd84232ceb3ec439110983322e495f7c",
    "src/platform/qt/main.cpp": "9d13ac16f4ec093a6e55d0ac4f71877f3266ddc46ec08516c74ec109ca94eda8",
    "src/feature/sqlite3/no-intro.h": "eaeb303112c2493a2f0a2fec9d7f6e3023f67eea8930438216a80592c767563e",
    "src/feature/sqlite3/no-intro.c": "9b7af3470f89d200bf29d5835750501c817c27fd711c2353bda1e12f49003b65",
    "src/platform/qt/GBAApp.cpp": "1e9b0c5e92cd75e95a50a8a937a4a853e5ecd353a7de4d2364f68a99178b478a",
    "src/third-party/sqlite3/sqlite3.h": "63eab637b70eb69af7fc5abccca5b072942b2aab5f342f3d3dc01ff8f71333c9",
}
EXPECTED_SQLITE_LINES = {
    20: "Fossil check-in",
    35: "disclaims copyright",
    168: "SQLITE_OMIT_LOAD_EXTENSION",
    320: "Include sqlite3.h",
    470: 'SQLITE_VERSION        "3.51.1"',
    472: "281fc0e9afc38674b9b0991943b9e9d1e64c",
    265905: "Return the source-id",
    265906: "sqlite3_sourceid",
}


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def canonical_sha256(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def read_pinned_source(path, source_root=None):
    if source_root is not None:
        return (source_root / path).read_bytes()
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{PIN}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-special-source-handoff"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def catalog_summary(raw):
    root = ET.fromstring(raw)
    messages = root.findall(".//message")
    unfinished = empty = numerus = mismatches = 0
    placeholder = re.compile(r"%(?:L?\d+|n)")
    for message in messages:
        translation = message.find("translation")
        if translation is None:
            raise AssertionError("catalog message lacks a translation node")
        unfinished += translation.get("type") == "unfinished"
        empty += not "".join(translation.itertext()).strip()
        numerus += message.get("numerus") == "yes"
        if translation.get("type") != "unfinished":
            source_text = message.findtext("source") or ""
            forms = translation.findall("numerusform") or [translation]
            source_tokens = sorted(placeholder.findall(source_text))
            if any(
                source_tokens != sorted(placeholder.findall("".join(form.itertext())))
                for form in forms
            ):
                mismatches += 1
    return {
        "language": root.get("language"),
        "source_language": root.get("sourcelanguage"),
        "contexts": len(root.findall("context")),
        "messages": len(messages),
        "unfinished": unfinished,
        "empty": empty,
        "numerus": numerus,
        "active_placeholder_mismatches": mismatches,
    }


def check_record(raw, record, packet_record, expected_index):
    identity = packet_record["identity"]
    lines = raw.decode("utf-8").splitlines()
    assert record["packet_index"] == expected_index
    assert packet_record["priority"] == "P0" and packet_record["independently_approved"] is False
    assert identity["repository"] == REPOSITORY and identity["pinned_commit"] == PIN
    assert record["path"] == identity["path"]
    assert record["git_blob_sha1"] == identity["git_blob_sha1"] == git_blob(raw)
    assert record["source_sha256"] == packet_record["whole_blob_sha256"] == hashlib.sha256(raw).hexdigest()
    assert record["machine_dossier_sha256"] == packet_record["dossier_sha256"]
    assert record["source_lines"] == packet_record["source_lines"] == len(lines)
    assert record["line_anchors"]
    assert all(type(line) is int and 0 < line <= len(lines) and lines[line - 1].strip() for line in record["line_anchors"])
    assert record["license_status"].startswith(("MPL-2.0_", "SQLITE_PUBLIC_DOMAIN_NOTICE_PRESENT_"))
    if expected_index < 128:
        assert record["license_status"] == "MPL-2.0_REPOSITORY_SCOPE_TRANSLATOR_PROVENANCE_PENDING"
        assert record["line_anchors"] == [1, 2, 3, 5, 7]
        assert record["catalog"] == catalog_summary(raw)
    else:
        assert record["path"] == SQLITE_PATH
        assert record["license_status"] == "SQLITE_PUBLIC_DOMAIN_NOTICE_PRESENT_COMBINED_DISTRIBUTION_REVIEW_PENDING"
        assert record["line_anchors"] == [1, 20, 35, 168, 320, 470, 472, 265905, 265906]
        assert record["file_bytes"] == len(raw) == 9_386_637
        assert record["source_observations"] == SQLITE_OBSERVATIONS
        assert record["unresolved"] == SQLITE_UNRESOLVED
        assert all(lines[line - 1] and text in lines[line - 1] for line, text in EXPECTED_SQLITE_LINES.items())


def reject_record(raw, record, packet_record, expected_index):
    try:
        check_record(raw, record, packet_record, expected_index)
    except (AssertionError, KeyError, TypeError, UnicodeDecodeError, ET.ParseError):
        return
    raise AssertionError("forged special-source record accepted")


def check_dependency(raw, dependency):
    path = dependency["path"]
    assert path in DEPENDENCY_IDENTITIES
    expected_blob, expected_sha = DEPENDENCY_IDENTITIES[path]
    assert dependency["git_blob_sha1"] == expected_blob == git_blob(raw)
    assert dependency["sha256"] == expected_sha == hashlib.sha256(raw).hexdigest()
    assert canonical_sha256(dependency["anchors"]) == DEPENDENCY_ANCHOR_SHA256[path]
    lines = raw.decode("utf-8").splitlines()
    assert dependency["anchors"]
    assert all(
        type(anchor["line"]) is int
        and 0 < anchor["line"] <= len(lines)
        and anchor["contains"] in lines[anchor["line"] - 1]
        for anchor in dependency["anchors"]
    )


def check_handoff(handoff, packet, prior_indices):
    assert handoff["schema"] == "xgba.phase1.second_packet_special_sources_handoff.v1"
    assert handoff["packet"] == "docs/phase1-review-readiness/packet-0100-0199.json"
    assert handoff["packet_git_blob_sha1"] == PACKET_BLOB
    assert handoff["source_pin"] == {"repository": REPOSITORY, "revision": PIN}
    assert handoff["scope"] == (
        "These packet identities map to mGBA Qt translation XML and the bundled SQLite amalgamation, not FireRed. "
        "This is source-grounded analyst partial evidence only; no translation-language judgment, complete SQLite "
        "semantic review, native Qt/QM runtime proof, or independent approval is claimed."
    )
    assert handoff["indices"] == INDICES
    assert len(packet) == 100
    assert len(handoff["records"]) == len(INDICES)
    assert [row["packet_index"] for row in handoff["records"]] == INDICES
    assert [row["path"] for row in handoff["records"]] == [
        packet[index - 100]["identity"]["path"] for index in INDICES
    ]
    assert prior_indices == set(range(100, 112)) | {128} | set(range(130, 200))
    assert prior_indices.isdisjoint(INDICES)
    assert handoff["prior_coverage"]["covered_second_packet_indices"] == 83
    assert handoff["prior_coverage"]["index"] == "docs/phase1-review-readiness/second-packet-partial-handoff-index-20261030.json"
    assert handoff["original_machine_dossier"]["path"] == "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
    assert handoff["original_machine_dossier"]["source_receipt"] == "docs/phase1-review-readiness/machine-dossier-byte-reconciliation-0000-0199-20261030.json"
    assert handoff["original_machine_dossier"]["git_blob_sha1"] == DOSSIER_BLOB
    assert handoff["original_machine_dossier"]["sha256"] == DOSSIER_SHA256
    assert handoff["original_machine_dossier"]["reconciled_rows"] == len(INDICES)
    assert handoff["whole_file_semantic_dispositions_added"] == handoff["independent_approvals_added"] == 0
    assert handoff["phase1_gate"] == "FAIL_INCOMPLETE"
    assert handoff["licensing"]["repository_license"] == "MPL-2.0"
    assert handoff["licensing"]["sqlite_amalgamation_notice"] == "SQLite copyright disclaimer/public-domain blessing appears in the source amalgamation."
    assert handoff["licensing"]["status"] == "PENDING_INDEPENDENT_CONTRIBUTOR_ATTRIBUTION_AND_COMBINED_DISTRIBUTION_REVIEW"
    assert handoff["licensing"]["limitations"] == [
        "The repository LICENSE identity does not establish individual translator contribution provenance.",
        "The SQLite source notice is recorded separately from mGBA's MPL-2.0; this is not a combined-work legal determination.",
    ]
    assert handoff["review_disposition"] == {
        "status": "ANALYST_PARTIAL_NEEDS_EVIDENCE",
        "whole_file_semantic_coverage": False,
        "independent_reviewer": None,
        "independent_verdict": "NEEDS_REVIEW",
        "approval_added": False,
    }
    assert handoff["record_defaults"] == {
        "applies_to_every_record": True,
        "analyst_status": "ANALYST_PARTIAL_NEEDS_EVIDENCE",
        "whole_file_semantic_coverage": False,
        "independent_reviewer": None,
        "independent_verdict": "NEEDS_REVIEW",
        "approval_added": False,
    }
    assert len(handoff["dependency_sources"]) == len(DEPENDENCY_IDENTITIES)
    assert {row["path"] for row in handoff["dependency_sources"]} == set(DEPENDENCY_IDENTITIES)
    assert handoff["dependency_edges"] == [
        {
            "group": "qt_translation_pipeline",
            "edges": [
                "Each non-template TS catalog is a candidate for the conditional Qt LinguistTools glob and QM generation.",
                "The generated translation resource uses /translations/ and is loaded by the Qt frontend's QTranslator path.",
                "The template catalog is explicitly removed from TS_FILES in both update and normal translation-generation branches.",
            ],
            "evidence_class": "PINNED_BUILD_AND_LOADER_SOURCE_ONLY",
            "not_verified": ["Qt LinguistTools availability", "generated QM/QRC bytes", "locale fallback behavior", "native UI translation correctness"],
        },
        {
            "group": "sqlite_no_intro_pipeline",
            "edges": [
                "Root CMake selects the bundled sqlite3.c fallback only when SQLite is wanted but no system SQLite was found.",
                "When SQLite is enabled, CMake adds no-intro.c and SQLite include/library dependencies.",
                "no-intro.c consumes SQLite APIs; its header declares the database load and ROM lookup functions.",
                "The Qt GBAApp source opens the No-Intro database and delegates database parsing.",
            ],
            "evidence_class": "PINNED_BUILD_AND_CALLER_SOURCE_ONLY",
            "not_verified": ["Which provider a configured build selects", "compiled SQLite ABI/options", "database compatibility, runtime lookup, or filesystem durability"],
        },
    ]
    assert handoff["shared_translation_observations"] == [
        "All 16 complete XML catalogs parse as Qt TS 2.1, with 71 contexts, 1,274 message records, and two numerus messages per file.",
        "Unfinished/empty translation counts and lexical placeholder-count deltas are recorded per catalog as triage only; they do not establish translation errors or language quality.",
        "The pinned Qt CMake source conditionally builds translations only when LinguistTools is found; it removes mgba-template.ts from both translation-generation branches. The QTranslator source path is static source evidence only.",
    ]
    assert handoff["shared_unresolved"] == [
        "Independently review each full catalog's wording, context, plural forms, placeholders, rich text, and contributor provenance.",
        "Verify the Qt toolchain actually emits each QM/QRC and test locale selection/fallback in the native frontend.",
        "Resolve all generated-source and build-configuration variants before making runtime or redistribution claims.",
    ]


def reject_handoff(handoff, packet, prior_indices):
    try:
        check_handoff(handoff, packet, prior_indices)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("forged handoff verdict or identity accepted")


def read_prior_indices():
    index = json.loads(PRIOR_INDEX.read_bytes())
    covered = set()
    for batch_path in index["batches"]:
        batch = json.loads((ROOT / batch_path).read_bytes())
        assert batch["source_packet_blob_sha1"] == PACKET_BLOB
        covered.update(batch["new_partial_indices"])
    return covered


def read_dossier_rows(indices, packet):
    raw = DOSSIER_PATH.read_bytes()
    assert git_blob(raw) == DOSSIER_BLOB
    assert hashlib.sha256(raw).hexdigest() == DOSSIER_SHA256
    wanted = {packet[index - 100]["identity"]["path"]: index for index in indices}
    found = {}
    with gzip.open(DOSSIER_PATH, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            provenance = row["provenance"]
            path = provenance["path"]
            if path not in wanted:
                continue
            index = wanted[path]
            packet_record = packet[index - 100]
            assert provenance["repository"] == REPOSITORY
            assert provenance["pinned_revision"] == PIN
            assert provenance["git_blob_sha"] == packet_record["identity"]["git_blob_sha1"]
            assert provenance["source_content_sha256"] == packet_record["whole_blob_sha256"]
            assert canonical_sha256(row) == packet_record["dossier_sha256"]
            found[index] = row
    assert sorted(found) == indices
    return found


def check_original_receipt():
    receipt = json.loads(DOSSIER_RECEIPT.read_bytes())
    assert receipt["packet_git_blobs"]["docs/phase1-review-readiness/packet-0100-0199.json"] == PACKET_BLOB
    assert receipt["machine_dossier_byte_checks"] == 200
    assert receipt["phase1_gate"] == "FAIL_INCOMPLETE"
    assert receipt["independent_p0_approved"] == receipt["independent_total_approved"] == 0
    assert receipt["whole_file_semantic_approved"] == 0


def source_root_is_pinned(source_root):
    result = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == PIN


def run_negative_controls(handoff, packet, prior_indices, dossier_raw, dependency_raws, source_root):
    negatives = 0
    for field, value in (
        ("phase1_gate", "PASS"),
        ("independent_approvals_added", 1),
        ("whole_file_semantic_dispositions_added", 1),
        ("indices", INDICES[:-1]),
        ("packet_git_blob_sha1", "0" * 40),
        ("dependency_sources", []),
        ("scope", "FireRed source and approved translations"),
        ("dependency_edges", []),
        ("shared_unresolved", []),
    ):
        forged = copy.deepcopy(handoff)
        forged[field] = value
        reject_handoff(forged, packet, prior_indices)
        negatives += 1
    for section, field, value in (
        ("review_disposition", "independent_verdict", "APPROVED"),
        ("review_disposition", "independent_reviewer", "fabricated"),
        ("review_disposition", "whole_file_semantic_coverage", True),
        ("record_defaults", "approval_added", True),
        ("record_defaults", "analyst_status", "APPROVED"),
    ):
        forged = copy.deepcopy(handoff)
        forged[section][field] = value
        reject_handoff(forged, packet, prior_indices)
        negatives += 1

    changed_packet = PACKET.read_bytes() + b"forged"
    assert git_blob(changed_packet) != PACKET_BLOB
    negatives += 1
    changed_dossier = dossier_raw[:-1] + bytes([dossier_raw[-1] ^ 1])
    assert hashlib.sha256(changed_dossier).hexdigest() != DOSSIER_SHA256
    negatives += 1

    for dependency, raw in zip(handoff["dependency_sources"], dependency_raws):
        changed = raw[:-1] + bytes([raw[-1] ^ 1])
        try:
            check_dependency(changed, dependency)
        except AssertionError:
            negatives += 1
        else:
            raise AssertionError(f"mutated dependency accepted: {dependency['path']}")
        forged = copy.deepcopy(dependency)
        forged["anchors"] = forged["anchors"][:-1]
        try:
            check_dependency(raw, forged)
        except AssertionError:
            negatives += 1
        else:
            raise AssertionError(f"mutated dependency anchors accepted: {dependency['path']}")

    malformed = b'<?xml version="1.0"?><TS><context><message></TS>'
    try:
        catalog_summary(malformed)
    except ET.ParseError:
        negatives += 1
    else:
        raise AssertionError("malformed translation catalog accepted")

    for record in handoff["records"]:
        index = record["packet_index"]
        packet_record = packet[index - 100]
        raw = read_pinned_source(record["path"], source_root)
        check_record(raw, record, packet_record, index)
        mutated = raw[:-1] + bytes([raw[-1] ^ 1])
        reject_record(mutated, record, packet_record, index)
        negatives += 1
        for field, value in (
            ("source_sha256", "0" * 64),
            ("machine_dossier_sha256", "0" * 64),
            ("line_anchors", [10**9]),
        ):
            forged = copy.deepcopy(record)
            forged[field] = value
            reject_record(raw, forged, packet_record, index)
            negatives += 1
        if index < 128:
            forged = copy.deepcopy(record)
            forged["catalog"]["messages"] += 1
            reject_record(raw, forged, packet_record, index)
            negatives += 1
    return negatives


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    if args.source_root is not None:
        source_root_is_pinned(args.source_root)

    packet_raw = PACKET.read_bytes()
    assert git_blob(packet_raw) == PACKET_BLOB
    packet = json.loads(packet_raw)["packets"]
    handoff = json.loads(HANDOFF.read_bytes())
    prior_indices = read_prior_indices()
    check_handoff(handoff, packet, prior_indices)
    check_original_receipt()
    dossier_rows = read_dossier_rows(INDICES, packet)
    assert len(dossier_rows) == len(INDICES)

    dependency_raws = []
    for dependency in handoff["dependency_sources"]:
        raw = read_pinned_source(dependency["path"], args.source_root)
        check_dependency(raw, dependency)
        dependency_raws.append(raw)

    negatives = run_negative_controls(
        handoff,
        packet,
        prior_indices,
        DOSSIER_PATH.read_bytes(),
        dependency_raws,
        args.source_root,
    )
    for record in handoff["records"]:
        print(
            "P0_SECOND_PACKET_SPECIAL_SOURCE_PARTIAL",
            record["packet_index"],
            record["path"],
            record["git_blob_sha1"],
        )
    print(
        "P0_SECOND_PACKET_SPECIAL_SOURCES_PASS "
        f"files={len(INDICES)} dependencies={len(dependency_raws)} negatives={negatives} "
        "source_and_dossier_bytes=VERIFIED whole_file_dispositions=0 approvals=0 "
        "gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()

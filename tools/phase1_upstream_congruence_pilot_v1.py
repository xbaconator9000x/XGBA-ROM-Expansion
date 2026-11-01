#!/usr/bin/env python3
"""Reconcile the pinned PR8 inventory and measure the mGBA ROM pilot."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from phase1_upstream_verified_v1 import (
    DOSSIER_BLOB,
    DOSSIER_PATH,
    DOSSIER_SHA256,
    GATE_BLOB,
    GATE_PATH,
    P0_CANDIDATES,
    QUEUE_BLOB,
    QUEUE_PATH,
    QUEUE_SHA256,
    REGISTER_BLOB,
    REGISTER_PATH,
    REGISTER_SHA256,
    EvidenceError,
    PINS,
    canonical_bytes,
    git_blob_sha,
    sha256,
)

SCHEMA = "xgba.phase1.upstream_congruence_pilot.v1"
BEHAVIOR_SCHEMA = "xgba.phase1.behavioral_congruence_evidence.v2"
INVENTORY_SIZE = 14834
PR8_HEAD = "12bebda10473877e8f82faf3806d4fbbf0f882df"
PR8_INDEX_PATH = "docs/phase1-review-readiness/inventory-source-index-20261101.json.gz"
PR8_INDEX_SHA256 = "aaeb605aa9906e979b66c532bc34336f88d8255e534701f2ea6629da3de8a0db"
PR8_INDEX_BLOB = "d82c9edd68b3facb4cdc1623111f62c397c0b486"
PR8_DOSSIER_PATH = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
PR8_DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
PR8_DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
PR8_QUEUE_BLOB = "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268"
PILOT_REPOSITORY = "mgba-emu/mgba"
PILOT_REVISION = "fd9dc5c2cbf234365068855851107e762fc6211b"
PILOT_LICENSE_BLOB = "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e"
PILOT_FILES = {
    "src/arm/arm.c": (
        "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
    ),
    "src/gba/cart/matrix.c": (
        "9ccbe883235b98bcf56cd609015e7b4003aa832c",
        "6e47afc6992d3631d67f89cb201d7fe9784ef8a9e8dcb305c1ab5de48550ef8f",
    ),
    "src/gba/dma.c": (
        "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
        "cd4c795f69ec16373e475b4c902e863e4a6db61cd2b9f1c4d851496d3202b9d1",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "src/gba/memory.c": (
        "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
    ),
    "src/gba/serialize.c": (
        "a307a51e751f412c64a7378323c56758304ebe85",
        "23947295749e6eeb27ab13d2a6d4c18bf88b587bcf3109e6d3e6bab5a5658dc3",
    ),
}
PILOT_RISK_CONTROLS = {
    "MATRIX_BACKING_RANGE": {
        "outcome": "UNSAFE_BEHAVIOR_REJECTED",
        "test_case": "native_matrix_rejects_physical_range_past_end",
        "paths": ["src/gba/cart/matrix.c"],
    },
    "MATRIX_SHORT_READ": {
        "outcome": "SHORT_READ_REJECTED",
        "test_case": "native_matrix_rejects_short_backing_read",
        "paths": ["src/gba/cart/matrix.c"],
    },
    "PREFETCH_INVALIDATION": {
        "outcome": "STALE_PREFETCH_REJECTED",
        "test_case": "native_remap_invalidates_prefetch_before_next_step",
        "paths": ["src/arm/arm.c", "src/gba/memory.c"],
    },
    "DMA_PERIPHERAL_INTERACTION": {
        "outcome": "UNSAFE_INTERACTION_REJECTED",
        "test_case": "native_dma_matrix_remap_preserves_peripheral_arbitration",
        "paths": ["src/gba/dma.c", "src/gba/cart/matrix.c", "src/gba/memory.c"],
    },
    "SAVESTATE_BACKING_IDENTITY": {
        "outcome": "ALTERED_BACKING_REJECTED",
        "test_case": "native_savestate_rejects_changed_backing_identity",
        "paths": ["src/gba/serialize.c", "src/gba/cart/matrix.c"],
    },
    "DEPENDENCY_CONSUMER_CLOSURE": {
        "outcome": "INCOMPLETE_CLOSURE_REJECTED",
        "test_case": "validator_rejects_incomplete_dependency_consumer_closure",
        "paths": sorted(PILOT_FILES),
    },
    "DISTRIBUTION_LICENSE_CLEARANCE": {
        "outcome": "UNCLEARED_LICENSE_REJECTED",
        "test_case": "validator_rejects_unassessed_or_incompatible_license",
        "paths": sorted(PILOT_FILES),
    },
}
PILOT_SOURCE_EVIDENCE = {
    "src/arm/CMakeLists.txt": "a86f0bea1f38aeb88222fb5b532b4ea9e256767f",
    "src/gba/CMakeLists.txt": "71ab7bbb199ad95422e35ded5774c06a1b2e7c5c",
    "src/gba/test/core.c": "25b8f3ce30b59c3ecde8ecb377ea80964888b0ae",
}
PILOT_CMAKE_MEMBERSHIP = {
    "src/arm/arm.c": "src/arm/CMakeLists.txt",
    "src/gba/cart/matrix.c": "src/gba/CMakeLists.txt",
    "src/gba/dma.c": "src/gba/CMakeLists.txt",
    "src/gba/gba.c": "src/gba/CMakeLists.txt",
    "src/gba/memory.c": "src/gba/CMakeLists.txt",
    "src/gba/serialize.c": "src/gba/CMakeLists.txt",
}
LOCAL_EVIDENCE = {
    "semantic-snapshots/current/resource_lifecycle_contracts.csv": (
        "4e55e0f333dad5a593eccbff236bff8c92ece1b968f51f08af5713dd9e4806b9",
        "806198b489f4e91c5817b3ff4de0f139ea5e5cb1",
    ),
    "semantic-snapshots/current/resource_lifecycle_contracts_summary.json": (
        "cd1be207a1042b486252bd6ece15a3a01a50e807c4eecb1cedee6535f3b627bb",
        "442b6189fd22beec3426b770e8ceea08718013ed",
    ),
    "tests/mgba_bank_boundary.c": (
        "f4ae6023b1d1416be1ec611e2c2df61610f3f28be6240354746a95467d350839",
        "e09ca92ee8614100efde34f443b84a7dc86e0676",
    ),
    "tests/run_pinned_mgba_boundary.sh": (
        "908139eb527ae84dac0c92c430571fdbda66216642ede81acfdd090cfc5788ae",
        "7a8462d60a4ff789e8e4972b871facbed9e06e92",
    ),
    "tests/CMakeLists.txt": (
        "7035354e527c93b37300b7dc4960d38457b78872cd940a52e8668938203346a5",
        "21287a7ce4504c0c8ae261d2d3fcecc24e888a23",
    ),
    "docs/PHASE1_P0_MATRIX_NATIVE_BOUNDARY_PROBE_2026-10-26.md": (
        "4faf43ed286f5bef42ce86ead00c990dd6917ecc4150236d7be85dfceae13ec3",
        "072bb651f8788bd1b8f39c0f6c41d70a67aa566e",
    ),
}
EXPECTED_PR8_LIMITS = {
    "Dependency edges are literal C-preprocessor or assembler include candidates, not compiler closure.",
    "Direct test include links are candidate links only and do not establish coverage.",
    "License files and notices do not establish distribution clearance.",
    "No record is semantically reviewed or approved by this indexer.",
    "No source-defined semantic invariants are automatically extracted by this index.",
}


def _read_exact(path: Path, expected_sha256: str, expected_blob: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise EvidenceError(f"Required pinned evidence is missing or unsafe: {path}", "BLOCKED")
    data = path.read_bytes()
    if sha256(data) != expected_sha256 or git_blob_sha(data) != expected_blob:
        raise EvidenceError(f"Pinned evidence digest mismatch: {path}", "BLOCKED")
    return data


def _load_json_gzip(data: bytes, label: str):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as stream:
            expanded = stream.read(512 * 1024 * 1024 + 1)
        if len(expanded) > 512 * 1024 * 1024:
            raise EvidenceError(f"Expanded {label} exceeds the 512 MiB limit", "BLOCKED")
        return json.loads(expanded)
    except (OSError, EOFError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Invalid compressed JSON in {label}", "BLOCKED") from exc


def _load_dossiers(
    data: bytes, label: str, expected_count: int = INVENTORY_SIZE
) -> dict[tuple[str, str], dict]:
    try:
        with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(data)), encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream]
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Invalid dossier archive: {label}", "BLOCKED") from exc
    result = {}
    for row in records:
        provenance = row.get("provenance", {})
        key = (provenance.get("repository"), provenance.get("path"))
        if not all(isinstance(part, str) and part for part in key) or key in result:
            raise EvidenceError(f"Duplicate or invalid dossier identity in {label}", "BLOCKED")
        result[key] = row
    if len(result) != expected_count:
        raise EvidenceError(f"Incomplete dossier archive: {label}", "BLOCKED")
    return result


def _load_queue(data: bytes, expected_count: int = INVENTORY_SIZE) -> dict[tuple[str, str], dict]:
    try:
        with io.TextIOWrapper(
            gzip.GzipFile(fileobj=io.BytesIO(data)), encoding="utf-8", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise EvidenceError("Invalid pinned review queue", "BLOCKED") from exc
    result = {}
    for row in rows:
        key = (row.get("repo"), row.get("path"))
        if not all(isinstance(part, str) and part for part in key) or key in result:
            raise EvidenceError("Duplicate or invalid review-queue identity", "BLOCKED")
        result[key] = row
    if len(result) != expected_count:
        raise EvidenceError("Incomplete pinned review queue", "BLOCKED")
    return result


def _verify_pinned_bytes(data: bytes, expected_sha256: str, expected_blob: str, label: str) -> None:
    if sha256(data) != expected_sha256 or git_blob_sha(data) != expected_blob:
        raise EvidenceError(f"Pinned evidence digest mismatch: {label}", "BLOCKED")


def _validate_pr8_index(index_bytes: bytes) -> dict:
    if sha256(index_bytes) != PR8_INDEX_SHA256 or git_blob_sha(index_bytes) != PR8_INDEX_BLOB:
        raise EvidenceError("PR8 source-index archive digest mismatch", "BLOCKED")
    index = _load_json_gzip(index_bytes, "PR8 source index")
    identity = index.get("snapshot_identity", {})
    if (
        index.get("schema") != "xgba.phase1.inventory_source_index.v1"
        or index.get("status") != "SOURCE_INDEX_ONLY_NO_SEMANTIC_DISPOSITIONS"
        or identity.get("mapping_gate_git_blob_sha1") != GATE_BLOB
        or identity.get("review_queue_git_blob_sha1") != PR8_QUEUE_BLOB
        or identity.get("source_dossier_archive_git_blob_sha1") != PR8_DOSSIER_BLOB
        or index.get("gate") != {
            "decision": "FAIL_INCOMPLETE",
            "inventory_total": INVENTORY_SIZE,
            "legacy_approvals": 0,
            "p0_total": P0_CANDIDATES,
            "semantic_dispositions_added": 0,
        }
        or index.get("run", {}).get("indexed_count") != INVENTORY_SIZE
        or index.get("run", {}).get("indexed_p0_count") != P0_CANDIDATES
        or index.get("run", {}).get("blocked_count") != 0
        or index.get("run", {}).get("unindexed_count") != 0
    ):
        raise EvidenceError("PR8 index snapshot or census metadata mismatch", "BLOCKED")
    if not EXPECTED_PR8_LIMITS.issubset(set(index.get("evidence_boundaries", []))):
        raise EvidenceError("PR8 index evidence boundaries are missing", "BLOCKED")
    rows = index.get("source_records")
    if not isinstance(rows, list) or len(rows) != INVENTORY_SIZE:
        raise EvidenceError("PR8 source index is incomplete", "BLOCKED")
    return index


def _verify_dossier_row(key, queue, pr2_dossier, pr8_dossier, index_row):
    pr2_hash = sha256(canonical_bytes(pr2_dossier))
    pr8_hash = sha256(canonical_bytes(pr8_dossier))
    provenance = pr2_dossier.get("provenance", {})
    identity = index_row.get("identity", {})
    source_sha256 = provenance.get("source_content_sha256")
    source_bytes = provenance.get("tracked_bytes")
    if (
        pr2_hash != queue.get("evidence_sha256")
        or pr8_hash != pr2_hash
        or provenance.get("repository") != key[0]
        or provenance.get("path") != key[1]
        or provenance.get("pinned_revision") != dict((repo, pin) for repo, pin, _ in PINS).get(key[0])
        or provenance.get("git_blob_sha") != queue.get("blob_sha")
        or pr2_dossier.get("review", {}).get("semantic_signoff") is not False
        or index_row.get("machine_dossier", {}).get("original_archive_git_blob_sha1") != PR8_DOSSIER_BLOB
        or index_row.get("machine_dossier", {}).get("sha256") != pr2_hash
        or index_row.get("machine_dossier", {}).get("semantic_signoff") is not False
        or (
            index_row.get("machine_dossier", {}).get("source_content_sha256_present") is True
            and not source_sha256
        )
        or (source_sha256 is not None and identity.get("source_sha256") != source_sha256)
        or (source_bytes is not None and identity.get("source_bytes") != int(source_bytes))
    ):
        raise EvidenceError(f"Queue/dossier/index identity mismatch: {key[0]}:{key[1]}", "BLOCKED")
    if (
        identity.get("repository") != key[0]
        or identity.get("path") != key[1]
        or identity.get("git_blob_sha1") != queue.get("blob_sha")
        or identity.get("pinned_commit") != provenance.get("pinned_revision")
        or index_row.get("approval_state") != "NOT_APPROVED"
        or index_row.get("semantic_review_state") != "NOT_SEMANTICALLY_REVIEWED"
        or index_row.get("source_index_state") != "SOURCE_INDEXED"
        or index_row.get("source_index_reason_code") != "SOURCE_BLOB_AND_DOSSIER_VERIFIED"
    ):
        raise EvidenceError(f"Source-index identity or non-approval state mismatch: {key[0]}:{key[1]}", "BLOCKED")
    return pr2_hash


def _reconcile_rows(queue, pr2_dossiers, pr8_dossiers, index_rows, expected_count=INVENTORY_SIZE):
    if not (
        len(queue) == len(pr2_dossiers) == len(pr8_dossiers) == len(index_rows) == expected_count
        and queue.keys() == pr2_dossiers.keys() == pr8_dossiers.keys() == index_rows.keys()
    ):
        raise EvidenceError("Queue, dossiers, and source index have incomplete or divergent identities", "BLOCKED")
    for key, queued in queue.items():
        if queued.get("repo") not in dict((repo, pin) for repo, pin, _ in PINS):
            raise EvidenceError(f"Unexpected repository in pinned queue: {key[0]}", "BLOCKED")
        _verify_dossier_row(key, queued, pr2_dossiers[key], pr8_dossiers[key], index_rows[key])


def _index_rows(rows) -> dict[tuple[str, str], dict]:
    result = {}
    for row in rows:
        identity = row.get("identity", {})
        key = (identity.get("repository"), identity.get("path"))
        if key in result or not all(isinstance(part, str) and part for part in key):
            raise EvidenceError("Duplicate or malformed PR8 source-index identity", "BLOCKED")
        result[key] = row
    return result


def _dependency_candidate_component(index_rows, seeds):
    graph = {}
    for (repository, path), row in index_rows.items():
        source = (repository, path)
        graph.setdefault(source, set())
        for dependency in row.get("direct_dependencies", []):
            for candidate in dependency.get("candidate_target_paths", []):
                target = (repository, candidate)
                graph.setdefault(target, set())
                graph[source].add(target)
                graph[target].add(source)
    component = set()
    pending = list(seeds)
    while pending:
        node = pending.pop()
        if node in component:
            continue
        component.add(node)
        pending.extend(graph.get(node, set()) - component)
    return component


def _validate_candidate_evidence(
    record: dict, expected: dict, verify_reference=None, verify_actions=None
) -> list[str]:
    """Validate a versioned behavioral claim; fixtures exercise this helper only."""
    if not isinstance(record, dict) or not isinstance(expected, dict):
        return ["BEHAVIORAL_RECORD_INVALID"]

    def positive_int(value):
        return type(value) is int and value > 0

    def sha256_hex(value):
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    reasons = []
    supplied_digest = record.get("record_sha256")
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    if record.get("schema") != BEHAVIOR_SCHEMA:
        reasons.append("BEHAVIORAL_SCHEMA_MISMATCH")
    if supplied_digest != sha256(canonical_bytes(payload)):
        reasons.append("BEHAVIORAL_RECORD_DIGEST_MISMATCH")
    if record.get("identity") != expected:
        reasons.append("SOURCE_OR_DOSSIER_IDENTITY_MISMATCH")
    scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    claim_ids = scope.get("claim_ids", [])
    if (
        scope.get("claim_level") != "whole_file"
        or scope.get("line_coverage") != [[1, expected.get("source_line_count")]]
        or not isinstance(claim_ids, list)
        or not claim_ids
        or any(not isinstance(claim_id, str) or not claim_id for claim_id in claim_ids)
        or len(set(claim_ids)) != len(claim_ids)
    ):
        reasons.append("WHOLE_FILE_SCOPE_INCOMPLETE")
        claim_ids = []
    semantic = record.get("semantic_map") if isinstance(record.get("semantic_map"), dict) else {}
    if (
        not semantic.get("statements")
        or semantic.get("claim_ids") != claim_ids
        or not semantic.get("source_refs")
        or not semantic.get("specification_refs")
    ):
        reasons.append("UPSTREAM_SEMANTIC_MAP_OR_SPECIFICATION_MISSING")
    closure = record.get("dependency_closure") if isinstance(record.get("dependency_closure"), dict) else {}
    dependencies = closure.get("dependencies", [])
    consumers = closure.get("consumers", [])
    if not isinstance(dependencies, list):
        dependencies = []
        reasons.append("DEPENDENCY_OR_CONSUMER_CLOSURE_INCOMPLETE")
    if (
        closure.get("complete") is not True
        or not dependencies
        or not isinstance(consumers, list)
        or not consumers
        or closure.get("unresolved")
        or closure.get("dependency_digest_sha256")
        != sha256(canonical_bytes({"dependencies": dependencies, "consumers": consumers}))
    ):
        reasons.append("DEPENDENCY_OR_CONSUMER_CLOSURE_INCOMPLETE")
    tests = record.get("tests") if isinstance(record.get("tests"), dict) else {}
    actions = tests.get("actions") if isinstance(tests.get("actions"), dict) else {}
    counterexample_claim_ids = tests.get("counterexample_claim_ids", [])
    if not isinstance(counterexample_claim_ids, list):
        counterexample_claim_ids = []
    if (
        tests.get("executed") is not True
        or type(tests.get("exit_code")) is not int
        or tests.get("exit_code") != 0
        or not tests.get("test_source_refs")
        or not positive_int(tests.get("positive_cases"))
        or not positive_int(tests.get("negative_counterexamples"))
        or tests.get("covered_claim_ids") != claim_ids
        or any(not isinstance(claim_id, str) or not claim_id for claim_id in counterexample_claim_ids)
        or not set(counterexample_claim_ids).issubset(set(claim_ids))
        or not counterexample_claim_ids
        or not sha256_hex(tests.get("result_sha256"))
        or actions.get("head_sha") != expected.get("revision")
        or actions.get("conclusion") != "success"
        or actions.get("event") not in {"push", "pull_request"}
        or not positive_int(actions.get("total_jobs"))
        or type(actions.get("successful_jobs")) is not int
        or type(actions.get("executed_jobs")) is not int
        or actions.get("successful_jobs") != actions.get("total_jobs")
        or actions.get("executed_jobs") != actions.get("total_jobs")
    ):
        reasons.append("PINNED_POSITIVE_AND_NEGATIVE_TEST_EXECUTION_MISSING")
    risk_controls = record.get("risk_controls")
    if not isinstance(risk_controls, list):
        risk_controls = []
    risk_control_map = {}
    for control in risk_controls:
        if not isinstance(control, dict):
            continue
        risk_id = control.get("risk_id")
        if not isinstance(risk_id, str) or risk_id not in PILOT_RISK_CONTROLS:
            reasons.append("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE")
        elif risk_id in risk_control_map:
            reasons.append("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE")
        else:
            risk_control_map[risk_id] = control
    if set(risk_control_map) != set(PILOT_RISK_CONTROLS):
        reasons.append("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE")
    risk_references = []
    for risk_id, requirement in PILOT_RISK_CONTROLS.items():
        control = risk_control_map.get(risk_id, {})
        result_digest = control.get("result_sha256")
        test_refs = control.get("test_source_refs")
        source_refs = control.get("source_refs")
        expected_source_refs = [
            {
                "repository": PILOT_REPOSITORY,
                "path": path,
                "revision": PILOT_REVISION,
                "git_blob_sha1": PILOT_FILES[path][0],
                "source_sha256": PILOT_FILES[path][1],
            }
            for path in requirement["paths"]
        ]
        if (
            control.get("executed") is not True
            or control.get("outcome") != requirement["outcome"]
            or control.get("test_case") != requirement["test_case"]
            or not isinstance(result_digest, str)
            or len(result_digest) != 64
            or any(character not in "0123456789abcdef" for character in result_digest)
            or not isinstance(test_refs, list)
            or not test_refs
            or source_refs != expected_source_refs
        ):
            reasons.append("RISK_SPECIFIC_NEGATIVE_CONTROLS_INCOMPLETE")
        else:
            risk_references.extend(test_refs)
            risk_references.extend(source_refs)
    licensing = record.get("licensing") if isinstance(record.get("licensing"), dict) else {}
    if licensing.get("distribution_clearance") != "CLEARED" or not licensing.get("evidence_refs"):
        reasons.append("LICENSING_SCOPE_NOT_CLEARED")
    if record.get("unresolved_objections") != []:
        reasons.append("UNRESOLVED_SUBSTANTIVE_OBJECTIONS")
    if record.get("contradictory_evidence") != []:
        reasons.append("CONTRADICTORY_EVIDENCE_PRESENT")
    reference_groups = (
        semantic.get("source_refs", []),
        semantic.get("specification_refs", []),
        dependencies,
        consumers,
        tests.get("test_source_refs", []),
        risk_references,
        licensing.get("evidence_refs", []),
    )
    if any(not isinstance(group, list) for group in reference_groups):
        reasons.append("REFERENCED_ARTIFACTS_NOT_REVERIFIED")
        references = []
    else:
        references = [reference for group in reference_groups for reference in group]
    if verify_reference is None or any(not verify_reference(reference) for reference in references):
        reasons.append("REFERENCED_ARTIFACTS_NOT_REVERIFIED")
    try:
        actions_verified = verify_actions is not None and verify_actions(actions)
    except Exception:
        actions_verified = False
    if not actions_verified:
        reasons.append("EXACT_HEAD_ACTIONS_PROVENANCE_NOT_REVERIFIED")
    return list(dict.fromkeys(reasons))


def _native_build_status(root: Path) -> dict:
    checkout = root / "upstream/mgba"
    source_present = (checkout / "src/gba/cart/matrix.c").is_file() and not checkout.is_symlink()
    cmake_present = shutil.which("cmake") is not None
    compiler_present = shutil.which("cc") is not None
    pinned_revision_verified = False
    checkout_clean = False
    if source_present:
        try:
            revision = subprocess.run(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            status = subprocess.run(
                ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=all"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            pinned_revision_verified = revision == PILOT_REVISION
            checkout_clean = not status
        except (OSError, subprocess.CalledProcessError):
            pass
    missing = []
    if not source_present:
        missing.append("PINNED_MGBA_SOURCE_CHECKOUT_ABSENT")
    elif not pinned_revision_verified:
        missing.append("PINNED_MGBA_REVISION_NOT_VERIFIED")
    if source_present and not checkout_clean:
        missing.append("PINNED_MGBA_CHECKOUT_NOT_CLEAN")
    if not cmake_present:
        missing.append("CMAKE_UNAVAILABLE")
    if not compiler_present:
        missing.append("C_COMPILER_UNAVAILABLE")
    return {
        "status": "BLOCKED" if missing else "READY_NOT_EXECUTED",
        "checkout_path": "upstream/mgba",
        "pinned_revision": PILOT_REVISION,
        "required_source_present": source_present,
        "pinned_revision_verified": pinned_revision_verified,
        "checkout_clean": checkout_clean,
        "cmake_available": cmake_present,
        "c_compiler_available": compiler_present,
        "native_probe_executed": False,
        "preprocessor_closure": "NOT_ESTABLISHED",
        "consumer_closure": "NOT_ESTABLISHED",
        "reason_codes": missing or ["NATIVE_PROBE_NOT_EXECUTED"],
        "configure_file": "tests/CMakeLists.txt",
        "configure_guard": "Requires upstream/mgba/src/gba/cart/matrix.c and otherwise exits before configuration.",
        "runner_caution": "Do not run the clone-capable runner when the pinned checkout is absent.",
    }


def _risk_obligation_report() -> list[dict]:
    records = [
        {
            "risk_id": "MATRIX_BACKING_RANGE",
            "paths": ["src/gba/cart/matrix.c"],
            "source_finding": "_remapMatrix validates the virtual window but does not check the physical range against backing-file size before mapping.",
            "fixture_case": "native_matrix_accepts_physical_range_past_end",
            "evidence_state": "SOURCE_GAP_AND_FIXTURE_CASE_PRESENT_NOT_EXECUTED",
            "reason_code": "MATRIX_BACKING_RANGE_CONTROL_NOT_EXECUTED",
        },
        {
            "risk_id": "MATRIX_SHORT_READ",
            "paths": ["src/gba/cart/matrix.c"],
            "source_finding": "_remapMatrix calls VFile seek/read without checking their return values.",
            "fixture_case": None,
            "evidence_state": "SHORT_READ_CONTROL_NOT_PRESENT_OR_EXECUTED",
            "reason_code": "MATRIX_SHORT_READ_CONTROL_MISSING",
        },
        {
            "risk_id": "PREFETCH_INVALIDATION",
            "paths": ["src/arm/arm.c", "src/gba/memory.c"],
            "source_finding": "ARM/Thumb execution consumes active-region and prefetch state; remapping requires explicit fetch-state synchronization.",
            "fixture_case": "native_remap_leaves_prefetch_stale_until_refetch",
            "evidence_state": "STALE_PREFETCH_OBSERVATION_PRESENT_NOT_EXECUTED",
            "reason_code": "PREFETCH_INVALIDATION_CONTROL_NOT_EXECUTED",
        },
        {
            "risk_id": "DMA_PERIPHERAL_INTERACTION",
            "paths": ["src/gba/dma.c", "src/gba/cart/matrix.c", "src/gba/memory.c"],
            "source_finding": "DMA has ROM2_EX and EEPROM-specific paths; the fixture covers EEPROM reads but not concurrent Matrix remap arbitration.",
            "fixture_case": "native_DMA3_16bit_ROM2_EX_reads_EEPROM",
            "evidence_state": "PERIPHERAL_FIXTURE_PRESENT_CROSS_SUBSYSTEM_CASE_NOT_EXECUTED",
            "reason_code": "DMA_MATRIX_INTERACTION_CONTROL_NOT_EXECUTED",
        },
        {
            "risk_id": "SAVESTATE_BACKING_IDENTITY",
            "paths": ["src/gba/serialize.c", "src/gba/cart/matrix.c"],
            "source_finding": "A ROM CRC mismatch warns rather than rejecting state; external backing identity is not bound by that CRC check.",
            "fixture_case": "native_savestate_external_bank_payload_change_unverified",
            "evidence_state": "UNVERIFIED_BACKING_OBSERVATION_PRESENT_NOT_EXECUTED",
            "reason_code": "SAVESTATE_BACKING_IDENTITY_CONTROL_NOT_EXECUTED",
        },
        {
            "risk_id": "DEPENDENCY_CONSUMER_CLOSURE",
            "paths": sorted(PILOT_FILES),
            "source_finding": "Pinned CMake lists establish target membership only; lexical include candidates do not prove preprocessor, call, data-flow, or consumer closure.",
            "fixture_case": None,
            "evidence_state": "BUILD_AND_CONSUMER_CLOSURE_NOT_ESTABLISHED",
            "reason_code": "PINNED_PREPROCESSOR_AND_CONSUMER_CLOSURE_NOT_ESTABLISHED",
        },
        {
            "risk_id": "DISTRIBUTION_LICENSE_CLEARANCE",
            "paths": sorted(PILOT_FILES),
            "source_finding": "Pinned source headers and LICENSE identify MPL-2.0; distribution and compatibility clearance is not assessed.",
            "fixture_case": None,
            "evidence_state": "LICENSE_NOTICE_PRESENT_DISTRIBUTION_CLEARANCE_NOT_ASSESSED",
            "reason_code": "LICENSE_DISTRIBUTION_CLEARANCE_NOT_ASSESSED",
        },
    ]
    return records


def _verify_local_evidence(root: Path) -> tuple[list[dict], dict]:
    for relative, (expected_sha, expected_blob) in LOCAL_EVIDENCE.items():
        _read_exact(root / relative, expected_sha, expected_blob)
    with (root / "semantic-snapshots/current/resource_lifecycle_contracts.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        contracts = list(csv.DictReader(stream))
    mgba_contracts = [row for row in contracts if row.get("repo") == PILOT_REPOSITORY]
    if len(mgba_contracts) != 6 or any(row.get("runtime_test_status") != "NOT_RUN" for row in mgba_contracts):
        raise EvidenceError("Pinned mGBA source-contract evidence changed or implies runtime execution", "BLOCKED")
    summary = json.loads(
        (root / "semantic-snapshots/current/resource_lifecycle_contracts_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        summary.get("critical_areas", {}).get("mGBA_ROM_lifecycle") != 6
        or summary.get("runtime_paths_exercised") != 0
        or summary.get("whole_file_semantic_dispositions_approved") != 0
    ):
        raise EvidenceError("Pinned mGBA source-contract summary changed", "BLOCKED")
    return mgba_contracts, summary


def reconcile(root: Path, index_bytes: bytes, pr8_dossier_bytes: bytes) -> dict:
    index = _validate_pr8_index(index_bytes)
    _verify_pinned_bytes(
        pr8_dossier_bytes, PR8_DOSSIER_SHA256, PR8_DOSSIER_BLOB, "PR8 original dossier archive"
    )

    gate = _read_exact(
        root / GATE_PATH,
        "7df6ceb6641ccb24cdc114f0ed6af10bc0ecbf3b42db484b26be41907e96d953",
        GATE_BLOB,
    )
    gate_data = json.loads(gate)
    if (
        gate_data.get("decision") != "FAIL_INCOMPLETE"
        or gate_data.get("verified_source_manifest_entries") != INVENTORY_SIZE
        or gate_data.get("machine_generated_dossiers") != INVENTORY_SIZE
        or gate_data.get("p0_review_candidates") != P0_CANDIDATES
        or gate_data.get("approved_semantic_dispositions") != 0
    ):
        raise EvidenceError("Historical Phase 1 gate baseline changed", "BLOCKED")
    register = json.loads(
        _read_exact(root / REGISTER_PATH, REGISTER_SHA256, REGISTER_BLOB)
    )
    if (
        register.get("schema") != "xgba.phase1.upstream_congruence_register.v1"
        or register.get("records") != []
    ):
        raise EvidenceError("Pinned exact-byte v1 proposal register is not empty or changed", "BLOCKED")

    queue_bytes = _read_exact(root / QUEUE_PATH, QUEUE_SHA256, QUEUE_BLOB)
    dossier_bytes = _read_exact(root / DOSSIER_PATH, DOSSIER_SHA256, DOSSIER_BLOB)
    queue = _load_queue(queue_bytes)
    pr2_dossiers = _load_dossiers(dossier_bytes, "PR2 original dossier archive")
    pr8_dossiers = _load_dossiers(pr8_dossier_bytes, "PR8 original dossier archive")
    index_rows = _index_rows(index["source_records"])
    _reconcile_rows(queue, pr2_dossiers, pr8_dossiers, index_rows)

    contracts, contract_summary = _verify_local_evidence(root)
    catalog = index.get("repository_evidence_catalog", {}).get(PILOT_REPOSITORY, {})
    license_state = catalog.get("license_assessment", {})
    if (
        catalog.get("pinned_commit") != PILOT_REVISION
        or license_state.get("distribution_clearance") != "NOT_ASSESSED"
        or catalog.get("test_source_evidence_state") != "HASH_VERIFIED_TEST_SOURCE_FILES_PRESENT_NOT_EXECUTED"
    ):
        raise EvidenceError("mGBA license or test evidence state changed", "BLOCKED")
    if len(index["run"].get("dependency_edges_by_resolution", {})) < 3:
        raise EvidenceError("PR8 dependency-candidate summary is incomplete", "BLOCKED")

    pilot_keys = {(PILOT_REPOSITORY, path) for path in PILOT_FILES}
    lexical_component = _dependency_candidate_component(index_rows, {min(pilot_keys)})
    if not pilot_keys.issubset(lexical_component):
        raise EvidenceError("The selected mGBA ROM files are not dependency-connected in the index", "BLOCKED")

    native_build = _native_build_status(root)
    risk_obligations = _risk_obligation_report()
    candidates = []
    resolution_totals = Counter()
    direct_test_links = 0
    unresolved_edges = 0
    for path, (expected_blob, expected_sha) in sorted(PILOT_FILES.items()):
        key = (PILOT_REPOSITORY, path)
        row = index_rows.get(key)
        if row is None:
            raise EvidenceError(f"mGBA ROM pilot source absent from index: {path}", "BLOCKED")
        identity = row["identity"]
        if (
            identity.get("pinned_commit") != PILOT_REVISION
            or identity.get("git_blob_sha1") != expected_blob
            or identity.get("source_sha256") != expected_sha
            or identity.get("source_materialization") != "ARCHIVE_BYTES_MATCH_PINNED_GIT_BLOB"
            or row.get("inventory", {}).get("priority") != "P0"
        ):
            raise EvidenceError(f"mGBA pilot source pin mismatch: {path}", "BLOCKED")
        resolution_counts = Counter(
            dependency.get("resolution") for dependency in row.get("direct_dependencies", [])
        )
        resolution_totals.update(resolution_counts)
        unresolved_edges += row.get("direct_dependency_unresolved_count", 0)
        direct_test_links += row.get("upstream_test_source_candidate_count", 0)
        reasons = [
            "NO_WHOLE_FILE_SEMANTIC_MAP",
            "LEXICAL_INCLUDE_CANDIDATES_ARE_NOT_DEPENDENCY_CLOSURE",
            "PINNED_POSITIVE_AND_NEGATIVE_TESTS_NOT_EXECUTED",
            "LICENSE_DISTRIBUTION_CLEARANCE_NOT_ASSESSED",
            "WHOLE_FILE_DEPENDENCY_AND_CONSUMER_SCOPE_NOT_ESTABLISHED",
            "SUBSTANTIVE_ROM_BOUNDARY_OBJECTIONS_REMAIN_OPEN",
        ]
        if row.get("upstream_test_source_candidate_count", 0) == 0:
            reasons.append("NO_DIRECT_TEST_LINK_CANDIDATE")
        if row.get("direct_dependency_unresolved_count", 0):
            reasons.append("UNRESOLVED_LITERAL_INCLUDE_CANDIDATE")
        file_contracts = [
            {
                "contract_id": contract["contract_id"],
                "begin_line": int(contract["begin_line"]),
                "end_line": int(contract["end_line"]),
                "source_exact_anchors": json.loads(contract["source_exact_anchors"]),
                "observed_semantics": contract["observed_semantics"],
                "required_extension_invariant": contract["required_extension_invariant"],
                "verification_type": contract["verification_type"],
                "runtime_test_status": contract["runtime_test_status"],
            }
            for contract in contracts
            if contract["path"] == path
        ]
        candidates.append(
            {
                "repository": PILOT_REPOSITORY,
                "path": path,
                "pinned_revision": PILOT_REVISION,
                "git_blob_sha1": expected_blob,
                "source_sha256": expected_sha,
                "priority": "P0",
                "v1_exact_bytes_eligible": False,
                "v1_reason_codes": ["NO_DISTINCT_BYTE_IDENTICAL_IMPLEMENTATION_REFERENCE"],
                "behavioral_congruence_disposition": "NEEDS_REVIEW",
                "behavioral_reason_codes": reasons,
                "source_index_state": row["source_index_state"],
                "semantic_review_state": row["semantic_review_state"],
                "source_and_dossier_evidence": {
                    "source_content_sha256": identity["source_sha256"],
                    "source_byte_count": identity["source_bytes"],
                    "source_identity_from_pinned_index": True,
                    "source_bytes_reopened_in_this_run": False,
                    "original_machine_dossier_sha256": row["machine_dossier"]["sha256"],
                    "pr8_original_compressed_dossier_sha256": PR8_DOSSIER_SHA256,
                    "pr2_original_compressed_dossier_sha256": DOSSIER_SHA256,
                    "canonical_dossier_records_equal": True,
                },
                "source_contract_evidence": file_contracts,
                "build_membership_evidence": {
                    "cmake_file": PILOT_CMAKE_MEMBERSHIP[path],
                    "cmake_git_blob_sha1": PILOT_SOURCE_EVIDENCE[
                        PILOT_CMAKE_MEMBERSHIP[path]
                    ],
                    "membership_state": "SOURCE_LISTED_NOT_COMPILED",
                    "preprocessor_and_consumer_closure": "NOT_ESTABLISHED",
                    "build_status": native_build["status"],
                },
                "license_evidence": {
                    "source_notice": "MPL-2.0",
                    "license_file_git_blob_sha1": PILOT_LICENSE_BLOB,
                    "distribution_clearance": "NOT_ASSESSED",
                },
                "risk_obligations": [
                    obligation
                    for obligation in risk_obligations
                    if path in obligation["paths"]
                ],
                "direct_dependency_candidates": len(row.get("direct_dependencies", [])),
                "direct_dependency_resolution_counts": dict(sorted(resolution_counts.items())),
                "direct_test_link_candidates": row.get("upstream_test_source_candidate_count", 0),
            }
        )

    if len(candidates) != len(PILOT_FILES):
        raise EvidenceError("mGBA ROM pilot target set is incomplete", "BLOCKED")
    return {
        "schema": SCHEMA,
        "proposal_state": "PROSPECTIVE_NOT_ACTIVATED",
        "pr8_evidence": {
            "head": PR8_HEAD,
            "index_path": PR8_INDEX_PATH,
            "index_sha256": PR8_INDEX_SHA256,
            "index_git_blob_sha1": PR8_INDEX_BLOB,
            "dossier_path": PR8_DOSSIER_PATH,
            "dossier_archive_sha256": PR8_DOSSIER_SHA256,
            "dossier_git_blob_sha1": PR8_DOSSIER_BLOB,
            "compressed_dossier_archives_byte_identical": False,
            "canonical_dossier_records_equal": True,
            "reconciled_inventory_identities": len(queue),
            "identity_mismatches": 0,
        },
        "historical_gate": {
            "decision": gate_data["decision"],
            "inventory_total": INVENTORY_SIZE,
            "p0_candidates": P0_CANDIDATES,
            "legacy_external_independent_approved": gate_data["approved_semantic_dispositions"],
        },
        "pr8_index_dispositions_added": index["gate"]["semantic_dispositions_added"],
        "v1_register_record_count": len(register["records"]),
        "pilot": {
            "subsystem": "mGBA ROM lifecycle / native Matrix / fetch / DMA / state interactions",
            "candidate_file_count": len(candidates),
            "lexical_dependency_component_candidate_nodes": len(lexical_component),
            "pilot_files_in_lexical_component": len(pilot_keys),
            "lexical_component_is_complete_semantic_closure": False,
            "v1_exact_bytes_eligible_count": 0,
            "v1_exact_bytes_ineligible_count": len(candidates),
            "behavioral_congruence_passed_count": 0,
            "behavioral_needs_review_count": len(candidates),
            "source_contract_rows": len(contracts),
            "source_contract_files": sorted({row["path"] for row in contracts}),
            "runtime_paths_exercised": contract_summary["runtime_paths_exercised"],
            "native_build_evidence": {
                **native_build,
                "cmake_evidence": {
                    path: {"git_blob_sha1": blob, "pinned_revision": PILOT_REVISION}
                    for path, blob in PILOT_SOURCE_EVIDENCE.items()
                },
                "configured_probe_options": {
                    "BUILD_TEST": "OFF",
                    "target": "xgba_mgba_bank_boundary",
                    "external_fixture_source": "tests/mgba_bank_boundary.c",
                },
                "upstream_core_test_scope": [
                    "GBACoreCreate",
                    "platform",
                    "reset",
                    "loadNullROM",
                ],
                "upstream_core_test_blob_sha1": PILOT_SOURCE_EVIDENCE["src/gba/test/core.c"],
                "upstream_core_tests_cover_pilot_risks": False,
            },
            "risk_obligations": risk_obligations,
            "direct_test_link_candidates": direct_test_links,
            "unresolved_literal_include_candidates": unresolved_edges,
            "license_distribution_clearance": license_state["distribution_clearance"],
            "dependency_candidate_resolution_counts": dict(sorted(resolution_totals.items())),
            "candidates": candidates,
        },
        "counters": {
            "legacy_external_independent_approved": gate_data["approved_semantic_dispositions"],
            "legacy_p0_external_independent_approved": 0,
            "v1_exact_bytes_eligible_count": 0,
            "v1_exact_bytes_ineligible_count": len(candidates),
            "behavioral_congruence_passed_count": 0,
            "behavioral_congruence_needs_review_count": len(candidates),
        },
        "completion_gate": "FAIL_INCOMPLETE",
        "source_bytes_reopened_in_this_run": False,
        "synthetic_fixtures_counted": 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr8-index", type=Path, required=True)
    parser.add_argument("--pr8-dossier", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = reconcile(
            args.repository_root.resolve(),
            args.pr8_index.read_bytes(),
            args.pr8_dossier.read_bytes(),
        )
    except (OSError, EvidenceError, ValueError, KeyError) as exc:
        print(json.dumps({"schema": SCHEMA, "disposition": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

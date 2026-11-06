#!/usr/bin/env python3
"""Emit a non-approving eligibility and dependency-closure matrix for six ARM files."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase1_mgba_arm_decode_emit_review_verify as arm_review
from phase1_bulk_triage import canonical, checked_dossiers, digest, read_queue

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REPOSITORY = "mgba-emu/mgba"
ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
ARCHIVE_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
RECEIPT_PATH = "docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"
ANALYSIS_PATH = "docs/phase1-review-readiness/analyst-arm-decode-emit-review-20261102.md"
ANALYSIS_SHA256 = "4096e0a5ea2b2aa7b065f7e14980cd696801aeaaff766e3ff70352a69c572acf"
ANALYSIS_COMMIT = "8222aac73928ca291f2eca553fe581f7909628bb"
COPILOT_ID = 198982749
COPILOT_LOGIN = "copilot-swe-agent[bot]"
SCHEMA = "xgba.phase1.arm_six_file_eligibility.v1"

BLOCKERS = {
    "include/mgba/internal/arm/arm.h": [
        "Active-region uint32_t accesses can alias declared uint16_t palette/OAM backing; alignment and strict-aliasing legality are not established.",
        "No target-native execution or complete memory-region caller contract is established by the host probes.",
    ],
    "include/mgba/internal/arm/decoder.h": [
        "ARMInstructionInfo bitfield layout was checked only with bounded compiler record-layout evidence, not the complete ARM API ABI.",
        "The declared ARMResolveMemoryAccess dependency has signed-shift and INT32_MIN-negation counterexamples.",
    ],
    "include/mgba/internal/arm/emitter-arm.h": [
        "Host table expansion does not independently validate ARMv4T semantics for every emitted slot and mapped handler.",
        "Handler dependencies retain signed arithmetic, memory-alias, and ABI objections.",
    ],
    "src/arm/decoder-arm.c": [
        "Branch decoding uses out-of-range unsigned-to-signed conversion and right-shifts a negative signed value; cross-toolchain behavior is unestablished.",
        "Reserved condition-F interpretation differs between CPU dispatch and debugger predicate paths; debugger semantics remain open.",
    ],
    "src/arm/decoder-thumb.c": [
        "Pinned conditional-branch and BL1 paths left-shift negative signed values; host UBSan reproduced both cases.",
        "A target-native or ARMv4T oracle comparison and application-specific runtime consequence are absent.",
    ],
    "src/arm/decoder.c": [
        "ARMResolveMemoryAccess signed left shift and INT32_MIN subtraction counterexamples remain unresolved.",
        "Observed resolver calls are debugger paths; full native/runtime behavior is not established.",
    ],
}
SOURCE_LINE_COUNTS = {
    "include/mgba/internal/arm/arm.h": 217,
    "include/mgba/internal/arm/decoder.h": 231,
    "include/mgba/internal/arm/emitter-arm.h": 336,
    "src/arm/decoder-arm.c": 466,
    "src/arm/decoder-thumb.c": 344,
    "src/arm/decoder.c": 601,
}
PRIOR_DISPOSITIONS = {
    "include/mgba/internal/arm/arm.h": "NEEDS_REVIEW",
    "include/mgba/internal/arm/decoder.h": "NEEDS_EVIDENCE",
    "include/mgba/internal/arm/emitter-arm.h": "NEEDS_EVIDENCE",
    "src/arm/decoder-arm.c": "NEEDS_REVIEW",
    "src/arm/decoder-thumb.c": "NEEDS_REVIEW",
    "src/arm/decoder.c": "NEEDS_REVIEW",
}

CLOSURE_SOURCES = {
    "include/mgba-util/common.h": {
        "blob": "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "sha256": "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "dossier": "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "role": "typed little-endian access implementation used by ARM memory helpers",
        "anchors": [
            (236, "#define LOAD_32LE(DEST, ADDR, ARR) DEST = *(uint32_t*) ((uintptr_t) (ARR) + (size_t) (ADDR))"),
            (239, "#define STORE_32LE(SRC, ADDR, ARR) *(uint32_t*) ((uintptr_t) (ARR) + (size_t) (ADDR)) = SRC"),
        ],
    },
    "include/mgba/internal/arm/isa-inlines.h": {
        "blob": "ebda28e411f627c6cd1570aff6f29a3b79a60840",
        "sha256": "17d976d898d9e412f863ea5a1ff41bde3232c16c13e08f9b0f9350a911e269a9",
        "dossier": "22099dfd7b67ee163af3dd04afe6aed7b70f059d9df2ebb14f713aeec91f58db",
        "role": "ARM signed-extension macros and debugger condition predicate",
        "anchors": [
            (30, "#define ARM_SXT_8(I) (((int8_t) (I) << 24) >> 24)"),
            (31, "#define ARM_SXT_16(I) (((int16_t) (I) << 16) >> 16)"),
            (129, "static inline bool ARMTestCondition(struct ARMCore* cpu, unsigned condition) {"),
        ],
    },
    "src/arm/arm.c": {
        "blob": "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "sha256": "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
        "dossier": "37c2acf57fc04d0327426d88d01b3353f46868be77fa73f3fa633fcc0a267934",
        "role": "ARM core condition-F dispatch and instruction execution boundary",
        "anchors": [
            (198, "0x0000 // NV"),
            (207, "unsigned condition = opcode >> 28;"),
            (211, "if (!conditionMet) {"),
        ],
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _has_mpl_2_notice(data: bytes) -> bool:
    normalized = b" ".join(data.replace(b"*", b" ").split())
    return b"Mozilla Public License" in normalized and b"2.0." in normalized


def _run_git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _copilot_analysis_authorship(repository_root: Path) -> dict:
    path = repository_root / ANALYSIS_PATH
    data = path.read_bytes()
    if _sha256(data) != ANALYSIS_SHA256:
        raise ValueError("ARM analysis authorship evidence hash mismatch")
    commit_blob = _run_git(repository_root, "rev-parse", f"{ANALYSIS_COMMIT}:{ANALYSIS_PATH}")
    if commit_blob != _git_blob(data):
        raise ValueError("ARM analysis commit does not contain the pinned evidence bytes")
    ancestor = subprocess.run(
        ["git", "-C", str(repository_root), "merge-base", "--is-ancestor", ANALYSIS_COMMIT, "HEAD"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    fields = _run_git(
        repository_root,
        "show",
        "-s",
        "--format=%H%x00%an%x00%ae",
        ANALYSIS_COMMIT,
    ).split("\0")
    if (
        ancestor.returncode != 0
        or len(fields) != 3
        or fields[0] != ANALYSIS_COMMIT
        or str(COPILOT_ID) not in fields[2]
        or "copilot" not in fields[1].casefold()
    ):
        raise ValueError("ARM analysis authorship provenance is not the expected Copilot identity")
    return {
        "path": ANALYSIS_PATH,
        "sha256": ANALYSIS_SHA256,
        "commit": fields[0],
        "author": {"login": COPILOT_LOGIN, "id": COPILOT_ID},
    }


def _register_counts(repository_root: Path) -> dict[str, int]:
    matches = {target["path"]: 0 for target in arm_review.TARGETS.values()}
    register = repository_root / RECEIPT_PATH
    for line in register.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        source = row.get("source", {})
        if source.get("repository") == REPOSITORY and source.get("path") in matches:
            matches[source["path"]] += 1
    return matches


def _load_original_dossiers(snapshot_root: Path) -> dict:
    archive_path = snapshot_root / "candidate_review_dossiers.jsonl.gz"
    archive = archive_path.read_bytes()
    if _sha256(archive) != ARCHIVE_SHA256 or _git_blob(archive) != ARCHIVE_BLOB:
        raise ValueError("Original compressed dossier archive identity mismatch")
    queue = read_queue(snapshot_root)
    return checked_dossiers(snapshot_root, queue)


def build_report(source_root: Path, snapshot_root: Path, repository_root: Path) -> dict:
    source_root = source_root.resolve()
    snapshot_root = snapshot_root.resolve()
    repository_root = repository_root.resolve()
    if _run_git(source_root, "rev-parse", "HEAD") != PIN:
        raise ValueError("Pinned mGBA source checkout revision mismatch")

    arm_review.verify_packet()
    arm_review.verify_sources(source_root)
    dossiers = _load_original_dossiers(snapshot_root)
    archive = (snapshot_root / "candidate_review_dossiers.jsonl.gz").read_bytes()
    target_receipts = _register_counts(repository_root)
    evidence_author = _copilot_analysis_authorship(repository_root)
    license_blob, license_sha = arm_review.SUPPORT["LICENSE"]
    license_bytes = (source_root / "LICENSE").read_bytes()
    if _git_blob(license_bytes) != license_blob or _sha256(license_bytes) != license_sha:
        raise ValueError("Pinned MPL-2.0 license identity mismatch")
    if b"Mozilla Public License Version 2.0" not in license_bytes:
        raise ValueError("Pinned root license is not MPL-2.0")

    targets = []
    for packet_index, expected in arm_review.TARGETS.items():
        path = expected["path"]
        source = (source_root / path).read_bytes()
        dossier = dossiers.get((REPOSITORY, path))
        if dossier is None or digest(canonical(dossier)) != expected["dossier"]:
            raise ValueError(f"Original machine dossier row identity mismatch: {path}")
        provenance = dossier.get("provenance", {})
        if (
            _git_blob(source) != expected["blob"]
            or _sha256(source) != expected["sha256"]
            or len(source.splitlines()) != SOURCE_LINE_COUNTS[path]
            or provenance.get("git_blob_sha") != expected["blob"]
            or provenance.get("source_content_sha256") != expected["sha256"]
        ):
            raise ValueError(f"Original pinned source identity mismatch: {path}")
        notice = b" ".join(source.replace(b"*", b" ").split())
        if b"Mozilla Public License, v. 2.0." not in notice:
            raise ValueError(f"Target file MPL-2.0 notice missing: {path}")
        dossier_review = dossier.get("review", {})
        targets.append({
            "packet_index": packet_index,
            "source": {
                "repository": REPOSITORY,
                "revision": PIN,
                "path": path,
                "line_count": SOURCE_LINE_COUNTS[path],
                "git_blob_sha1": expected["blob"],
                "source_sha256": expected["sha256"],
            },
            "original_dossier_sha256": expected["dossier"],
            "machine_triage": {
                "reviewer": dossier_review.get("reviewer"),
                "semantic_signoff": dossier_review.get("semantic_signoff", False),
                "status": dossier_review.get("status", "UNSPECIFIED"),
            },
            "license": {
                "file_notice": "MPL-2.0_VERIFIED",
                "root_license_git_blob_sha1": license_blob,
                "root_license_sha256": license_sha,
                "combined_distribution_clearance": False,
            },
            "review": {
                "eligibility": "NEEDS_EVIDENCE",
                "prior_source_status": PRIOR_DISPOSITIONS[path],
                "semantic_disposition": "NOT_PERFORMED",
                "whole_file_coverage": {
                    "status": "NOT_PERFORMED",
                    "reviewed_line_ranges": [],
                },
                "canonical_receipt_rows": target_receipts[path],
                "durable_copilot_attestation": "ABSENT" if target_receipts[path] == 0 else "UNVALIDATED",
                "reviewer_independence": "BLOCKED_AUTHOR_CONFLICT",
                "blockers": BLOCKERS[path],
            },
        })

    dependencies = []
    for path, spec in CLOSURE_SOURCES.items():
        blob, source_sha = spec["blob"], spec["sha256"]
        source = (source_root / path).read_bytes()
        dossier = dossiers.get((REPOSITORY, path))
        if dossier is None:
            raise ValueError(f"Original machine dossier dependency row missing: {path}")
        row_sha = digest(canonical(dossier))
        if (
            _git_blob(source) != blob
            or _sha256(source) != source_sha
            or row_sha != spec["dossier"]
            or not _has_mpl_2_notice(source)
        ):
            raise ValueError(f"Dependency source, dossier, or license identity mismatch: {path}")
        lines = source.decode("utf-8", "strict").splitlines()
        anchors = []
        for line_number, expected in spec["anchors"]:
            if line_number < 1 or line_number > len(lines) or lines[line_number - 1].strip() != expected:
                raise ValueError(f"Dependency source anchor mismatch: {path}:{line_number}")
            anchors.append({"line": line_number, "text": expected})
        dependencies.append({
            "repository": REPOSITORY,
            "revision": PIN,
            "path": path,
            "role": spec["role"],
            "git_blob_sha1": blob,
            "source_sha256": source_sha,
            "original_dossier_sha256": spec["dossier"],
            "anchors": anchors,
            "license_notice": "MPL-2.0_VERIFIED",
        })

    return {
        "schema": SCHEMA,
        "repository_head": _run_git(repository_root, "rev-parse", "HEAD"),
        "upstream": {"repository": REPOSITORY, "revision": PIN},
        "original_dossier_archive": {
            "git_blob_sha1": _git_blob(archive),
            "sha256": _sha256(archive),
        },
        "copilot_authorship_conflict_evidence": evidence_author,
        "candidate_copilot_reviewer_identity": {"login": COPILOT_LOGIN, "id": COPILOT_ID},
        "targets": targets,
        "bounded_dependency_closure": {
            "status": "PARTIAL_NOT_COMPLETE",
            "verified_dependency_count": len(dependencies),
            "dependencies": dependencies,
            "remaining_scope": (
                "These three cross-cutting sources do not constitute a complete per-file dependency, "
                "caller, native ABI, runtime, or distribution-license closure."
            ),
        },
        "evidence_limits": {
            "compiled_native": "NOT_CLAIMED",
            "host_probes": "PREVIOUSLY_RECORDED_ONLY_NOT_REPEATED",
            "armv4t_oracle": "NOT_RUN",
            "combined_distribution_license_clearance": False,
            "independent_semantic_reviews_added": 0,
            "independent_approvals_added": 0,
            "gate_contribution": 0,
            "gate": "FAIL_INCOMPLETE",
        },
    }


def validate_reviewer_independence(reviewer_id: int, evidence_author_ids: list[int]) -> None:
    if not isinstance(reviewer_id, int) or reviewer_id in evidence_author_ids:
        raise ValueError("Reviewer and dossier/substantive-evidence author conflict")


def validate_report(report: dict) -> None:
    if set(report) != {
        "schema",
        "repository_head",
        "upstream",
        "original_dossier_archive",
        "copilot_authorship_conflict_evidence",
        "candidate_copilot_reviewer_identity",
        "targets",
        "bounded_dependency_closure",
        "evidence_limits",
    }:
        raise ValueError("Unsupported report fields")
    if report.get("schema") != SCHEMA or report.get("upstream") != {
        "repository": REPOSITORY,
        "revision": PIN,
    }:
        raise ValueError("Unexpected report schema or pinned upstream")
    head = report.get("repository_head")
    if not isinstance(head, str) or len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        raise ValueError("Repository head identity is malformed")
    archive = report.get("original_dossier_archive", {})
    if archive.get("sha256") != ARCHIVE_SHA256 or archive.get("git_blob_sha1") != ARCHIVE_BLOB:
        raise ValueError("Original dossier archive identity mismatch")
    expected_targets = {
        item["path"]: (index, item) for index, item in arm_review.TARGETS.items()
    }
    targets = report.get("targets")
    if not isinstance(targets, list) or len(targets) != len(expected_targets):
        raise ValueError("Six-file target coverage is incomplete")
    paths = [row.get("source", {}).get("path") for row in targets]
    if len(set(paths)) != len(paths) or set(paths) != set(expected_targets):
        raise ValueError("Six-file target coverage is partial or duplicated")
    for row in targets:
        path = row["source"]["path"]
        packet_index, expected = expected_targets[path]
        if set(row) != {"packet_index", "source", "original_dossier_sha256", "machine_triage", "license", "review"}:
            raise ValueError(f"Unsupported target evidence fields: {path}")
        source = row["source"]
        if set(source) != {
            "repository", "revision", "path", "line_count", "git_blob_sha1", "source_sha256"
        }:
            raise ValueError(f"Unsupported source identity fields: {path}")
        if (
            row.get("packet_index") != packet_index
            or source.get("repository") != REPOSITORY
            or source.get("revision") != PIN
            or source.get("git_blob_sha1") != expected["blob"]
            or source.get("source_sha256") != expected["sha256"]
            or source.get("line_count") != SOURCE_LINE_COUNTS[path]
            or row.get("original_dossier_sha256") != expected["dossier"]
        ):
            raise ValueError(f"Stale source or dossier identity: {path}")
        if row.get("machine_triage") != {
            "reviewer": None,
            "semantic_signoff": False,
            "status": "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
        }:
            raise ValueError(f"Machine triage cannot be promoted: {path}")
        if row.get("license") != {
            "file_notice": "MPL-2.0_VERIFIED",
            "root_license_git_blob_sha1": arm_review.SUPPORT["LICENSE"][0],
            "root_license_sha256": arm_review.SUPPORT["LICENSE"][1],
            "combined_distribution_clearance": False,
        }:
            raise ValueError("Ambiguous or unsupported combined-distribution license claim")
        review = row.get("review", {})
        if set(review) != {
            "eligibility", "prior_source_status", "semantic_disposition", "whole_file_coverage",
            "canonical_receipt_rows", "durable_copilot_attestation",
            "reviewer_independence", "blockers",
        }:
            raise ValueError(f"Unsupported review status fields: {path}")
        if review.get("whole_file_coverage") != {
            "status": "NOT_PERFORMED",
            "reviewed_line_ranges": [],
        }:
            if review.get("semantic_disposition") == "NOT_PERFORMED":
                raise ValueError(f"Unsupported whole-file coverage claim: {path}")
        if review.get("semantic_disposition") != "NOT_PERFORMED":
            coverage = review.get("whole_file_coverage", {})
            if (
                coverage.get("status") != "WHOLE_FILE"
                or coverage.get("reviewed_line_ranges") != [[1, source.get("line_count")]]
            ):
                raise ValueError("Partial semantic coverage cannot qualify as a whole-file review")
            raise ValueError("This eligibility matrix cannot create semantic reviews or receipts")
        if review.get("eligibility") != "NEEDS_EVIDENCE":
            raise ValueError("Unsupported review eligibility promotion")
        if review.get("prior_source_status") != PRIOR_DISPOSITIONS[path]:
            raise ValueError("Prior source status does not match the existing dossier")
        if review.get("reviewer_independence") != "BLOCKED_AUTHOR_CONFLICT":
            raise ValueError("Reviewer authorship conflict was not preserved")
        if review.get("blockers") != BLOCKERS[path]:
            raise ValueError(f"Per-file blockers changed or were omitted: {path}")
        if review.get("canonical_receipt_rows") != 0 or review.get("durable_copilot_attestation") != "ABSENT":
            raise ValueError("Unsupported receipt or attestation claim")
    closure = report.get("bounded_dependency_closure", {})
    dependencies = closure.get("dependencies")
    if set(closure) != {"status", "verified_dependency_count", "dependencies", "remaining_scope"}:
        raise ValueError("Unsupported dependency closure fields")
    if closure.get("status") != "PARTIAL_NOT_COMPLETE" or not isinstance(dependencies, list):
        raise ValueError("Incomplete dependency closure cannot be promoted")
    if closure.get("verified_dependency_count") != len(CLOSURE_SOURCES):
        raise ValueError("Dependency closure is partial or unsupported")
    expected_dependency_paths = set(CLOSURE_SOURCES)
    if {item.get("path") for item in dependencies} != expected_dependency_paths:
        raise ValueError("Bounded dependency closure coverage is incomplete")
    for item in dependencies:
        path = item.get("path")
        spec = CLOSURE_SOURCES.get(path)
        if spec is None or set(item) != {
            "repository", "revision", "path", "role", "git_blob_sha1", "source_sha256",
            "original_dossier_sha256", "anchors", "license_notice",
        }:
            raise ValueError("Unexpected dependency closure row")
        if (
            item.get("git_blob_sha1") != spec["blob"]
            or item.get("source_sha256") != spec["sha256"]
            or item.get("original_dossier_sha256") != spec["dossier"]
            or item.get("repository") != REPOSITORY
            or item.get("revision") != PIN
            or item.get("role") != spec["role"]
            or item.get("anchors") != [
                {"line": line, "text": text} for line, text in spec["anchors"]
            ]
        ):
            raise ValueError("Stale dependency source identity")
        if item.get("license_notice") != "MPL-2.0_VERIFIED":
            raise ValueError("Dependency licensing is ambiguous")
    conflict = report.get("copilot_authorship_conflict_evidence", {})
    if set(conflict) != {"path", "sha256", "commit", "author"} or (
        conflict.get("path") != ANALYSIS_PATH
        or conflict.get("sha256") != ANALYSIS_SHA256
        or conflict.get("commit") != ANALYSIS_COMMIT
        or conflict.get("author") != {"login": COPILOT_LOGIN, "id": COPILOT_ID}
    ):
        raise ValueError("Copilot authorship conflict evidence is missing")
    if report.get("candidate_copilot_reviewer_identity") != {
        "login": COPILOT_LOGIN,
        "id": COPILOT_ID,
    }:
        raise ValueError("Candidate reviewer identity provenance is unsupported")
    if report["candidate_copilot_reviewer_identity"]["id"] != conflict["author"]["id"]:
        raise ValueError("Reviewer authorship conflict was not represented accurately")
    limits = report.get("evidence_limits", {})
    if set(limits) != {
        "compiled_native", "host_probes", "armv4t_oracle",
        "combined_distribution_license_clearance", "independent_semantic_reviews_added",
        "independent_approvals_added", "gate_contribution", "gate",
    }:
        raise ValueError("Unsupported native, oracle, licensing, approval, or gate claim")
    if (
        limits.get("compiled_native") != "NOT_CLAIMED"
        or limits.get("armv4t_oracle") != "NOT_RUN"
        or limits.get("combined_distribution_license_clearance") is not False
        or limits.get("independent_semantic_reviews_added") != 0
        or limits.get("independent_approvals_added") != 0
        or limits.get("gate_contribution") != 0
        or limits.get("gate") != "FAIL_INCOMPLETE"
    ):
        raise ValueError("Unsupported native, oracle, licensing, approval, or gate claim")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, default=ROOT / "semantic-snapshots/current")
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.source_root, args.snapshot_root, args.repository_root)
    validate_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        "P0_ARM_SIX_FILE_ELIGIBILITY_PASS targets=6 dependencies=3 "
        "semantic_reviews=0 eligible_receipts=0 approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()

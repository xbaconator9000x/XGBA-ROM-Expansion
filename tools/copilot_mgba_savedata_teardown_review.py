#!/usr/bin/env python3
"""Verify the bounded PR13 mGBA VFile teardown review evidence; never an approval."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
RECORD_SHA256 = "b3bec6ce260d6184fc22a859b9c5bbc518348966cb0092a4fbe56f296667c475"
DEFAULT_RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata-teardown/review.json"
)


class EvidenceRejected(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceRejected(message)


def verify_record_digest(raw: bytes) -> None:
    require(sha256(raw) == RECORD_SHA256, "review record SHA-256 mismatch")


def validate_record(record: dict) -> None:
    require(
        record.get("schema") == "xgba.copilot.mgba_savedata_teardown_review.v1",
        "review record schema mismatch",
    )
    require(record.get("upstream", {}).get("revision") == PIN, "source pin mismatch")

    state = record.get("phase1_state", {})
    require(
        state
        == {
            "decision": "FAIL_INCOMPLETE",
            "p0_candidates": 338,
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "inventory_total": 14834,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
        },
        "Phase 1 gate or approval accounting changed",
    )
    reviewer = record.get("reviewer", {})
    require(reviewer.get("approval_eligible") is False, "reviewer claims approval eligibility")

    files = record.get("source_files")
    require(isinstance(files, list) and len(files) == 20, "expected 20 pinned source files")
    file_paths = [item.get("path") for item in files]
    require(len(set(file_paths)) == len(files), "duplicate source file")
    objection_ids = {
        item.get("id") for item in record.get("objection_resolution_matrix", [])
    }
    require(objection_ids, "missing objection/resolution matrix")
    matrix = record["objection_resolution_matrix"]
    require(len(objection_ids) == len(matrix), "duplicate objection/resolution ID")
    evidence_ids = {item.get("id") for item in record.get("evidence", [])}
    for item in matrix:
        require(
            item.get("evidence_ids")
            and set(item["evidence_ids"]).issubset(evidence_ids),
            f"missing or unbound evidence for objection {item.get('id')}",
        )
    for item in files:
        require(item.get("verdict") == "NEEDS_EVIDENCE", "new file verdict was promoted")
        require(item.get("independent_approval") is False, "approval claim in file matrix")
        require(
            item.get("objections")
            and set(item["objections"]).issubset(objection_ids),
            f"missing or unbound objection for {item.get('path')}",
        )
        require(
            re.fullmatch(r"[0-9a-f]{40}", item.get("git_blob_sha1", "")) is not None,
            f"invalid Git blob SHA-1 for {item.get('path')}",
        )
        for field in ("source_sha256", "dossier_row_sha256"):
            require(
                re.fullmatch(r"[0-9a-f]{64}", item.get(field, "")) is not None,
                f"invalid {field} for {item.get('path')}",
            )
    require(
        all(item.get("status") for item in record["objection_resolution_matrix"]),
        "objection matrix has an unclassified resolution",
    )

    evidence = record.get("evidence", [])
    ids = [item.get("id") for item in evidence]
    require(len(ids) == len(set(ids)) and len(ids) == 11, "evidence inventory mismatch")
    for item in evidence:
        require(
            re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is not None,
            f"invalid evidence SHA-256: {item.get('id')}",
        )

    tests = record.get("test_provenance", {})
    evidence_by_id = {item["id"]: item["sha256"] for item in evidence}
    require(tests.get("fd", {}).get("native_case_count_claimed") == 6, "fd case count changed")
    require(tests.get("fd", {}).get("parser_test_methods") == 20, "fd parser test count changed")
    require(
        tests.get("stdio", {}).get("native_case_count_claimed") == 7,
        "stdio case count changed",
    )
    require(
        tests.get("stdio", {}).get("parser_test_methods") == 18,
        "stdio parser test count changed",
    )
    require(
        tests.get("fd", {}).get("local_result_independently_reproduced") is False
        and tests.get("stdio", {}).get("local_result_independently_reproduced") is False,
        "unreproduced local native evidence was promoted",
    )
    require(tests["fd"]["fixture_sha256"] == evidence_by_id["fd-native-6-case-fixture"],
            "fd fixture hash does not match the evidence inventory")
    require(tests["fd"]["parser_test_sha256"] == evidence_by_id["fd-parser-tests"],
            "fd parser test hash does not match the evidence inventory")
    require(tests["stdio"]["fixture_sha256"] == evidence_by_id["stdio-native-7-case-fixture"],
            "stdio fixture hash does not match the evidence inventory")
    require(tests["stdio"]["parser_test_sha256"] == evidence_by_id["stdio-parser-tests"],
            "stdio parser test hash does not match the evidence inventory")

    workflow = record.get("workflow_evidence", {})
    pr13 = workflow.get("pr13", {})
    require(pr13.get("push_trigger") is False, "PR13 workflow now claims push coverage")
    require(pr13.get("push_run_found") is False, "unsupported PR13 push run claim")
    for key in ("code_bearing_fd_head", "code_bearing_stdio_head", "current_head"):
        run = pr13.get(key, {})
        require(run.get("conclusion") == "action_required", f"PR13 {key} CI conclusion changed")
        require(run.get("jobs") == 0 and run.get("job_step_logs") is False,
                f"PR13 {key} improperly claims executed CI")
    old_fd = pr13.get("prior_fd_code_same_docs_head", {})
    require(
        old_fd.get("conclusion") == "success"
        and old_fd.get("sha") != pr13.get("current_head", {}).get("sha")
        and old_fd.get("artifacts") == 0,
        "historical fd CI was misrepresented as current exact-head evidence",
    )
    pr35 = workflow.get("pr35", {})
    require(
        pr35.get("reviewed_head") == record.get("target", {}).get("expected_head_before_review")
        and "did not include this teardown review package" in pr35.get("interpretation", ""),
        "PR35 prior CI misrepresented as validation of this packet",
    )
    require(record.get("per_file_verdict") == "NEEDS_EVIDENCE", "review disposition promoted")
    require(record.get("all_new_files_independent_approval") is False,
            "review claims an independent approval")


def verify_sources(source_dir: Path, record: dict) -> int:
    checked = 0
    for item in record["source_files"]:
        data = (source_dir / item["path"]).read_bytes()
        require(git_blob_sha1(data) == item["git_blob_sha1"],
                f"pinned source Git blob mismatch: {item['path']}")
        require(sha256(data) == item["source_sha256"],
                f"pinned source SHA-256 mismatch: {item['path']}")
        if item["path"].endswith((".c", ".h")):
            notice = b"Mozilla Public" in data[:800] and b"License, v. 2.0." in data[:800]
            require(notice, f"MPL-2.0 notice missing: {item['path']}")
        checked += 1
    return checked


def verify_dossier(dossier_path: Path, record: dict) -> int:
    metadata = record["upstream"]["machine_dossier"]
    raw = dossier_path.read_bytes()
    require(sha256(raw) == metadata["sha256"], "machine dossier SHA-256 mismatch")
    require(git_blob_sha1(raw) == metadata["git_blob_sha1"], "machine dossier Git blob mismatch")

    expected = {item["path"]: item["dossier_row_sha256"] for item in record["source_files"]}
    observed = {}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path not in expected
            ):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(sha256(canonical) == expected[path], f"dossier row mismatch: {path}")
            require(path not in observed, f"duplicate dossier row: {path}")
            require(provenance.get("git_blob_sha") == next(
                item["git_blob_sha1"] for item in record["source_files"] if item["path"] == path
            ), f"dossier source blob mismatch: {path}")
            require(provenance.get("source_content_sha256") == next(
                item["source_sha256"] for item in record["source_files"] if item["path"] == path
            ), f"dossier source SHA-256 mismatch: {path}")
            observed[path] = True
    require(set(observed) == set(expected), "dossier does not cover all 20 pinned source files")
    return len(observed)


def verify_evidence(evidence_dir: Path, record: dict) -> int:
    checked = 0
    for item in record["evidence"]:
        data = (evidence_dir / item["path"]).read_bytes()
        require(sha256(data) == item["sha256"], f"PR13 evidence hash mismatch: {item['id']}")
        checked += 1
    return checked


def expect_rejected(callback, message: str) -> None:
    try:
        callback()
    except (EvidenceRejected, OSError, ValueError):
        return
    raise EvidenceRejected(f"mutation control escaped: {message}")


def run_self_tests(
    record: dict, raw_record: bytes, source_dir: Path, evidence_dir: Path
) -> int:
    validate_record(record)
    rejected = 0

    def mutated(change, label):
        candidate = copy.deepcopy(record)
        change(candidate)
        expect_rejected(lambda: validate_record(candidate), label)

    mutated(lambda d: d["phase1_state"].update(decision="PASS"), "gate promotion")
    rejected += 1
    mutated(
        lambda d: d["phase1_state"].update(shared_gate_or_register_edited=True),
        "unauthorized shared gate/register modification",
    )
    rejected += 1
    mutated(lambda d: d["phase1_state"].update(approved_after=1), "approval count increment")
    rejected += 1
    mutated(lambda d: d["source_files"][0].update(verdict="COPILOT_REVIEWED/PASSED"),
            "per-file verdict promotion")
    rejected += 1
    mutated(lambda d: d["source_files"].pop(), "missing source file")
    rejected += 1
    mutated(lambda d: d["source_files"][0].update(objections=["unbound"]),
            "unbound objection")
    rejected += 1
    mutated(lambda d: d["workflow_evidence"]["pr13"]["current_head"].update(conclusion="success"),
            "fabricated exact-head success")
    rejected += 1
    mutated(lambda d: d["workflow_evidence"]["pr13"]["current_head"].update(jobs=1),
            "fabricated executed job")
    rejected += 1
    mutated(lambda d: d["test_provenance"]["stdio"].update(parser_test_methods=7),
            "test-kind/count mutation")
    rejected += 1
    mutated(lambda d: d["workflow_evidence"]["pr13"].update(push_trigger=True),
            "fabricated push coverage")
    rejected += 1
    expect_rejected(
        lambda: verify_record_digest(raw_record.replace(b"NEEDS_EVIDENCE", b"APPROVED", 1)),
        "record byte mutation",
    )
    rejected += 1

    with tempfile.TemporaryDirectory(prefix="mgba-teardown-review-") as directory:
        root = Path(directory)
        mutated_source = record["source_files"][0]
        source_bytes = (source_dir / mutated_source["path"]).read_bytes()
        source_target = root / "source" / mutated_source["path"]
        source_target.parent.mkdir(parents=True, exist_ok=True)
        source_target.write_bytes(source_bytes[:-1] + bytes([source_bytes[-1] ^ 1]))
        expect_rejected(
            lambda: verify_sources(root / "source", record),
            "pinned source byte mutation",
        )
        rejected += 1

        mutated_evidence = record["evidence"][0]
        evidence_bytes = (evidence_dir / mutated_evidence["path"]).read_bytes()
        evidence_target = root / "evidence" / mutated_evidence["path"]
        evidence_target.parent.mkdir(parents=True, exist_ok=True)
        evidence_target.write_bytes(evidence_bytes[:-1] + bytes([evidence_bytes[-1] ^ 1]))
        expect_rejected(
            lambda: verify_evidence(root / "evidence", record),
            "PR13 evidence byte mutation",
        )
    rejected += 1
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--dossier", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        raw_record = args.record.read_bytes()
        verify_record_digest(raw_record)
        record = json.loads(raw_record.decode("utf-8"))
        validate_record(record)
        if args.self_test:
            if not (args.source_dir and args.evidence_dir):
                raise EvidenceRejected(
                    "--source-dir and --evidence-dir are required for mutation controls"
                )
            controls = run_self_tests(record, raw_record, args.source_dir, args.evidence_dir)
            print(f"PASS review packet invariants; {controls} fail-closed mutation controls rejected")
            if not args.dossier:
                return 0
        if not (args.source_dir and args.dossier and args.evidence_dir):
            raise EvidenceRejected(
                "--source-dir, --dossier, and --evidence-dir are required for evidence verification"
            )
        source_count = verify_sources(args.source_dir, record)
        dossier_rows = verify_dossier(args.dossier, record)
        evidence_count = verify_evidence(args.evidence_dir, record)
    except (OSError, UnicodeError, json.JSONDecodeError, EvidenceRejected) as error:
        print(f"FAIL_CLOSED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "decision": "PASS_PINNED_SOURCE_AND_EVIDENCE_INTEGRITY_ONLY",
        "source_revision": PIN,
        "source_files_verified": source_count,
        "canonical_dossier_rows_verified": dossier_rows,
        "pr13_evidence_files_verified": evidence_count,
        "all_candidate_verdicts": "NEEDS_EVIDENCE",
        "semantic_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify the pinned mGBA cross-tranche matrix without approving sources."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
MATRIX = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "cross-tranche-objection-matrix.json"
)
BASE = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata-teardown/"
    "review.json"
)
FD_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "fd-stdio-error-propagation-handoff.json"
)
LIFECYCLE_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "gba-lifecycle-error-contract-handoff.json"
)
FINAL_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "final-source-tranche-handoff.json"
)
SAVEDATA_REVIEW = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json"
)
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
GATE = Path("semantic-snapshots/current/phase1_mapping_gate.json")
WORKFLOW = Path(".github/workflows/copilot-mgba-savedata-review.yml")

MATRIX_SHA256 = "cef746229ddd522f30c9df2eba1276eeeb0ac0a8aa8a2af568414e6d979aab04"
BASE_SHA256 = "b3bec6ce260d6184fc22a859b9c5bbc518348966cb0092a4fbe56f296667c475"
FD_HANDOFF_SHA256 = "e6333debeed736a58146bf1834b5960ca464cd1116216e67cf6edb5b8a765320"
LIFECYCLE_HANDOFF_SHA256 = "994e10c0cf611a9d247d23335972d9d3d0f300731274562d7d11b5ecd98e6b06"
FINAL_HANDOFF_SHA256 = "61885348028f22e363aaf29880839eea5e16b76a99e608e72c1969280ac98535"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
ALLOWED_DISPOSITIONS = {"RESOLVED_SOURCE_ONLY", "NEEDS_EVIDENCE"}
EXPECTED_EVIDENCE_CLASSES = {
    "pinned-source-analysis": "SOURCE_ONLY",
    "pr13-teardown-fixtures": "PR13_WORKPAPER_REPORTED_LOCAL_LINUX_NATIVE_HOST_FIXTURES",
    "pr13-savedata-callback-witness": "PR13_WORKPAPER_REPORTED_LOCAL_LINUX_SOURCE_EXTRACTED_NATIVE_HOST_WITNESS",
    "pr35-pinned-native-regression": "NATIVE_MGBA_SYNTHETIC_CARTRIDGE_CI",
    "exact-parent-pr35-check": "ACTIONS_BLOCKED_NO_JOB_EXECUTION",
    "push-coverage-check": "NO_PUSH_TRIGGER_OR_RUN",
}
EXPECTED_CONTROLS = [
    "source-hash-mismatch",
    "incomplete-20-file-closure",
    "false-native-gameplay-label",
    "missing-file-license",
    "combined-license-overclaim",
    "approval-promotion",
    "ci-success-overclaim",
    "source-revision-mismatch",
]


class Rejected(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def read_json(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return raw, value


def dossier_rows(path: Path, expected_paths: set[str]) -> dict[str, tuple[str, str, str]]:
    raw = path.read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "machine dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "machine dossier Git blob mismatch")
    rows = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path_value = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path_value not in expected_paths
            ):
                continue
            require(path_value not in rows, f"duplicate dossier row: {path_value}")
            rows[path_value] = (
                sha256(canonical(row)),
                provenance.get("git_blob_sha"),
                provenance.get("source_content_sha256"),
            )
    require(set(rows) == expected_paths, "20 canonical dossier rows are incomplete")
    return rows


def load_context(root: Path, checkout: Path | None):
    matrix_raw, matrix = read_json(root / MATRIX)
    require(MATRIX_SHA256 != "PENDING" and sha256(matrix_raw) == MATRIX_SHA256,
            "cross-tranche matrix SHA-256 mismatch")
    base_raw, base = read_json(root / BASE)
    require(sha256(base_raw) == BASE_SHA256, "original 20-file inventory changed")
    fd_raw, fd_handoff = read_json(root / FD_HANDOFF)
    require(sha256(fd_raw) == FD_HANDOFF_SHA256, "fd/stdio handoff changed")
    lifecycle_raw, lifecycle = read_json(root / LIFECYCLE_HANDOFF)
    require(sha256(lifecycle_raw) == LIFECYCLE_HANDOFF_SHA256,
            "GBA lifecycle handoff changed")
    final_raw, final = read_json(root / FINAL_HANDOFF)
    require(sha256(final_raw) == FINAL_HANDOFF_SHA256,
            "final source tranche handoff changed")
    _, savedata_review = read_json(root / SAVEDATA_REVIEW)
    _, gate = read_json(root / GATE)
    original_files = {item["path"]: item for item in base.get("source_files", [])}
    require(len(original_files) == 20, "original inventory is not exactly 20 files")
    rows = dossier_rows(root / DOSSIER, set(original_files))
    sources = None
    if checkout:
        require(git(checkout, "rev-parse", "HEAD") == PIN,
                "mGBA checkout does not match immutable revision")
        sources = {}
        for path in original_files:
            raw = (checkout / path).read_bytes()
            require(raw, f"missing pinned source: {path}")
            sources[path] = raw
    return matrix, base, original_files, fd_handoff, lifecycle, final, savedata_review, gate, rows, sources


def validate(
    matrix: dict,
    base: dict,
    original_files: dict,
    fd_handoff: dict,
    lifecycle: dict,
    final: dict,
    savedata_review: dict,
    gate: dict,
    rows: dict[str, tuple[str, str, str]],
    sources: dict[str, bytes] | None = None,
) -> None:
    require(
        matrix.get("schema")
        == "xgba.copilot.mgba_savedata_cross_tranche_objection_matrix.v1",
        "matrix schema mismatch",
    )
    review = matrix.get("review", {})
    require(
        review.get("pull_request") == 35
        and review.get("comment_id") == 6649003109
        and review.get("expected_parent_head")
        == "11d68642e705b72958203daee19f3022458a4cf5"
        and review.get("approval_eligible") is False
        and "not a distinct human reviewer" in review.get("identity_limit", ""),
        "review attribution or approval eligibility mismatch",
    )
    pinned = matrix.get("pinned_source", {})
    require(
        pinned.get("repository") == "mgba-emu/mgba"
        and pinned.get("revision") == PIN
        and pinned.get("original_inventory_sha256") == BASE_SHA256
        and pinned.get("machine_dossier_sha256") == DOSSIER_SHA256
        and pinned.get("whole_file_census_repeated") is False,
        "source pin, inventory identity, dossier identity, or review scope changed",
    )
    dispositions = matrix.get("file_dispositions", [])
    require(len(dispositions) == 20, "matrix must cover exactly 20 source records")
    require({item.get("path") for item in dispositions} == set(original_files),
            "matrix source closure differs from the original 20-file inventory")
    subsets = [
        set(fd_handoff["scope"]["subset"]),
        set(lifecycle["scope"]["subset"]),
        set(final["scope"]["subset"]),
    ]
    require([len(group) for group in subsets] == [5, 6, 9],
            "prior tranche boundaries changed")
    require(not (subsets[0] & subsets[1] or subsets[0] & subsets[2] or subsets[1] & subsets[2])
            and set.union(*subsets) == set(original_files),
            "prior 5+6+9 handoffs do not partition the original inventory")
    require(
        all(item.get("scope", {}).get("source_revision") == PIN
            for item in (fd_handoff, lifecycle, final)),
        "a prior tranche source revision changed",
    )

    evidence = matrix.get("evidence_classes", [])
    require(
        len(evidence) == len(EXPECTED_EVIDENCE_CLASSES)
        and {item.get("id"): item.get("class") for item in evidence}
        == EXPECTED_EVIDENCE_CLASSES,
        "evidence class labels or provenance changed",
    )
    by_id = {item["id"]: item for item in evidence}
    host = by_id["pr13-teardown-fixtures"]
    require(
        host.get("source_sha256")
        == [
            "c731670c511ceaf53db2fac8372efe5bfa36ad443bf8808b675b740e4e2cbe9f",
            "2458e0ed4e5cafc1e60dbac18e2bc5945b718377bd25b55213e63f55bf5c7a39",
        ]
        and all(term in " ".join(host.get("limits", [])) for term in
                ("not current PR35 Actions", "not full emulator gameplay", "power-loss durability")),
        "PR13 local host evidence is overclaimed or misidentified",
    )
    callback = by_id["pr13-savedata-callback-witness"]
    require(
        callback.get("fixture_sha256")
        == "4963287bf10a7e2a3cd5e52788bc3aa518d70319fafb8e580c1a9b935059b6d4"
        and callback.get("runner_sha256")
        == "cc67ed3f5fd9b3a6a9e7f30076b38422dc19a43b3530a6576b97b4f1ed13bb53"
        and callback.get("local_log_sha256")
        == "95d5ad944151504b3b80293c9b064ab6a7ec3d60a2aa7244581f76905efbd939"
        and all(term in " ".join(callback.get("limits", [])) for term in
                ("Not the full mGBA runtime", "physical Flash", "not exact-head PR35 CI")),
        "PR13 callback fixture provenance or evidence limits changed",
    )
    synthetic = by_id["pr35-pinned-native-regression"]
    require(
        synthetic.get("run_id") == 41920176499
        and synthetic.get("head_sha") == "da037a0f87e0bc71c09ca158cab7bf7c85b5ebbb"
        and synthetic.get("job_id") == 126922594700
        and synthetic.get("test_source_sha256")
        == "233206a92473469d5ebcd74cdcdedaf6e49395cb67b0cbe19cb2d3a0e2fead18"
        and synthetic.get("runtime_log_sha256")
        == "334addf291ce91cd7f2419b7dc8b4780b63825959ce28c8f13af3aa5c7e23000"
        and all(term in " ".join(synthetic.get("limits", [])) for term in
                ("Earlier PR35 head", "Does not run PR13 teardown fixtures", "physical Flash")),
        "PR35 synthetic native evidence has wrong identity or claim scope",
    )
    blocked = by_id["exact-parent-pr35-check"]
    require(
        blocked.get("run_id") == 41957555966
        and blocked.get("head_sha") == review.get("expected_parent_head")
        and blocked.get("conclusion") == "action_required"
        and blocked.get("job_count") == 0,
        "parent exact-head CI blocker was changed or overclaimed",
    )
    require(
        by_id["push-coverage-check"].get("push_event_run_count") == 0,
        "push coverage was overclaimed",
    )

    for item in dispositions:
        path = item["path"]
        original = original_files[path]
        require(
            item.get("git_blob_sha1") == original.get("git_blob_sha1")
            and item.get("source_sha256") == original.get("source_sha256")
            and item.get("dossier_row_sha256") == original.get("dossier_row_sha256"),
            f"pinned file or dossier identity mismatch: {path}",
        )
        require(
            rows.get(path)
            == (
                original.get("dossier_row_sha256"),
                original.get("git_blob_sha1"),
                original.get("source_sha256"),
            ),
            f"canonical dossier identity mismatch: {path}",
        )
        require(
            original.get("verdict") == "NEEDS_EVIDENCE"
            and original.get("independent_approval") is False,
            f"original candidate disposition was promoted: {path}",
        )
        require(item.get("license_notice") == "MPL-2.0",
                f"file license notice is missing or changed: {path}")
        require(item.get("source_lines") and item.get("source_contract"),
                f"source contract citations missing: {path}")
        for citation in item["source_lines"]:
            match = re.fullmatch(r"(.+):([1-9][0-9]*)-([1-9][0-9]*)", citation)
            require(match and match.group(1) == path,
                    f"invalid source citation for {path}: {citation}")
            start, end = int(match.group(2)), int(match.group(3))
            if sources is not None:
                raw = sources[path]
                require(sha256(raw) == item["source_sha256"]
                        and blob_sha1(raw) == item["git_blob_sha1"],
                        f"pinned source bytes changed: {path}")
                line_count = len(raw.decode("utf-8").splitlines())
                require(end <= line_count, f"source citation outside file: {citation}")
                require(
                    b"Mozilla Public" in raw[:800]
                    and b"License, v. 2.0." in raw[:800]
                    and b"mozilla.org/MPL/2.0/" in raw[:800],
                    f"source MPL-2.0 notice missing: {path}",
                )
        objections = item.get("objections", [])
        require(objections, f"per-file objection record missing: {path}")
        for objection in objections:
            require(
                objection.get("disposition") in ALLOWED_DISPOSITIONS
                and objection.get("id")
                and objection.get("resolution"),
                f"invalid objection disposition: {path}",
            )
            if objection["disposition"] == "NEEDS_EVIDENCE":
                require(objection.get("resolution"), f"open objection unexplained: {path}")

    edge_paths = set(original_files)
    edges = matrix.get("dependency_edges", [])
    require(len(edges) >= 6, "cross-file dependency/caller closure is incomplete")
    for edge in edges:
        require(edge.get("from") in edge_paths and edge.get("to")
                and set(edge["to"]) <= edge_paths and edge.get("contract"),
                "dependency edge is outside pinned 20-file closure or incomplete")
    require(
        matrix.get("license_boundary", {}).get("all_twenty_file_notices")
        == "MPL-2.0, as recorded in the existing pinned source inventory"
        and matrix["license_boundary"].get("dossier_and_source_hashes_bound") is True
        and matrix["license_boundary"].get("transitive_dependency_closure_complete") is False
        and matrix["license_boundary"].get("combined_distribution_legal_conclusion") is False
        and matrix["license_boundary"].get("disposition") == "NEEDS_EVIDENCE",
        "license notice or distribution boundary is missing or overclaimed",
    )
    require(len(matrix.get("unresolved_cross_file_obligations", [])) >= 6,
            "cross-file unresolved obligations were removed")
    require(
        matrix.get("verdict_policy", {}).get("allowed_objection_dispositions")
        == ["RESOLVED_SOURCE_ONLY", "NEEDS_EVIDENCE"]
        and matrix["verdict_policy"].get("file_level_semantic_approval") is False
        and matrix["verdict_policy"].get("external_approved") is False
        and matrix["verdict_policy"].get("validation_workflow_is_not_reviewer") is True,
        "approval policy widened beyond non-approving source-only dispositions",
    )
    require(
        matrix.get("phase1_state")
        == {
            "decision": "FAIL_INCOMPLETE",
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
            "semantic_approval": False,
        }
        and base.get("phase1_state", {}).get("decision") == "FAIL_INCOMPLETE"
        and base.get("phase1_state", {}).get("approved_after") == 0
        and savedata_review.get("phase1_gate") == "FAIL_INCOMPLETE"
        and savedata_review.get("approval_accounting", {}).get("approved_after") == 0
        and gate.get("decision") == "FAIL_INCOMPLETE",
        "Phase 1 gate or zero-approval invariants changed",
    )


def verify_workflow(root: Path) -> None:
    text = (root / WORKFLOW).read_text(encoding="utf-8")
    events = text.split("workflow_dispatch:", 1)[0]
    script = "tools/copilot_mgba_cross_tranche_matrix_verify.py"
    require(script in events and script in text and "--checkout upstream/mgba" in text
            and "--self-test" in text,
            "existing scoped workflow does not select and execute the matrix verifier")


def run_controls(context) -> int:
    matrix, base, original_files, fd, lifecycle, final, review, gate, rows, sources = context
    rejected = []

    def control(name: str, mutate) -> None:
        candidate = copy.deepcopy(matrix)
        mutate(candidate)
        try:
            validate(candidate, base, original_files, fd, lifecycle, final, review, gate, rows, sources)
        except Rejected:
            rejected.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control(
        "source-hash-mismatch",
        lambda value: value["file_dispositions"][0].update(source_sha256="0" * 64),
    )
    control(
        "incomplete-20-file-closure",
        lambda value: value["file_dispositions"].pop(),
    )
    control(
        "false-native-gameplay-label",
        lambda value: value["evidence_classes"][3].update(
            {"class": "NATIVE_MGBA_GAMEPLAY_PHYSICAL_FLASH"}
        ),
    )
    control(
        "missing-file-license",
        lambda value: value["file_dispositions"][0].update(license_notice=""),
    )
    control(
        "combined-license-overclaim",
        lambda value: value["license_boundary"].update(
            combined_distribution_legal_conclusion=True
        ),
    )
    control(
        "approval-promotion",
        lambda value: value["file_dispositions"][0]["objections"][0].update(
            disposition="COPILOT_REVIEWED/PASSED"
        ),
    )
    control(
        "ci-success-overclaim",
        lambda value: value["evidence_classes"][4].update(conclusion="success", job_count=1),
    )
    control(
        "source-revision-mismatch",
        lambda value: value["pinned_source"].update(revision="0" * 40),
    )
    require(rejected == EXPECTED_CONTROLS, "negative-control inventory mismatch")
    return len(rejected)


def git(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    checkout = args.checkout.resolve() if args.checkout else None
    context = load_context(root, checkout)
    matrix, base, files, fd, lifecycle, final, review, gate, rows, sources = context
    validate(matrix, base, files, fd, lifecycle, final, review, gate, rows, sources)
    verify_workflow(root)
    controls = run_controls(context) if args.self_test else 0
    print(
        f"PASS cross-tranche matrix: {len(files)} source records, "
        f"{len(matrix['dependency_edges'])} caller/dependency edges, "
        "all Phase 1 approvals remain zero"
        + (f", {controls} mutation controls rejected" if args.self_test else "")
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"REJECTED: {error}")
        raise SystemExit(1)

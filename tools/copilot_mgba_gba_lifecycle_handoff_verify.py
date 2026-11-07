#!/usr/bin/env python3
"""Verify the bounded GBA savedata lifecycle handoff; never an approval."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "gba-lifecycle-error-contract-handoff.json"
)
BASE_RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata-teardown/"
    "review.json"
)
PRIOR_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "fd-stdio-error-propagation-handoff.json"
)
SAVEDATA_REVIEW = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json"
)
GATE = Path("semantic-snapshots/current/phase1_mapping_gate.json")
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
WORKFLOW = Path(".github/workflows/copilot-mgba-savedata-review.yml")
RECORD_SHA256 = "994e10c0cf611a9d247d23335972d9d3d0f300731274562d7d11b5ecd98e6b06"
BASE_RECORD_SHA256 = "b3bec6ce260d6184fc22a859b9c5bbc518348966cb0092a4fbe56f296667c475"
PRIOR_HANDOFF_SHA256 = "e6333debeed736a58146bf1834b5960ca464cd1116216e67cf6edb5b8a765320"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
SELECTED = {
    "src/gba/core.c",
    "include/mgba/core/core.h",
    "include/mgba/gba/core.h",
    "include/mgba/internal/gba/gba.h",
    "include/mgba/internal/gba/savedata.h",
    "include/mgba/internal/defines.h",
}
ANCHORS = {
    "src/gba/core.c": [
        "src/gba/core.c:309-330",
        "src/gba/core.c:1469-1506",
        "src/gba/core.c:1641-1729",
    ],
    "include/mgba/core/core.h": [
        "include/mgba/core/core.h:56-57",
        "include/mgba/core/core.h:161-164",
    ],
    "include/mgba/gba/core.h": ["include/mgba/gba/core.h:13-17"],
    "include/mgba/internal/gba/gba.h": [
        "include/mgba/internal/gba/gba.h:65-105",
        "include/mgba/internal/gba/gba.h:145-146",
    ],
    "include/mgba/internal/gba/savedata.h": [
        "include/mgba/internal/gba/savedata.h:64-104",
        "include/mgba/internal/gba/savedata.h:90-94",
        "include/mgba/internal/gba/savedata.h:118-125",
    ],
    "include/mgba/internal/defines.h": [
        "include/mgba/internal/defines.h:9-28"
    ],
}
OBJECTIONS = {
    "core-savedata-result-sinks",
    "destroy-and-caller-closure",
    "rtc-and-serialization-contract",
    "dirty-transition-is-not-sync-result",
    "transitive-dependency-and-license-closure",
}
FIXTURE_SHA256 = "4963287bf10a7e2a3cd5e52788bc3aa518d70319fafb8e580c1a9b935059b6d4"
RUNNER_SHA256 = "cc67ed3f5fd9b3a6a9e7f30076b38422dc19a43b3530a6576b97b4f1ed13bb53"
WORKPAPER_SHA256 = "e27d8a3069db06230192db21d8ce3365b3ddcdf75611d69068cfe50a3deb3ac8"
OBSERVATIONS = {
    "failed_sync_calls": 1,
    "failed_sync_dirty_after_clean": 0,
    "failed_sync_rtc_writes": 0,
    "rtc_writes_after_clean_next_frame": 0,
    "rtc_writes_after_success": 1,
    "script_notifications_after_clean_next_frame": 1,
    "script_notifications_after_failed_sync": 1,
    "script_notifications_after_success": 2,
    "sync_calls_after_new_write_then_success": 2,
    "sync_retries_without_new_write": 0,
}
OBSERVATIONS_SHA256 = "bb2010e085ba10656b9d66594b6fed9f700bb444e8609f915fd82c7b801bbae4"
LOCAL_RUN_LOG = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "gba-lifecycle-native-local-run.log"
)
LOCAL_RUN_LOG_SHA256 = "95d5ad944151504b3b80293c9b064ab6a7ec3d60a2aa7244581f76905efbd939"
NATIVE_OUTPUT = [
    "PHASE1_GBA_CALLBACK_CASE failure_async_ms=1 failure_rtc=0 failure_dirty=0 failure_script_events=1 retry_async_ms=0 retry_script_events=1 retry_rtc=0 new_write_success_async_ms=2 success_rtc=1 success_script_events=2",
    "PHASE1_GBA_CALLBACK_DONE",
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


def citation_supported(path: str, line_range: str) -> bool:
    cited = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", line_range)
    if not cited:
        return False
    start, end = map(int, cited.groups())
    return line_range == "1-20" or any(
        (bounds := re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", anchor.rpartition(":")[2]))
        and int(bounds.group(1)) <= start <= end <= int(bounds.group(2))
        for anchor in ANCHORS[path]
    )


def read_json(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return raw, value


def load_dossier(path: Path) -> tuple[bytes, dict[str, tuple[str, str, str]]]:
    raw = path.read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "pinned machine dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "pinned machine dossier Git blob mismatch")
    rows: dict[str, tuple[str, str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path_value = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path_value not in SELECTED
            ):
                continue
            require(path_value not in rows, f"duplicate dossier row: {path_value}")
            rows[path_value] = (
                hashlib.sha256(canonical(row)).hexdigest(),
                provenance.get("git_blob_sha"),
                provenance.get("source_content_sha256"),
            )
    require(set(rows) == SELECTED, "selected dossier rows are incomplete")
    return raw, rows


def validate(
    record: dict,
    sources: dict[str, bytes],
    base: dict,
    prior: dict,
    savedata_review: dict,
    gate: dict,
    dossier_rows: dict[str, tuple[str, str, str]],
) -> None:
    require(record.get("schema") == "xgba.copilot.mgba_gba_savedata_lifecycle_error_contract_handoff.v1",
            "handoff schema mismatch")
    reviewer = record.get("reviewer", {})
    require(
        reviewer.get("identity") == "GitHub Copilot Coding Agent (@copilot), reviewer-side PR #35 follow-up"
        and reviewer.get("source_packet_interpreter")
        == "xbaconator9000x, PR #13 pinned GBA callback workpaper and fixture"
        and reviewer.get("approval_eligible") is False
        and "not a distinct human review" in reviewer.get("identity_limit", ""),
        "reviewer identity or limitation changed",
    )
    attribution = record.get("request_attribution", {})
    require(
        attribution.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and attribution.get("pull_request") == 35
        and attribution.get("comment_id") == 6647254744
        and attribution.get("comment_author") == "xbaconator9000x",
        "request attribution mismatch",
    )
    scope = record.get("scope", {})
    require(
        scope.get("repository") == "mgba-emu/mgba"
        and scope.get("source_revision") == PIN
        and set(scope.get("subset", [])) == SELECTED
        and scope.get("overall_file_verdict") == "NEEDS_EVIDENCE"
        and scope.get("semantic_approval") is False,
        "scope or non-approval disposition changed",
    )
    require(
        "20-file inventory" in scope.get("purpose", "")
        and "fd/stdio handoff" in scope.get("purpose", ""),
        "handoff does not establish a disjoint review purpose",
    )
    base_files = {item["path"]: item for item in base.get("source_files", [])}
    old_subset = set(prior.get("scope", {}).get("subset", []))
    require(not SELECTED.intersection(old_subset), "new source subset overlaps the prior handoff")
    require(
        set(base_files).issuperset(SELECTED),
        "selected source is not in the existing pinned 20-file inventory",
    )
    file_records = record.get("selected_files", [])
    require(len(file_records) == len(SELECTED), "selected file count mismatch")
    require({item.get("path") for item in file_records} == SELECTED,
            "selected source paths differ")
    require(set(sources) == SELECTED, "verified source bytes differ from selected paths")
    for item in file_records:
        path = item["path"]
        original = base_files[path]
        raw = sources[path]
        require(item.get("verdict", "NEEDS_EVIDENCE") == "NEEDS_EVIDENCE",
                f"file disposition promoted: {path}")
        require(item.get("independent_approval", False) is False,
                f"independent approval claimed: {path}")
        for field in ("git_blob_sha1", "source_sha256", "dossier_row_sha256"):
            require(item.get(field) == original.get(field),
                    f"base {field} mismatch: {path}")
        require(blob_sha1(raw) == original["git_blob_sha1"],
                f"pinned source Git blob mismatch: {path}")
        require(sha256(raw) == original["source_sha256"],
                f"pinned source SHA-256 mismatch: {path}")
        require(
            dossier_rows.get(path)
            == (
                original["dossier_row_sha256"],
                original["git_blob_sha1"],
                original["source_sha256"],
            ),
            f"pinned dossier row or source identity mismatch: {path}",
        )
        require(item.get("source_anchors") == ANCHORS[path],
                f"source anchors mismatch: {path}")
        source_lines = raw.decode("utf-8").splitlines()
        for anchor in item["source_anchors"]:
            anchor_path, separator, bounds = anchor.rpartition(":")
            match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", bounds)
            require(separator and anchor_path == path and match,
                    f"unbound source anchor: {anchor}")
            start, end = map(int, match.groups())
            require(start <= end <= len(source_lines),
                    f"source anchor outside complete file: {anchor}")
        require(
            b"Mozilla Public" in raw[:800]
            and b"License, v. 2.0." in raw[:800]
            and b"mozilla.org/MPL/2.0/" in raw[:800],
            f"MPL-2.0 notice absent from leading source bytes: {path}",
        )
    objections = record.get("objection_resolutions", [])
    require(
        len(objections) == len(OBJECTIONS)
        and {item.get("id") for item in objections} == OBJECTIONS,
        "objection matrix is incomplete or expanded",
    )
    for item in objections:
        paths = set(item.get("source_files", []))
        require(paths and paths.issubset(SELECTED),
                f"objection cites out-of-scope source: {item.get('id')}")
        require(item.get("source_lines"), f"source lines missing: {item.get('id')}")
        for citation in item["source_lines"]:
            path, separator, line_range = citation.rpartition(":")
            require(
                separator
                and path in paths
                and citation_supported(path, line_range),
                f"unbound objection citation: {citation}",
            )
        require(item.get("resolution") and item.get("remaining"),
                f"resolution or remaining obligation missing: {item.get('id')}")
        test = item.get("negative_test_evidence", {})
        require(
            test.get("fixture_path") == "tests/phase1_mgba_vfs_fd_callback_native.c"
            and test.get("fixture_sha256") == FIXTURE_SHA256
            and test.get("result") in {
                "NOT_EXERCISED",
                "EXECUTED_NATIVE_HOST_ONLY",
                "PARTIAL_SOURCE_IDENTITY_ONLY",
            }
            and test.get("reason"),
            f"negative evidence identity or limitation missing: {item.get('id')}",
        )

    provenance = record.get("pr13_evidence_provenance", {})
    require(
        provenance.get("head_reviewed") == "d4a753a8909f364ed133eda4b4253a06a985b9ab"
        and provenance.get("workpaper", {}).get("sha256") == WORKPAPER_SHA256
        and provenance.get("runner", {}).get("sha256") == RUNNER_SHA256
        and provenance.get("fixture", {}).get("sha256") == FIXTURE_SHA256,
        "PR13 source/evidence identity mismatch",
    )
    fixture_scope = provenance.get("fixture_test_scope", {})
    require(
        "src/gba/core.c savedataClone/savedataRestore or full mCore teardown"
        in fixture_scope.get("not_tested", [])
        and "GBASavedataSerialize/Deserialize and RTC data round trip"
        in fixture_scope.get("not_tested", []),
        "PR13 fixture limitations are missing",
    )
    reproduction = provenance.get("reproduction", {})
    require(
        reproduction.get("runner_reported_source_tree_identity_verified") is False
        and reproduction.get("execution_class", "").startswith("Local agent Linux native")
        and reproduction.get("compiled_artifact_sha256")
        == "59b757bb3a6622e839e5832239637104d6c354fd7b69dbbcfb3da2eb17c67572"
        and reproduction.get("source_mutations_rejected") == 3
        and reproduction.get("evidence_mutations_rejected") == 8
        and reproduction.get("observed_output") == NATIVE_OUTPUT
        and reproduction.get("observations") == OBSERVATIONS
        and sha256(canonical(reproduction.get("observations", {})))
        == OBSERVATIONS_SHA256
        and reproduction.get("observations_canonical_sha256") == OBSERVATIONS_SHA256,
        "native reproduction data or limits mismatch",
    )
    actions = provenance.get("github_actions", {})
    require(
        actions.get("pr13_current_head_run")
        == {
            "run_id": 41882603072,
            "event": "pull_request",
            "head_sha": "d4a753a8909f364ed133eda4b4253a06a985b9ab",
            "conclusion": "action_required",
            "job_count": 0,
        }
        and actions.get("pr13_prior_baseline_run", {}).get("run_id") == 41485392440
        and actions.get("pr13_prior_baseline_run", {}).get("conclusion") == "success"
        and actions.get("pr13_prior_baseline_run", {}).get("head_sha")
        != provenance.get("head_reviewed")
        and actions.get("pr13_push_event_runs_for_reviewed_branch") == 0,
        "PR13 workflow provenance incorrectly claims current-head or push coverage",
    )
    pr35 = record.get("pr35_actions_observation_at_review_head", {})
    require(
        pr35.get("review_head") == "fba327c6661b7cfb94c35618056882c374e5a711"
        and pr35.get("run_id") == 41944711116
        and pr35.get("event") == "pull_request"
        and pr35.get("conclusion") == "action_required"
        and pr35.get("job_count") == 0
        and pr35.get("push_event_runs_for_reviewed_branch") == 0,
        "PR35 Actions observation improperly claims executed coverage",
    )
    verifier = record.get("review_verifier", {})
    expected_controls = [
        "request-attribution",
        "source-revision",
        "remove-selected-source",
        "add-out-of-scope-source",
        "mutate-git-blob",
        "mutate-source-digest",
        "mutate-dossier-row",
        "promote-file-verdict",
        "claim-independent-approval",
        "mutate-source-anchor",
        "remove-objection",
        "change-fixture-identity",
        "mutate-native-observation",
        "claim-actions-pass",
        "claim-push-coverage",
        "erase-license-gap",
        "promote-phase1-gate",
        "drop-unresolved-obligations",
        "mutate-source-bytes",
    ]
    require(
        verifier.get("path") == "tools/copilot_mgba_gba_lifecycle_handoff_verify.py"
        and verifier.get("negative_controls") == expected_controls
        and verifier.get("negative_control_count") == len(expected_controls),
        "review verifier mutation-control inventory mismatch",
    )
    license_info = record.get("licensing_and_dependency", {})
    require(
        license_info.get("notice") == "MPL-2.0"
        and license_info.get("notice_checked_in_leading_bytes") is True
        and license_info.get("whole_file_hashes_and_dossier_rows_pinned") is True
        and license_info.get("complete_transitive_dependency_closure") is False
        and license_info.get("combined_distribution_conclusion") is False,
        "license/dependency boundary mismatch",
    )
    phase = record.get("phase1_state", {})
    require(
        phase
        == {
            "decision": "FAIL_INCOMPLETE",
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
        },
        "handoff changes protected Phase 1 state",
    )
    require(
        base.get("phase1_state", {}).get("decision") == "FAIL_INCOMPLETE"
        and base.get("phase1_state", {}).get("approved_before") == 0
        and base.get("phase1_state", {}).get("approved_after") == 0
        and base.get("phase1_state", {}).get("p0_approved_before") == 0
        and base.get("phase1_state", {}).get("p0_approved_after") == 0
        and savedata_review.get("phase1_gate") == "FAIL_INCOMPLETE"
        and savedata_review.get("approval_accounting", {}).get("approved_before") == 0
        and savedata_review.get("approval_accounting", {}).get("approved_after") == 0
        and gate.get("decision") == "FAIL_INCOMPLETE",
        "live/base Phase 1 gate or approval invariants changed",
    )
    require(record.get("unresolved_obligations") and len(record["unresolved_obligations"]) >= 8,
            "unresolved obligations missing")


def load_context(root: Path, source_root: Path | None):
    record_raw, record = read_json(root / RECORD)
    require(
        RECORD_SHA256 != "PENDING" and sha256(record_raw) == RECORD_SHA256,
        "handoff record SHA-256 mismatch",
    )
    base_raw, base = read_json(root / BASE_RECORD)
    require(sha256(base_raw) == BASE_RECORD_SHA256, "20-file review record hash mismatch")
    prior_raw, prior = read_json(root / PRIOR_HANDOFF)
    require(sha256(prior_raw) == PRIOR_HANDOFF_SHA256, "prior handoff hash mismatch")
    _, savedata_review = read_json(root / SAVEDATA_REVIEW)
    _, gate = read_json(root / GATE)
    dossier_raw, dossier_rows = load_dossier(root / DOSSIER)
    sources = {}
    for path in SELECTED:
        source = (source_root / path).read_bytes() if source_root else b""
        require(source, f"pinned source file missing: {path}")
        sources[path] = source
    return record_raw, record, base, prior, savedata_review, gate, dossier_raw, dossier_rows, sources


def git(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], text=True
    ).strip()


def verify_workflow(root: Path) -> None:
    text = (root / WORKFLOW).read_text(encoding="utf-8")
    require(
        "tools/copilot_mgba_gba_lifecycle_handoff_verify.py" in text
        and "--checkout upstream/mgba" in text
        and "--self-test" in text
        and "tools/copilot_mgba_gba_lifecycle_handoff_verify.py" in text.split("pull_request:", 1)[1].split("workflow_dispatch:", 1)[0],
        "existing scoped workflow does not invoke and watch the lifecycle verifier",
    )


def verify_native_log(root: Path, record: dict) -> None:
    log_record = record.get("pr13_evidence_provenance", {}).get(
        "reproduction", {}
    ).get("local_run_log", {})
    raw = (root / LOCAL_RUN_LOG).read_bytes()
    require(
        log_record.get("path") == LOCAL_RUN_LOG.as_posix()
        and log_record.get("sha256") == LOCAL_RUN_LOG_SHA256
        and sha256(raw) == LOCAL_RUN_LOG_SHA256,
        "local native run log identity mismatch",
    )
    lines = raw.decode("utf-8").splitlines()
    require(len(lines) == 1 and lines[0].startswith("PHASE1_GBA_CALLBACK_EVIDENCE "),
            "unexpected local native run log shape")
    evidence = json.loads(lines[0].partition(" ")[2])
    require(
        evidence.get("class") == "PINNED_MGBA_GBA_SAVEDATA_FAILED_SYNC_CALLBACK_NATIVE"
        and evidence.get("mgba_commit") == PIN
        and evidence.get("fixture_sha256") == FIXTURE_SHA256
        and evidence.get("artifact_sha256")
        == "59b757bb3a6622e839e5832239637104d6c354fd7b69dbbcfb3da2eb17c67572"
        and evidence.get("source_tree_identity_verified") is False
        and evidence.get("full_gba_translation_unit_compiled") is False
        and evidence.get("observations") == OBSERVATIONS
        and evidence.get("raw_output") == NATIVE_OUTPUT
        and evidence.get("source_mutations_rejected") == 3
        and evidence.get("evidence_mutations_rejected") == 8
        and evidence.get("gate") == "FAIL_INCOMPLETE"
        and evidence.get("independent_approvals") == 0,
        "local native log content or evidence limits mismatch",
    )


def self_test(context) -> int:
    _, record, base, prior, savedata_review, gate, _, dossier_rows, sources = context
    controls = []

    def control(name, mutate_record=lambda value: None, mutate_sources=lambda value: None):
        candidate = copy.deepcopy(record)
        source_copy = dict(sources)
        mutate_record(candidate)
        mutate_sources(source_copy)
        try:
            validate(candidate, source_copy, base, prior, savedata_review, gate, dossier_rows)
        except Rejected:
            controls.append(name)
        else:
            raise Rejected(f"negative control was accepted: {name}")

    control("request-attribution", lambda value: value["request_attribution"].update(comment_id=1))
    control("source-revision", lambda value: value["scope"].update(source_revision="0" * 40))
    control("remove-selected-source", lambda value: value["scope"].update(subset=value["scope"]["subset"][:-1]))
    control("add-out-of-scope-source", lambda value: value["scope"]["subset"].append("src/gba/savedata.c"))
    control("mutate-git-blob", lambda value: value["selected_files"][0].update(git_blob_sha1="0" * 40))
    control("mutate-source-digest", lambda value: value["selected_files"][0].update(source_sha256="0" * 64))
    control("mutate-dossier-row", lambda value: value["selected_files"][0].update(dossier_row_sha256="0" * 64))
    control("promote-file-verdict", lambda value: value["selected_files"][0].update(verdict="COPILOT_REVIEWED/PASSED"))
    control("claim-independent-approval", lambda value: value["selected_files"][0].update(independent_approval=True))
    control("mutate-source-anchor", lambda value: value["selected_files"][0]["source_anchors"].__setitem__(0, "src/gba/core.c:1-1"))
    control("remove-objection", lambda value: value["objection_resolutions"].pop())
    control("change-fixture-identity", lambda value: value["objection_resolutions"][0]["negative_test_evidence"].update(fixture_sha256="0" * 64))
    control("mutate-native-observation", lambda value: value["pr13_evidence_provenance"]["reproduction"]["observations"].update(failed_sync_dirty_after_clean=1))
    control("claim-actions-pass", lambda value: value["pr13_evidence_provenance"]["github_actions"]["pr13_current_head_run"].update(conclusion="success", job_count=1))
    control("claim-push-coverage", lambda value: value["pr35_actions_observation_at_review_head"].update(push_event_runs_for_reviewed_branch=1))
    control("erase-license-gap", lambda value: value["licensing_and_dependency"].update(complete_transitive_dependency_closure=True))
    control("promote-phase1-gate", lambda value: value["phase1_state"].update(decision="PASS"))
    control("drop-unresolved-obligations", lambda value: value.update(unresolved_obligations=[]))
    control("mutate-source-bytes", mutate_sources=lambda value: value.update({"src/gba/core.c": value["src/gba/core.c"] + b"\n"}))
    return len(controls)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    source_root = args.checkout.resolve()
    if (source_root / ".git").exists() or (source_root / ".git").is_file():
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA checkout revision")
    context = load_context(root, source_root)
    _, record, base, prior, savedata_review, gate, _, dossier_rows, sources = context
    validate(record, sources, base, prior, savedata_review, gate, dossier_rows)
    verify_native_log(root, record)
    verify_workflow(root)
    if args.self_test:
        count = self_test(context)
        print(f"PASS lifecycle handoff: {len(SELECTED)} pinned files; {count} mutation controls rejected")
    else:
        print(f"PASS lifecycle handoff: {len(SELECTED)} pinned files; all dispositions NEEDS_EVIDENCE")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"REJECTED: {error}", file=sys.stderr)
        raise SystemExit(1)

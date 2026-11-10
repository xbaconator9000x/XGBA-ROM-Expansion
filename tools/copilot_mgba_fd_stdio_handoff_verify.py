#!/usr/bin/env python3
"""Verify the bounded fd/stdio savedata objection handoff; never an approval."""
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
BASE_RECORD_SHA256 = "b3bec6ce260d6184fc22a859b9c5bbc518348966cb0092a4fbe56f296667c475"
HANDOFF_SHA256 = "e6333debeed736a58146bf1834b5960ca464cd1116216e67cf6edb5b8a765320"
BASE_RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata-teardown/review.json"
)
HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "fd-stdio-error-propagation-handoff.json"
)
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
WORKFLOW = Path(".github/workflows/copilot-mgba-savedata-review.yml")
SELECTED = {
    "include/mgba-util/vfs.h",
    "src/util/vfs/vfs-fd.c",
    "src/util/vfs/vfs-file.c",
    "src/gba/savedata.c",
    "src/gba/gba.c",
}
EXPECTED_OBJECTIONS = {
    "vfile-return-contract",
    "posix-unmap-msync-munmap",
    "bool-close-and-caller",
    "stdio-fflush-fclose-short-io",
    "savedata-short-io-propagation",
    "license-and-dependency-boundary",
}
EXPECTED_ACTIONS = {
    "run_id": 41920176499,
    "run_attempt": 2,
    "event": "pull_request",
    "head_sha": "da037a0f87e0bc71c09ca158cab7bf7c85b5ebbb",
    "run_conclusion": "success",
    "job_id": 126922594700,
    "job_name": "pinned-savedata-review",
    "job_conclusion": "success",
    "completed_steps": 14,
    "artifact_id": 13370374104,
    "artifact_sha256": "eb34bbbd12ce288af393871697fe5cdd0202bec609528bcc69040f3e3446d752",
}


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


def git(checkout: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(checkout), *args])


def verify_base_and_handoff(base_raw: bytes, base: dict, handoff_raw: bytes, handoff: dict) -> None:
    require(sha256(base_raw) == BASE_RECORD_SHA256, "20-file base review record hash mismatch")
    require(sha256(handoff_raw) == HANDOFF_SHA256, "handoff record hash mismatch")
    require(
        base.get("schema") == "xgba.copilot.mgba_savedata_teardown_review.v1"
        and base.get("upstream", {}).get("revision") == PIN,
        "base review record identity mismatch",
    )
    require(
        base.get("phase1_state", {}).get("decision") == "FAIL_INCOMPLETE"
        and base.get("phase1_state", {}).get("p0_approved_before") == 0
        and base.get("phase1_state", {}).get("p0_approved_after") == 0
        and base.get("phase1_state", {}).get("approved_before") == 0
        and base.get("phase1_state", {}).get("approved_after") == 0
        and base.get("phase1_state", {}).get("shared_gate_or_register_edited") is False,
        "base Phase 1 gate/approval invariants changed",
    )
    require(
        handoff.get("schema") == "xgba.copilot.mgba_fd_stdio_error_propagation_handoff.v1",
        "handoff schema mismatch",
    )
    reviewer = handoff.get("reviewer", {})
    require(reviewer.get("approval_eligible") is False, "reviewer claims approval eligibility")
    require(
        "not a distinct human review" in reviewer.get("identity_limit", ""),
        "reviewer identity limitation missing",
    )
    attribution = handoff.get("request_attribution", {})
    require(
        attribution.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and attribution.get("pull_request") == 35
        and attribution.get("comment_id") == 6646374068
        and attribution.get("comment_author") == "xbaconator9000x",
        "review request attribution mismatch",
    )
    scope = handoff.get("scope", {})
    require(scope.get("source_revision") == PIN, "handoff source pin mismatch")
    require(scope.get("overall_file_verdict") == "NEEDS_EVIDENCE", "file verdict promoted")
    require(scope.get("semantic_approval") is False, "semantic approval claimed")
    require(set(scope.get("subset", [])) == SELECTED, "selected source subset changed")
    require(
        "20-file identity inventory" in scope.get("purpose", ""),
        "handoff repeats or replaces the prior source inventory",
    )

    dossier = handoff.get("machine_dossier", {})
    expected_dossier = base["upstream"]["machine_dossier"]
    require(
        dossier.get("path") == expected_dossier.get("path")
        and dossier.get("git_blob_sha1") == expected_dossier.get("git_blob_sha1")
        and dossier.get("sha256") == expected_dossier.get("sha256"),
        "machine dossier identity differs from pinned base record",
    )
    base_files = {item["path"]: item for item in base.get("source_files", [])}
    base_evidence = {item["id"]: item for item in base.get("evidence", [])}
    files = handoff.get("selected_files", [])
    require(len(files) == len(SELECTED), "selected file count mismatch")
    require({item.get("path") for item in files} == SELECTED, "selected file paths mismatch")
    for item in files:
        original = base_files.get(item["path"])
        require(original is not None, f"source not in pinned review record: {item['path']}")
        for field in ("git_blob_sha1", "source_sha256", "dossier_row_sha256"):
            require(item.get(field) == original.get(field), f"{field} mismatch: {item['path']}")
        require(original.get("verdict") == "NEEDS_EVIDENCE", f"base verdict promoted: {item['path']}")
        require(item.get("source_anchors") and item.get("scope_note"),
                f"source scope missing: {item['path']}")

    test_provenance = handoff.get("pr13_test_provenance", {})
    base_tests = base.get("test_provenance", {})
    expected_cases = {
        "fd": {
            "fixture_id": "fd-native-6-case-fixture",
            "parser_id": "fd-parser-tests",
            "parser_methods": 20,
            "native_case_count": 6,
        },
        "stdio": {
            "fixture_id": "stdio-native-7-case-fixture",
            "parser_id": "stdio-parser-tests",
            "parser_methods": 18,
            "native_case_count": 7,
        },
    }
    for backend, expected in expected_cases.items():
        claimed = test_provenance.get(backend, {})
        original = base_tests.get(backend, {})
        fixture = base_evidence.get(expected["fixture_id"], {})
        parser = base_evidence.get(expected["parser_id"], {})
        require(
            claimed.get("fixture_sha256") == fixture.get("sha256")
            and claimed.get("fixture_sha256") == original.get("fixture_sha256"),
            f"{backend} fixture SHA-256 mismatch",
        )
        require(
            claimed.get("parser_test_path") == parser.get("path")
            and claimed.get("parser_test_sha256") == parser.get("sha256")
            and claimed.get("parser_test_sha256") == original.get("parser_test_sha256"),
            f"{backend} parser test identity mismatch",
        )
        require(
            claimed.get("parser_methods") == expected["parser_methods"]
            and original.get("parser_test_methods") == expected["parser_methods"]
            and claimed.get("parser_methods_are_native_cases") is False,
            f"{backend} parser methods conflated with native cases",
        )
        require(
            len(claimed.get("native_cases", [])) == expected["native_case_count"]
            and claimed.get("native_cases") == original.get("native_case_names"),
            f"{backend} native case inventory mismatch",
        )

    objections = handoff.get("objection_resolutions", [])
    require(
        len(objections) == len(EXPECTED_OBJECTIONS)
        and {item.get("id") for item in objections} == EXPECTED_OBJECTIONS,
        "objection resolution matrix incomplete or expanded",
    )
    required_fixture_ids = {
        "fd-native-6-case-fixture",
        "stdio-native-7-case-fixture",
    }
    require(required_fixture_ids.issubset(base_evidence), "PR13 fixture evidence missing from base record")
    for objection in objections:
        source_files = set(objection.get("source_files", []))
        require(
            source_files and source_files.issubset(SELECTED),
            f"source references missing or out of scope: {objection.get('id')}",
        )
        source_lines = objection.get("source_lines", [])
        require(source_lines, f"source lines missing: {objection.get('id')}")
        for location in source_lines:
            path, separator, lines = location.rpartition(":")
            require(
                separator
                and path in source_files
                and re.fullmatch(r"\d+-\d+", lines) is not None,
                f"unbound source-line citation: {location}",
            )
        require(objection.get("finding") and objection.get("remaining"),
                f"finding or remaining limitation missing: {objection.get('id')}")
        tests = objection.get("negative_test_evidence", [])
        require(tests, f"negative test evidence missing: {objection.get('id')}")
        for test in tests:
            fixture_id = (
                "fd-parser-tests"
                if test.get("fixture") == "tests/test_phase1_mgba_vfs_fd_teardown_native.py"
                else "stdio-parser-tests"
                if test.get("fixture") == "tests/test_phase1_mgba_vfs_stdio_native.py"
                else "fd-native-6-case-fixture"
                if "fd_teardown" in test.get("fixture", "")
                else "stdio-native-7-case-fixture"
                if "stdio_native" in test.get("fixture", "")
                else None
            )
            require(fixture_id is not None, f"unrecognized negative test fixture: {test}")
            fixture = base_evidence[fixture_id]
            require(test.get("sha256") == fixture.get("sha256"), "negative test fixture hash mismatch")
            require(test.get("fixture") == fixture.get("path"),
                    "negative test path mismatch")
            require(test.get("case") and test.get("execution"),
                    "negative test case or provenance missing")
            if fixture_id.endswith("native-6-case-fixture"):
                require(test["case"] in test_provenance["fd"]["native_cases"],
                        "fd test case not in fixture inventory")
            elif fixture_id.endswith("native-7-case-fixture"):
                require(test["case"] in test_provenance["stdio"]["native_cases"],
                        "stdio test case not in fixture inventory")
            elif fixture_id == "fd-parser-tests":
                require(test["case"] == "test_internal_evidence_mutations",
                        "fd parser negative-test case mismatch")
            elif fixture_id == "stdio-parser-tests":
                require(test["case"] == "test_internal_evidence_mutations",
                        "stdio parser negative-test case mismatch")
            require(
                "not run in PR35 Actions" in test["execution"]
                or "local native" in test["execution"]
                or "workpaper-reported local" in test["execution"]
                or "PR13 parser/evidence control source" in test["execution"],
                "PR13 test incorrectly presented as PR35 CI",
            )
    statuses = {item["id"]: item["status"] for item in objections}
    require(statuses["vfile-return-contract"] == "RESOLVED_SOURCE_CONTRACT",
            "VFile return-contract resolution changed")
    require("NEEDS_EVIDENCE" in statuses["posix-unmap-msync-munmap"],
            "POSIX runtime evidence promoted")
    require("NEEDS_EVIDENCE" in statuses["bool-close-and-caller"],
            "close semantics promoted")
    require("NEEDS_EVIDENCE" in statuses["stdio-fflush-fclose-short-io"],
            "stdio runtime evidence promoted")
    require("NEEDS_EVIDENCE" in statuses["savedata-short-io-propagation"],
            "savedata caller runtime evidence promoted")
    require("NEEDS_EVIDENCE" in statuses["license-and-dependency-boundary"],
            "license/dependency scope promoted")

    ci = handoff.get("pr35_actions", {})
    require(
        ci.get("workflow_file") == str(WORKFLOW)
        and ci.get("workflow_id") == 401590285,
        "workflow identity mismatch",
    )
    for key, value in EXPECTED_ACTIONS.items():
        require(ci.get(key) == value, f"PR35 Actions identity mismatch: {key}")
    baseline = ci.get("native_baseline", {})
    require(
        baseline.get("mGBA_revision") == PIN
        and baseline.get("test_source_sha256") == "233206a92473469d5ebcd74cdcdedaf6e49395cb67b0cbe19cb2d3a0e2fead18"
        and baseline.get("runtime_log_sha256") == "334addf291ce91cd7f2419b7dc8b4780b63825959ce28c8f13af3aa5c7e23000"
        and baseline.get("assertions") == 43
        and baseline.get("savedata_assertions") == 9
        and baseline.get("hazard_observations") == 4
        and baseline.get("source_mutations_rejected") == 3
        and baseline.get("phase1_gate") == "FAIL_INCOMPLETE"
        and baseline.get("semantic_approvals") == 0,
        "actual PR35 CI baseline evidence mismatch",
    )
    require(
        "does not execute either PR13 teardown fixture" in ci.get("scope_limit", ""),
        "PR35 CI scope overclaimed",
    )

    push = handoff.get("push_coverage", {})
    require(
        push.get("workflow_events") == ["pull_request", "workflow_dispatch"]
        and push.get("push_trigger_configured") is False
        and push.get("actions_push_run_query", {}).get("workflow_id") == 401590285
        and push.get("actions_push_run_query", {}).get("filter_event") == "push"
        and push.get("actions_push_run_query", {}).get("result_count") == 0,
        "push coverage claim mismatch",
    )
    require(
        "do not infer push success" in push.get("conclusion", ""),
        "push coverage conclusion missing",
    )
    pr13 = handoff.get("pr13_fixture_ci", {})
    require(
        pr13.get("current_head") == "d4a753a8909f364ed133eda4b4253a06a985b9ab"
        and pr13.get("current_head_run_id") == 41882603072
        and pr13.get("current_head_conclusion") == "action_required"
        and pr13.get("current_head_jobs") == 0
        and pr13.get("prior_fd_code_run_conclusion") == "success"
        and pr13.get("prior_fd_code_run_is_current_head") is False
        and pr13.get("stdio_code_head_run_conclusion") == "action_required"
        and pr13.get("stdio_code_head_jobs") == 0
        and pr13.get("current_teardown_fixture_ci") == "NEEDS_EVIDENCE",
        "PR13 exact-head or historical CI status misrepresented",
    )
    phase = handoff.get("phase1_state", {})
    require(
        phase == {
            "decision": "FAIL_INCOMPLETE",
            "p0_candidates": 338,
            "p0_approved": 0,
            "inventory_total": 14834,
            "approved": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
        },
        "Phase 1 gate or counts changed",
    )
    gate = handoff.get("promotion_gate", {})
    require(
        gate.get("all_selected_file_verdicts") == "NEEDS_EVIDENCE"
        and gate.get("copilot_reviewed_passed") is False
        and gate.get("external_approved") is False
        and len(gate.get("reasons", [])) >= 4,
        "handoff promotion gate was weakened",
    )


def verify_sources_and_dossier(
    checkout: Path | None,
    source_dir: Path | None,
    dossier_path: Path,
    base: dict,
    handoff: dict,
) -> tuple[int, int]:
    require((checkout is None) != (source_dir is None),
            "provide exactly one of --checkout or --source-dir")
    if checkout:
        require(git(checkout, "rev-parse", "HEAD").decode().strip() == PIN,
                "upstream checkout is not the immutable mGBA pin")
    base_files = {item["path"]: item for item in base["source_files"]}
    checked = 0
    required_source_fragments = {
        "include/mgba-util/vfs.h": (
            b"bool (*close)(struct VFile* vf);",
            b"ssize_t (*read)(struct VFile* vf, void* buffer, size_t size);",
            b"ssize_t (*write)(struct VFile* vf, const void* buffer, size_t size);",
            b"void (*unmap)(struct VFile* vf, void* memory, size_t size);",
        ),
        "src/util/vfs/vfs-fd.c": (
            b"if (close(vfd->fd) < 0)",
            b"msync(memory, size, MS_SYNC);",
            b"munmap(memory, size);",
        ),
        "src/util/vfs/vfs-file.c": (
            b"if (fclose(vff->file) < 0)",
            b"return fflush(vff->file) == 0;",
            b"fwrite(memory, size, 1, vff->file);",
        ),
        "src/gba/savedata.c": (
            b"read = savedata->vf->write(savedata->vf, buffer, read);",
            b"return read >= 0;",
            b"GBASavedataLoad(savedata, vf);",
        ),
        "src/gba/gba.c": (
            b"savedata.realVf->close(gba->memory.savedata.realVf);",
            b"gba->memory.savedata.realVf = 0;",
        ),
    }
    for item in handoff["selected_files"]:
        data = (
            git(checkout, "show", f"{PIN}:{item['path']}")
            if checkout
            else (source_dir / item["path"]).read_bytes()
        )
        original = base_files[item["path"]]
        require(blob_sha1(data) == original["git_blob_sha1"], f"source Git blob mismatch: {item['path']}")
        require(sha256(data) == original["source_sha256"], f"source SHA-256 mismatch: {item['path']}")
        require(data.startswith(b"/*") and b"Mozilla Public" in data[:800]
                and b"License, v. 2.0." in data[:800],
                f"MPL-2.0 notice not verified: {item['path']}")
        require(
            all(fragment in data for fragment in required_source_fragments[item["path"]]),
            f"selected full-file source anchors mismatch: {item['path']}",
        )
        checked += 1

    raw_dossier = dossier_path.read_bytes()
    dossier_meta = handoff["machine_dossier"]
    require(sha256(raw_dossier) == dossier_meta["sha256"], "compressed dossier SHA-256 mismatch")
    require(blob_sha1(raw_dossier) == dossier_meta["git_blob_sha1"], "compressed dossier Git blob mismatch")
    expected_rows = {item["path"]: item["dossier_row_sha256"] for item in handoff["selected_files"]}
    observed = set()
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path not in expected_rows
            ):
                continue
            canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            require(sha256(canonical) == expected_rows[path], f"canonical dossier row mismatch: {path}")
            selected = next(item for item in handoff["selected_files"] if item["path"] == path)
            require(
                provenance.get("git_blob_sha") == selected["git_blob_sha1"]
                and provenance.get("source_content_sha256") == selected["source_sha256"],
                f"dossier provenance/source identity mismatch: {path}",
            )
            require(path not in observed, f"duplicate dossier row: {path}")
            observed.add(path)
    require(observed == set(expected_rows), "selected dossier rows are incomplete")
    return checked, len(observed)


def verify_workflow_event_scope(workflow_path: Path) -> None:
    text = workflow_path.read_text(encoding="utf-8")
    trigger = re.search(r"(?ms)^on:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*\s*:|\Z)", text)
    require(trigger is not None, "cannot locate workflow trigger block")
    events = set(re.findall(r"(?m)^  ([A-Za-z_][A-Za-z0-9_-]*):", trigger.group(1)))
    require(events == {"pull_request", "workflow_dispatch"}, "workflow event scope changed")
    require(not re.search(r"(?m)^  push\s*:", trigger.group(1)), "push trigger unexpectedly configured")
    require(
        "Verify fd and stdio error-propagation handoff" in text
        and "python3 tools/copilot_mgba_fd_stdio_handoff_verify.py" in text
        and "tools/copilot_mgba_fd_stdio_handoff_verify.py \\" in text
        and "--self-test" in text,
        "existing PR validation workflow does not execute this handoff verifier",
    )


def expect_rejected(callback, label: str) -> None:
    try:
        callback()
    except Rejected:
        return
    raise Rejected(f"mutation control escaped: {label}")


def mutation_controls(base_raw: bytes, base: dict, handoff_raw: bytes, handoff: dict) -> int:
    verify_base_and_handoff(base_raw, base, handoff_raw, handoff)
    rejected = 0

    def mutate(change, label: str) -> None:
        candidate = copy.deepcopy(handoff)
        change(candidate)
        expect_rejected(lambda: verify_base_and_handoff(base_raw, base, handoff_raw, candidate), label)

    mutate(lambda d: d["phase1_state"].update(decision="PASS"), "gate promotion")
    rejected += 1
    mutate(lambda d: d["phase1_state"].update(approved=1), "approval count increment")
    rejected += 1
    mutate(lambda d: d["scope"].update(overall_file_verdict="COPILOT_REVIEWED/PASSED"),
           "file verdict promotion")
    rejected += 1
    mutate(lambda d: d["selected_files"][0].update(source_sha256="0" * 64),
           "source hash mutation")
    rejected += 1
    mutate(lambda d: d["machine_dossier"].update(sha256="0" * 64),
           "dossier hash mutation")
    rejected += 1
    mutate(lambda d: d["pr35_actions"].update(head_sha="0" * 40),
           "CI head mutation")
    rejected += 1
    mutate(lambda d: d["pr35_actions"].update(event="push"),
           "false CI event")
    rejected += 1
    mutate(lambda d: d["pr35_actions"].update(job_conclusion="failure"),
           "failed job accepted")
    rejected += 1
    mutate(lambda d: d["pr35_actions"]["native_baseline"].update(assertions=42),
           "native assertion count mutation")
    rejected += 1
    mutate(lambda d: d["pr35_actions"].update(scope_limit="PR35 executed teardown fixtures"),
           "overclaimed PR35 test scope")
    rejected += 1
    mutate(lambda d: d["push_coverage"].update(push_trigger_configured=True),
           "fabricated push trigger")
    rejected += 1
    mutate(lambda d: d["push_coverage"]["actions_push_run_query"].update(result_count=1),
           "fabricated push run")
    rejected += 1
    mutate(lambda d: d["pr13_fixture_ci"].update(current_head_conclusion="success"),
           "fabricated current PR13 fixture CI success")
    rejected += 1
    mutate(lambda d: d["objection_resolutions"][0]["negative_test_evidence"][0].update(
        sha256="0" * 64), "negative fixture hash mutation")
    rejected += 1
    mutate(lambda d: d["objection_resolutions"].pop(), "missing unresolved objection")
    rejected += 1

    altered = bytearray(handoff_raw)
    altered[-2] ^= 1
    expect_rejected(
        lambda: require(sha256(bytes(altered)) == HANDOFF_SHA256, "handoff mutation accepted"),
        "handoff byte mutation",
    )
    rejected += 1
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--checkout", type=Path)
    source.add_argument("--source-dir", type=Path)
    parser.add_argument("--base-record", type=Path, default=BASE_RECORD)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--dossier", type=Path, default=DOSSIER)
    parser.add_argument("--workflow", type=Path, default=WORKFLOW)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        base_raw = args.base_record.read_bytes()
        handoff_raw = args.handoff.read_bytes()
        base = json.loads(base_raw.decode("utf-8"))
        handoff = json.loads(handoff_raw.decode("utf-8"))
        verify_base_and_handoff(base_raw, base, handoff_raw, handoff)
        checkout = args.checkout
        if checkout is None and args.source_dir is None:
            checkout = Path("upstream/mgba")
        sources, rows = verify_sources_and_dossier(
            checkout,
            args.source_dir,
            args.dossier,
            base,
            handoff,
        )
        verify_workflow_event_scope(args.workflow)
        controls = mutation_controls(base_raw, base, handoff_raw, handoff) if args.self_test else 0
    except (OSError, UnicodeError, json.JSONDecodeError, subprocess.CalledProcessError, Rejected) as error:
        print(f"FAIL_CLOSED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "decision": "PASS_BOUNDED_SOURCE_AND_REVIEWER_HANDOFF_INTEGRITY_ONLY",
        "source_revision": PIN,
        "selected_source_files_verified": sources,
        "selected_dossier_rows_verified": rows,
        "actions_run_id": 41920176499,
        "actions_head_sha": EXPECTED_ACTIONS["head_sha"],
        "actions_event": "pull_request",
        "actions_job_id": 126922594700,
        "actions_job_conclusion": "success",
        "push_coverage": "NONE",
        "teardown_fixtures_executed_by_pr35_actions": False,
        "all_file_verdicts": "NEEDS_EVIDENCE",
        "semantic_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
        "mutation_controls_rejected": controls,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed workflow run and game-save evidence provenance checks."""
import argparse
import datetime
import json
import os
import re
import subprocess
from pathlib import Path

EXPECTED_BASE_REF = "phase1/firered-mgba-save-loader-steptrace-20261028"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _sha(value, name):
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError(f"{name} must be a full lowercase commit SHA")
    return value


def build_run_provenance(event_name, payload, environment, checked_out_sha,
                         current_base_sha=None, base_is_ancestor=None):
    checked_out_sha = _sha(checked_out_sha, "checked_out_sha")
    run_id = environment.get("GITHUB_RUN_ID")
    attempt = environment.get("GITHUB_RUN_ATTEMPT")
    if not run_id or not run_id.isdigit() or not attempt or not attempt.isdigit():
        raise ValueError("Missing or invalid workflow run identity")
    repository = environment.get("GITHUB_REPOSITORY")
    if not repository:
        raise ValueError("Missing workflow repository identity")
    provenance = {
        "schema": "xgba-phase1-github-run-provenance-v1",
        "repository": repository,
        "workflow": environment.get("GITHUB_WORKFLOW", ""),
        "workflow_ref": environment.get("GITHUB_WORKFLOW_REF", ""),
        "run_id": int(run_id),
        "run_attempt": int(attempt),
        "event_name": event_name,
        "checked_out_sha": checked_out_sha,
        "base_ref": None,
        "base_sha": None,
        "current_base_sha": None,
        "base_fresh": None,
        "base_is_ancestor": None,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approval": False,
    }
    if event_name == "pull_request":
        pr = payload.get("pull_request")
        if not isinstance(pr, dict):
            raise ValueError("pull_request event payload is missing pull_request")
        head = pr.get("head") or {}
        base = pr.get("base") or {}
        head_sha = _sha(head.get("sha"), "pull_request.head.sha")
        base_sha = _sha(base.get("sha"), "pull_request.base.sha")
        base_ref = base.get("ref")
        if base_ref != EXPECTED_BASE_REF:
            raise ValueError("Pull request targets an unexpected or stale base branch")
        if (head.get("repo") or {}).get("full_name") != repository:
            raise ValueError("Pull request head repository does not match this repository")
        if checked_out_sha != head_sha:
            raise ValueError("Checked-out commit is not the exact pull request head")
        if current_base_sha != base_sha:
            raise ValueError("Pull request base SHA is stale relative to current base branch")
        if base_is_ancestor is not True:
            raise ValueError("Pull request head does not contain its current base commit")
        provenance.update({
            "head_sha": head_sha,
            "head_ref": head.get("ref"),
            "base_ref": base_ref,
            "base_sha": base_sha,
            "current_base_sha": current_base_sha,
            "base_fresh": True,
            "base_is_ancestor": True,
            "merge_sha": _sha(environment.get("GITHUB_SHA"), "GITHUB_SHA"),
        })
    elif event_name == "push":
        after = _sha(payload.get("after"), "push.after")
        event_sha = _sha(environment.get("GITHUB_SHA"), "GITHUB_SHA")
        if checked_out_sha != after or event_sha != after:
            raise ValueError("Push event SHA does not match checked-out commit")
        provenance.update({
            "head_sha": after,
            "head_ref": payload.get("ref"),
        })
    elif event_name == "workflow_dispatch":
        event_sha = _sha(environment.get("GITHUB_SHA"), "GITHUB_SHA")
        if checked_out_sha != event_sha:
            raise ValueError("Manual run SHA does not match checked-out commit")
        provenance["head_sha"] = event_sha
    else:
        raise ValueError("Unsupported workflow trigger; provenance is incomplete")
    return provenance


def validate_required_pr_run(records, expected_head, expected_base_ref=EXPECTED_BASE_REF):
    expected_head = _sha(expected_head, "expected_head")
    if not isinstance(records, list):
        raise AssertionError("Workflow run evidence must be a list")
    matches = [
        record for record in records
        if isinstance(record, dict)
        and record.get("event_name") == "pull_request"
        and record.get("head_sha") == expected_head
        and record.get("checked_out_sha") == expected_head
        and record.get("base_ref") == expected_base_ref
        and isinstance(record.get("base_sha"), str)
        and SHA_RE.fullmatch(record["base_sha"])
        and isinstance(record.get("current_base_sha"), str)
        and SHA_RE.fullmatch(record["current_base_sha"])
        and record.get("base_sha") == record.get("current_base_sha")
        and record.get("base_fresh") is True
        and record.get("base_is_ancestor") is True
        and type(record.get("run_id")) is int
        and record["run_id"] > 0
        and type(record.get("run_attempt")) is int
        and record["run_attempt"] > 0
        and record.get("run_url")
        == f"https://github.com/{record.get('repository')}/actions/runs/{record.get('run_id')}"
        and record.get("job_conclusion") == "success"
    ]
    if not matches:
        raise AssertionError("No successful exact-head pull_request run provenance")
    return matches[0]


def validate_game_save_evidence(record):
    if not isinstance(record, dict):
        raise AssertionError("Save evidence must be a JSON object")
    if (record.get("output_save_origin") == "game_generated"
            and record.get("game_initiated_save_verified") is not True):
        raise AssertionError("Unverified output is mislabeled as a game-generated save")
    if record.get("game_initiated_save_verified") is not True:
        return False
    if (record.get("case") != "pallet_save_dense_confirm"
            or record.get("input_save_origin") != "synthetic_fixture"
            or record.get("output_save_origin") != "game_generated"
            or record.get("source_fixture") != "synthetic_pallet_valid"
            or record.get("physical_save_changed") is not True):
        raise AssertionError("Synthetic fixture evidence is mislabeled as a game-generated save")
    native = record.get("native") or {}
    if (native.get("start_menu_save_hits", 0) <= 0
            or native.get("save_dialog_do_save_hits", 0) <= 0
            or native.get("try_saving_data_entry_hits", 0) <= 0
            or native.get("try_saving_data_return_hits", 0) <= 0
            or native.get("first_try_saving_data_return_value") != 1
            or native.get("program_flash_sector_and_verify_entry_hits") != 14
            or native.get("program_flash_sector_and_verify_return_hits") != 14
            or native.get("host_flash_writes") != 0
            or native.get("flash_changed_bytes", 0) <= 0):
        raise AssertionError("Game-save claim lacks compiled controller/save/Flash evidence")
    trace = native.get("flash_program_trace")
    if not isinstance(trace, list) or len(trace) != 14:
        raise AssertionError("Game-save claim lacks all fourteen Flash-sector observations")
    if sorted(row.get("sector") for row in trace if isinstance(row, dict)) != list(range(14, 28)):
        raise AssertionError("Game-save claim has incomplete or duplicate physical sectors")
    return True


def _current_base_sha(base_ref):
    if not isinstance(base_ref, str) or not re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        raise ValueError("Invalid base ref")
    subprocess.run(
        ["git", "fetch", "--no-tags", "origin",
         f"refs/heads/{base_ref}:refs/remotes/origin/{base_ref}"],
        check=True, capture_output=True, text=True,
    )
    return _sha(subprocess.run(
        ["git", "rev-parse", f"refs/remotes/origin/{base_ref}"],
        check=True, capture_output=True, text=True,
    ).stdout.strip(), "current_base_sha")


def _base_is_ancestor(base_sha, head_sha):
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_sha, head_sha],
        check=False,
    ).returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, default=Path(os.environ.get("GITHUB_EVENT_PATH", "event.json")))
    parser.add_argument("--output", type=Path, default=Path("evidence/results/workflow_provenance.json"))
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--job-conclusion", choices=("success", "failure", "cancelled"))
    args = parser.parse_args()
    if args.finalize:
        provenance = json.loads(args.output.read_text())
        provenance["job_conclusion"] = args.job_conclusion or "failure"
        provenance["exact_head_pr_run_verified"] = False
        if provenance.get("event_name") == "pull_request" and provenance["job_conclusion"] == "success":
            validate_required_pr_run(
                [dict(provenance, job_conclusion=provenance["job_conclusion"])],
                provenance.get("head_sha"),
            )
            provenance["exact_head_pr_run_verified"] = True
        provenance["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        return
    payload = json.loads(args.event.read_text())
    checked_out_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    current_base_sha = None
    is_ancestor = None
    try:
        if event_name == "pull_request":
            base = (payload.get("pull_request") or {}).get("base") or {}
            if base.get("ref") != EXPECTED_BASE_REF:
                raise ValueError("Unexpected pull_request base; refusing stale or unrelated PR evidence")
            current_base_sha = _current_base_sha(base["ref"])
            is_ancestor = _base_is_ancestor(base["sha"], payload["pull_request"]["head"]["sha"])
        provenance = build_run_provenance(
            event_name, payload, os.environ, checked_out_sha,
            current_base_sha=current_base_sha, base_is_ancestor=is_ancestor,
        )
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        pr = payload.get("pull_request") or {}
        head = pr.get("head") or {}
        base = pr.get("base") or {}
        provenance = {
            "schema": "xgba-phase1-github-run-provenance-v1",
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": int(os.environ.get("GITHUB_RUN_ID", "0")) or None,
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")) or None,
            "event_name": event_name,
            "head_sha": head.get("sha") or payload.get("after"),
            "checked_out_sha": checked_out_sha,
            "base_ref": base.get("ref"),
            "base_sha": base.get("sha"),
            "current_base_sha": current_base_sha,
            "base_fresh": current_base_sha == base.get("sha") if base.get("sha") else False,
            "base_is_ancestor": is_ancestor,
            "provenance_valid": False,
            "validation_error": str(error),
            "phase1_gate": "FAIL_INCOMPLETE",
            "independent_approval": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        raise SystemExit(str(error))
    provenance["provenance_valid"] = True
    provenance["run_url"] = (
        f"https://github.com/{provenance['repository']}/actions/runs/{provenance['run_id']}"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    print(json.dumps(provenance, sort_keys=True))


if __name__ == "__main__":
    main()

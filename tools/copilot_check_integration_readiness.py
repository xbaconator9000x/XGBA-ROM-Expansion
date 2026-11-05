#!/usr/bin/env python3
"""Observational, fail-closed readiness check for the audited draft PR stack."""

import argparse
from collections import Counter
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "development/copilot-integration/manifest.json"
API = "https://api.github.com"
SHA1 = re.compile(r"^[0-9a-f]{40}$")


def _pr_number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _workflow_ref(run, number):
    refs = run.get("pull_requests", [])
    for ref in refs:
        ref_number = (
            _pr_number(ref.get("number"))
            if isinstance(ref, dict)
            else _pr_number(ref)
        )
        if ref_number == number:
            return ref
    return None


def _run_provenance(run, number, observed, commit_details):
    """Return whether the executed commit is this PR's current head/base."""
    ref = _workflow_ref(run, number)
    if ref is None:
        return False, "run is not scoped to this PR"

    head_sha = observed.get("head_sha")
    base_sha = observed.get("base_sha")
    executed_sha = run.get("head_sha")
    if not isinstance(executed_sha, str) or not SHA1.fullmatch(executed_sha):
        return False, "executed commit SHA is missing or malformed"
    if (
        run.get("event") == "pull_request_target"
        and executed_sha == base_sha
        and executed_sha != head_sha
    ):
        return False, "pull_request_target executed only base code"
    if executed_sha == head_sha:
        if not isinstance(ref, dict):
            return False, "run does not report PR head/base provenance"
        if ref.get("head_sha") != head_sha or ref.get("base_sha") != base_sha:
            return False, "PR head/base provenance is missing or stale"
        return True, "exact current PR head and base provenance"

    if not isinstance(ref, dict):
        return False, "run does not bind the executed commit to current PR head/base"
    if ref.get("head_sha") != head_sha or ref.get("base_sha") != base_sha:
        return False, "PR head/base provenance is stale"

    commit = commit_details.get(executed_sha)
    if not isinstance(commit, dict) or commit.get("sha") != executed_sha:
        return False, "merge commit object was not independently verified"
    if commit.get("parents") != [base_sha, head_sha]:
        return False, "merge commit parents do not match current PR base/head"
    return True, "verified merge commit with exact base/head parents"


def classify_workflow_evidence(number, workflow_id, observed, runs, commit_details):
    """Classify the latest exact-scope run, retaining URLs and actionable detail."""
    candidates = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("workflow_id") == workflow_id
        and _workflow_ref(run, number) is not None
    ]
    base_result = {
        "pr_number": number,
        "workflow_id": workflow_id,
        "expected_head_sha": observed.get("head_sha"),
        "expected_base_sha": observed.get("base_sha"),
        "run_id": None,
        "run_attempt": None,
        "event": None,
        "executed_sha": None,
        "reported_head_sha": None,
        "reported_base_sha": None,
        "run_url": None,
        "job_urls": [],
        "provenance_status": "unverified",
        "detail": "",
    }
    if not candidates:
        return dict(base_result, status="missing",
                    detail="no run for this PR and required workflow was observed")

    current, stale = [], []
    for run in candidates:
        matches, provenance = _run_provenance(run, number, observed, commit_details)
        item = (run, provenance)
        (current if matches else stale).append(item)

    def run_rank(item):
        run = item[0]
        return (
            str(run.get("created_at") or ""),
            run.get("run_number") if isinstance(run.get("run_number"), int) else 0,
            run.get("run_attempt") if isinstance(run.get("run_attempt"), int) else 0,
            run.get("id") if isinstance(run.get("id"), int) else 0,
        )

    if not current:
        run, provenance = max(stale, key=run_rank)
        result = dict(
            base_result,
            status="stale_head_base",
            provenance_status="stale_head_base",
            run_id=run.get("id"),
            run_attempt=run.get("run_attempt"),
            event=run.get("event"),
            executed_sha=run.get("head_sha"),
            reported_head_sha=(
                _workflow_ref(run, number).get("head_sha")
                if isinstance(_workflow_ref(run, number), dict)
                else None
            ),
            reported_base_sha=(
                _workflow_ref(run, number).get("base_sha")
                if isinstance(_workflow_ref(run, number), dict)
                else None
            ),
            run_url=run.get("html_url"),
            detail=provenance,
        )
        jobs = run.get("jobs")
        if run.get("status") in ("queued", "in_progress", "requested", "waiting"):
            result.update(
                status="pending",
                detail="run is pending, but current head/base provenance is unverified: "
                + provenance,
            )
        elif (
            run.get("conclusion") == "action_required"
            and isinstance(jobs, dict)
            and jobs.get("available") is True
            and jobs.get("total_count") == 0
        ):
            result.update(
                status="action_required_zero_job",
                detail=(
                    "GitHub requires workflow authorization; zero jobs executed. "
                    "The run also lacks current PR head/base provenance: "
                    + provenance
                ),
            )
        return result

    run, provenance = max(current, key=run_rank)
    result = dict(
        base_result,
        run_id=run.get("id"),
        run_attempt=run.get("run_attempt"),
        event=run.get("event"),
        executed_sha=run.get("head_sha"),
        reported_head_sha=(
            _workflow_ref(run, number).get("head_sha")
            if isinstance(_workflow_ref(run, number), dict)
            else None
        ),
        reported_base_sha=(
            _workflow_ref(run, number).get("base_sha")
            if isinstance(_workflow_ref(run, number), dict)
            else None
        ),
        run_url=run.get("html_url"),
        provenance=provenance,
        provenance_status="verified",
    )
    jobs = run.get("jobs")
    if (
        not isinstance(run.get("run_attempt"), int)
        or isinstance(run.get("run_attempt"), bool)
        or run.get("run_attempt") < 1
    ):
        return dict(result, status="missing",
                    detail="run attempt number is absent or malformed")

    if run.get("status") in ("queued", "in_progress", "requested", "waiting"):
        return dict(result, status="pending", detail="workflow run has not completed")
    if run.get("conclusion") == "action_required" or run.get("status") == "action_required":
        if isinstance(jobs, dict) and jobs.get("available") is True:
            if jobs.get("total_count") == 0:
                return dict(
                    result,
                    status="action_required_zero_job",
                    detail=(
                        "GitHub requires workflow authorization; no job executed. "
                        "A maintainer with write access must approve the run in GitHub Actions."
                    ),
                )
            return dict(
                result,
                status="missing",
                detail="action_required run unexpectedly reports jobs; inspect run metadata",
            )
        return dict(
            result,
            status="missing",
            detail="action_required run has no verified job-count response",
        )

    if run.get("status") != "completed":
        return dict(result, status="pending",
                    detail="workflow run is not in a completed state")
    if not isinstance(jobs, dict) or jobs.get("available") is not True:
        return dict(result, status="missing",
                    detail="job execution evidence is unavailable")
    job_rows = jobs.get("jobs")
    total_count = jobs.get("total_count")
    if (
        not isinstance(total_count, int)
        or isinstance(total_count, bool)
        or total_count < 0
        or not isinstance(job_rows, list)
        or not jobs.get("complete", True)
        or len(job_rows) != total_count
    ):
        return dict(result, status="missing",
                    detail="workflow job list is malformed or incomplete")
    result["job_urls"] = [
        job.get("html_url")
        for job in job_rows
        if isinstance(job, dict) and isinstance(job.get("html_url"), str)
    ]
    if total_count == 0:
        return dict(result, status="missing",
                    detail="completed run has no executed job evidence")

    job_statuses = [job.get("status") for job in job_rows if isinstance(job, dict)]
    job_conclusions = [
        job.get("conclusion") for job in job_rows if isinstance(job, dict)
    ]
    if len(job_statuses) != total_count:
        return dict(result, status="missing",
                    detail="workflow job records contain malformed entries")
    if any(
        not isinstance(job.get("run_attempt"), int)
        or isinstance(job.get("run_attempt"), bool)
        or job.get("run_attempt") != run.get("run_attempt")
        for job in job_rows
    ):
        return dict(
            result,
            status="missing",
            detail="job attempt provenance is absent or does not match the selected run attempt",
        )
    if any(status != "completed" for status in job_statuses):
        return dict(result, status="pending",
                    detail="one or more workflow jobs have not completed")
    if (
        run.get("conclusion") == "success"
        and all(conclusion in ("success", "skipped") for conclusion in job_conclusions)
        and "success" in job_conclusions
    ):
        return dict(result, status="executed_success",
                    detail="completed run and all executed jobs succeeded")
    return dict(result, status="executed_failure",
                detail="completed run or one or more jobs did not succeed")


def classify_main_base_ancestry(observation):
    """Classify a recorded main base only when compare-API provenance is complete."""
    if not isinstance(observation, dict):
        return "unverified_ancestry", "main-base observation is missing"
    expected_base = observation.get("expected_base_sha")
    observed_base = observation.get("observed_base_sha")
    main_sha = observation.get("current_main_sha")
    if any(not isinstance(sha, str) or not SHA1.fullmatch(sha)
           for sha in (expected_base, observed_base, main_sha)):
        return "unverified_ancestry", "main-base SHA provenance is missing or malformed"
    if observed_base != expected_base:
        return "changed_base", "live PR base differs from the pinned manifest base"

    compare = observation.get("compare")
    if not isinstance(compare, dict):
        return "unverified_ancestry", "GitHub compare ancestry evidence is unavailable"
    if (
        compare.get("base_sha") != observed_base
        or compare.get("head_sha") != main_sha
        or not isinstance(compare.get("merge_base_sha"), str)
        or not SHA1.fullmatch(compare["merge_base_sha"])
    ):
        return (
            "unverified_ancestry",
            "compare evidence does not bind the recorded base to current main",
        )
    ahead = compare.get("ahead_by")
    behind = compare.get("behind_by")
    if (
        not isinstance(ahead, int) or isinstance(ahead, bool) or ahead < 0
        or not isinstance(behind, int) or isinstance(behind, bool) or behind < 0
    ):
        return "unverified_ancestry", "compare commit counts are missing or malformed"
    if (
        observed_base == main_sha
        and compare.get("status") == "identical"
        and ahead == 0
        and behind == 0
        and compare["merge_base_sha"] == observed_base
    ):
        return "current", "PR base equals current main"
    if (
        compare.get("status") == "ahead"
        and ahead > 0
        and behind == 0
        and compare["merge_base_sha"] == observed_base
    ):
        return "stale_ancestor", "recorded PR base is an ancestor of current main"
    return (
        "diverged_or_inconsistent",
        "compare evidence does not prove a current or ancestor base",
    )


def missing_required_workflow_events(required_events, observed_runs):
    """Return configured event types with no observed run; unconfigured events are ignored."""
    if (
        not isinstance(required_events, list)
        or any(not isinstance(event, str) or not event for event in required_events)
        or not isinstance(observed_runs, list)
    ):
        return ["workflow event evidence is malformed"]
    observed = {
        run.get("event")
        for run in observed_runs
        if isinstance(run, dict) and isinstance(run.get("event"), str)
    }
    return sorted(set(required_events) - observed)


def _format_workflow_blocker(evidence):
    status = evidence["status"]
    workflow_id = evidence["workflow_id"]
    number = evidence["pr_number"]
    run = "run %s" % evidence["run_id"] if evidence["run_id"] is not None else "no run"
    if evidence.get("run_attempt") is not None:
        run += " attempt %s" % evidence["run_attempt"]
    url = evidence.get("run_url") or "unavailable"
    detail = evidence["detail"]
    if status == "action_required_zero_job":
        action = (
            "Required action: a maintainer with write access must approve this "
            "workflow run at %s; do not retry or count it as green." % url
        )
    elif status == "pending":
        action = "Required action: wait for the run/jobs to complete; do not infer success."
    elif status == "executed_failure":
        action = "Required action: inspect run/job logs before deciding on a repair; no retry was requested."
    elif status == "stale_head_base":
        action = "Required action: obtain evidence on the current head/base; stale evidence is not reusable."
    else:
        action = "Required action: restore or query complete exact-scope run/job evidence."
    job_urls = ",".join(evidence.get("job_urls", [])) or "unavailable"
    return (
        "PR #%d required evidence absent: workflow #%d status=%s, %s, URL=%s, "
        "job_URLs=%s, tested_head=%s, tested_base=%s, executed_sha=%s, "
        "reported_head=%s, reported_base=%s; "
        "%s; %s" % (
            number,
            workflow_id,
            status,
            run,
            url,
            job_urls,
            evidence.get("expected_head_sha") or "unknown",
            evidence.get("expected_base_sha") or "unknown",
            evidence.get("executed_sha") or "unknown",
            evidence.get("reported_head_sha") or "unknown",
            evidence.get("reported_base_sha") or "unknown",
            detail,
            action,
        )
    )


def validate(manifest, snapshot):
    """Return readiness blockers; never interprets CI as semantic approval."""
    issues = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    if not isinstance(snapshot, dict):
        return ["snapshot must be a JSON object"]

    raw_prs = manifest.get("pull_requests")
    if not isinstance(raw_prs, list) or not raw_prs:
        return ["manifest pull_requests must be a non-empty list"]
    expected_prs = {}
    for index, pr in enumerate(raw_prs):
        if not isinstance(pr, dict):
            issues.append("manifest pull_requests[%d] must be an object" % index)
            continue
        number = pr.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            issues.append("manifest pull_requests[%d] has an invalid PR number" % index)
            continue
        if number in expected_prs:
            issues.append("manifest has duplicate PR #%d scope" % number)
            continue
        expected_prs[number] = pr
        for field in ("head", "base"):
            ref = pr.get(field)
            if not isinstance(ref, dict):
                issues.append("PR #%d manifest %s must be an object" % (number, field))
                continue
            if not isinstance(ref.get("ref"), str) or not ref.get("ref"):
                issues.append("PR #%d manifest %s ref is missing" % (number, field))
            sha = ref.get("sha")
            if not isinstance(sha, str) or not SHA1.fullmatch(sha):
                issues.append("PR #%d manifest %s SHA is malformed" % (number, field))
        dependencies = pr.get("depends_on")
        if not isinstance(dependencies, list):
            issues.append("PR #%d depends_on must be a list" % number)
        elif any(
            not isinstance(dep, int) or isinstance(dep, bool) or dep <= 0
            for dep in dependencies
        ):
            issues.append("PR #%d has a malformed dependency scope" % number)
        elif len(dependencies) != len(set(dependencies)):
            issues.append("PR #%d has duplicate dependencies" % number)
        evidence = pr.get("required_evidence")
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not item.strip() for item in evidence
        ):
            issues.append("PR #%d required_evidence must be a non-empty string list" % number)

    if issues:
        return issues

    expected_main = manifest.get("main")
    if not isinstance(expected_main, dict):
        return ["manifest main must be an object"]
    if not isinstance(expected_main.get("ref"), str) or not expected_main.get("ref"):
        issues.append("manifest main ref is missing")

    raw_workflow_ids = manifest.get("required_workflow_ids")
    if not isinstance(raw_workflow_ids, dict):
        issues.append("manifest required_workflow_ids must be an object")

    # Validate that the explicit PR order covers the scope exactly once and is
    # topological with respect to the declared parent dependencies.
    pr_order = manifest.get("pull_request_order")
    if not isinstance(pr_order, list) or not pr_order:
        issues.append("manifest pull_request_order must be a non-empty list")
        pr_order = []
    if any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in pr_order):
        issues.append("manifest pull_request_order contains an invalid PR number")
    elif len(pr_order) != len(set(pr_order)):
        issues.append("manifest pull_request_order contains duplicate PRs")
    elif set(pr_order) != set(expected_prs):
        issues.append("manifest pull_request_order must cover every PR scope exactly once")

    steps = manifest.get("integration_order")
    if not isinstance(steps, list) or not steps:
        issues.append("manifest integration_order must be a non-empty list")
    elif any(
        not isinstance(step, dict)
        or not isinstance(step.get("order"), int)
        or isinstance(step.get("order"), bool)
        or not isinstance(step.get("action"), str)
        or not step.get("action").strip()
        for step in steps
    ):
        issues.append("manifest integration_order contains a malformed step")
    elif [step["order"] for step in steps] != list(range(1, len(steps) + 1)):
        issues.append("manifest integration_order must be contiguous and in sequence")

    for number, pr in expected_prs.items():
        dependencies = pr["depends_on"]
        for dependency in dependencies:
            if dependency not in expected_prs:
                issues.append("PR #%d is missing dependency PR #%s" % (number, dependency))

    # A cycle makes any declared integration sequence unsafe.
    visiting = set()
    visited = set()

    def visit(number):
        if number in visiting:
            issues.append("dependency cycle includes PR #%d" % number)
            return
        if number in visited:
            return
        visiting.add(number)
        for dependency in expected_prs[number]["depends_on"]:
            if dependency in expected_prs:
                visit(dependency)
        visiting.remove(number)
        visited.add(number)

    for number in expected_prs:
        visit(number)
    if (
        isinstance(pr_order, list)
        and all(isinstance(n, int) and not isinstance(n, bool) for n in pr_order)
        and len(pr_order) == len(set(pr_order))
    ):
        positions = {number: index for index, number in enumerate(pr_order)}
        for number, pr in expected_prs.items():
            for dependency in pr["depends_on"]:
                if (
                    dependency in positions
                    and number in positions
                    and positions[dependency] >= positions[number]
                ):
                    issues.append(
                        "integration order places PR #%d before dependency PR #%d"
                        % (number, dependency)
                    )

    live_main = snapshot.get("main")
    if not isinstance(live_main, dict):
        issues.append("snapshot main must be an object")
        live_main = {}
    if not SHA1.fullmatch(str(expected_main.get("sha", ""))):
        issues.append("manifest main SHA is not a full 40-character Git SHA")
    if not live_main.get("sha"):
        issues.append("current main SHA is missing")
    elif live_main.get("sha") != expected_main.get("sha"):
        issues.append(
            "main SHA changed: expected %s, observed %s"
            % (expected_main.get("sha"), live_main.get("sha"))
        )

    raw_live_prs = snapshot.get("pull_requests")
    live_prs = {}
    if not isinstance(raw_live_prs, dict) or not raw_live_prs:
        issues.append("snapshot pull_requests must be a non-empty object")
    else:
        for raw_number, pr in raw_live_prs.items():
            number = _pr_number(raw_number)
            if number is None or number <= 0:
                issues.append("snapshot contains an invalid PR scope: %r" % raw_number)
                continue
            if number in live_prs:
                issues.append("snapshot has duplicate PR #%d scope" % number)
                continue
            if not isinstance(pr, dict):
                issues.append("snapshot PR #%d must be an object" % number)
                continue
            live_prs[number] = pr

    raw_runs = snapshot.get("workflow_runs")
    runs = []
    if not isinstance(raw_runs, list):
        issues.append("snapshot workflow_runs must be a list")
    else:
        for index, run in enumerate(raw_runs):
            if not isinstance(run, dict):
                issues.append("snapshot workflow_runs[%d] must be an object" % index)
                continue
            if not isinstance(run.get("pull_requests"), list):
                issues.append("workflow run %r pull_requests must be a list" % run.get("id"))
                continue
            runs.append(run)
    commit_details = snapshot.get("commit_details", {})
    if not isinstance(commit_details, dict):
        issues.append("snapshot commit_details must be an object")
        commit_details = {}
    has_main_ancestry = "main_base_ancestry" in snapshot
    main_ancestry = snapshot.get("main_base_ancestry")
    if has_main_ancestry and not isinstance(main_ancestry, dict):
        issues.append("snapshot main_base_ancestry must be an object")
        main_ancestry = {}
    has_workflow_events = "required_workflow_events" in snapshot
    workflow_events = snapshot.get("required_workflow_events")
    if has_workflow_events and not isinstance(workflow_events, dict):
        issues.append("snapshot required_workflow_events must be an object")
        workflow_events = {}

    for number, pr in sorted(expected_prs.items()):
        observed = live_prs.get(number)
        if observed is None:
            issues.append("PR #%d is missing from the current API snapshot" % number)
            continue
        expected_head = pr.get("head", {}).get("sha")
        expected_base = pr.get("base", {}).get("sha")
        if not SHA1.fullmatch(str(expected_head or "")):
            issues.append("PR #%d manifest head SHA is not a full Git SHA" % number)
        if not SHA1.fullmatch(str(expected_base or "")):
            issues.append(
                "PR #%d manifest base SHA is not a full 40-character Git SHA (%d characters)"
                % (number, len(str(expected_base or "")))
            )
        if not SHA1.fullmatch(str(observed.get("head_sha") or "")):
            issues.append("PR #%d observed head SHA is not a full Git SHA" % number)
        if not SHA1.fullmatch(str(observed.get("base_sha") or "")):
            issues.append("PR #%d observed base SHA is not a full Git SHA" % number)
        if observed.get("head_sha") != expected_head:
            issues.append(
                "PR #%d head SHA changed: expected %s, observed %s"
                % (number, expected_head, observed.get("head_sha"))
            )
        if observed.get("base_sha") != expected_base:
            issues.append(
                "PR #%d base SHA changed: expected %s, observed %s"
                % (number, expected_base, observed.get("base_sha"))
            )
        if observed.get("base_ref") != pr.get("base", {}).get("ref"):
            issues.append(
                "PR #%d base ref changed: expected %s, observed %s"
                % (number, pr.get("base", {}).get("ref"), observed.get("base_ref"))
            )
        if (
            observed.get("state") != "open"
            or observed.get("draft") is not True
            or observed.get("merged") is True
        ):
            issues.append("PR #%d is no longer in the observed open-draft state" % number)

        for dependency in pr.get("depends_on", []):
            parent = expected_prs.get(dependency)
            parent_live = live_prs.get(dependency)
            if parent is None or parent_live is None:
                issues.append(
                    "PR #%d is missing dependency PR #%s"
                    % (number, dependency)
                )
                continue
            parent_head = parent_live.get("head_sha")
            if pr.get("base", {}).get("ref") != parent.get("head", {}).get("ref"):
                issues.append(
                    "PR #%d dependency #%s branch does not match its base ref"
                    % (number, dependency)
                )
            if observed.get("base_sha") != parent_head:
                issues.append(
                    "PR #%d base SHA %s does not match dependency PR #%s head %s"
                    % (
                        number,
                        observed.get("base_sha"),
                        dependency,
                        parent_head,
                    )
                )
        if pr.get("base", {}).get("ref") == expected_main.get("ref"):
            if observed.get("base_sha") != live_main.get("sha"):
                issues.append(
                    "PR #%d is based on stale main SHA %s (current %s)"
                    % (number, observed.get("base_sha"), live_main.get("sha"))
                )
            if has_main_ancestry:
                status, detail = classify_main_base_ancestry(
                    main_ancestry.get(str(number))
                )
                if status not in ("current", "stale_ancestor"):
                    issues.append(
                        "PR #%d main-base ancestry status=%s: %s"
                        % (number, status, detail)
                    )

        workflow_ids = (
            raw_workflow_ids.get(str(number), [])
            if isinstance(raw_workflow_ids, dict)
            else []
        )
        if not isinstance(workflow_ids, list) or not workflow_ids:
            issues.append("PR #%d required workflow ID is unverified in the manifest" % number)
            continue
        if any(not isinstance(workflow_id, int) or isinstance(workflow_id, bool)
               for workflow_id in workflow_ids):
            issues.append("PR #%d has an invalid required workflow ID" % number)
            continue
        if len(workflow_ids) != len(set(workflow_ids)):
            issues.append("PR #%d has duplicate required workflow IDs" % number)
            continue
        for workflow_id in workflow_ids:
            evidence = classify_workflow_evidence(
                number, workflow_id, observed, runs, commit_details
            )
            if evidence["status"] != "executed_success":
                issue = _format_workflow_blocker(evidence)
                if evidence["status"] == "stale_head_base":
                    issue += "; green workflow lacks matching current head/base provenance"
                issues.append(issue)
            if has_workflow_events:
                configured = workflow_events.get(str(number))
                events = (
                    configured.get(str(workflow_id))
                    if isinstance(configured, dict)
                    else None
                )
                scoped_runs = [
                    run for run in runs
                    if run.get("workflow_id") == workflow_id
                    and _workflow_ref(run, number) is not None
                ]
                missing_events = missing_required_workflow_events(events, scoped_runs)
                if missing_events:
                    issues.append(
                        "PR #%d workflow #%d missing required event evidence: %s"
                        % (number, workflow_id, ", ".join(missing_events))
                    )

    for number in live_prs.keys() - expected_prs.keys():
        issues.append("unexpected PR #%d is absent from the pinned manifest" % number)
    return issues


def classify_stacked_dependency_observation(observation):
    """Classify one parent/child relation without treating green CI as approval."""
    findings = []

    def add(code, detail):
        findings.append({"code": code, "detail": detail})

    if not isinstance(observation, dict):
        return {"status": "BLOCKED", "findings": [
            {"code": "invalid_observation", "detail": "dependency observation is missing"}
        ]}

    manifest = observation.get("manifest")
    live = observation.get("live_pr")
    dependency = observation.get("dependency")
    if not isinstance(dependency, dict) or not dependency.get("url"):
        add("missing_dependency", "declared parent PR metadata is missing")
        dependency = {}
    if not isinstance(manifest, dict) or not isinstance(live, dict):
        add("missing_pr_metadata", "manifest or live child PR metadata is missing")
        manifest = manifest if isinstance(manifest, dict) else {}
        live = live if isinstance(live, dict) else {}

    child_head = live.get("head_sha")
    child_base = live.get("base_sha")
    parent_head = dependency.get("live_head_sha")
    expected_child_head = manifest.get("head_sha")
    expected_child_base = manifest.get("base_sha")
    expected_parent_head = dependency.get("manifest_head_sha")
    required_shas = (
        child_head,
        child_base,
        parent_head,
        expected_child_head,
        expected_child_base,
        expected_parent_head,
    )
    if any(not isinstance(sha, str) or not SHA1.fullmatch(sha)
           for sha in required_shas):
        add("invalid_sha_provenance", "manifest or live dependency SHA is missing or malformed")
    else:
        if child_head != expected_child_head:
            add("changed_child_head", "live child head differs from its manifest pin")
        if child_base != expected_child_base:
            add("changed_child_base", "live child base differs from its manifest pin")
        if parent_head != expected_parent_head:
            add("changed_dependency_head", "live dependency head differs from its manifest pin")
        if child_base != parent_head:
            add(
                "stale_dependency_base",
                "live child base SHA does not equal the dependency's live head SHA",
            )
        if live.get("base_ref") != dependency.get("branch"):
            add("dependency_ref_mismatch", "live child base ref differs from the dependency branch")

    compare = observation.get("compare")
    if not isinstance(compare, dict):
        add("unverified_ancestry", "GitHub compare ancestry evidence is missing")
    else:
        left = compare.get("left_sha", compare.get("base_sha"))
        right = compare.get("right_sha", compare.get("head_sha"))
        merge_base = compare.get("merge_base_sha")
        if (
            not isinstance(left, str)
            or not SHA1.fullmatch(left)
            or not isinstance(right, str)
            or not SHA1.fullmatch(right)
            or {left, right} != {child_head, parent_head}
            or not isinstance(merge_base, str)
            or not SHA1.fullmatch(merge_base)
            or compare.get("url") not in (
                "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/compare/%s...%s"
                % (left, right),
                "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/compare/%s...%s"
                % (right, left),
            )
        ):
            add("unverified_ancestry", "compare evidence does not bind both live heads")
        elif merge_base != parent_head:
            add(
                "dependency_history_diverged",
                "the dependency head is not the recorded merge base of the child and parent heads",
            )

    workflow = observation.get("workflow")
    if not isinstance(workflow, dict):
        add("missing_workflow", "required workflow definition or run evidence is missing")
        workflow = {}
    required_events = workflow.get("required_automatic_events")
    configured_events = workflow.get("configured_events")
    runs = workflow.get("runs")
    if not isinstance(required_events, list) or not required_events:
        add("missing_required_events", "workflow required-event list is missing")
        required_events = []
    if (
        not isinstance(configured_events, list)
        or not configured_events
        or any(not isinstance(event, str) or not event for event in configured_events)
    ):
        add("missing_configured_events", "workflow configured-event list is missing or malformed")
        configured_events = []
    if not isinstance(runs, list):
        add("missing_workflow_runs", "workflow run records are missing")
        runs = []

    for event in required_events:
        if event not in configured_events:
            add("unconfigured_required_event", "required %s event is not configured" % event)
        event_runs = [run for run in runs
                      if isinstance(run, dict) and run.get("event") == event]
        if not event_runs:
            add("missing_event", "no recorded %s run exists" % event)
            continue
        matching_head = [
            run for run in event_runs
            if run.get("head_sha") == child_head
        ]
        if not matching_head:
            add("stale_workflow_head", "recorded %s runs do not test the live child head" % event)
            continue
        run = max(matching_head, key=lambda item: (
            item.get("attempt") if isinstance(item.get("attempt"), int) else 0,
            item.get("id") if isinstance(item.get("id"), int) else 0,
        ))
        run_id = run.get("id")
        if (
            not isinstance(run_id, int)
            or isinstance(run_id, bool)
            or run_id < 1
            or run.get("url") != (
                "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/%s"
                % run_id
            )
            or not isinstance(run.get("head_sha"), str)
            or not SHA1.fullmatch(run.get("head_sha", ""))
        ):
            add("invalid_workflow_run_identity", "%s run ID, URL, or head SHA is invalid" % event)
        if (
            not isinstance(run.get("attempt"), int)
            or isinstance(run.get("attempt"), bool)
            or run["attempt"] < 1
            or run.get("status") != "completed"
        ):
            add("incomplete_workflow_run", "%s run attempt is missing or incomplete" % event)
            continue
        if run.get("conclusion") != "success":
            add("workflow_not_successful", "%s run did not conclude successfully" % event)
            continue
        jobs = run.get("jobs")
        if not isinstance(jobs, list) or not jobs:
            add("missing_executed_jobs", "%s run has no verified job records" % event)
            continue
        for job in jobs:
            if (
                not isinstance(job, dict)
                or not isinstance(job.get("id"), int)
                or isinstance(job.get("id"), bool)
                or job.get("conclusion") != "success"
                or not isinstance(job.get("steps_completed"), int)
                or isinstance(job.get("steps_completed"), bool)
                or job.get("steps_completed", 0) <= 0
                or job.get("successful_steps") != job.get("steps_completed")
                or not isinstance(job.get("critical_steps"), list)
                or not job.get("critical_steps")
                or job.get("url") != (
                    "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/%s/job/%s"
                    % (run_id, job.get("id"))
                )
            ):
                add("incomplete_job_evidence", "%s run has incomplete or unsuccessful job/step evidence" % event)
                break
        if event == "pull_request" and (
            run.get("base_sha") != live.get("base_sha")
            or run.get("base_provenance") != "reported by Actions API"
        ):
            add(
                "unverified_workflow_base",
                "successful pull_request run does not expose the live PR base SHA",
            )

    return {
        "status": "READY" if not findings else "BLOCKED",
        "findings": findings,
        "workflow_runs_are_semantic_approval": False,
    }


def dependency_readiness_report(fixture, manifest, actual_source_hashes=None):
    """Reconcile a dated dependency observation against immutable manifest pins."""
    if not isinstance(fixture, dict):
        fixture = {}
    source_findings = []
    if not isinstance(manifest, dict):
        source_findings.append({
            "code": "invalid_manifest",
            "detail": "manifest is not a JSON object",
        })
        manifest = {}
    pinned_hashes = fixture.get("source_hashes")
    if not isinstance(pinned_hashes, dict):
        pinned_hashes = {}
        source_findings.append({
            "code": "missing_source_hashes",
            "detail": "dated evidence does not pin its manifest and triage sources",
        })
    expected_source_paths = {
        "development/copilot-integration/manifest.json",
        "development/copilot-integration/blocker-triage-20261104.json",
        "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json",
    }
    if set(pinned_hashes) != expected_source_paths:
        source_findings.append({
            "code": "source_hash_set_mismatch",
            "detail": "dated evidence must pin the manifest, original triage, and prior workflow receipt",
        })
    if actual_source_hashes is not None and not isinstance(actual_source_hashes, dict):
        source_findings.append({
            "code": "invalid_source_hashes",
            "detail": "observed source hashes are not a JSON object",
        })
        actual_source_hashes = {}
    if actual_source_hashes is not None:
        for path, expected in pinned_hashes.items():
            observed = actual_source_hashes.get(path)
            if (
                not isinstance(expected, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected)
                or observed != expected
            ):
                source_findings.append({
                    "code": "source_hash_mismatch",
                    "detail": "%s does not match the SHA-256 pinned by the observation" % path,
                })

    prs = manifest.get("pull_requests") if isinstance(manifest, dict) else None
    expected_prs = {
        pr.get("number"): pr
        for pr in prs
        if (
            isinstance(pr, dict)
            and isinstance(pr.get("number"), int)
            and not isinstance(pr.get("number"), bool)
        )
    } if isinstance(prs, list) else {}
    expected_dependencies = {
        number: pr.get("depends_on", [])
        for number, pr in expected_prs.items()
        if number == 8
        or (
            isinstance(pr.get("depends_on"), list)
            and 8 in pr.get("depends_on", [])
        )
    }
    rows = fixture.get("rows")
    if not isinstance(rows, list):
        rows = []
        source_findings.append({
            "code": "missing_dependency_rows",
            "detail": "dated evidence has no dependency rows",
        })
    by_number = {
        row.get("pr_number"): row
        for row in rows
        if (
            isinstance(row, dict)
            and isinstance(row.get("pr_number"), int)
            and not isinstance(row.get("pr_number"), bool)
        )
    }
    report_rows = []
    for number in sorted(set(expected_dependencies) | set(by_number)):
        row = by_number.get(number)
        expected_pr = expected_prs.get(number)
        if row is None or expected_pr is None:
            report_rows.append({
                "pr_number": number,
                "status": "BLOCKED",
                "findings": [{
                    "code": "missing_dependency_record",
                    "detail": "manifest dependency or dated live observation is missing",
                }],
            })
            continue
        expected_dependency = expected_dependencies[number]
        dependency_number = row.get("dependency_pr")
        findings = []
        if expected_dependency != [dependency_number]:
            findings.append({
                "code": "manifest_dependency_mismatch",
                "detail": "dated evidence does not match the manifest dependency edge",
            })
        manifest_row = row.get("manifest")
        if not isinstance(manifest_row, dict) or any((
            manifest_row.get("head_sha") != (
                expected_pr.get("head", {}).get("sha")
                if isinstance(expected_pr.get("head"), dict) else None
            ),
            manifest_row.get("base_ref") != (
                expected_pr.get("base", {}).get("ref")
                if isinstance(expected_pr.get("base"), dict) else None
            ),
            manifest_row.get("base_sha") != (
                expected_pr.get("base", {}).get("sha")
                if isinstance(expected_pr.get("base"), dict) else None
            ),
        )):
            findings.append({
                "code": "manifest_pin_mismatch",
                "detail": "dated evidence does not match the current manifest's immutable PR pins",
            })
        classified = classify_stacked_dependency_observation(row)
        findings.extend(classified["findings"])
        workflow = row.get("workflow")
        required_workflow_ids = manifest.get("required_workflow_ids", {})
        pinned_ids = (
            required_workflow_ids.get(str(number))
            if isinstance(required_workflow_ids, dict)
            else None
        )
        if (
            not isinstance(workflow, dict)
            or not isinstance(pinned_ids, list)
            or workflow.get("id") not in pinned_ids
        ):
            findings.append({
                "code": "workflow_id_mismatch",
                "detail": "observed workflow ID is not pinned for this PR in the manifest",
            })
        source_pins = workflow.get("source_pins") if isinstance(workflow, dict) else None
        if (
            not isinstance(source_pins, list)
            or any(
                not isinstance(pin, str)
                or not re.fullmatch(r"[^@\s]+@(?:[0-9a-f]{40})", pin)
                for pin in source_pins
            )
        ):
            findings.append({
                "code": "invalid_source_pin",
                "detail": "upstream source pin list is malformed",
            })
        if (
            not isinstance(workflow, dict)
            or not isinstance(workflow.get("blob_sha"), str)
            or not SHA1.fullmatch(workflow.get("blob_sha", ""))
            or workflow.get("verified_at_head_sha")
            != (row.get("live_pr", {}).get("head_sha")
                if isinstance(row.get("live_pr"), dict) else None)
        ):
            findings.append({
                "code": "workflow_source_unverified",
                "detail": "workflow source blob is not bound to the observed current PR head",
            })
        report_rows.append({
            "blocker_id": row.get("blocker_id"),
            "pr_number": number,
            "dependency_pr": dependency_number,
            "status": "READY" if not findings and classified["status"] == "READY" else "BLOCKED",
            "findings": findings,
            "closure_action": row.get("closure_action"),
            "live_pr_url": row.get("live_pr", {}).get("url")
            if isinstance(row.get("live_pr"), dict) else None,
            "dependency_url": row.get("dependency", {}).get("url")
            if isinstance(row.get("dependency"), dict) else None,
        })
    if set(by_number) != set(expected_dependencies) or len(by_number) != len(rows):
        source_findings.append({
            "code": "dependency_row_set_mismatch",
            "detail": "dated evidence must contain each and only each manifest dependency row",
        })

    policy = fixture.get("policy")
    approval_count = policy.get("independent_approvals") if isinstance(policy, dict) else None
    policy_matches = (
        isinstance(policy, dict)
        and policy.get("phase1_gate") == "FAIL_INCOMPLETE"
        and isinstance(approval_count, int)
        and not isinstance(approval_count, bool)
        and approval_count == 0
        and policy.get("historical_external_approvals_p0") == "0/338"
        and policy.get("historical_external_approvals_total") == "0/14834"
        and policy.get("source_pins_changed") is False
        and policy.get("semantic_approval_from_ci") is False
    )
    if not policy_matches:
        source_findings.append({
            "code": "policy_mismatch",
            "detail": "Phase 1 gate, approval total, source pins, or CI semantics are not preserved",
        })
    blocked = bool(source_findings) or any(row["status"] != "READY" for row in report_rows)
    return {
        "schema": "xgba.phase1.dependency_readiness_report.v1",
        "status": "BLOCKED" if blocked else "READY",
        "source_findings": source_findings,
        "row_count": len(report_rows),
        "blocked_count": sum(row["status"] == "BLOCKED" for row in report_rows),
        "phase1_gate": policy.get("phase1_gate") if isinstance(policy, dict) else None,
        "independent_approvals": policy.get("independent_approvals")
        if isinstance(policy, dict) else None,
        "first_concrete_blocker": fixture.get("first_concrete_blocker"),
        "safe_integration_order": fixture.get("safe_integration_order"),
        "dependency_advance": fixture.get("dependency_advance"),
        "rows": report_rows,
    }


def _triage_details(issue):
    if "is based on stale main SHA" in issue:
        return (
            "stale_main_base",
            "Refresh or explicitly reconcile this PR against the current main SHA, "
            "review the resulting diff, then collect evidence for the refreshed head/base.",
        )
    if "base SHA " in issue and "does not match dependency PR" in issue:
        return (
            "stale_dependency_base",
            "Reconcile the child PR base to its declared parent's exact current head; "
            "compare the resulting tree before refreshing downstream children.",
        )
    if "dependency branch does not match its base ref" in issue:
        return (
            "dependency_ref_mismatch",
            "Reconcile the declared dependency branch and PR base ref, then verify the "
            "parent-child relationship from live PR metadata.",
        )
    if "required workflow ID is unverified" in issue:
        return (
            "unverified_workflow_id",
            "Identify and pin the required workflow ID from the workflow definition and "
            "observed run; then query its complete exact-scope run/job evidence.",
        )
    if "status=stale_head_base" in issue:
        return (
            "stale_workflow_evidence",
            "Obtain a new authorized run for the current PR head/base and verify the "
            "run attempt and every job; stale green evidence is not reusable.",
        )
    if "required evidence absent:" in issue:
        return (
            "incomplete_workflow_evidence",
            "Query or restore the complete run, attempt, and job records for the required "
            "workflow; if execution is authorization-gated, obtain maintainer approval "
            "without treating the gated run as success.",
        )
    if "base SHA changed" in issue or "base ref changed" in issue:
        return (
            "changed_pr_base",
            "Reconcile the manifest with the current PR base ref and SHA after verifying "
            "the intended dependency; do not substitute a merge-base or target-ref tip.",
        )
    if "head SHA changed" in issue:
        return (
            "changed_pr_head",
            "Reconcile the manifest with the current PR head, then require workflow "
            "evidence executed on that exact head.",
        )
    return (
        "other_readiness_blocker",
        "Resolve the specific manifest or API-snapshot discrepancy in the issue, then "
        "rerun the fail-closed checker.",
    )


def blocker_triage_report(
    manifest, snapshot, issues, manifest_sha256=None, live_observations=None
):
    """Create one actionable, source-linked record for every readiness issue."""
    if not isinstance(manifest, dict):
        manifest = {}
    repository = manifest.get("repository", "unknown/unknown")
    if not isinstance(repository, str):
        repository = "unknown/unknown"
    owner, _, repo = repository.partition("/")
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        policy = {}
    raw_prs = manifest.get("pull_requests")
    if not isinstance(raw_prs, list):
        raw_prs = []
    pull_requests = {
        pr.get("number"): pr
        for pr in raw_prs
        if isinstance(pr, dict) and isinstance(pr.get("number"), int)
    }
    blockers = []
    counts = Counter()
    for index, issue in enumerate(issues, 1):
        match = re.search(r"PR #(\d+)", issue)
        number = int(match.group(1)) if match else None
        pr = pull_requests.get(number, {})
        category, action = _triage_details(issue)
        counts[category] += 1
        run_match = re.search(r"\brun (\d+)\b", issue)
        run_id = int(run_match.group(1)) if run_match else None
        source_refs = [
            "development/copilot-integration/manifest.json",
        ]
        if number is not None:
            source_refs.append(
                "https://github.com/%s/%s/pull/%d" % (owner, repo, number)
            )
        if run_id is not None:
            source_refs.append(
                "https://github.com/%s/%s/actions/runs/%d"
                % (owner, repo, run_id)
            )
        blockers.append({
            "id": "B%03d" % index,
            "pr_number": number,
            "category": category,
            "issue": issue,
            "closure_action": action,
            "manifest_head_sha": (
                pr.get("head", {}).get("sha")
                if isinstance(pr.get("head"), dict)
                else None
            ),
            "manifest_base_ref": (
                pr.get("base", {}).get("ref")
                if isinstance(pr.get("base"), dict)
                else None
            ),
            "manifest_base_sha": (
                pr.get("base", {}).get("sha")
                if isinstance(pr.get("base"), dict)
                else None
            ),
            "observed_run_id": run_id,
            "source_refs": source_refs,
        })
    return {
        "schema_version": 1,
        "repository": repository,
        "status": "BLOCKED" if blockers else "READY",
        "basis": "recorded_manifest_snapshot_only",
        "live_state_note": (
            "The blocker list is reproduced from the pinned offline manifest. "
            "Supplemental live observations are separate and do not clear blockers."
        ),
        "manifest_sha256": manifest_sha256,
        "blocker_count": len(blockers),
        "category_counts": dict(sorted(counts.items())),
        "policy": {
            "phase": policy.get("phase"),
            "phase1_gate": policy.get("phase1_gate"),
            "independent_approvals": policy.get("independent_approvals"),
            "ci_is_semantic_approval": policy.get("ci_is_semantic_approval"),
            "semantic_review": "not evaluated by this integration checker",
        },
        "live_observations": live_observations,
        "blockers": blockers,
    }


def workflow_evidence_report(manifest, snapshot):
    """Return per-workflow classifications suitable for CLI reporting."""
    if not isinstance(manifest, dict) or not isinstance(snapshot, dict):
        return []
    prs = manifest.get("pull_requests")
    live_prs = snapshot.get("pull_requests")
    runs = snapshot.get("workflow_runs")
    commit_details = snapshot.get("commit_details", {})
    workflow_ids = manifest.get("required_workflow_ids")
    if (
        not isinstance(prs, list)
        or not isinstance(live_prs, dict)
        or not isinstance(runs, list)
        or not isinstance(commit_details, dict)
        or not isinstance(workflow_ids, dict)
    ):
        return []
    report = []
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        observed = live_prs.get(str(number), live_prs.get(number))
        if not isinstance(observed, dict):
            continue
        ids = workflow_ids.get(str(number))
        if not isinstance(ids, list):
            continue
        for workflow_id in ids:
            if not isinstance(workflow_id, int) or isinstance(workflow_id, bool):
                continue
            report.append(
                classify_workflow_evidence(
                    number, workflow_id, observed, runs, commit_details
                )
            )
    return report


def fetch_public_snapshot(manifest):
    """Fetch current PR metadata and branch workflow runs without credentials."""
    owner, repo = manifest["repository"].split("/", 1)

    def get_json(path, query=None):
        url = API + path
        if query:
            url += "?" + urlencode(query)
        request = Request(url, headers={"Accept": "application/vnd.github+json",
                                       "User-Agent": "xgba-integration-readiness"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        all_prs = get_json("/repos/%s/%s/pulls" % (owner, repo),
                           {"state": "all", "per_page": 100})
        by_number = {int(pr["number"]): pr for pr in all_prs}
        wanted = {int(pr["number"]) for pr in manifest.get("pull_requests", [])}
        snapshot_prs = {}
        runs = []
        branch_refs = set()
        for number in sorted(wanted):
            pr = by_number.get(number)
            if pr is None:
                continue
            snapshot_prs[str(number)] = {
                "head_sha": pr["head"]["sha"],
                "base_sha": pr["base"]["sha"],
                "base_ref": pr["base"]["ref"],
                "state": pr["state"],
                "draft": pr.get("draft"),
                "merged": pr.get("merged"),
            }
            branch_refs.add(pr["head"]["ref"])
        main_ref = manifest["main"]["ref"]
        main_sha = get_json("/repos/%s/%s/commits/%s" % (owner, repo, quote(main_ref, safe="")))
        main_sha_value = main_sha["sha"]
        main_base_ancestry = {}
        comparisons = {}
        for number, pr in snapshot_prs.items():
            pinned = next(
                item for item in manifest["pull_requests"]
                if item["number"] == int(number)
            )
            if pinned.get("base", {}).get("ref") != main_ref:
                continue
            base_sha = pr["base_sha"]
            if base_sha not in comparisons:
                comparison = None
                try:
                    result = get_json(
                        "/repos/%s/%s/compare/%s...%s"
                        % (
                            owner,
                            repo,
                            quote(base_sha, safe=""),
                            quote(main_sha_value, safe=""),
                        )
                    )
                    comparison = {
                        "base_sha": (result.get("base_commit") or {}).get("sha"),
                        "head_sha": (result.get("head_commit") or {}).get("sha"),
                        "merge_base_sha": (
                            result.get("merge_base_commit") or {}
                        ).get("sha"),
                        "status": result.get("status"),
                        "ahead_by": result.get("ahead_by"),
                        "behind_by": result.get("behind_by"),
                    }
                except (HTTPError, URLError, TimeoutError, KeyError, ValueError):
                    pass
                comparisons[base_sha] = comparison
            comparison = comparisons[base_sha]
            main_base_ancestry[number] = {
                "expected_base_sha": pinned["base"]["sha"],
                "observed_base_sha": pr["base_sha"],
                "current_main_sha": main_sha_value,
                "compare": comparison,
            }
        required_ids = manifest.get("required_workflow_ids", {})
        current_heads = {
            int(pr["number"]): pr["head"]["sha"]
            for pr in manifest.get("pull_requests", [])
            if isinstance(pr, dict)
            and isinstance(pr.get("number"), int)
            and isinstance(pr.get("head"), dict)
        }
        for branch in sorted(branch_refs):
            response = get_json(
                "/repos/%s/%s/actions/runs" % (owner, repo),
                {"branch": branch, "per_page": 100},
            )
            for run in response.get("workflow_runs", []):
                refs = []
                for ref in run.get("pull_requests", []):
                    refs.append({
                        "number": ref.get("number"),
                        "head_sha": (ref.get("head") or {}).get("sha"),
                        "base_sha": (ref.get("base") or {}).get("sha"),
                        "merge_sha": (ref.get("merge_commit_sha")
                                      or (ref.get("merge_commit") or {}).get("sha")),
                    })
                runs.append({
                    "id": run.get("id"),
                    "run_number": run.get("run_number"),
                    "run_attempt": run.get("run_attempt"),
                    "workflow_id": run.get("workflow_id"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                    "html_url": run.get("html_url"),
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "pull_requests": refs,
                })
        for run in runs:
            if not isinstance(run.get("id"), int):
                continue
            required_prs = {
                _pr_number(ref.get("number"))
                for ref in run.get("pull_requests", [])
                if isinstance(ref, dict)
            }
            if not any(
                number in required_prs
                and run.get("workflow_id") in required_ids.get(str(number), [])
                for number in wanted
            ):
                continue
            attempt = run.get("run_attempt")
            attempt_path = (
                "/repos/%s/%s/actions/runs/%s/attempts/%s/jobs"
                % (owner, repo, run["id"], attempt)
                if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt > 0
                else "/repos/%s/%s/actions/runs/%s/jobs" % (owner, repo, run["id"])
            )
            job_rows = []
            total_count = None
            complete = True
            try:
                page = 1
                while True:
                    response = get_json(
                        attempt_path,
                        {"per_page": 100, "page": page},
                    )
                    if not isinstance(response, dict) or not isinstance(
                        response.get("jobs"), list
                    ):
                        raise ValueError("workflow job response is malformed")
                    if total_count is None:
                        total_count = response.get("total_count")
                        if not isinstance(total_count, int) or isinstance(total_count, bool):
                            raise ValueError("workflow job count is malformed")
                    for job in response["jobs"]:
                        if not isinstance(job, dict):
                            continue
                        job_rows.append({
                            "id": job.get("id"),
                            "name": job.get("name"),
                            "status": job.get("status"),
                            "conclusion": job.get("conclusion"),
                            "html_url": job.get("html_url"),
                            "run_attempt": job.get("run_attempt"),
                        })
                    if len(job_rows) >= total_count or not response["jobs"]:
                        break
                    page += 1
                    if page > 20:
                        complete = False
                        break
                if len(job_rows) != total_count:
                    complete = False
                run["jobs"] = {
                    "available": True,
                    "total_count": total_count,
                    "jobs": job_rows,
                    "complete": complete,
                }
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError):
                run["jobs"] = {
                    "available": False,
                    "total_count": None,
                    "jobs": [],
                    "complete": False,
                }
        commit_details = {}
        for run in runs:
            if run.get("event") not in ("pull_request", "pull_request_target"):
                continue
            run_sha = run.get("head_sha")
            if not isinstance(run_sha, str) or not SHA1.fullmatch(run_sha):
                continue
            if not any(
                ref.get("head_sha") != run_sha
                and ref.get("head_sha") == current_heads.get(ref.get("number"))
                and run.get("workflow_id") in required_ids.get(str(ref.get("number")), [])
                for ref in run.get("pull_requests", [])
            ):
                continue
            try:
                details = get_json(
                    "/repos/%s/%s/commits/%s" % (owner, repo, quote(run_sha, safe=""))
                )
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError):
                continue
            parents = details.get("parents")
            if (
                details.get("sha") == run_sha
                and isinstance(parents, list)
                and all(isinstance(parent, dict) for parent in parents)
            ):
                commit_details[run_sha] = {
                    "sha": run_sha,
                    "parents": [parent.get("sha") for parent in parents],
                }
        return {
            "main": {"ref": main_ref, "sha": main_sha_value},
            "pull_requests": snapshot_prs,
            "workflow_runs": runs,
            "commit_details": commit_details,
            "main_base_ancestry": main_base_ancestry,
        }
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        raise RuntimeError(
            "public GitHub read failed; no PAT is requested or used: %s" % exc
        ) from exc


def recorded_snapshot(manifest):
    """Build an offline snapshot from only the observations preserved here."""
    prs = {}
    runs = []
    for pr in manifest.get("pull_requests", []):
        number = int(pr["number"])
        prs[str(number)] = {
            "head_sha": pr["head"]["sha"],
            "base_sha": pr["base"]["sha"],
            "base_ref": pr["base"]["ref"],
            "state": "open",
            "draft": True,
            "merged": False,
        }
        for observed in pr.get("observed_runs", []):
            if observed.get("conclusion") != "success":
                continue
            runs.append({
                "id": observed.get("id"),
                "run_number": observed.get("run_number"),
                "run_attempt": observed.get("run_attempt"),
                "workflow_id": observed.get("workflow_id"),
                "event": observed.get("event"),
                "status": "completed",
                "conclusion": "success",
                "head_sha": observed.get("head_sha"),
                "html_url": observed.get("html_url"),
                "created_at": observed.get("created_at"),
                "updated_at": observed.get("updated_at"),
                "jobs": observed.get("jobs", {
                    "available": False,
                    "total_count": None,
                    "jobs": [],
                    "complete": False,
                }),
                "pull_requests": [number],
            })
    return {
        "main": dict(manifest.get("main", {})),
        "pull_requests": prs,
        "workflow_runs": runs,
        "commit_details": {},
    }


def closure_index_report(index, manifest, triage, package_documents, actual_hashes):
    """Validate a deduplicated index against immutable blocker/evidence sources."""
    findings = []
    if not isinstance(index, dict):
        index = {}
        findings.append("closure index must be a JSON object")
    if index.get("schema") != "copilot-integration-closure-index-v1":
        findings.append("closure index schema is missing or unsupported")
    if index.get("repository") != "xbaconator9000x/XGBA-ROM-Expansion":
        findings.append("closure index repository identity does not match")
    if index.get("base_provenance_limit") != (
        "Actions run metadata does not expose run-time PR base SHA; "
        "pr_metadata_base_sha is a separate current PR metadata observation, not run provenance."
    ):
        findings.append("closure index must distinguish current PR base from run-time base provenance")
    if not isinstance(manifest, dict) or not isinstance(triage, dict):
        findings.append("manifest and original blocker triage must be JSON objects")
        manifest = manifest if isinstance(manifest, dict) else {}
        triage = triage if isinstance(triage, dict) else {}

    source_hashes = index.get("source_hashes")
    if not isinstance(source_hashes, dict) or not isinstance(actual_hashes, dict):
        findings.append("closure index source hashes or observed hashes are missing")
        source_hashes = source_hashes if isinstance(source_hashes, dict) else {}
        actual_hashes = actual_hashes if isinstance(actual_hashes, dict) else {}
    if set(source_hashes) != set(actual_hashes):
        findings.append("closure index source hash set does not match checked source files")
    for path, expected_hash in source_hashes.items():
        if (
            not isinstance(expected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or actual_hashes.get(path) != expected_hash
        ):
            findings.append("source evidence hash mismatch: %s" % path)

    original_rows = triage.get("blockers")
    index_rows = index.get("rows")
    if not isinstance(original_rows, list):
        original_rows = []
        findings.append("original blocker triage has no blocker list")
    if not isinstance(index_rows, list):
        index_rows = []
        findings.append("closure index has no blocker rows")
    original_by_id = {
        row.get("id"): row
        for row in original_rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    indexed_ids = [
        row[0] for row in index_rows
        if isinstance(row, list) and row and isinstance(row[0], str)
    ]
    if len(indexed_ids) != len(set(indexed_ids)):
        findings.append("closure index contains duplicate blocker IDs")
    if set(indexed_ids) != set(original_by_id) or len(indexed_ids) != len(original_by_id):
        findings.append("closure index blocker ID set does not exactly match original triage")

    manifest_rows = {
        row.get("number"): row
        for row in manifest.get("pull_requests", [])
        if isinstance(row, dict) and isinstance(row.get("number"), int)
    }
    package_sources = {
        "stale_main_base":
            "tests/fixtures/copilot-integration-readiness/stale_main_base_evidence_20261105.json",
        "stale_dependency_base":
            "development/copilot-integration/dependency-base-reconciliation-20261105.json",
        "stale_workflow_evidence":
            "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json",
        "unverified_workflow_id":
            "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json",
    }
    current_by_number = {}
    current_rows = index.get("current_pr_observations")
    if not isinstance(current_rows, list):
        current_rows = []
        findings.append("current public PR metadata observations are missing")
    for item in current_rows:
        if not isinstance(item, list) or len(item) != 4:
            findings.append("current PR observation has invalid shape")
            continue
        number, head_sha, base_ref, base_sha = item
        if not isinstance(number, int) or isinstance(number, bool):
            findings.append("current PR observation has invalid PR number")
            continue
        if number in current_by_number:
            findings.append("current PR observation duplicates PR #%s" % number)
            continue
        current_by_number[number] = item
        if (
            not isinstance(head_sha, str) or not SHA1.fullmatch(head_sha)
            or not isinstance(base_sha, str) or not SHA1.fullmatch(base_sha)
            or not isinstance(base_ref, str) or not base_ref
        ):
            findings.append("current PR #%s has malformed head/base metadata" % number)
    expected_numbers = {
        row.get("pr_number") for row in original_rows if isinstance(row, dict)
    }
    if not expected_numbers.issubset(current_by_number):
        findings.append("current PR observations do not cover the original blocker PR set")

    expanded_rows = []
    for indexed in index_rows:
        if not isinstance(indexed, list) or len(indexed) != 3:
            findings.append("closure index row has invalid shape")
            continue
        blocker_id, number, category = indexed
        if not isinstance(blocker_id, str):
            findings.append("closure index row has invalid blocker ID")
            continue
        original = original_by_id.get(blocker_id)
        if original is None:
            findings.append("closure index references unknown blocker %s" % blocker_id)
            continue
        if number != original.get("pr_number") or category != original.get("category"):
            findings.append("%s PR/category differs from original triage" % blocker_id)
        if index.get("status") != "BLOCKED":
            findings.append("%s must remain BLOCKED" % blocker_id)
        pr_manifest = manifest_rows.get(number)
        if not isinstance(pr_manifest, dict):
            findings.append("%s has no manifest PR row" % blocker_id)
            continue
        manifest_head = (pr_manifest.get("head") or {}).get("sha")
        manifest_base = (pr_manifest.get("base") or {}).get("sha")
        manifest_base_ref = (pr_manifest.get("base") or {}).get("ref")
        if (
            manifest_head != original.get("manifest_head_sha")
            or manifest_base != original.get("manifest_base_sha")
            or manifest_base_ref != original.get("manifest_base_ref")
        ):
            findings.append("%s manifest identity differs from original triage" % blocker_id)
        if not isinstance(manifest_head, str) or not SHA1.fullmatch(manifest_head):
            findings.append("%s manifest head SHA is malformed" % blocker_id)
        if not isinstance(manifest_base, str) or not SHA1.fullmatch(manifest_base):
            findings.append("%s manifest base SHA is malformed" % blocker_id)

        source_path = package_sources.get(category)
        package_record = None
        if source_path is None:
            findings.append("%s has no recognized evidence package" % blocker_id)
        else:
            package = package_documents.get(source_path)
            package_rows = package.get("rows", []) if isinstance(package, dict) else []
            if category == "unverified_workflow_id":
                package_record = next(
                    (row for row in package_rows
                     if isinstance(row, dict) and row.get("pr") == number),
                    None,
                )
            else:
                package_record = next(
                    (row for row in package_rows
                     if isinstance(row, dict) and row.get("blocker_id") == blocker_id),
                    None,
                )
            if package_record is None:
                findings.append("%s evidence package record is absent" % blocker_id)
        current = current_by_number.get(number)
        if current:
            current_head, current_base_ref, current_base = current[1:]
            expanded_rows.append({
                "id": blocker_id,
                "pr_number": number,
                "category": category,
                "status": "BLOCKED",
                "manifest_identity": {
                    "head_sha": manifest_head,
                    "base_ref": manifest_base_ref,
                    "base_sha": manifest_base,
                },
                "current_observation": {
                    "head_sha": current_head,
                    "base_ref": current_base_ref,
                    "base_sha": current_base,
                    "head_changed_since_manifest": current_head != manifest_head,
                    "base_changed_since_manifest": current_base != manifest_base,
                    "observed_at": index.get("observed_at"),
                    "source_url": (
                        "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/%s"
                        % number
                    ),
                },
                "evidence_package": source_path,
                "evidence_record_present": package_record is not None,
                "evidence_record": package_record,
                "closure_action": original.get("closure_action"),
            })

    fresh_runs = index.get("fresh_workflow_observations")
    if not isinstance(fresh_runs, list):
        fresh_runs = []
        findings.append("fresh exact-head workflow observations are missing")
    fresh_run_by_pr = {}
    for run in fresh_runs:
        if not isinstance(run, dict):
            findings.append("fresh workflow observation has invalid shape")
            continue
        number = run.get("pr_number")
        if not isinstance(number, int) or isinstance(number, bool):
            findings.append("fresh workflow observation has invalid PR number")
            continue
        current = current_by_number.get(number)
        run_id = run.get("run_id")
        if number in fresh_run_by_pr:
            findings.append("fresh workflow observation duplicates PR #%s" % number)
        if (
            current is None
            or not isinstance(run_id, int) or isinstance(run_id, bool)
            or run.get("attempt") != 1
            or run.get("event") != "pull_request"
            or run.get("status") != "completed"
            or run.get("conclusion") != "action_required"
            or run.get("head_sha") != current[1]
            or run.get("pr_metadata_base_sha") != current[3]
            or run.get("reported_base_sha") is not None
            or run.get("base_provenance") != "unavailable_actions_api"
            or run.get("job_count") != 0
            or run.get("url")
            != "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/%s" % run_id
        ):
            findings.append(
                "fresh PR #%s run is not an exact-head zero-job gate or misstates unavailable run-time base provenance"
                % number
            )
        fresh_run_by_pr[number] = {
            **run,
            "classification": "action_required_zero_job",
            "head_matches_current_pr": current is not None and run.get("head_sha") == current[1],
            "run_time_base_provenance": "unavailable",
        }
    if not {35, 36, 37}.issubset(fresh_run_by_pr):
        findings.append("current authorization-gated runs for PRs #35, #36, and #37 are not all recorded")
    expected_policy = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "p0_approvals": 0,
        "total_historical_approvals": 0,
        "source_pins_changed": False,
        "semantic_approval_from_ci": False,
    }
    if index.get("policy") != expected_policy:
        findings.append("closure index policy does not preserve Phase 1 gate and approval totals")
    for row in expanded_rows:
        row["fresh_workflow_observation"] = fresh_run_by_pr.get(row["pr_number"])
    return {
        "status": "BLOCKED",
        "blocker_count": len(expanded_rows),
        "unique_blocker_ids": len(set(indexed_ids)),
        "category_counts": dict(sorted(Counter(
            row["category"] for row in expanded_rows
        ).items())),
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "base_provenance_limit": index.get("base_provenance_limit"),
        "findings": sorted(set(findings)),
        "rows": expanded_rows,
    }


def blocker_action_closure_report(fixture, manifest, triage, workflow_receipts, actual_hashes):
    """Validate current action dispositions for the selected workflow-ID blockers."""
    findings = []
    if not isinstance(fixture, dict):
        fixture = {}
        findings.append("action-closure evidence must be a JSON object")
    if fixture.get("schema") != "copilot-integration-action-closure-v1":
        findings.append("action-closure evidence schema is missing or unsupported")
    if fixture.get("repository") != "xbaconator9000x/XGBA-ROM-Expansion":
        findings.append("action-closure repository identity does not match")
    if not isinstance(manifest, dict) or not isinstance(triage, dict):
        findings.append("manifest and immutable blocker triage are required")
        manifest = manifest if isinstance(manifest, dict) else {}
        triage = triage if isinstance(triage, dict) else {}
    source_hashes = fixture.get("source_hashes")
    if not isinstance(source_hashes, dict) or not isinstance(actual_hashes, dict):
        findings.append("action-closure source hashes are missing")
        source_hashes = source_hashes if isinstance(source_hashes, dict) else {}
        actual_hashes = actual_hashes if isinstance(actual_hashes, dict) else {}
    if set(source_hashes) != set(actual_hashes):
        findings.append("action-closure source hash set does not match checked sources")
    for path, digest in source_hashes.items():
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or actual_hashes.get(path) != digest
        ):
            findings.append("action-closure source hash mismatch: %s" % path)

    original_rows = {
        row.get("id"): row
        for row in triage.get("blockers", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    manifest_rows = {
        row.get("number"): row
        for row in manifest.get("pull_requests", [])
        if isinstance(row, dict) and isinstance(row.get("number"), int)
    }
    receipt_rows = {
        row.get("pr"): row
        for row in workflow_receipts.get("rows", [])
        if isinstance(row, dict) and isinstance(row.get("pr"), int)
    } if isinstance(workflow_receipts, dict) else {}
    rows = fixture.get("rows")
    if not isinstance(rows, list) or len(rows) != 2:
        findings.append("action-closure scope must contain exactly B043 and B044")
        rows = rows if isinstance(rows, list) else []
    if [row.get("blocker_id") for row in rows if isinstance(row, dict)] != [
        "B043", "B044"
    ]:
        findings.append("action-closure rows must be ordered B043, B044 exactly once")

    report_rows = []
    for row in rows:
        if not isinstance(row, dict):
            findings.append("action-closure row is malformed")
            continue
        blocker_id = row.get("blocker_id")
        original = original_rows.get(blocker_id)
        if original is None:
            findings.append("%s is absent from immutable blocker triage" % blocker_id)
            continue
        number = original.get("pr_number")
        if (
            row.get("pr_number") != number
            or original.get("category") != "unverified_workflow_id"
            or row.get("before", {}).get("category") != original.get("category")
            or row.get("before", {}).get("status") != "BLOCKED"
            or row.get("before", {}).get("manifest_head_sha")
            != original.get("manifest_head_sha")
            or row.get("before", {}).get("manifest_base_sha")
            != original.get("manifest_base_sha")
            or row.get("before", {}).get("manifest_base_ref")
            != original.get("manifest_base_ref")
            or row.get("before", {}).get("observed_run_id")
            != original.get("observed_run_id")
        ):
            findings.append("%s before-disposition differs from its immutable triage row" % blocker_id)
        pr_manifest = manifest_rows.get(number)
        if not isinstance(pr_manifest, dict):
            findings.append("%s has no pinned manifest row" % blocker_id)
            continue
        workflow_ids = manifest.get("required_workflow_ids", {}).get(str(number))
        workflow_id = row.get("current_run", {}).get("workflow_id")
        if (
            not isinstance(workflow_ids, list)
            or len(workflow_ids) != 1
            or workflow_ids[0] != workflow_id
        ):
            findings.append("%s workflow ID is not verified by the pinned manifest" % blocker_id)
        receipt = receipt_rows.get(number)
        prior = row.get("prior_evidence")
        if (
            not isinstance(receipt, dict)
            or not isinstance(prior, dict)
            or receipt.get("workflow_id") != workflow_id
            or receipt.get("run", {}).get("id") != prior.get("run_id")
            or receipt.get("run", {}).get("head") != prior.get("head_sha")
        ):
            findings.append("%s historical evidence does not match the pinned reconciliation" % blocker_id)

        current_pr = row.get("current_pr")
        current_run = row.get("current_run")
        after = row.get("after")
        if not isinstance(current_pr, dict) or not isinstance(current_run, dict):
            findings.append("%s current PR/run evidence is missing" % blocker_id)
            continue
        manifest_head = (pr_manifest.get("head") or {}).get("sha")
        run_id = current_run.get("run_id")
        expected_run_url = (
            "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/%s"
            % run_id
        )
        current_valid = (
            current_pr.get("url")
            == "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/%s" % number
            and isinstance(current_pr.get("head_sha"), str)
            and SHA1.fullmatch(current_pr["head_sha"])
            and isinstance(current_pr.get("base_sha"), str)
            and SHA1.fullmatch(current_pr["base_sha"])
            and current_run.get("workflow_id") == workflow_id
            and isinstance(run_id, int) and not isinstance(run_id, bool)
            and isinstance(current_run.get("attempt"), int)
            and not isinstance(current_run.get("attempt"), bool)
            and current_run.get("attempt") > 0
            and current_run.get("event") == "pull_request"
            and current_run.get("status") == "completed"
            and current_run.get("conclusion") == "action_required"
            and current_run.get("head_sha") == current_pr.get("head_sha")
            and current_run.get("reported_run_base_sha") is None
            and current_run.get("run_time_base_provenance")
            == "unavailable_actions_api"
            and current_run.get("job_count") == 0
            and current_run.get("job_ids") == []
            and current_run.get("url") == expected_run_url
            and current_pr.get("base_ref") == (pr_manifest.get("base") or {}).get("ref")
            and current_pr.get("base_sha") == (pr_manifest.get("base") or {}).get("sha")
            and current_pr.get("head_sha") != manifest_head
        )
        if not current_valid:
            findings.append("%s current run is not an exact-head action_required zero-job observation" % blocker_id)
        expected_after = {
            "category": "stale_manifest_head_and_action_required_zero_job",
            "status": "BLOCKED",
            "workflow_id": workflow_id,
            "head_matches_current_pr": current_run.get("head_sha")
            == current_pr.get("head_sha"),
            "head_matches_immutable_manifest": current_run.get("head_sha")
            == manifest_head,
            "run_time_base_provenance": "unavailable",
            "required_human_action": (
                "A maintainer with write access must authorize the run in GitHub Actions, "
                "then inspect the executed jobs and steps. Do not retry or treat "
                "authorization as success."
            ),
            "action_url": expected_run_url,
            "resolved": False,
        }
        if after != expected_after:
            findings.append("%s after-disposition clears or misstates an unresolved action" % blocker_id)
        before_fingerprint = hashlib.sha256(json.dumps(
            original, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        evidence_fingerprint = hashlib.sha256(json.dumps(
            {"current_pr": current_pr, "current_run": current_run},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        after_fingerprint = hashlib.sha256(json.dumps(
            after, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        report_rows.append({
            "blocker_id": blocker_id,
            "pr_number": number,
            "source_refs": original.get("source_refs", []),
            "before": row.get("before"),
            "prior_evidence": prior,
            "after": after,
            "before_fingerprint_sha256": before_fingerprint,
            "current_evidence_fingerprint_sha256": evidence_fingerprint,
            "after_fingerprint_sha256": after_fingerprint,
            "current_run_url": current_run.get("url"),
            "current_pr_url": current_pr.get("url"),
            "status": "BLOCKED",
        })

    gate = fixture.get("validation_gate")
    if not isinstance(gate, dict) or any((
        gate.get("pr37_head_sha") != "e7a7bb76540dc556d356cc9f5046988eaa5f4487",
        gate.get("pr_workflow_id") != 401606059,
        gate.get("pr_run_id") != 41970778177,
        gate.get("pr_run_attempt") != 1,
        gate.get("pr_event") != "pull_request",
        gate.get("pr_conclusion") != "action_required",
        gate.get("pr_job_count") != 0,
        gate.get("push_event_configured") is not False,
        gate.get("push_event_coverage") != "not_configured",
        gate.get("repair_validation") != "UNVERIFIED",
        gate.get("pr_url")
        != "https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41970778177",
    )):
        findings.append("exact-head PR/push validation gate is missing, stale, or falsely green")
    expected_policy = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "p0_approvals": 0,
        "total_historical_approvals": 0,
        "source_pins_changed": False,
        "semantic_approval_from_ci": False,
    }
    if fixture.get("policy") != expected_policy:
        findings.append("action-closure policy changes protected Phase 1 state")
    remaining = fixture.get("remaining_blockers")
    if not isinstance(remaining, dict) or any((
        remaining.get("original_blocker_count") != 44,
        remaining.get("selected_blocker_count") != 2,
        remaining.get("selected_resolved_count") != 0,
        remaining.get("selected_blocked_count") != 2,
        remaining.get("phase1_gate") != "FAIL_INCOMPLETE",
        remaining.get("independent_approvals") != 0,
    )):
        findings.append("remaining blocker totals are missing or inconsistent")
    return {
        "status": "UNVERIFIED" if not findings else "BLOCKED",
        "observed_at": fixture.get("observed_at"),
        "source_hashes": actual_hashes,
        "selected_blocker_count": len(report_rows),
        "selected_resolved_count": 0,
        "selected_blocked_count": len(report_rows),
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "repair_validation": "UNVERIFIED",
        "findings": sorted(set(findings)),
        "rows": report_rows,
        "validation_gate": gate,
        "remaining_blockers": remaining,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="offline API-shaped JSON snapshot (no network access)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="evaluate only the observations already recorded in the manifest",
    )
    parser.add_argument(
        "--triage-json",
        action="store_true",
        help="emit every readiness blocker with its closure action and source references",
    )
    parser.add_argument(
        "--live-observations",
        type=Path,
        help="attach a read-only, source-linked live API observation record to JSON triage",
    )
    parser.add_argument(
        "--dependency-observations",
        type=Path,
        help="classify a dated, source-linked stacked-dependency observation without network access",
    )
    parser.add_argument(
        "--closure-index",
        type=Path,
        help="validate the deduplicated B001-B044 evidence index without network access",
    )
    parser.add_argument(
        "--action-closure",
        type=Path,
        help="validate the bounded before/after workflow-action closure evidence offline",
    )
    args = parser.parse_args(argv)
    try:
        manifest_bytes = args.manifest.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if args.action_closure:
            if (
                args.snapshot or args.offline or args.live_observations
                or args.triage_json or args.dependency_observations
                or args.closure_index
            ):
                parser.error("--action-closure is a standalone offline mode")
            source_paths = {
                "development/copilot-integration/manifest.json":
                    ROOT / "development/copilot-integration/manifest.json",
                "development/copilot-integration/blocker-triage-20261104.json":
                    ROOT / "development/copilot-integration/blocker-triage-20261104.json",
                "development/copilot-integration/closure-index-20261105.json":
                    ROOT / "development/copilot-integration/closure-index-20261105.json",
                "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json":
                    ROOT / "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json",
            }
            triage = json.loads(source_paths[
                "development/copilot-integration/blocker-triage-20261104.json"
            ].read_text(encoding="utf-8"))
            closure_index = json.loads(source_paths[
                "development/copilot-integration/closure-index-20261105.json"
            ].read_text(encoding="utf-8"))
            workflow_receipts = json.loads(source_paths[
                "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json"
            ].read_text(encoding="utf-8"))
            actual_hashes = {
                path: hashlib.sha256(source.read_bytes()).hexdigest()
                for path, source in source_paths.items()
            }
            fixture = json.loads(args.action_closure.read_text(encoding="utf-8"))
            report = blocker_action_closure_report(
                fixture, manifest, triage, workflow_receipts, actual_hashes
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1 if report["status"] != "READY" else 0
        if args.closure_index:
            if args.snapshot or args.offline or args.live_observations or args.triage_json or args.dependency_observations:
                parser.error("--closure-index is a standalone offline mode")
            source_paths = {
                "development/copilot-integration/manifest.json":
                    ROOT / "development/copilot-integration/manifest.json",
                "development/copilot-integration/blocker-triage-20261104.json":
                    ROOT / "development/copilot-integration/blocker-triage-20261104.json",
                "development/copilot-integration/dependency-base-reconciliation-20261105.json":
                    ROOT / "development/copilot-integration/dependency-base-reconciliation-20261105.json",
                "tests/fixtures/copilot-integration-readiness/stale_main_base_evidence_20261105.json":
                    ROOT / "tests/fixtures/copilot-integration-readiness/stale_main_base_evidence_20261105.json",
                "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json":
                    ROOT / "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json",
                "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json":
                    ROOT / "tests/fixtures/copilot-integration-readiness/workflow_id_reconciliation_20261104.json",
            }
            package_documents = {
                path: json.loads(source.read_text(encoding="utf-8"))
                for path, source in source_paths.items()
                if path != "development/copilot-integration/manifest.json"
                and path != "development/copilot-integration/blocker-triage-20261104.json"
            }
            triage = json.loads(source_paths[
                "development/copilot-integration/blocker-triage-20261104.json"
            ].read_text(encoding="utf-8"))
            actual_hashes = {
                path: hashlib.sha256(source.read_bytes()).hexdigest()
                for path, source in source_paths.items()
            }
            index = json.loads(args.closure_index.read_text(encoding="utf-8"))
            report = closure_index_report(
                index, manifest, triage, package_documents, actual_hashes
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1 if report["status"] == "BLOCKED" else 0
        if args.dependency_observations:
            if args.snapshot or args.offline or args.live_observations or args.triage_json:
                parser.error("--dependency-observations is a standalone offline mode")
            observation = json.loads(
                args.dependency_observations.read_text(encoding="utf-8")
            )
            source_paths = {
                "development/copilot-integration/manifest.json":
                    ROOT / "development/copilot-integration/manifest.json",
                "development/copilot-integration/blocker-triage-20261104.json":
                    ROOT / "development/copilot-integration/blocker-triage-20261104.json",
                "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json":
                    ROOT / "tests/fixtures/copilot-integration-readiness/stale_workflow_evidence_20261104.json",
            }
            actual_hashes = {
                path: hashlib.sha256(source.read_bytes()).hexdigest()
                for path, source in source_paths.items()
                if source.is_file()
            }
            actual_hashes[
                "development/copilot-integration/manifest.json"
            ] = hashlib.sha256(manifest_bytes).hexdigest()
            report = dependency_readiness_report(
                observation, manifest, actual_hashes
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1 if report["status"] == "BLOCKED" else 0
        if args.offline and args.snapshot:
            parser.error("--offline and --snapshot are mutually exclusive")
        snapshot = (
            json.loads(args.snapshot.read_text(encoding="utf-8"))
            if args.snapshot
            else recorded_snapshot(manifest) if args.offline
            else fetch_public_snapshot(manifest)
        )
        live_observations = (
            json.loads(args.live_observations.read_text(encoding="utf-8"))
            if args.live_observations
            else None
        )
        if live_observations is not None and not isinstance(live_observations, dict):
            raise ValueError("--live-observations must contain a JSON object")
    except (OSError, ValueError, RuntimeError) as exc:
        print("BLOCKED: %s" % exc, file=sys.stderr)
        return 2
    issues = validate(manifest, snapshot)
    if args.triage_json:
        report = blocker_triage_report(
            manifest,
            snapshot,
            issues,
            hashlib.sha256(manifest_bytes).hexdigest(),
            live_observations,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if issues else 0
    for evidence in workflow_evidence_report(manifest, snapshot):
        run = str(evidence.get("run_id") or "none")
        attempt = str(evidence.get("run_attempt") or "none")
        print(
            "WORKFLOW_EVIDENCE PR #%s workflow #%s status=%s run=%s attempt=%s "
            "event=%s expected_head=%s expected_base=%s executed_sha=%s "
            "reported_head=%s reported_base=%s run_url=%s job_urls=%s detail=%s"
            % (
                evidence["pr_number"],
                evidence["workflow_id"],
                evidence["status"],
                run,
                attempt,
                evidence.get("event") or "unknown",
                evidence.get("expected_head_sha") or "unknown",
                evidence.get("expected_base_sha") or "unknown",
                evidence.get("executed_sha") or "unknown",
                evidence.get("reported_head_sha") or "unknown",
                evidence.get("reported_base_sha") or "unknown",
                evidence.get("run_url") or "unavailable",
                ",".join(evidence.get("job_urls", [])) or "unavailable",
                evidence["detail"],
            )
        )
    for item in manifest.get("integration_order", []):
        print("%s. %s" % (item["order"], item["action"]))
    if issues:
        print("BLOCKED (%d readiness issues):" % len(issues))
        for issue in issues:
            print("- " + issue)
        return 1
    print("READY: integration metadata and required workflow provenance match.")
    print("This result is observational; it is not semantic approval or Phase 1 completion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

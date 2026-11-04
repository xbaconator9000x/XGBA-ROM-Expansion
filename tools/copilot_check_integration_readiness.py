#!/usr/bin/env python3
"""Observational, fail-closed readiness check for the audited draft PR stack."""

import argparse
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
        if isinstance(ref, dict):
            if ref.get("head_sha") not in (None, head_sha):
                return False, "PR head provenance is stale"
            if ref.get("base_sha") not in (None, base_sha):
                return False, "PR base provenance is stale"
        return True, "exact current PR head"

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
        return dict(
            base_result,
            status="stale_head_base",
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

    for number in live_prs.keys() - expected_prs.keys():
        issues.append("unexpected PR #%d is absent from the pinned manifest" % number)
    return issues


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
            "main": {"ref": main_ref, "sha": main_sha["sha"]},
            "pull_requests": snapshot_prs,
            "workflow_runs": runs,
            "commit_details": commit_details,
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
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.offline and args.snapshot:
            parser.error("--offline and --snapshot are mutually exclusive")
        snapshot = (
            json.loads(args.snapshot.read_text(encoding="utf-8"))
            if args.snapshot
            else recorded_snapshot(manifest) if args.offline
            else fetch_public_snapshot(manifest)
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print("BLOCKED: %s" % exc, file=sys.stderr)
        return 2
    issues = validate(manifest, snapshot)
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

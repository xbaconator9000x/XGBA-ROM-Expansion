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
            candidates = [
                run
                for run in runs
                if isinstance(run, dict)
                and run.get("workflow_id") == workflow_id
                and any(
                    _pr_number(ref.get("number") if isinstance(ref, dict) else ref) == number
                    for ref in run.get("pull_requests", [])
                )
            ]
            passing = [
                run
                for run in candidates
                if run.get("status") == "completed" and run.get("conclusion") == "success"
            ]
            qualified = []
            for run in passing:
                executed_sha = run.get("head_sha")
                for ref in run.get("pull_requests", []):
                    ref_number = (
                        _pr_number(ref.get("number"))
                        if isinstance(ref, dict)
                        else _pr_number(ref)
                    )
                    if ref_number != number:
                        continue
                    if not SHA1.fullmatch(str(executed_sha or "")):
                        continue
                    if executed_sha == observed.get("head_sha"):
                        if (
                            run.get("event") == "pull_request_target"
                            and executed_sha == observed.get("base_sha")
                        ):
                            continue
                        qualified.append(run)
                        continue
                    if not isinstance(ref, dict):
                        continue
                    if (
                        ref.get("head_sha") != observed.get("head_sha")
                        or ref.get("base_sha") != observed.get("base_sha")
                    ):
                        continue
                    commit = commit_details.get(executed_sha)
                    if not isinstance(commit, dict) or commit.get("sha") != executed_sha:
                        continue
                    parents = commit.get("parents")
                    if (
                        isinstance(parents, list)
                        and parents == [observed.get("base_sha"), observed.get("head_sha")]
                    ):
                        qualified.append(run)
            if not qualified:
                if not candidates:
                    detail = "required workflow #%d was not observed for the PR" % workflow_id
                elif not passing:
                    detail = "required workflow #%d has no successful completed run" % workflow_id
                else:
                    detail = (
                        "green workflow #%d lacks matching current head/base provenance"
                        % workflow_id
                    )
                issues.append("PR #%d required evidence absent: %s" % (number, detail))

    for number in live_prs.keys() - expected_prs.keys():
        issues.append("unexpected PR #%d is absent from the pinned manifest" % number)
    return issues


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
                    "workflow_id": run.get("workflow_id"),
                    "event": run.get("event"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "head_sha": run.get("head_sha"),
                    "pull_requests": refs,
                })
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
                "workflow_id": observed.get("workflow_id"),
                "event": observed.get("event"),
                "status": "completed",
                "conclusion": "success",
                "head_sha": observed.get("head_sha"),
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

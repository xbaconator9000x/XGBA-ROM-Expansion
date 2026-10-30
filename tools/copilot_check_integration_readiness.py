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
    expected_prs = {
        int(pr["number"]): pr
        for pr in manifest.get("pull_requests", [])
        if isinstance(pr, dict) and str(pr.get("number", "")).isdigit()
    }
    live_prs = {
        int(number): pr
        for number, pr in snapshot.get("pull_requests", {}).items()
        if str(number).isdigit() and isinstance(pr, dict)
    }
    live_main = snapshot.get("main", {})
    expected_main = manifest.get("main", {})
    if not SHA1.fullmatch(str(expected_main.get("sha", ""))):
        issues.append("manifest main SHA is not a full 40-character Git SHA")
    if not live_main.get("sha"):
        issues.append("current main SHA is missing")
    elif live_main.get("sha") != expected_main.get("sha"):
        issues.append(
            "main SHA changed: expected %s, observed %s"
            % (expected_main.get("sha"), live_main.get("sha"))
        )

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
            parent = expected_prs.get(int(dependency)) if str(dependency).isdigit() else None
            parent_live = live_prs.get(int(dependency)) if str(dependency).isdigit() else None
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

        requirements = pr.get("required_evidence")
        if not isinstance(requirements, list) or not requirements:
            issues.append("PR #%d has no required workflow evidence configured" % number)
            continue
        workflow_ids = manifest.get("required_workflow_ids", {}).get(str(number), [])
        if not isinstance(workflow_ids, list) or not workflow_ids:
            issues.append("PR #%d required workflow ID is unverified in the manifest" % number)
            continue
        runs = snapshot.get("workflow_runs", [])
        for workflow_id in workflow_ids:
            if not isinstance(workflow_id, int):
                issues.append("PR #%d has an invalid required workflow ID" % number)
                continue
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
                if run.get("event") not in ("pull_request", "pull_request_target"):
                    continue
                for ref in run.get("pull_requests", []):
                    if not isinstance(ref, dict) or _pr_number(ref.get("number")) != number:
                        continue
                    if (
                        ref.get("head_sha") == observed.get("head_sha")
                        and ref.get("base_sha") == observed.get("base_sha")
                        and SHA1.fullmatch(str(run.get("head_sha", "")))
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
        return {
            "main": {"ref": main_ref, "sha": main_sha["sha"]},
            "pull_requests": snapshot_prs,
            "workflow_runs": runs,
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

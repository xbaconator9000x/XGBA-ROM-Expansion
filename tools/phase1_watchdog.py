#!/usr/bin/env python3
"""XGBA Phase 1 watchdog, deliberately read-only toward audit jobs.

Checks every Phase 1 GitHub Actions workflow, marks failures and potentially
stalled jobs, and updates a persistent GitHub issue. No run cancellation,
rerun, dispatch, or semantic completion certification.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "xbaconator9000x/XGBA-ROM-Expansion")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
ISSUE_NUMBER = int(os.environ.get("WATCHDOG_ISSUE_NUMBER", "1"))
STALE_JOB_MINUTES = int(os.environ.get("WATCHDOG_STALE_MINUTES", "45"))
QUEUE_MINUTES = int(os.environ.get("WATCHDOG_QUEUE_MINUTES", "60"))
MAX_TABLE_ROWS = 40
API = "https://api.github.com/repos/" + REPOSITORY
UTC = dt.timezone.utc
META_FINGERPRINT = re.compile(r"<!-- xgba-watchdog-fingerprint: ([0-9a-f]{64}) -->")
META_LAST_CHECK = re.compile(r"<!-- xgba-watchdog-lastcheck: ([^>]+) -->")


def request(method: str, suffix: str, payload=None):
    if not TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN / GH_TOKEN")
    url = API + suffix
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + TOKEN,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "XGBA-Phase1-Watchdog",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:1400]
        raise RuntimeError(f"GitHub API {method} {suffix} returned {error.code}: {body}") from error


def timestamp(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def minutes_ago(s, now):
    at = timestamp(s)
    if at is None:
        return None
    return max(0, int((now - at).total_seconds() / 60))


def minutes_str(number):
    if number is None:
        return "unknown"
    if number >= 60:
        return f"{number // 60}h {number % 60}m"
    return f"{number}m"


def clean_cell(s):
    return str(s).replace("|", r"\|").replace("\r", " ").replace("\n", " ")[:130]


def status_for_run(run, now):
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion")
    if status == "completed":
        if conclusion == "success":
            return ("PASSED", None)
        if conclusion in ("cancelled", "skipped", "neutral"):
            return (conclusion.upper(), None)
        return ("FAILED", {
            "kind": "failed", "workflow": run.get("name", ""),
            "run_id": run["id"], "url": run["html_url"],
            "conclusion": conclusion or "unknown",
        })
    if status in ("queued", "requested", "waiting", "pending"):
        age = minutes_ago(run.get("created_at"), now)
        if age is not None and age >= QUEUE_MINUTES:
            return ("QUEUED: CHECK", {
                "kind": "queued_too_long", "workflow": run.get("name", ""),
                "run_id": run["id"], "url": run["html_url"], "age_minutes": age,
            })
        return ("QUEUED", None)
    if status == "in_progress":
        jobs = request("GET", f"/actions/runs/{run['id']}/jobs?per_page=100").get("jobs", [])
        active_steps = [
            (job, step) for job in jobs for step in job.get("steps", [])
            if step.get("status") == "in_progress"
        ]
        age_candidates = [
            minutes_ago(step.get("started_at"), now) for _, step in active_steps
        ]
        age_candidates = [x for x in age_candidates if x is not None]
        if active_steps:
            longest = max(age_candidates) if age_candidates else None
            step_name = active_steps[age_candidates.index(longest)][1].get("name", "step") if longest is not None else "unknown"
        else:
            longest = minutes_ago(run.get("run_started_at") or run.get("created_at"), now)
            step_name = "no active step reported"
        if longest is not None and longest >= STALE_JOB_MINUTES:
            return ("POSSIBLY STUCK", {
                "kind": "possibly_stuck", "workflow": run.get("name", ""),
                "run_id": run["id"], "url": run["html_url"],
                "age_minutes": longest, "step": step_name,
            })
        return ("RUNNING", None)
    return ("UNKNOWN", None)


def main():
    now = dt.datetime.now(UTC)
    workflows = request("GET", "/actions/workflows?per_page=100").get("workflows", [])
    audited = [
        w for w in workflows
        if w.get("name", "").startswith("Phase 1 ")
        and "watchdog" not in w.get("name", "").lower()
        and w.get("state") in ("active", "disabled_manually")
    ]
    if not audited:
        raise RuntimeError("No Phase 1 audit workflows discovered; cannot claim healthy")

    states, alerts, evidence = [], [], []
    for flow in sorted(audited, key=lambda w: w.get("name", "")):
        latest = request("GET", f"/actions/workflows/{flow['id']}/runs?per_page=1").get("workflow_runs", [])
        if not latest:
            states.append((flow["name"], "NEVER RUN", None, None))
            continue
        run = latest[0]
        verdict, alert = status_for_run(run, now)
        states.append((flow["name"], verdict, run["id"], run["html_url"]))
        evidence.append({
            "workflow_id": flow["id"], "name": flow["name"],
            "run_id": run["id"], "status": run.get("status"),
            "conclusion": run.get("conclusion"), "verdict": verdict,
            "updated_at": run.get("updated_at"), "html_url": run["html_url"],
        })
        if alert:
            alerts.append(alert)

    counts = {}
    for _, verdict, _, _ in states:
        counts[verdict] = counts.get(verdict, 0) + 1

    alert_dedup = sorted(
        (a["workflow"], a["kind"], str(a["run_id"])) for a in alerts
    )
    signature = hashlib.sha256(json.dumps({
        "states": [(name, status, run_id) for name, status, run_id, _ in states],
        "alerts": alert_dedup,
    }, sort_keys=True).encode()).hexdigest()

    alert_lines = []
    for a in alerts:
        if a["kind"] == "possibly_stuck":
            text = (f"**Possibly stuck**: [{clean_cell(a['workflow'])}]({a['url']}) "
                    f"has a step running for {minutes_str(a['age_minutes'])} "
                    f"({clean_cell(a['step'])}). This is a warning, not proof of a deadlock.")
        elif a["kind"] == "queued_too_long":
            text = (f"**Long queue**: [{clean_cell(a['workflow'])}]({a['url']}) "
                    f"queued for {minutes_str(a['age_minutes'])}.")
        else:
            text = (f"**Failed**: [{clean_cell(a['workflow'])}]({a['url']}) "
                    f"concluded {clean_cell(a.get('conclusion', 'failure'))}.")
        alert_lines.append("- " + text)

    table = ["| Audit | Latest state | Latest run |", "|---|---|---|"]
    for name, verdict, rid, url in states[:MAX_TABLE_ROWS]:
        link = f"[#{rid}]({url})" if url else "none"
        table.append(f"| {clean_cell(name)} | **{clean_cell(verdict)}** | {link} |")

    prior = request("GET", f"/issues/{ISSUE_NUMBER}")
    old_body = prior.get("body") or ""
    old_fp_match = META_FINGERPRINT.search(old_body)
    old_fp = old_fp_match.group(1) if old_fp_match else None
    old_check = META_LAST_CHECK.search(old_body)
    old_check_date = timestamp(old_check.group(1).strip()) if old_check else None

    unchanged = old_fp == signature
    check_age = ((now - old_check_date).total_seconds() / 60
                 if old_check_date else 9999)
    # Keep the issue fresh without issuing a GitHub edit every 15 minutes
    should_update = not unchanged or check_age >= 60

    phase_note = (
        "**Phase 1 semantic mapping is NOT certified by this dashboard.** "
        "A successful GitHub Actions run only verifies its individual tests. "
        "The fail-closed semantic mapping gate is authoritative."
    )
    health = ("Potential issue(s) found" if alerts
              else "Active work" if counts.get("RUNNING", 0) or counts.get("QUEUED", 0)
              else "Idle — all discovered latest runs are complete or have not run")
    body = "\n".join([
        "# XGBA Phase 1 — automated watchdog",
        "",
        f"**Last check (UTC):** {now.isoformat(timespec='seconds')}",
        f"**Health:** {health}",
        f"**Audits discovered:** {len(audited)}",
        "",
        phase_note, "",
        "## Actions requiring inspection",
        *(alert_lines if alert_lines else ["No new failure or possible stall detected."]),
        "",
        "## Latest run per audit workflow",
        *table,
        "",
        "## Controls and limitations",
        "- This check runs approximately every 15 minutes. GitHub may delay scheduled jobs.",
        f"- An active step over {STALE_JOB_MINUTES} minutes is flagged for review, not automatically cancelled.",
        "- Watchdog never reruns/cancels an audit, alters source code, or declares Phase 1 complete.",
        "- To inspect a red status, open its run link and inspect the failed step.",
        "- GitHub Actions monitoring cannot refresh or revive a frozen ChatGPT response.",
        "",
        f"<!-- xgba-watchdog-fingerprint: {signature} -->",
        f"<!-- xgba-watchdog-lastcheck: {now.isoformat(timespec='seconds')} -->",
        "",
    ])
    if should_update:
        request("PATCH", f"/issues/{ISSUE_NUMBER}", {
            "body": body,
        })
        print("Issue dashboard refreshed")
    else:
        print("No state change: retaining existing issue body")

    # Emit a comment only when the alert set/underlying latest runs changed,
    # and there actually is a new problem.
    if alerts and not unchanged:
        request("POST", f"/issues/{ISSUE_NUMBER}/comments", {
            "body": ("### XGBA Phase 1 watchdog alert\n\n" +
                     "\n".join(alert_lines) +
                     "\n\nNo audit job was automatically restarted or cancelled."),
        })
        print(f"Logged {len(alerts)} warning(s) in the issue")

    result = {
        "timestamp": now.isoformat(),
        "repository": REPOSITORY,
        "issue_number": ISSUE_NUMBER,
        "issue_url": f"https://github.com/{REPOSITORY}/issues/{ISSUE_NUMBER}",
        "workflow_count": len(audited),
        "counts": counts,
        "states": evidence,
        "alerts": alerts,
        "fingerprint": signature,
        "dashboard_updated": should_update,
        "semantics_approved": False,
        "phase1_completion_claimed": False,
    }
    pathlib.Path("watchdog-output").mkdir(exist_ok=True)
    pathlib.Path("watchdog-output/status.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": health, "discovered": len(audited),
        "alerts": len(alerts), "dashboard_updated": should_update,
    }, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"WATCHDOG CHECK FAILED: {exc!r}\n")
        raise

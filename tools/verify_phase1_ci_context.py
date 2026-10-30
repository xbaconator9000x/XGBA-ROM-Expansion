#!/usr/bin/env python3
"""Verify that a PR validation job is running on its exact pull-request head."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys


SHA1 = re.compile(r"^[0-9a-f]{40}$")


def validate_event(event_name, event, checkout_sha, repository):
    issues = []
    if event_name != "pull_request":
        issues.append("workflow event must be pull_request")
    if not isinstance(event, dict):
        return issues + ["GitHub event payload must be an object"]

    event_repository = event.get("repository")
    if not isinstance(repository, str) or not repository:
        issues.append("GITHUB_REPOSITORY scope is missing")
    elif (
        not isinstance(event_repository, dict)
        or event_repository.get("full_name") != repository
    ):
        issues.append("event repository scope does not match GITHUB_REPOSITORY")

    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        issues.append("pull_request event scope is missing")
        return issues

    number = pull_request.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        issues.append("pull_request number scope is missing or malformed")

    head = pull_request.get("head")
    expected_sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(expected_sha, str) or not SHA1.fullmatch(expected_sha):
        issues.append("pull_request head SHA is missing or malformed")
    if not isinstance(checkout_sha, str) or not SHA1.fullmatch(checkout_sha):
        issues.append("checked-out commit SHA is missing or malformed")
    elif isinstance(expected_sha, str) and SHA1.fullmatch(expected_sha):
        if checkout_sha != expected_sha:
            issues.append(
                "checked-out commit %s does not equal PR head %s"
                % (checkout_sha, expected_sha)
            )
    return issues


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    try:
        if not event_path:
            raise ValueError("GITHUB_EVENT_PATH is missing")
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        checkout_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print("PHASE1_CI_CONTEXT_BLOCKED: " + str(exc), file=sys.stderr)
        return 2

    issues = validate_event(
        os.environ.get("GITHUB_EVENT_NAME"),
        event,
        checkout_sha,
        os.environ.get("GITHUB_REPOSITORY"),
    )
    if issues:
        for issue in issues:
            print("PHASE1_CI_CONTEXT_BLOCKED: " + issue, file=sys.stderr)
        return 2

    print(
        "PHASE1_CI_CONTEXT_VERIFIED: PR #%d exact head %s"
        % (event["pull_request"]["number"], checkout_sha)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

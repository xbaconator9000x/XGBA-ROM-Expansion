#!/usr/bin/env python3
"""Fail-closed public *tracked-worktree* privacy and credential hygiene check.

No content snippets are printed: a failing scan reports path, line and category.
This does not rewrite Git history or inspect PR comments, GitHub Actions logs,
organization permissions, release attachments or previously cloned repositories.
Functional Copilot Agent Task definitions are intentionally *not* mistaken for
private chat transcripts; inspect those separately if public prompt publication
is not desired.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

# Split sensitive token prefixes so that this very checker does not contain a
# syntactically plausible credential string.
PATTERN_RULES = (
    ("private-key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ("github-access-token", r"gh(?:p|o|u|s|r)_[A-Za-z0-9_]{24,}"),
    ("github-fine-grained-token", r"github_pat_[A-Za-z0-9_]{25,}"),
    ("openai-api-key", r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    ("aws-access-key", r"AKIA[A-Z0-9]{16}"),
    ("slack-token", r"xox[baprs]-[A-Za-z0-9-]{24,}"),
    ("private-conversation-marker", r"(?m)^\s*(?:User|Assistant|Human|Developer|System):\s+\S"),
    ("raw-chat-serialization", r'["\x27]role["\x27]\s*:\s*["\x27](?:user|assistant|system|developer)["\x27]\s*,\s*["\x27]content["\x27]'),
    ("private-chat-wire-format", r"<\|im_(?:start|end)\|>"),
    ("personal-chat-session", r"(?i)\b(?:Chat" + r"GPT (?:hourly (?:task|automation)|response|conversation)|generated in Chat" + r"GPT|billing scree" + r"nshot|owner requested reduc" + r"tion|user separately conf" + r"irmed)\b"),
    ("individual-financial-preference", r"(?i)\b(?:my|the user(?:'s)?)\s+(?:AI[- ]credit |GitHub |subscription |billing |spending )?(?:budget|overage|spending cap|subscription cost)\b"),
)
RULES = tuple((label, re.compile(pattern)) for label, pattern in PATTERN_RULES)
EMAIL = re.compile(r"(?<![A-Za-z0-9_.+-])[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_AU = re.compile(r"(?<!\d)(?:\+61\s?4|04)\d{2}[ -]?\d{3}[ -]?\d{3}(?!\d)")
FORBIDDEN_FILE = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\..+)?|id_(?:rsa|ed25519)|credentials(?:\.json)?|"
    r".+\.(?:p12|pfx|pem|key|keystore|kdbx)|.+\.(?:chat|transcript|jsonl))$"
)
SAFE_EMAIL_SUFFIXES = ("@users.noreply.github.com", "@noreply.github.com")
# Retired dispatchers must not be reintroduced by an old automated branch.
# Game-side resource loaders and native CI are intentionally NOT on this list.
RETIRED_DISPATCH_FILES = frozenset({
    ".github/workflows/phase1-copilot-chain.yml",
    ".github/workflows/phase1-agent-task-pilot.yml",
    ".github/workflows/xgba-autonomous-product.yml",
    "tools/phase1_agent_task_pilot.py",
    "tools/xgba_autonomous_product.py",
    "tests/test_phase1_agent_task_pilot.py",
    "tests/test_xgba_autonomous_product.py",
})

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".yaml", ".yml",
    ".c", ".h", ".inc", ".sh", ".toml", ".ini", ".cmake", ".gitignore",
    ".css", ".html", ".js", ".ts", ".xml", ".cfg",
}


def tracked_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return [root / p.decode("utf-8", "surrogateescape")
            for p in result.stdout.split(b"\x00") if p]


def audit_bytes(path: str, data: bytes) -> list[tuple[str, int]]:
    problems: list[tuple[str, int]] = []
    basename = Path(path).name
    if FORBIDDEN_FILE.search(path):
        problems.append(("sensitive-file-name", 0))
    if b"\x00" in data:
        return problems
    try:
        value = data.decode("utf-8")
    except UnicodeDecodeError:
        return problems
    for label, regex in RULES:
        for match in regex.finditer(value):
            problems.append((label, value.count("\n", 0, match.start()) + 1))
    for match in EMAIL.finditer(value):
        email = match.group(0).lower()
        if not email.endswith(SAFE_EMAIL_SUFFIXES) and email not in (
            "example@example.com", "test@example.com"
        ):
            problems.append(("potential-email-address", value.count("\n", 0, match.start()) + 1))
    for match in PHONE_AU.finditer(value):
        problems.append(("potential-australian-mobile", value.count("\n", 0, match.start()) + 1))
    return sorted(set(problems))


def check_readme(content: str) -> list[str]:
    headings = (
        "## What XGBA is", "## Goals", "## Potential implications",
        "## AI disclosure", "## Development history and verified results",
    )
    locations = [content.find(s) for s in headings]
    errors = []
    if any(n < 0 for n in locations) or locations != sorted(locations):
        errors.append("README intro headings absent or out of requested order")
    if ("I am developing XGBA with the help of AI for coding and logging purposes."
            not in content):
        errors.append("README first-person AI disclosure absent")
    # The verified history advances with each proven release. Reject absent,
    # malformed or regressed summaries, but do not freeze the README at R27.
    version = re.search(r"\\bR6[–-]R(\\d+)\\s+verified\\b", content)
    if not version or int(version.group(1)) < 27:
        errors.append("README current verified milestone summary unexpectedly missing")
    return errors


def audit_repository(root: Path) -> tuple[int, list[tuple[str, int, str]]]:
    violations: list[tuple[str, int, str]] = []
    count = 0
    for path in tracked_paths(root):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        count += 1
        if rel in RETIRED_DISPATCH_FILES:
            violations.append((rel, 0, "retired-dispatcher-reintroduced"))
        # Forbid credential/archive paths regardless of whether they are text.
        if FORBIDDEN_FILE.search(rel):
            violations.append((rel, 0, "sensitive-file-name"))
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in (
            ".gitignore", "CMakeLists.txt", "Makefile",
        ):
            continue
        for label, line in audit_bytes(rel, path.read_bytes()):
            if label == "sensitive-file-name":
                continue
            violations.append((rel, line, label))
    readme = root / "README.md"
    if not readme.exists():
        violations.append(("README.md", 0, "missing-readme"))
    else:
        for error in check_readme(readme.read_text(encoding="utf-8")):
            violations.append(("README.md", 0, error))
    return count, sorted(set(violations))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repo.resolve()
    count, findings = audit_repository(root)
    for path, line, rule in findings:
        print(f"PRIVACY_AUDIT_FINDING {path}:{line} {rule}")
    if findings:
        print(f"FAIL_REPO_PRIVACY_AUDIT tracked_files={count} findings={len(findings)}")
        return 1
    print(f"PASS_REPO_PRIVACY_AUDIT tracked_files={count} high_confidence_findings=0 "
          "scope=current_tracked_worktree history_and_remote_prs_not_scanned=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

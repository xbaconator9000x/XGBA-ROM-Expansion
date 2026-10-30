#!/usr/bin/env python3
"""Verify task-scoped pinned Poryscript/FireRed review evidence."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = (
    ROOT
    / "semantic-snapshots/independent-reviews/copilot-poryscript-abi/review.json"
)
PINS = {
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
}
VERDICTS = {"APPROVED", "REJECTED", "NEEDS_EVIDENCE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate_record(record):
    require(record.get("schema") == "copilot-poryscript-abi-review/v1",
            "unsupported review record schema")
    reviewer = record.get("reviewer", {})
    require(reviewer.get("identity") and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity"),
            "reviewer identity must be distinct from the original source interpreter")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE",
            "Phase 1 gate must remain FAIL_INCOMPLETE")
    require(accounting.get("approved_before") == 0 and
            accounting.get("new_approvals") == 0,
            "review must preserve the existing zero approval total")
    require(accounting.get("shared_queue_register_gate_modified") is False,
            "shared review queue, register, or gate must not be modified")

    sources = {}
    for source in record.get("source_evidence", []):
        repository = source.get("repository")
        require(repository in PINS, "source repository is not one of the pinned inputs")
        require(source.get("commit") == PINS[repository],
                "source commit does not match the immutable pin: " + str(repository))
        path = PurePosixPath(source.get("path", ""))
        require(path.parts and not path.is_absolute() and ".." not in path.parts,
                "source path must be a safe repository-relative path")
        key = (repository, path.as_posix())
        require(key not in sources, "duplicate source evidence identity: " + str(key))
        sources[key] = source

        for field in ("git_blob_sha1", "sha256"):
            digest = source.get(field, "")
            require(len(digest) == (40 if field == "git_blob_sha1" else 64) and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid " + field + " for " + path.as_posix())
        ranges = source.get("evidence_ranges", [])
        require(ranges, "source evidence must include exact line ranges")
        for item in ranges:
            start, end = item.get("start"), item.get("end")
            require(isinstance(start, int) and isinstance(end, int) and
                    1 <= start <= end, "invalid source evidence line range")
            digest = item.get("sha256", "")
            require(len(digest) == 64 and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid line-range SHA-256")

    require(sources, "review must cite immutable source evidence")
    for item in record.get("file_verdicts", []):
        key = (item.get("repository"), item.get("path"))
        require(key in sources, "per-file verdict lacks pinned source evidence")
        require(item.get("verdict") in VERDICTS, "invalid proposed per-file verdict")
        require(item.get("basis"), "per-file verdict must state its basis")

    witness = record.get("actual_cli_witness", {})
    require(witness.get("status") == "success" and
            witness.get("actual_poryscript_cli_executed") is True and
            witness.get("actual_firered_preprocessor_used") is True and
            witness.get("negative_controls_passed") == 7,
            "actual CLI witness must retain its exact successful result")
    require(len(witness.get("artifact_zip_sha256", "")) == 64,
            "actual CLI witness artifact digest is required")
    require(record.get("local_rerun", {}).get("status") ==
            "BLOCKED_MISSING_PINNED_CHECKOUTS_AND_GNU_ARM_BINUTILS",
            "local rerun blocker must be explicit")
    return sources


def verify_source_entry(source, root):
    path = PurePosixPath(source["path"])
    file_path = root.joinpath(*path.parts)
    require(file_path.is_file(), "missing pinned source file: " + str(file_path))
    data = file_path.read_bytes()
    require(git_blob_sha1(data) == source["git_blob_sha1"],
            "Git blob mismatch: " + source["repository"] + ":" + source["path"])
    require(hashlib.sha256(data).hexdigest() == source["sha256"],
            "file SHA-256 mismatch: " + source["repository"] + ":" + source["path"])
    lines = data.splitlines(keepends=True)
    for item in source["evidence_ranges"]:
        require(item["end"] <= len(lines), "line range exceeds source file: " + source["path"])
        excerpt = b"".join(lines[item["start"] - 1:item["end"]])
        require(hashlib.sha256(excerpt).hexdigest() == item["sha256"],
                "line-range SHA-256 mismatch: %s:%d-%d" %
                (source["path"], item["start"], item["end"]))


def verify_sources(record, roots, source_files_only=False):
    sources = validate_record(record)
    commit_status = {}
    for repository, root in roots.items():
        require(repository in PINS, "unexpected source root: " + repository)
        git_dir = root / ".git"
        if git_dir.exists():
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            )
            require(result.stdout.strip() == PINS[repository],
                    "upstream checkout HEAD differs for " + repository)
            commit_status[repository] = "VERIFIED"
        else:
            require(source_files_only,
                    "source checkout lacks .git metadata; pass --source-files-only "
                    "to verify file blobs without claiming commit verification")
            commit_status[repository] = "NOT_CHECKED_FILE_BLOBS_ONLY"

    verified = 0
    for (repository, _), source in sources.items():
        require(repository in roots, "missing source root for " + repository)
        verify_source_entry(source, roots[repository])
        verified += 1
    return {
        "status": "PASS_SOURCE_BLOBS_AND_LINE_RANGES",
        "source_files_verified": verified,
        "checkout_commits": commit_status,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--poryscript-root", type=Path)
    parser.add_argument("--firered-root", type=Path)
    parser.add_argument("--source-files-only", action="store_true")
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding="utf-8"))
    roots = {}
    if args.poryscript_root:
        roots["huderlem/poryscript"] = args.poryscript_root.resolve()
    if args.firered_root:
        roots["pret/pokefirered"] = args.firered_root.resolve()
    if roots:
        result = verify_sources(record, roots, args.source_files_only)
    else:
        validate_record(record)
        result = {
            "status": "PASS_RECORD_STRUCTURE_ONLY",
            "source_files_verified": 0,
            "approval_count_changed": False,
            "phase1_gate": "FAIL_INCOMPLETE",
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

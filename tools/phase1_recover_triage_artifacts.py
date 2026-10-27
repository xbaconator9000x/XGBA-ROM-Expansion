#!/usr/bin/env python3
"""Recover immutable CI triage shards; never infer semantic review or approval.

This verifies GitHub's ZIP digest and the extracted JSON digest before checking
record identities. The existing pinned-queue integrity verifier remains mandatory
for the cumulative checkpoint. No workflow re-runs or fresh source verification
are claimed by this recovery operation.
"""
import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PINS = {
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
    "huderlem/porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/agbcc": "da598c1d918402c42c0c0d7128ba14567f3175e9",
}
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
MAX_ZIP = 2_000_000
MAX_JSON = 2_000_000


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fetch_zip(repo, artifact_id, token):
    require(token, "GitHub token required for remote recovery")
    url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "xgba-phase1-artifact-recovery",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(MAX_ZIP + 1)
    require(len(raw) <= MAX_ZIP, "Artifact exceeds size limit")
    return raw


def verify(manifest, artifact_dir=None, token=None):
    require(manifest.get("schema") == "xgba-phase1-artifact-recovery-v1", "Bad manifest schema")
    require(manifest.get("repo") == "xbaconator9000x/XGBA-ROM-Expansion", "Unexpected repo")
    require(manifest.get("phase1_gate") == "FAIL_INCOMPLETE", "Phase 1 gate drift")
    require(manifest.get("independent_approvals") == 0, "Unexpected approval")
    require(manifest.get("analyst_prepared_baseline") == 113, "Prepared register drift")
    require(manifest.get("prior_committed_total") == 3000, "Prior coverage drift")
    require(manifest.get("start") == 3000 and manifest.get("end_exclusive") == 4000,
            "Recovery range drift")
    require(HEX40.fullmatch(str(manifest.get("source_workflow_head", ""))), "Invalid workflow source head")
    shards = manifest.get("shards")
    require(isinstance(shards, list) and len(shards) == 4, "Expected four immutable shards")
    seen = set()
    validated = []
    for i, shard in enumerate(sorted(shards, key=lambda x: x["offset"])):
        start = 3000 + i * 250
        end = start + 249
        filename = f"batch-{start:06d}-{end:06d}.json"
        require(shard.get("offset") == start and shard.get("count") == 250, "Shard range drift")
        require(shard.get("filename") == filename, "Unexpected archive member name")
        require(isinstance(shard.get("artifact_id"), int) and shard["artifact_id"] > 0,
                "Invalid artifact ID")
        require(HEX64.fullmatch(str(shard.get("zip_sha256", ""))) and
                HEX64.fullmatch(str(shard.get("content_sha256", ""))), "Invalid digest")
        if artifact_dir is None:
            raw_zip = fetch_zip(manifest["repo"], shard["artifact_id"], token)
        else:
            raw_zip = (artifact_dir / f"github-actions-artifact-{shard['artifact_id']}.zip").read_bytes()
        require(len(raw_zip) <= MAX_ZIP and sha256(raw_zip) == shard["zip_sha256"],
                "ZIP digest/size mismatch: " + filename)
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
            members = z.infolist()
            require(len(members) == 1 and members[0].filename == filename,
                    "Unexpected archive members: " + filename)
            require(members[0].file_size <= MAX_JSON, "JSON member exceeds limit")
            content = z.read(members[0])
        require(sha256(content) == shard["content_sha256"], "JSON digest mismatch: " + filename)
        doc = json.loads(content)
        require(doc.get("schema") == "xgba-phase1-machine-triage-v1" and
                doc.get("snapshot_gate") == "FAIL_INCOMPLETE" and
                doc.get("inventory_total") == 14834 and
                doc.get("prepared_register_baseline") == 113 and
                doc.get("selected_count") == 250 and
                doc.get("offset") == start and
                doc.get("source_reverified") is True, "Shard header mismatch: " + filename)
        records = doc.get("records")
        require(isinstance(records, list) and len(records) == 250, "Shard count mismatch")
        for record in records:
            identity = record.get("identity") or {}
            repo = identity.get("repository")
            path = identity.get("path")
            require(repo in PINS and identity.get("pinned_commit") == PINS[repo] and
                    isinstance(path, str) and bool(path) and
                    HEX40.fullmatch(str(identity.get("git_blob_sha1", ""))),
                    "Pinned identity mismatch")
            key = (repo, path)
            require(key not in seen, "Duplicate identity across recovered shards")
            seen.add(key)
            evidence = record.get("evidence") or {}
            structure = record.get("whole_file_structure") or {}
            require(evidence.get("source_blob_reverified_this_run") is True and
                    evidence.get("snapshot_provenance_verified") is True and
                    HEX64.fullmatch(str(evidence.get("dossier_sha256", ""))),
                    "Missing recorded source provenance")
            require(HEX64.fullmatch(str(structure.get("whole_blob_sha256", ""))) and
                    HEX64.fullmatch(str(structure.get("all_lines_sha256", ""))) and
                    isinstance(structure.get("source_lines"), int) and
                    isinstance(structure.get("includes"), list) and
                    isinstance(structure.get("conditional_directive_lines"), list),
                    "Missing structural evidence")
            require(record.get("state") == "MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW" and
                    record.get("prepared_whole_file_candidate") is False and
                    record.get("independent_approval") is False, "Review/approval inflation")
        validated.append((filename, content))
    require(len(seen) == 1000, "Expected exactly 1,000 unique identities")
    return validated


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=Path("docs/phase1-machine-triage/recovery-003000-003999.json"))
    p.add_argument("--artifact-dir", type=Path, help="Local ZIP directory; omit for authenticated GitHub API")
    p.add_argument("--output-dir", type=Path, default=Path("docs/phase1-machine-triage"))
    p.add_argument("--write", action="store_true", help="Write verified shards only after all pass")
    p.add_argument("--reconcile", action="store_true", help="Run full pinned-queue integrity check after writing")
    args = p.parse_args()
    require(not args.reconcile or args.write, "--reconcile requires --write")
    manifest = json.loads(args.manifest.read_text())
    validated = verify(manifest, args.artifact_dir, os.environ.get("GITHUB_TOKEN"))
    if args.write:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in validated:
            target = args.output_dir / filename
            if target.exists():
                require(target.read_bytes() == content, "Existing shard differs: " + filename)
                continue
            with tempfile.NamedTemporaryFile(dir=args.output_dir, delete=False) as tmp:
                tmp.write(content)
                temp_name = tmp.name
            os.replace(temp_name, target)
        if args.reconcile:
            from phase1_bulk_triage_integrity_range import verify as verify_cumulative
            verify_cumulative(args.output_dir, Path("semantic-snapshots/current"),
                              Path("docs/phase1-disposition-candidates/README.md"), 4000, 3000)
    print(json.dumps({"artifact_shards_verified": len(validated),
                      "distinct_recovered_records": 1000,
                      "committed_records_claimed": 0,
                      "reconciled": bool(args.reconcile),
                      "written": bool(args.write),
                      "phase1_gate": "FAIL_INCOMPLETE",
                      "independent_approvals": 0}, sort_keys=True))


if __name__ == "__main__":
    main()

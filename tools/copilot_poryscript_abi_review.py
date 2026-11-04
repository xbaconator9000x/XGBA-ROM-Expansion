#!/usr/bin/env python3
"""Verify task-scoped pinned Poryscript/FireRed review evidence."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = (
    ROOT
    / "semantic-snapshots/independent-reviews/copilot-poryscript-abi/review.json"
)
DEFAULT_CLOSURE_RECORD = (
    ROOT
    / "semantic-snapshots/independent-reviews/copilot-poryscript-abi/closure-review.json"
)
PINS = {
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "pret/agbcc": "da598c1d918402c42c0c0d7128ba14567f3175e9",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
}
REPOSITORY_ALIASES = {
    "p": "huderlem/poryscript",
    "f": "pret/pokefirered",
    "a": "pret/agbcc",
    "m": "mgba-emu/mgba",
}
EXPECTED_ARCHIVES = {
    "dossiers": {
        "path": "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz",
        "bytes": 949448,
        "sha256": "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609",
        "git_blob_sha1": "3b982876c7d810a827af8c80c7e5d9231fdaa327",
    },
    "queue": {
        "path": "semantic-snapshots/current/semantic_review_queue.csv.gz",
        "bytes": 1051376,
        "sha256": "c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff",
        "git_blob_sha1": "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268",
    },
}
PR20_WITNESS_ARTIFACT_SHA256 = (
    "37cc5d0e03fd481c61721816533b8869709b1a23b7b9bc6f76df701252f988e5"
)
PR36_WITNESS_ARTIFACT_SHA256 = (
    "0991fb3a015b27370dcc01994bbe597da382b671c30d0f6c30a9d52e11a8fa9a"
)
LOCAL_PROBE_SHA256 = {
    "fixture_sha256": "bfcb3889acda709bfac862c57de0cbbae7796605c5fd912ac906a6d101b1894e",
    "emitted_assembly_sha256": "15b063d131599e920d79181112080cea048d3398fb6cdf0a69d11f4430ee92a7",
    "unlinked_rodata_sha256": "37c32ab9ec8d289aa0f0c7ae4ed68f39e8a08b333b0a1014121cffa845bfcc49",
    "linked_rodata_sha256": "523ef7b38fd6cdae81782fbbb5b242e964f7a3f4c7838fa3023daf7feacec168",
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

    original_witness = record.get("original_evidence", {}).get(
        "actual_cli_workflow", {}
    )
    require(original_witness.get("workflow_run_id") == 40506170513 and
            original_witness.get("job_id") == 122195911391 and
            original_witness.get("head_sha") ==
            "587132181ef728b635968dd091b1cf171e78f753" and
            original_witness.get("artifact_id") == 12735216391 and
            original_witness.get("artifact_zip_sha256") ==
            PR20_WITNESS_ARTIFACT_SHA256,
            "original PR #20 witness provenance changed")
    witness = record.get("actual_cli_witness", {})
    require(witness.get("status") == "success" and
            witness.get("actual_poryscript_cli_executed") is True and
            witness.get("actual_firered_preprocessor_used") is True and
            witness.get("negative_controls_passed") == 7 and
            witness.get("artifact_zip_sha256") ==
            PR20_WITNESS_ARTIFACT_SHA256,
            "actual CLI witness must retain its exact successful result")
    require(record.get("local_rerun", {}).get("status") ==
            "BLOCKED_MISSING_PINNED_CHECKOUTS_AND_GNU_ARM_BINUTILS",
            "local rerun blocker must be explicit")
    return sources


def validate_closure_record(record, archive_root=ROOT):
    require(record.get("schema") == "copilot-poryscript-abi-closure-review/v1",
            "unsupported closure record schema")
    reviewer = record.get("reviewer", {})
    require(reviewer.get("id") == "copilot-issue33-closure" and
            reviewer.get("identity") and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity") and
            reviewer.get("distinct_from_evidence_author") is True,
            "closure reviewer must be identified and distinct from the evidence author")
    require(reviewer.get("separate_human_attestation") is False and
            reviewer.get("authenticated_github_review_attribution") is False,
            "closure record must not claim missing external attestation")
    require(record.get("pins") == PINS,
            "closure source pins differ from the immutable assignments")
    require(record.get("repository_aliases") ==
            {repository: alias for alias, repository in REPOSITORY_ALIASES.items()},
            "closure repository aliases differ")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE" and
            accounting.get("approved_p0") == 0 and
            accounting.get("p0_total") == 338 and
            accounting.get("approved_total") == 0 and
            accounting.get("inventory_total") == 14834 and
            accounting.get("phase2_started") is False and
            accounting.get("shared_queue_register_gate_modified") is False,
            "closure must preserve the Phase 1 gate, approval totals, and scope")

    archives = record.get("original_machine_evidence", {})
    require(set(archives) == set(EXPECTED_ARCHIVES),
            "original dossier and queue archive identities are required")
    root = archive_root.resolve()
    for name, expected in EXPECTED_ARCHIVES.items():
        archive = archives[name]
        require(archive == expected,
                "original machine evidence identity differs from pinned " + name)
        path = PurePosixPath(archive.get("path", ""))
        require(path.parts and not path.is_absolute() and ".." not in path.parts,
                "machine evidence path must be repository-relative")
        resolved = root.joinpath(*path.parts).resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("machine evidence path escapes archive root: " +
                             path.as_posix()) from exc
        data = resolved.read_bytes()
        require(len(data) == archive.get("bytes") and
                hashlib.sha256(data).hexdigest() == archive.get("sha256") and
                git_blob_sha1(data) == archive.get("git_blob_sha1"),
                "original machine evidence bytes or digest changed: " + path.as_posix())

    coverage = record.get("coverage", {})
    file_rows = coverage.get("file_rows", [])
    require(coverage.get("source_dossier_rows") == 81 and len(file_rows) == 81,
            "closure must retain the 81 source/dossier inventory rows")
    require(coverage.get("whole_file_semantic_reviews") == 0 and
            coverage.get("all_file_rows_verdict") == "NEEDS_EVIDENCE" and
            coverage.get("all_file_rows_reviewer_id") == reviewer.get("id"),
            "per-file records must remain attributed and non-approving")

    files = {}
    for row in file_rows:
        require(isinstance(row, list) and len(row) == 7,
                "invalid per-file closure row")
        alias, source_path, blob, source_sha, dossier_line_sha, range_code, verdict = row
        repository = REPOSITORY_ALIASES.get(alias)
        path = PurePosixPath(source_path)
        require(repository is not None and path.parts and not path.is_absolute() and
                ".." not in path.parts,
                "unsafe or unknown per-file source identity")
        key = (repository, path.as_posix())
        require(key not in files, "duplicate per-file closure identity: " + str(key))
        require(verdict == "NEEDS_EVIDENCE",
                "only NEEDS_EVIDENCE per-file verdicts are allowed")
        require(range_code in {"H", "R"},
                "unknown per-file source coverage code")
        for field, digest, width in (
                ("Git blob", blob, 40), ("source SHA-256", source_sha, 64),
                ("dossier line SHA-256", dossier_line_sha, 64)):
            require(len(digest) == width and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid " + field + " for " + path.as_posix())
        files[key] = {
            "repository": repository,
            "path": path.as_posix(),
            "git_blob_sha1": blob,
            "sha256": source_sha,
            "dossier_record_line_sha256": dossier_line_sha,
            "coverage_code": range_code,
        }

    dossier_archive = archives["dossiers"]
    dossier_path = PurePosixPath(dossier_archive["path"])
    dossier_file = archive_root.joinpath(*dossier_path.parts)
    remaining = set(files)
    with gzip.open(dossier_file, "rb") as stream:
        for line in stream:
            dossier = json.loads(line)
            provenance = dossier.get("provenance", {})
            key = (provenance.get("repository"), provenance.get("path"))
            if key not in remaining:
                continue
            source = files[key]
            require(provenance.get("pinned_revision") == PINS[key[0]] and
                    provenance.get("git_blob_sha") == source["git_blob_sha1"],
                    "machine dossier source identity differs: " + str(key))
            require(hashlib.sha256(line).hexdigest() ==
                    source["dossier_record_line_sha256"],
                    "machine dossier record line changed: " + str(key))
            content_sha = provenance.get("source_content_sha256")
            require(content_sha is None or content_sha == source["sha256"],
                    "machine dossier source SHA-256 differs: " + str(key))
            machine_review = dossier.get("review", {})
            require(machine_review.get("semantic_signoff") is False and
                    machine_review.get("status") != "APPROVED",
                    "machine dossier must not be interpreted as approval: " + str(key))
            remaining.remove(key)
            if not remaining:
                break
    require(not remaining,
            "per-file receipt lacks its original machine dossier row: " +
            str(sorted(remaining)[:3]))

    ranges = {}
    for row in coverage.get("evidence_ranges", []):
        require(isinstance(row, list) and len(row) == 5,
                "invalid closure evidence range")
        alias, source_path, start, end, digest = row
        repository = REPOSITORY_ALIASES.get(alias)
        key = (repository, PurePosixPath(source_path).as_posix())
        require(repository is not None and key in files and
                isinstance(start, int) and isinstance(end, int) and
                1 <= start <= end and len(digest) == 64 and
                all(c in "0123456789abcdef" for c in digest),
                "invalid or unpinned line-range evidence")
        require((key, start, end) not in ranges,
                "duplicate line-range evidence: " + str(key))
        ranges[(key, start, end)] = digest
    range_files = {key for key, _, _ in ranges}
    for key, source in files.items():
        expected_code = "R" if key in range_files else "H"
        require(source["coverage_code"] == expected_code,
                "per-file coverage code does not match line evidence: " + str(key))
    require(len(ranges) == coverage.get("bounded_line_ranges") and
            len(range_files) == coverage.get("bounded_range_files"),
            "closure range counts do not match per-file evidence")

    for edge in coverage.get("dependency_edges", []):
        require(isinstance(edge, list) and len(edge) == 5,
                "invalid ABI dependency edge")
        from_repo, from_path, to_repo, to_path, relation = edge
        from_key = (REPOSITORY_ALIASES.get(from_repo),
                    PurePosixPath(from_path).as_posix())
        to_key = (REPOSITORY_ALIASES.get(to_repo),
                  PurePosixPath(to_path).as_posix())
        require(from_key in files and to_key in files and relation,
                "dependency edge endpoint lacks a per-file receipt")

    objection_ids = set()
    for objection in record.get("objections", []):
        identifier = objection.get("id")
        require(identifier and objection.get("status") == "UNRESOLVED" and
                objection.get("observation") and objection.get("resolution"),
                "every objection must retain its unresolved evidence and resolution")
        require(identifier not in objection_ids, "duplicate objection identity")
        objection_ids.add(identifier)
    objection_map = coverage.get("objection_map", {})
    require("all" in objection_map and all(
        identifier in objection_ids for values in objection_map.values()
        for identifier in values
    ), "per-file objection map references an unknown obligation")
    require(set(objection_map) == {"all", *REPOSITORY_ALIASES},
            "per-repository unresolved obligations are incomplete")

    historical = record.get("historical_witness", {})
    require(historical.get("run_id") == 41035493919 and
            historical.get("head_sha") == "2c2805ead909df69a491cea84feb7dd562758e9b" and
            historical.get("artifact_id") == 12968950310 and
            historical.get("negative_controls_passed") == 7 and
            historical.get("artifact_zip_sha256") ==
            PR36_WITNESS_ARTIFACT_SHA256,
            "historical exact-head witness provenance changed")
    probe = record.get("local_actual_cli_probe", {})
    require(probe.get("status") ==
            "PASS_ACTUAL_PINNED_CLI_PREPROCESSOR_GNU_ARM_OBJECT_FIXTURE" and
            probe.get("poryscript_commit") == PINS["huderlem/poryscript"] and
            probe.get("firered_commit") == PINS["pret/pokefirered"] and
            probe.get("relocation_type") == "R_ARM_ABS32" and
            probe.get("relocation_offsets") ==
            [1, 6, 11, 16, 21, 26, 35, 45, 53, 63, 71] and
            probe.get("negative_controls") ==
            {"overflow-operand": "PASS", "zero-operand": "PASS"} and
            probe.get("phase1_gate") == "FAIL_INCOMPLETE" and
            probe.get("approval_count_changed") is False,
            "actual CLI object-probe evidence is incomplete")
    for field, digest in LOCAL_PROBE_SHA256.items():
        require(probe.get(field) == digest,
                "local actual CLI probe digest changed: " + field)
    return files, ranges


def validate_file_inspection_record(record, closure_record):
    require(record.get("schema") ==
            "copilot-poryscript-abi-file-inspection/v1",
            "unsupported file-inspection record schema")
    reviewer = record.get("reviewer", {})
    require(reviewer.get("id") == "copilot-issue33-file-inspection-followup" and
            reviewer.get("identity") ==
            "@copilot (GitHub Copilot Coding Agent; issue #33 review-readiness follow-up)" and
            reviewer.get("source_interpreter_identity") ==
            "xbaconator9000x (author of the original PR #20 witness implementation)" and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity") and
            reviewer.get("distinct_from_source_interpreter") is True,
            "file-inspection reviewer identity is missing or not distinct")
    require(reviewer.get("authenticated_github_review_attribution") is False and
            reviewer.get("independent_human_attestation") is False and
            reviewer.get("attribution_blocker"),
            "file-inspection record must state its missing authenticated attribution")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE" and
            accounting.get("approved_p0") == 0 and
            accounting.get("p0_total") == 338 and
            accounting.get("approved_total") == 0 and
            accounting.get("inventory_total") == 14834 and
            accounting.get("whole_file_semantic_reviews") == 0 and
            accounting.get("new_qualifying_copilot_receipts") == 0 and
            accounting.get("phase2_started") is False and
            accounting.get("shared_queue_register_gate_modified") is False,
            "file-inspection record must remain non-approving and Phase 1 only")

    basis = record.get("basis", {})
    require(basis.get("prior_exact_head") ==
            "fc54588319aea2a798f2455fb594c367209f8b85" and
            basis.get("prior_workflow_run_id") == 41850174614 and
            basis.get("prior_review_record_job_id") == 126702487227 and
            basis.get("prior_actual_cli_job_id") == 126702487573 and
            basis.get("prior_run_note"),
            "prior exact-head validation provenance is incomplete")

    closure_files, closure_ranges = validate_closure_record(closure_record)
    expected_files = {
        ("huderlem/poryscript", "emitter/emitter.go"),
        ("huderlem/poryscript", "parser/parser.go"),
        ("pret/pokefirered", "src/script.c"),
        ("mgba-emu/mgba", "src/gba/memory.c"),
    }
    files = record.get("files", [])
    require(len(files) == len(expected_files),
            "file-inspection receipt must contain the four scoped files")
    seen = set()
    for item in files:
        key = (item.get("repository"), item.get("path"))
        require(key in expected_files and key not in seen,
                "unknown or duplicate file-inspection identity: " + str(key))
        seen.add(key)
        require(item.get("commit") == PINS[key[0]],
                "file-inspection source pin differs: " + str(key))
        source = closure_files.get(key)
        require(source is not None and
                item.get("git_blob_sha1") == source["git_blob_sha1"] and
                item.get("sha256") == source["sha256"] and
                item.get("dossier_record_line_sha256") ==
                source["dossier_record_line_sha256"],
                "file-inspection source/dossier identity differs: " + str(key))
        require(item.get("extent") and
                item.get("whole_file_semantic_disposition") is False and
                item.get("verdict") == "NEEDS_EVIDENCE" and
                item.get("source_observations"),
                "file-inspection record must not claim whole-file disposition")

        cited_ranges = {}
        for citation in item.get("evidence_ranges", []):
            start, end = citation.get("start"), citation.get("end")
            range_key = (key, start, end)
            require(range_key in closure_ranges and
                    closure_ranges[range_key] == citation.get("sha256"),
                    "file-inspection line evidence differs from closure: " +
                    str(range_key))
            cited_ranges[range_key] = citation["sha256"]
        expected_ranges = {
            range_key: digest for range_key, digest in closure_ranges.items()
            if range_key[0] == key
        }
        require(cited_ranges == expected_ranges and cited_ranges,
                "file-inspection must cite every existing bounded range: " +
                str(key))

        dependencies = item.get("dependency_links", [])
        require(dependencies, "file-inspection dependencies are required: " + str(key))
        for dependency in dependencies:
            target = (dependency.get("repository"), dependency.get("path"))
            require(target in closure_files and
                    dependency.get("direction") in {"inbound", "outbound"} and
                    dependency.get("relation"),
                    "file-inspection dependency lacks a pinned endpoint: " +
                    str(target))
        for objection in item.get("unresolved_obligations", []):
            require(any(entry.get("id") == objection and
                        entry.get("status") == "UNRESOLVED"
                        for entry in closure_record.get("objections", [])),
                    "file-inspection references a resolved or unknown objection")

    summary = record.get("summary", {})
    require(seen == expected_files and
            summary.get("files_with_full_source_text_retrieved") == 4 and
            summary.get("whole_file_semantic_reviews") == 0 and
            summary.get("new_copilot_reviewed_passed_files") == 0 and
            summary.get("new_approvals") == 0 and
            summary.get("phase1_gate") == "FAIL_INCOMPLETE",
            "file-inspection summary overstates review completion")
    return {
        "status": "PASS_FILE_PROVENANCE_NOT_SEMANTIC_APPROVAL",
        "files_with_full_source_text_retrieved": 4,
        "whole_file_semantic_reviews": 0,
        "new_qualifying_copilot_receipts": 0,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def verify_closure_sources(record, roots, source_files_only=False,
                           archive_root=ROOT):
    files, ranges = validate_closure_record(record, archive_root)
    commit_status = {}
    for repository, root in roots.items():
        require(repository in PINS, "unexpected closure source root: " + repository)
        if (root / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            )
            require(result.stdout.strip() == PINS[repository],
                    "upstream checkout HEAD differs for " + repository)
            commit_status[repository] = "VERIFIED_PINNED_COMMIT"
        else:
            require(source_files_only,
                    "source checkout lacks .git metadata; pass --source-files-only "
                    "to verify file blobs without claiming commit verification")
            commit_status[repository] = "FILE_BLOBS_ONLY"

    require(set(roots) == set(PINS),
            "closure validation requires all four pinned source roots")
    ranges_by_key = {}
    for (key, start, end), digest in ranges.items():
        ranges_by_key.setdefault(key, []).append({
            "start": start, "end": end, "sha256": digest,
        })
    for key, source in files.items():
        entry = dict(source)
        entry["evidence_ranges"] = ranges_by_key.get(key, [])
        verify_source_entry(entry, roots[key[0]])
    return {
        "status": "PASS_HASHED_CLOSURE_NOT_SEMANTIC_APPROVAL",
        "source_files_verified": len(files),
        "bounded_line_ranges_verified": len(ranges),
        "checkout_commits": commit_status,
        "whole_file_semantic_reviews": 0,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


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
    parser.add_argument("--closure-record", type=Path)
    parser.add_argument("--file-inspection-record", type=Path)
    parser.add_argument("--poryscript-root", type=Path)
    parser.add_argument("--firered-root", type=Path)
    parser.add_argument("--agbcc-root", type=Path)
    parser.add_argument("--mgba-root", type=Path)
    parser.add_argument("--source-files-only", action="store_true")
    args = parser.parse_args()
    record_path = args.closure_record or args.record
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if args.file_inspection_record:
        require(args.closure_record is not None,
                "--file-inspection-record requires --closure-record")
        inspection = json.loads(
            args.file_inspection_record.read_text(encoding="utf-8")
        )
        print(json.dumps(validate_file_inspection_record(inspection, record),
                         sort_keys=True))
        return
    roots = {}
    if args.poryscript_root:
        roots["huderlem/poryscript"] = args.poryscript_root.resolve()
    if args.firered_root:
        roots["pret/pokefirered"] = args.firered_root.resolve()
    if args.agbcc_root:
        roots["pret/agbcc"] = args.agbcc_root.resolve()
    if args.mgba_root:
        roots["mgba-emu/mgba"] = args.mgba_root.resolve()
    if args.closure_record and roots:
        result = verify_closure_sources(record, roots, args.source_files_only)
    elif args.closure_record:
        validate_closure_record(record)
        result = {
            "status": "PASS_CLOSURE_RECORD_STRUCTURE_NOT_SEMANTIC_APPROVAL",
            "source_files_verified": 0,
            "approval_count_changed": False,
            "phase1_gate": "FAIL_INCOMPLETE",
        }
    elif roots:
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

#!/usr/bin/env python3
"""Incrementally index the pinned Phase 1 inventory without semantic approval."""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import posixpath
import re
import time
from pathlib import Path, PurePosixPath

from phase1_bulk_triage import (
    PINS, TOTAL, canonical, checked_dossiers, digest, git_blob, read_queue,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_BLOBS = {
    "candidate_review_dossiers.jsonl.gz": "3b982876c7d810a827af8c80c7e5d9231fdaa327",
    "semantic_review_queue.csv.gz": "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268",
    "phase1_mapping_gate.json": "dab5789433dc55cf325a917a220d060088bf1d29",
}
CACHE_SCHEMA = "xgba.phase1.inventory_source_cache.v2"
OUTPUT_SCHEMA = "xgba.phase1.inventory_source_index.v1"
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_CACHE_ENTRIES = TOTAL
MAX_INCLUDES_PER_FILE = 512
MAX_SOURCE_BYTES = 64 * 1024 * 1024
UNVERIFIED_EXTERNAL_REFERENCES = [
    {
        "id": "GBATEK",
        "url": "https://mgba-emu.github.io/gbatek/",
        "retrieval": "UNVERIFIED_EXTERNAL_REFERENCE_ONLY",
        "used_to_support_index_claim": False,
    },
    {
        "id": "NBA_HW_DOCS",
        "url": "https://nba-emu.github.io/hw-docs/",
        "retrieval": "UNVERIFIED_EXTERNAL_REFERENCE_ONLY",
        "used_to_support_index_claim": False,
    },
]

INCLUDE_PATTERNS = (
    re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]'),
    re.compile(r"""^\s*\.include\s+["']([^"']+)["']""", re.IGNORECASE),
)
UNEXPANDED_INCLUDE = re.compile(r"^\s*#\s*include\b")
TEST_PATH = re.compile(
    r"(?:^|/)(?:test|tests|testing|spec|specs)(?:/|$)|"
    r"(?:^|/)test_[^/]+$|(?:^|/)[^/]+_test\.[^/]+$|_test\.go$",
    re.IGNORECASE,
)
DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
LICENSE_NAMES = {
    "license", "license.md", "license.txt", "license.rst",
    "copying", "copying.md", "notice", "notice.md",
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _validate_snapshot(snapshot: Path) -> tuple[list[dict], dict, dict]:
    for name, expected_blob in SNAPSHOT_BLOBS.items():
        if git_blob((snapshot / name).read_bytes()) != expected_blob:
            raise ValueError(f"Original machine snapshot drift: {name}")

    gate = json.loads((snapshot / "phase1_mapping_gate.json").read_text(encoding="utf-8"))
    if (
        gate.get("decision") != "FAIL_INCOMPLETE"
        or gate.get("approved_semantic_dispositions") != 0
        or gate.get("p0_review_candidates") != 338
        or gate.get("machine_generated_dossiers") != TOTAL
    ):
        raise ValueError("Authoritative Phase 1 gate changed; stop and reconcile")

    queue = read_queue(snapshot)
    dossiers = checked_dossiers(snapshot, queue)
    if len(queue) != TOTAL or len(dossiers) != TOTAL:
        raise ValueError("Original inventory or dossier count mismatch")
    return queue, dossiers, gate


def _safe_relative_path(raw_path: str) -> bool:
    if not raw_path or "\\" in raw_path or raw_path.startswith("/"):
        return False
    path = PurePosixPath(raw_path)
    return all(part not in {"", ".", ".."} for part in path.parts)


def _source_bytes(source_root: Path, relative_path: str) -> bytes:
    if not _safe_relative_path(relative_path):
        raise ValueError(f"INVALID_INVENTORY_PATH: {relative_path}")
    root = source_root.resolve()
    path = source_root.joinpath(*PurePosixPath(relative_path).parts)
    try:
        if path.is_symlink():
            return os.readlink(path).encode("utf-8", "surrogateescape")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"SOURCE_PATH_ESCAPES_ROOT: {relative_path}")
        if resolved.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError(f"SOURCE_FILE_TOO_LARGE: {relative_path}")
        return resolved.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"SOURCE_FILE_MISSING: {relative_path}") from exc


def _verified_source_content(
    source_root: Path, row: dict, attributes_row: dict | None,
) -> tuple[bytes, str]:
    archive_bytes = _source_bytes(source_root, row["path"])
    if git_blob(archive_bytes) == row["blob_sha"]:
        return archive_bytes, "ARCHIVE_BYTES_MATCH_PINNED_GIT_BLOB"
    if attributes_row is None:
        raise ValueError(f"SOURCE_BLOB_MISMATCH: {row['path']}")
    attributes = _source_bytes(source_root, ".gitattributes")
    if git_blob(attributes) != attributes_row["blob_sha"]:
        raise ValueError("GITATTRIBUTES_BLOB_MISMATCH")
    for raw_line in attributes.decode("utf-8", "replace").splitlines():
        fields = raw_line.split()
        if len(fields) != 3 or fields[1:] != ["text", "eol=crlf"]:
            continue
        pattern = fields[0]
        basename_only = "/" not in pattern
        candidate = PurePosixPath(row["path"]).name if basename_only else row["path"]
        if not fnmatch.fnmatchcase(candidate, pattern):
            continue
        if b"\r" in archive_bytes.replace(b"\r\n", b""):
            break
        normalized = archive_bytes.replace(b"\r\n", b"\n")
        if git_blob(normalized) == row["blob_sha"]:
            return normalized, "CRLF_NORMALIZED_USING_PINNED_GITATTRIBUTES"
        break
    raise ValueError(f"SOURCE_BLOB_MISMATCH: {row['path']}")


def _cache_payload(cache_path: Path | None, snapshot_id: dict) -> dict[str, dict]:
    if cache_path is None or not cache_path.exists():
        return {}
    compressed = cache_path.read_bytes()
    if len(compressed) > MAX_CACHE_BYTES:
        raise ValueError("CACHE_EXCEEDS_BOUNDED_SIZE")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            raw = stream.read(MAX_CACHE_BYTES * 8 + 1)
        if len(raw) > MAX_CACHE_BYTES * 8:
            raise ValueError("CACHE_EXPANDED_SIZE_LIMIT")
        payload = json.loads(raw)
    except (OSError, EOFError, json.JSONDecodeError) as exc:
        raise ValueError("CACHE_INVALID_GZIP_OR_JSON") from exc
    if payload.get("schema") != CACHE_SCHEMA:
        raise ValueError("CACHE_SCHEMA_MISMATCH")
    if payload.get("snapshot_identity") != snapshot_id:
        raise ValueError("CACHE_SNAPSHOT_IDENTITY_MISMATCH")
    entries = payload.get("entries")
    if not isinstance(entries, dict) or len(entries) > MAX_CACHE_ENTRIES:
        raise ValueError("CACHE_ENTRY_COUNT_INVALID")
    for key, entry in entries.items():
        if not isinstance(entry, dict) or entry.get("cache_key") != key:
            raise ValueError("CACHE_ENTRY_MALFORMED")
        claimed = entry.get("cache_record_sha256")
        body = {name: value for name, value in entry.items() if name != "cache_record_sha256"}
        if claimed != digest(canonical(body)):
            raise ValueError(f"CACHE_RECORD_CHECKSUM_MISMATCH: {key}")
    return entries


def _write_cache(cache_path: Path | None, snapshot_id: dict, entries: dict[str, dict]) -> None:
    if cache_path is None:
        return
    ordered = {key: entries[key] for key in sorted(entries)}
    if len(ordered) > MAX_CACHE_ENTRIES:
        raise ValueError("CACHE_ENTRY_COUNT_LIMIT")
    raw = canonical({
        "schema": CACHE_SCHEMA,
        "snapshot_identity": snapshot_id,
        "entries": ordered,
    })
    compressed = gzip.compress(raw, mtime=0)
    if len(compressed) > MAX_CACHE_BYTES:
        raise ValueError("CACHE_EXCEEDS_BOUNDED_SIZE")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(compressed)


def _extract_file_facts(content: bytes, repo_path: str, category: str) -> dict:
    if b"\0" in content[:8192]:
        text = None
    else:
        text = content.decode("utf-8", "replace")
    includes = []
    unsupported_include_lines = []
    include_scan_complete = True
    unsupported_include_scan_truncated = False
    line_count = 0
    if text is not None:
        for line_count, line in enumerate(text.splitlines(), 1):
            match = next((pattern.match(line) for pattern in INCLUDE_PATTERNS
                          if pattern.match(line)), None)
            if match:
                if len(includes) < MAX_INCLUDES_PER_FILE:
                    includes.append({"line": line_count, "literal": match.group(1)})
                else:
                    include_scan_complete = False
            elif UNEXPANDED_INCLUDE.match(line):
                if len(unsupported_include_lines) < MAX_INCLUDES_PER_FILE:
                    unsupported_include_lines.append(line_count)
                else:
                    unsupported_include_scan_truncated = True
        if unsupported_include_scan_truncated:
            include_scan_complete = False
        if not text or not text.endswith(("\n", "\r")):
            line_count = len(text.splitlines())
    suffix = PurePosixPath(repo_path).suffix.lower()
    name = PurePosixPath(repo_path).name.lower()
    roles = []
    if TEST_PATH.search(repo_path):
        roles.append("UPSTREAM_TEST_SOURCE_FILE_HASH_VERIFIED_NOT_EXECUTED")
    if category == "documentation" or suffix in DOC_SUFFIXES:
        roles.append("UPSTREAM_DOCUMENT_FILE_HASH_VERIFIED_NOT_REVIEWED")
    if name in LICENSE_NAMES or name.startswith("license."):
        roles.append("LICENSE_TEXT_FILE_HASH_VERIFIED_NO_CLEARANCE")
    return {
        "source_bytes": len(content),
        "source_lines": line_count,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "direct_include_literals": includes,
        "direct_include_scan_complete": include_scan_complete,
        "unsupported_include_lines": unsupported_include_lines,
        "unsupported_include_scan_truncated": unsupported_include_scan_truncated,
        "text_scanned": text is not None,
        "upstream_evidence_roles": roles,
    }


def _cache_record(
    key: str, repo: str, row: dict, dossier: dict, content: bytes,
    materialization: str = "ARCHIVE_BYTES_MATCH_PINNED_GIT_BLOB",
) -> dict:
    source_blob = git_blob(content)
    if source_blob != row["blob_sha"]:
        raise ValueError(f"SOURCE_BLOB_MISMATCH: {repo}:{row['path']}")
    source_sha = hashlib.sha256(content).hexdigest()
    provenance = dossier["provenance"]
    if str(provenance.get("tracked_bytes")) != str(len(content)):
        raise ValueError(f"DOSSIER_TRACKED_BYTES_MISMATCH: {repo}:{row['path']}")
    dossier_source_sha = provenance.get("source_content_sha256")
    if dossier_source_sha is not None and dossier_source_sha != source_sha:
        raise ValueError(f"DOSSIER_SOURCE_SHA256_MISMATCH: {repo}:{row['path']}")
    if dossier.get("review", {}).get("semantic_signoff") is not False:
        raise ValueError(f"DOSSIER_SIGNOFF_NOT_FALSE: {repo}:{row['path']}")
    entry = {
        "cache_key": key,
        "repository": repo,
        "pinned_commit": PINS[repo],
        "path": row["path"],
        "git_blob_sha1": row["blob_sha"],
        "source_sha256": source_sha,
        "source_materialization": materialization,
        "dossier_sha256": row["evidence_sha256"],
        "dossier_source_sha256_present": dossier_source_sha is not None,
        "facts": _extract_file_facts(content, row["path"], row["category"]),
    }
    entry["cache_record_sha256"] = digest(canonical(entry))
    return entry


def _row_key(repo: str, path: str) -> str:
    return f"{repo}:{path}"


def _validated_cached_record(
    key: str, entry: dict, row: dict, dossier: dict, source_root: Path,
    attributes_row: dict | None,
) -> dict:
    if (
        entry.get("repository") != row["repo"]
        or entry.get("pinned_commit") != PINS[row["repo"]]
        or entry.get("path") != row["path"]
        or entry.get("git_blob_sha1") != row["blob_sha"]
        or entry.get("dossier_sha256") != row["evidence_sha256"]
    ):
        raise ValueError(f"CACHE_SOURCE_OR_DOSSIER_IDENTITY_MISMATCH: {key}")
    try:
        content, materialization = _verified_source_content(
            source_root, row, attributes_row,
        )
    except ValueError as exc:
        if str(exc).startswith("SOURCE_BLOB_MISMATCH"):
            raise ValueError(f"SOURCE_DRIFT_FROM_CACHE: {key}") from exc
        raise
    if git_blob(content) != row["blob_sha"]:
        raise ValueError(f"SOURCE_DRIFT_FROM_CACHE: {key}")
    source_sha = hashlib.sha256(content).hexdigest()
    if entry.get("source_sha256") != source_sha:
        raise ValueError(f"CACHE_SOURCE_SHA256_MISMATCH: {key}")
    if entry.get("source_materialization") != materialization:
        raise ValueError(f"CACHE_SOURCE_MATERIALIZATION_MISMATCH: {key}")
    if str(dossier["provenance"].get("tracked_bytes")) != str(len(content)):
        raise ValueError(f"DOSSIER_TRACKED_BYTES_MISMATCH: {key}")
    original_sha = dossier["provenance"].get("source_content_sha256")
    if original_sha is not None and original_sha != source_sha:
        raise ValueError(f"DOSSIER_SOURCE_SHA256_MISMATCH: {key}")
    return entry


def _resolve_include(source_path: str, literal: str, inventory_paths: set[str]) -> dict:
    candidates = set()
    for candidate in (
        posixpath.normpath(posixpath.join(posixpath.dirname(source_path), literal)),
        posixpath.normpath(literal),
        posixpath.normpath(posixpath.join("include", literal)),
        posixpath.normpath(posixpath.join("src", literal)),
    ):
        if _safe_relative_path(candidate) and candidate in inventory_paths:
            candidates.add(candidate)
    sorted_candidates = sorted(candidates)
    if len(sorted_candidates) == 1:
        return {
            "resolution": "UNIQUE_PINNED_PATH_CANDIDATE",
            "candidate_paths": sorted_candidates,
        }
    if sorted_candidates:
        return {
            "resolution": "AMBIGUOUS_PINNED_PATH_CANDIDATES",
            "candidate_paths": sorted_candidates,
        }
    return {
        "resolution": "UNRESOLVED_OUTSIDE_OR_ABSENT_FROM_PINNED_INVENTORY",
        "candidate_paths": [],
    }


def _license_assessment(catalog: dict) -> dict:
    paths = catalog.get("license_file_paths", [])
    if not paths:
        return {
            "state": "BLOCKED_NO_HASH_VERIFIED_LICENSE_FILE",
            "reason_code": "LICENSE_EVIDENCE_MISSING",
            "distribution_clearance": "NOT_ASSESSED",
        }
    return {
        "state": "LICENSE_FILES_HASH_VERIFIED",
        "reason_code": None,
        "license_file_paths": paths,
        "distribution_clearance": "NOT_ASSESSED",
    }


def _validate_license_boundary(catalogs: dict) -> None:
    for catalog in catalogs.values():
        assessment = catalog.get("license_assessment", {})
        if assessment.get("distribution_clearance") != "NOT_ASSESSED":
            raise ValueError("UNSUPPORTED_LICENSE_CLEARANCE_ASSUMPTION")


def _looks_like_license_path(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return name in LICENSE_NAMES or name.startswith("license.")


def _require_test_evidence(test_paths: list[str]) -> None:
    if not test_paths:
        raise ValueError("UPSTREAM_TEST_EVIDENCE_MISSING")


def _test_link_state(test_candidates: list[str], verified_test_paths: list[str]) -> str:
    if test_candidates:
        return "DIRECT_TEST_INCLUDE_CANDIDATE_FOUND_NOT_COVERAGE"
    if verified_test_paths:
        return "NO_DIRECT_TEST_INCLUDE_CANDIDATE_FOUND"
    return "NO_HASH_VERIFIED_TEST_SOURCE_IN_CURRENT_INDEX"


def _validate_no_unsupported_inference(
    external_references: list[dict], claims: list[dict],
) -> None:
    ids = {item["id"]: item for item in external_references}
    for claim in claims:
        for reference_id in claim.get("reference_ids", []):
            reference = ids.get(reference_id)
            if not reference:
                raise ValueError("UNGROUNDED_EXTERNAL_REFERENCE")
            if (
                reference.get("retrieval") != "RETRIEVED_AND_HASHED"
                or not reference.get("content_sha256")
            ):
                raise ValueError("UNVERIFIED_REFERENCE_CANNOT_SUPPORT_CLAIM")


def _select_batch(queue: list[dict], offset: int, limit: int | None) -> list[dict]:
    ordered = sorted(queue, key=lambda row: (
        PRIORITY_ORDER.get(row["priority"], 9),
        row["category"] != "source",
        -int(row["incoming_includes"]),
        -int(row["symbol_candidates"]),
        row["repo"],
        row["path"],
    ))
    return ordered[offset:offset + limit] if limit is not None else ordered[offset:]


def _pending_records(queue: list[dict], indexed_keys: set[str]) -> list[dict]:
    return [
        row for row in queue
        if _row_key(row["repo"], row["path"]) not in indexed_keys
    ]


def _root_for_repo(source_roots: Path, repository: str) -> Path | None:
    repo_name = repository.split("/")[-1]
    exact = source_roots / repo_name
    if exact.is_dir():
        return exact
    matches = sorted(path for path in source_roots.glob(repo_name + "-*") if path.is_dir())
    if len(matches) == 1:
        return matches[0]
    return None


def build_index(
    snapshot: Path,
    source_roots: Path,
    cache_path: Path | None,
    output: Path,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> dict:
    started = time.monotonic()
    queue, dossiers, gate = _validate_snapshot(snapshot)
    snapshot_identity = {
        "source_dossier_archive_git_blob_sha1":
            SNAPSHOT_BLOBS["candidate_review_dossiers.jsonl.gz"],
        "review_queue_git_blob_sha1":
            SNAPSHOT_BLOBS["semantic_review_queue.csv.gz"],
        "mapping_gate_git_blob_sha1": SNAPSHOT_BLOBS["phase1_mapping_gate.json"],
    }
    cache = _cache_payload(cache_path, snapshot_identity)
    rows_by_key = {_row_key(row["repo"], row["path"]): row for row in queue}
    if len(rows_by_key) != TOTAL:
        raise ValueError("Inventory identity collision")

    # Cached content is only reused after rechecking the current upstream blob and dossier identity.
    indexed = {}
    cache_revalidated = 0
    blocked = {}
    for key, entry in cache.items():
        row = rows_by_key.get(key)
        if row is None:
            raise ValueError(f"CACHE_PATH_NOT_IN_INVENTORY: {key}")
        repo_root = _root_for_repo(source_roots, row["repo"])
        if repo_root is None:
            blocked[key] = "SOURCE_ROOT_MISSING"
            continue
        try:
            attributes_row = rows_by_key.get(_row_key(row["repo"], ".gitattributes"))
            indexed[key] = _validated_cached_record(
                key, entry, row, dossiers[(row["repo"], row["path"])],
                repo_root, attributes_row,
            )
            cache_revalidated += 1
        except ValueError as exc:
            blocked[key] = str(exc).split(":", 1)[0]

    batch = _select_batch(_pending_records(queue, set(indexed)), offset, limit)
    for row in batch:
        repo, path = row["repo"], row["path"]
        key = _row_key(repo, path)
        repo_root = _root_for_repo(source_roots, repo)
        if repo_root is None:
            blocked[key] = "SOURCE_ROOT_MISSING"
            indexed.pop(key, None)
            continue
        try:
            if key in indexed:
                continue
            attributes_row = rows_by_key.get(_row_key(repo, ".gitattributes"))
            content, materialization = _verified_source_content(
                repo_root, row, attributes_row,
            )
            indexed[key] = _cache_record(
                key, repo, row, dossiers[(repo, path)], content, materialization,
            )
            blocked.pop(key, None)
        except (OSError, ValueError) as exc:
            reason = str(exc).split(":", 1)[0]
            blocked[key] = reason
            indexed.pop(key, None)

    # Remove stale cache records; only currently verified index records are retained.
    indexed = {key: indexed[key] for key in sorted(indexed)}
    _write_cache(cache_path, snapshot_identity, indexed)

    inventory_paths_by_repo = {
        repo: {row["path"] for row in queue if row["repo"] == repo}
        for repo in PINS
    }
    source_records = []
    dependency_edges = []
    repo_catalog = {
        repo: {
            "catalog_id": f"repo-evidence:{repo}@{PINS[repo]}",
            "pinned_commit": PINS[repo],
            "verified_test_source_paths": [],
            "verified_document_paths": [],
            "license_file_paths": [],
            "inventory_test_path_count": sum(
                bool(TEST_PATH.search(row["path"]))
                for row in queue if row["repo"] == repo
            ),
            "inventory_license_candidate_paths": sorted(
                row["path"] for row in queue
                if row["repo"] == repo and _looks_like_license_path(row["path"])
            ),
            "coverage_note": "Repository-level file presence only; relevance, execution, or license clearance is not inferred.",
        }
        for repo in PINS
    }

    for key, entry in indexed.items():
        row = rows_by_key[key]
        roles = entry["facts"]["upstream_evidence_roles"]
        repo = row["repo"]
        if any(role.startswith("UPSTREAM_TEST_SOURCE") for role in roles):
            repo_catalog[repo]["verified_test_source_paths"].append(row["path"])
        if any(role.startswith("UPSTREAM_DOCUMENT") for role in roles):
            repo_catalog[repo]["verified_document_paths"].append(row["path"])
        if any(role.startswith("LICENSE_TEXT_FILE") for role in roles):
            repo_catalog[repo]["license_file_paths"].append(row["path"])

    all_edge_rows = []
    for key, entry in indexed.items():
        row = rows_by_key[key]
        original_assessment = dossiers[(row["repo"], row["path"])]["machine_assessment"]
        repo, path = row["repo"], row["path"]
        references = []
        unresolved = 0
        for include in entry["facts"]["direct_include_literals"]:
            resolution = _resolve_include(
                path, include["literal"], inventory_paths_by_repo[repo],
            )
            targets = resolution["candidate_paths"]
            if resolution["resolution"] == "UNIQUE_PINNED_PATH_CANDIDATE":
                target_key = _row_key(repo, targets[0])
                target_state = (
                    "SOURCE_INDEXED" if target_key in indexed
                    else "INVENTORIED_TARGET_NOT_YET_SOURCE_INDEXED"
                )
                if target_key not in indexed:
                    unresolved += 1
            else:
                target_state = "NO_UNIQUE_PINNED_TARGET"
                unresolved += 1
            edge = {
                "from": key,
                "line": include["line"],
                "literal": include["literal"],
                "resolution": resolution["resolution"],
                "candidate_target_paths": targets,
                "target_index_state": target_state,
            }
            all_edge_rows.append(edge)
            if len(references) < 32:
                references.append({
                    "line": include["line"],
                    "literal": include["literal"],
                    "resolution": resolution["resolution"],
                    "candidate_target_paths": targets,
                })
        if len(entry["facts"]["direct_include_literals"]) > 32:
            references.append({
                "truncated": True,
                "reason_code": "DEPENDENCY_REFERENCES_TRUNCATED_IN_ITEM",
                "total_include_count": len(entry["facts"]["direct_include_literals"]),
            })
        source_records.append({
            "identity": {
                "repository": repo,
                "pinned_commit": PINS[repo],
                "path": path,
                "git_blob_sha1": row["blob_sha"],
                "source_sha256": entry["source_sha256"],
                "source_materialization": entry["source_materialization"],
                "source_bytes": entry["facts"]["source_bytes"],
                "source_lines": entry["facts"]["source_lines"],
            },
            "machine_dossier": {
                "sha256": row["evidence_sha256"],
                "source_content_sha256_present":
                    entry["dossier_source_sha256_present"],
                "original_archive_git_blob_sha1":
                    SNAPSHOT_BLOBS["candidate_review_dossiers.jsonl.gz"],
                "semantic_signoff": False,
            },
            "inventory": {
                "category": row["category"],
                "priority": row["priority"],
                "machine_review_status": row["machine_review_status"],
            },
            "original_machine_triage": {
                "lexical_sites_total": original_assessment["lexical_sites_total"],
                "rule_counts": original_assessment["rule_counts"],
                "symbol_candidates_total":
                    original_assessment["symbol_candidates_total"],
                "incoming_include_candidates":
                    original_assessment["incoming_include_candidates"],
                "outgoing_include_candidates":
                    original_assessment["outgoing_include_candidates"],
                "resolved_include_candidates":
                    original_assessment["resolved_include_candidates"],
                "ambiguous_include_candidates":
                    original_assessment["ambiguous_include_candidates"],
                "unresolved_include_candidates":
                    original_assessment["unresolved_include_candidates"],
                "source": "ORIGINAL_HASH_VERIFIED_MACHINE_DOSSIER_NOT_SEMANTIC_REVIEW",
            },
            "source_index_state": "SOURCE_INDEXED",
            "source_index_reason_code": "SOURCE_BLOB_AND_DOSSIER_VERIFIED",
            "semantic_review_state": "NOT_SEMANTICALLY_REVIEWED",
            "approval_state": "NOT_APPROVED",
            "direct_dependency_state": (
                "LEXICAL_INCLUDE_CANDIDATES_INCOMPLETE_OR_UNRESOLVED"
                if unresolved or entry["facts"]["unsupported_include_lines"]
                or not entry["facts"]["direct_include_scan_complete"]
                else (
                    "LITERAL_INCLUDE_CANDIDATES_INDEXED"
                    if entry["facts"]["direct_include_literals"]
                    else "NO_SUPPORTED_LITERAL_INCLUDE_DECLARATIONS_FOUND"
                )
            ),
            "direct_dependency_unresolved_count": unresolved,
            "unsupported_include_declaration_lines":
                entry["facts"]["unsupported_include_lines"],
            "unsupported_include_scan_truncated":
                entry["facts"]["unsupported_include_scan_truncated"],
            "direct_include_scan_complete":
                entry["facts"]["direct_include_scan_complete"],
            "direct_dependencies": references,
            "repository_evidence_catalog_id":
                repo_catalog[repo]["catalog_id"],
            "evidence_role_codes": roles,
        })

    test_source_keys = {
        _row_key(repo, path)
        for repo, catalog in repo_catalog.items()
        for path in catalog["verified_test_source_paths"]
    }
    incoming_by_target: dict[str, list[dict]] = {}
    for edge in all_edge_rows:
        source_repo, _ = edge["from"].split(":", 1)
        for candidate in edge["candidate_target_paths"]:
            target_key = _row_key(source_repo, candidate)
            incoming_by_target.setdefault(target_key, []).append(edge)
    for record in source_records:
        identity = record["identity"]
        record_key = _row_key(identity["repository"], identity["path"])
        incoming = incoming_by_target.get(record_key, [])
        record["incoming_include_candidate_count"] = len(incoming)
        record["incoming_include_candidates"] = [
            {
                "source_path": edge["from"].split(":", 1)[1],
                "line": edge["line"],
                "literal": edge["literal"],
                "resolution": edge["resolution"],
            }
            for edge in incoming[:32]
        ]
        record["incoming_include_candidates_truncated"] = len(incoming) > 32
        test_users = sorted({
            edge["from"] for edge in incoming
            if edge["from"] in test_source_keys
        })
        record["upstream_test_source_candidates"] = [
            source_key.split(":", 1)[1] for source_key in test_users[:32]
        ]
        record["upstream_test_source_candidate_count"] = len(test_users)
        record["test_link_state"] = _test_link_state(
            test_users,
            repo_catalog[identity["repository"]]["verified_test_source_paths"],
        )

    indexed_keys = set(indexed)
    for row in queue:
        key = _row_key(row["repo"], row["path"])
        if key in indexed_keys or key in blocked:
            continue
        blocked[key] = "UNINDEXED_NOT_SELECTED_IN_THIS_BATCH"

    indexed_rows = [rows_by_key[key] for key in indexed_keys]
    p0_total = sum(row["priority"] == "P0" for row in queue)
    indexed_p0 = sum(row["priority"] == "P0" for row in indexed_rows)
    reason_counts = {}
    for reason in blocked.values():
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    all_edge_rows.sort(key=lambda edge: (
        edge["from"], edge["line"], edge["literal"], edge["resolution"],
    ))
    for catalog in repo_catalog.values():
        for name in (
            "verified_test_source_paths",
            "verified_document_paths",
            "license_file_paths",
        ):
            catalog[name].sort()
        catalog["license_assessment"] = _license_assessment(catalog)
        catalog["test_source_evidence_state"] = (
            "HASH_VERIFIED_TEST_SOURCE_FILES_PRESENT_NOT_EXECUTED"
            if catalog["verified_test_source_paths"]
            else (
                "TEST_PATHS_IN_INVENTORY_NOT_YET_SOURCE_VERIFIED"
                if catalog["inventory_test_path_count"]
                else "BLOCKED_NO_TEST_PATH_IN_INVENTORY"
            )
        )
        if not catalog["license_file_paths"] and catalog["inventory_license_candidate_paths"]:
            catalog["license_assessment"] = {
                "state": "LICENSE_CANDIDATES_IN_INVENTORY_NOT_YET_SOURCE_VERIFIED",
                "reason_code": "LICENSE_EVIDENCE_NOT_YET_INDEXED",
                "inventory_candidate_paths": catalog["inventory_license_candidate_paths"],
                "distribution_clearance": "NOT_ASSESSED",
            }
    _validate_license_boundary(repo_catalog)
    claims = [{
        "claim_id": "source-index-inventory",
        "reference_ids": [],
        "evidence_level": "PINNED_SOURCE_IDENTITY_ONLY",
    }]
    _validate_no_unsupported_inference(UNVERIFIED_EXTERNAL_REFERENCES, claims)

    output_doc = {
        "schema": OUTPUT_SCHEMA,
        "status": "SOURCE_INDEX_ONLY_NO_SEMANTIC_DISPOSITIONS",
        "snapshot_identity": snapshot_identity,
        "gate": {
            "decision": gate["decision"],
            "inventory_total": TOTAL,
            "p0_total": p0_total,
            "legacy_approvals": 0,
            "semantic_dispositions_added": 0,
        },
        "run": {
            "batch_offset": offset,
            "batch_limit": limit,
            "batch_selected": len(batch),
            "cache_entries_loaded": len(cache),
            "cache_entries_revalidated": cache_revalidated,
            "indexed_count": len(indexed_keys),
            "unindexed_count": sum(
                reason == "UNINDEXED_NOT_SELECTED_IN_THIS_BATCH"
                for reason in blocked.values()
            ),
            "blocked_count": sum(
                reason != "UNINDEXED_NOT_SELECTED_IN_THIS_BATCH"
                for reason in blocked.values()
            ),
            "indexed_p0_count": indexed_p0,
            "indexed_by_repository": {
                repo: sum(row["repo"] == repo for row in indexed_rows)
                for repo in PINS
            },
            "indexed_by_inventory_category": {
                category: sum(row["category"] == category for row in indexed_rows)
                for category in sorted({row["category"] for row in indexed_rows})
            },
            "dependency_edge_count": len(all_edge_rows),
            "dependency_edges_by_resolution": {
                resolution: sum(edge["resolution"] == resolution for edge in all_edge_rows)
                for resolution in sorted({edge["resolution"] for edge in all_edge_rows})
            },
            "unindexed_and_blocked_reason_counts": dict(sorted(reason_counts.items())),
            "cache_max_bytes": MAX_CACHE_BYTES,
            "cache_is_not_semantic_evidence": True,
        },
        "source_records": sorted(
            source_records,
            key=lambda record: (
                record["identity"]["repository"], record["identity"]["path"],
            ),
        ),
        "dependency_edges": all_edge_rows,
        "blocked_or_unindexed_records": [
            {
                "repository": row["repo"],
                "pinned_commit": PINS[row["repo"]],
                "path": row["path"],
                "git_blob_sha1": row["blob_sha"],
                "machine_dossier_sha256": row["evidence_sha256"],
                "state": (
                    "UNINDEXED" if blocked[_row_key(row["repo"], row["path"])]
                    == "UNINDEXED_NOT_SELECTED_IN_THIS_BATCH" else "BLOCKED"
                ),
                "reason_code": blocked[_row_key(row["repo"], row["path"])],
                "semantic_review_state": "NOT_SEMANTICALLY_REVIEWED",
                "approval_state": "NOT_APPROVED",
            }
            for row in queue
            if _row_key(row["repo"], row["path"]) in blocked
        ],
        "repository_evidence_catalog": repo_catalog,
        "external_references": UNVERIFIED_EXTERNAL_REFERENCES,
        "evidence_boundaries": [
            "Source-indexed means exact pinned Git blob and original machine dossier identity checked.",
            "Dependency edges are literal C-preprocessor or assembler include candidates, not compiler closure.",
            "Incoming include candidates are not a call graph, data-flow, reader/writer, or execution analysis.",
            "No source-defined semantic invariants are automatically extracted by this index.",
            "Test paths prove hash-verified upstream test-source presence only, not relevance or execution.",
            "Direct test include links are candidate links only and do not establish coverage.",
            "Documentation identity does not establish semantic accuracy.",
            "License files and notices do not establish distribution clearance.",
            "GBATEK and NBA references are unverified and support no claim.",
            "No record is semantically reviewed or approved by this indexer.",
        ],
    }
    raw_output = canonical(output_doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(raw_output, mtime=0))
    elapsed = time.monotonic() - started
    print(json.dumps({
        "inventory": TOTAL,
        "batch_selected": len(batch),
        "indexed": len(indexed_keys),
        "unindexed": output_doc["run"]["unindexed_count"],
        "blocked": output_doc["run"]["blocked_count"],
        "indexed_p0": indexed_p0,
        "p0_total": p0_total,
        "dependency_edges": len(all_edge_rows),
        "cache_entries_revalidated": cache_revalidated,
        "elapsed_seconds": round(elapsed, 3),
        "records_per_second": round(len(batch) / elapsed, 1) if elapsed else None,
        "gate": gate["decision"],
        "approvals": 0,
        "output_sha256": digest(output.read_bytes()),
    }, sort_keys=True))
    return output_doc


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "semantic-snapshots/current")
    parser.add_argument("--source-roots", type=Path, required=True,
                        help="Directory containing extracted, pinned upstream repository trees")
    parser.add_argument("--cache", type=Path, default=Path.home() /
                        ".cache/xgba/phase1-inventory-source-cache.json.gz")
    parser.add_argument("--output", type=Path, default=ROOT /
                        "docs/phase1-review-readiness/inventory-source-index-20261101.json.gz")
    parser.add_argument("--offset", type=int, default=0,
                        help="Skip this many currently unindexed records in priority order")
    parser.add_argument("--limit", type=int, default=2000,
                        help="Maximum new inventory records to process in this incremental batch")
    args = parser.parse_args()
    if args.offset < 0 or args.limit < 1 or args.limit > 2000:
        parser.error("offset must be nonnegative and limit must be in [1, 2000]")
    build_index(
        args.snapshot, args.source_roots, args.cache, args.output,
        offset=args.offset, limit=args.limit,
    )


if __name__ == "__main__":
    _main()

#!/usr/bin/env python3
"""Validate one source-pinned, non-approving mapjson build-objection record."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = (
    ROOT
    / "development/copilot-integration/"
    "mapjson-build-dependency-objection-20261107.json"
)
QUEUE_PATH = ROOT / "semantic-snapshots/current/semantic_review_queue.csv.gz"
DOSSIERS_PATH = (
    ROOT / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
)
MANIFEST_PATH = ROOT / "development/copilot-integration/manifest.json"
TRIAGE_PATH = ROOT / "development/copilot-integration/blocker-triage-20261104.json"
REPOSITORY = "pret/pokefirered"
REVISION = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
EXPECTED_PATHS = {
    "Makefile",
    "make_tools.mk",
    "map_data_rules.mk",
    "tools/mapjson/Makefile",
    "tools/mapjson/mapjson.cpp",
    "tools/mapjson/mapjson.h",
    "tools/mapjson/json11.cpp",
    "tools/mapjson/json11.h",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return _sha256(encoded)


def load_reference(root: Path = ROOT) -> dict:
    queue_path = root / QUEUE_PATH.relative_to(ROOT)
    dossiers_path = root / DOSSIERS_PATH.relative_to(ROOT)
    with gzip.open(queue_path, "rt", encoding="utf-8", newline="") as stream:
        queue = {
            row["path"]: row
            for row in csv.DictReader(stream)
            if row.get("repo") == REPOSITORY and row.get("path") in EXPECTED_PATHS
        }

    dossiers = {}
    with gzip.open(dossiers_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if provenance.get("repository") == REPOSITORY and path in EXPECTED_PATHS:
                dossiers[path] = row

    manifest_path = root / MANIFEST_PATH.relative_to(ROOT)
    triage_path = root / TRIAGE_PATH.relative_to(ROOT)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    triage = json.loads(triage_path.read_text(encoding="utf-8"))
    return {
        "queue": queue,
        "dossiers": dossiers,
        "manifest": manifest,
        "triage": triage,
        "source_hashes": {
            str(path.relative_to(root)): _sha256(path.read_bytes())
            for path in (
                queue_path,
                dossiers_path,
                manifest_path,
                triage_path,
            )
        },
    }


def validate_source_objection(evidence: dict, reference: dict) -> list[str]:
    findings = []
    if not isinstance(evidence, dict):
        return ["evidence record must be a JSON object"]
    if evidence.get("schema") != "xgba.phase1.source-objection-evidence.v1":
        findings.append("unsupported evidence schema")
    if evidence.get("case_id") != "MAPJSON-INCREMENTAL-HEADER-DEPENDENCY-20261107":
        findings.append("unexpected objection case identity")
    if evidence.get("source_registry", {}).get("repository") != REPOSITORY:
        findings.append("source repository identity mismatch")
    if evidence.get("source_registry", {}).get("revision") != REVISION:
        findings.append("source revision mismatch")
    if evidence.get("source_registry", {}).get("queue_sha256") != reference[
        "source_hashes"
    ].get("semantic-snapshots/current/semantic_review_queue.csv.gz"):
        findings.append("source queue archive hash mismatch")
    if evidence.get("source_registry", {}).get("dossiers_sha256") != reference[
        "source_hashes"
    ].get("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"):
        findings.append("source dossier archive hash mismatch")
    if evidence.get("source_registry", {}).get("manifest_sha256") != reference[
        "source_hashes"
    ].get("development/copilot-integration/manifest.json"):
        findings.append("integration manifest hash mismatch")
    if evidence.get("source_registry", {}).get("triage_sha256") != reference[
        "source_hashes"
    ].get("development/copilot-integration/blocker-triage-20261104.json"):
        findings.append("immutable blocker triage hash mismatch")

    source_files = evidence.get("source_files")
    if not isinstance(source_files, list):
        source_files = []
        findings.append("source file identities are missing")
    paths = [row.get("path") for row in source_files if isinstance(row, dict)]
    if len(paths) != len(set(paths)):
        findings.append("source file identities contain duplicates")
    if set(paths) != EXPECTED_PATHS:
        findings.append("source file and caller/dependency closure is incomplete")

    queue = reference.get("queue", {})
    dossiers = reference.get("dossiers", {})
    if set(queue) != EXPECTED_PATHS or set(dossiers) != EXPECTED_PATHS:
        findings.append("pinned source registry does not cover the expected closure")
    for source in source_files:
        if not isinstance(source, dict):
            findings.append("source file identity is malformed")
            continue
        path = source.get("path")
        queued = queue.get(path)
        dossier = dossiers.get(path)
        if queued is None or dossier is None:
            findings.append("%s is absent from the pinned queue or dossier" % path)
            continue
        provenance = dossier.get("provenance", {})
        expected = {
            "git_blob_sha": queued.get("blob_sha"),
            "source_sha256": provenance.get("source_content_sha256"),
            "dossier_sha256": _canonical_sha256(dossier),
            "priority": queued.get("priority"),
            "machine_status": queued.get("machine_review_status"),
        }
        for key, value in expected.items():
            if source.get(key) != value:
                findings.append("%s %s differs from pinned registry" % (path, key))
        if provenance.get("pinned_revision") != REVISION:
            findings.append("%s dossier revision differs from pinned source" % path)
        if queued.get("evidence_sha256") != expected["dossier_sha256"]:
            findings.append("%s original dossier hash does not match queue" % path)

    blocker = evidence.get("related_integration_blocker", {})
    blocker_row = next(
        (
            row
            for row in reference.get("triage", {}).get("blockers", [])
            if row.get("id") == "B010"
        ),
        None,
    )
    if blocker_row is None:
        findings.append("original B010 triage record is unavailable")
    else:
        if blocker.get("original_triage_row_sha256") != _canonical_sha256(blocker_row):
            findings.append("B010 triage-row fingerprint mismatch")
        if (
            blocker.get("id") != "B010"
            or blocker.get("pr_number") != 7
            or blocker.get("category") != "stale_main_base"
            or blocker.get("disposition") != "BLOCKED"
        ):
            findings.append("related blocker identity or blocked disposition changed")
        if (
            blocker.get("manifest_head_sha") != blocker_row.get("manifest_head_sha")
            or blocker.get("manifest_base_sha") != blocker_row.get("manifest_base_sha")
            or blocker.get("manifest_base_ref") != blocker_row.get("manifest_base_ref")
        ):
            findings.append("B010 immutable manifest identity mismatch")
        manifest_row = next(
            (
                row
                for row in reference.get("manifest", {}).get("pull_requests", [])
                if row.get("number") == 7
            ),
            None,
        )
        if manifest_row is None:
            findings.append("PR #7 manifest pin is unavailable")
        else:
            if (
                (manifest_row.get("head") or {}).get("sha")
                != blocker.get("manifest_head_sha")
                or (manifest_row.get("base") or {}).get("sha")
                != blocker.get("manifest_base_sha")
            ):
                findings.append("B010 manifest row differs from original triage")

    objection = evidence.get("objection", {})
    if (
        objection.get("id") != "MAPJSON-MAKEFILE-OMITS-JSON11-HEADER"
        or objection.get("status") != "NEEDS_EVIDENCE"
        or objection.get("source_lines")
        != [
            {"path": "tools/mapjson/Makefile", "lines": "5-7,20"},
            {"path": "tools/mapjson/mapjson.cpp", "lines": "27-30"},
            {"path": "tools/mapjson/json11.cpp", "lines": "20-21"},
        ]
    ):
        findings.append("objection identity, source scope, or NEEDS_EVIDENCE status changed")
    edges = evidence.get("dependency_edges", [])
    if not any(
        edge.get("from") == "tools/mapjson/Makefile:5-7,20"
        and edge.get("to") == "tools/mapjson/json11.h"
        and "missing prerequisite" in edge.get("relation", "")
        for edge in edges
        if isinstance(edge, dict)
    ):
        findings.append("missing json11.h build-prerequisite objection is absent")

    licensing = evidence.get("licensing", {})
    if (
        licensing.get("json11", {}).get("status")
        != "MIT_NOTICE_PRESENT_IN_PINNED_SOURCE"
        or licensing.get("distribution_clearance") != "NEEDS_EVIDENCE"
        or licensing.get("mapjson_component", {}).get("status") != "NEEDS_EVIDENCE"
    ):
        findings.append("licensing evidence was removed or over-promoted")

    host = evidence.get("host_synthetic_validation", {})
    transcript = host.get("transcript")
    if (
        host.get("classification") != "HOST_SYNTHETIC"
        or host.get("source_mutation_in_repository") is not False
        or host.get("pinned_makefile", {}).get(
            "exit_code_after_temporary_json11_header_change"
        ) != 0
        or host.get("negative_control", {}).get("exit_code") != 1
        or not isinstance(transcript, list)
        or host.get("transcript_sha256") != _canonical_sha256(transcript)
    ):
        findings.append("host-synthetic transcript is incomplete, changed, or unbound")
    if any(
        evidence.get("unverified", {}).get(key) is not True
        for key in (
            "clean_full_firered_rom_build",
            "arm_target_build",
            "runtime_gameplay",
            "save_restart_or_physical_flash",
            "independent_whole_file_disposition",
            "source_component_license_clearance",
        )
    ):
        findings.append("unsupported native, runtime, license, or review state was promoted")

    phase1 = evidence.get("phase1", {})
    if (
        phase1.get("gate") != "FAIL_INCOMPLETE"
        or phase1.get("approved_dispositions") != 0
        or phase1.get("p0_approved_dispositions") != 0
        or phase1.get("disposition") != "NEEDS_EVIDENCE"
        or phase1.get("blocker_b010") != "BLOCKED"
        or phase1.get("blockers_resolved") != 0
        or phase1.get("semantic_approval_from_host_or_ci") is not False
        or phase1.get("source_pins_changed") is not False
    ):
        findings.append("Phase 1 gate, approval totals, or blocker state was promoted")
    return sorted(set(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        reference = load_reference(args.root)
        findings = validate_source_objection(evidence, reference)
    except (OSError, ValueError, KeyError, TypeError) as error:
        findings = ["unable to load source-objection evidence: %s" % error]
    report = {
        "evidence_validation": "INVALID" if findings else "VALID_NOT_APPROVED",
        "disposition": "NEEDS_EVIDENCE",
        "related_blocker": "B010",
        "related_blocker_status": "BLOCKED",
        "phase1_gate": "FAIL_INCOMPLETE",
        "approved_dispositions": 0,
        "findings": findings,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

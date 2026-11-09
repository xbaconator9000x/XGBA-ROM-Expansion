#!/usr/bin/env python3
"""Build a fail-closed, non-approving mGBA observer receipt-eligibility report."""
import argparse
import importlib.util
import json
import re
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
BRANCH = "phase1/mgba-savedata-boundary-witness-20261027"
WORKFLOW_ID = 398059096
MANIFEST = (
    "docs/phase1-review-readiness/"
    "mgba-observer-receipt-eligibility-20261105.json"
)
CROSS_MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-cross-backend-save-observability-20261105.json"
)
PLATFORM_MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-platform-save-observer-closure-20261105.json"
)
HANDOFF_MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-fault-to-observer-handoff-20261105.json"
)
RECEIPT_STATUS = "COPILOT_REVIEWED/PASSED"


def expected_manifest():
    return {
        "schema": "phase1.mgba.observer-receipt-eligibility.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "source_matrix": CROSS_MATRIX,
        "platform_matrix": PLATFORM_MATRIX,
        "observer_handoff": HANDOFF_MATRIX,
        "source_record_contract": {
            "matrix_field": "reviewed_new_files",
            "expected_distinct_records": 16,
            "required_source_disposition": "reviewed_source_only",
            "coverage": "complete_file_bytes_hash_and_anchored_source_review",
        },
        "attribution_contract": {
            "reviewer": "Copilot",
            "scope": "per_file_source_only",
            "independent": False,
            "required_for_receipt_eligibility": True,
            "user_override_status": RECEIPT_STATUS,
            "github_independent_review_id": None,
        },
        "ci_contract": {
            "workflow_id": WORKFLOW_ID,
            "branch": BRANCH,
            "required_events": ["pull_request", "push"],
            "required_conclusion": "success",
            "same_exact_head": True,
            "evidence_input": (
                "normalized GitHub Actions API metadata; field validation does "
                "not authenticate the evidence source"
            ),
        },
        "non_approval_contract": {
            "independent_approval": False,
            "historical_gate_mutated": False,
            "dirty_to_clean_means_durable_save": False,
            "frontend_delivery_observed": False,
            "native_frontend_observed": False,
            "physical_flash_or_power_loss_evidence": False,
        },
    }


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_module(root, relative_path, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, Path(root) / relative_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_manifest(manifest):
    require(manifest == expected_manifest(),
            "receipt eligibility manifest differs from the fail-closed contract")
    return True


def validate_source_matrices(cross, platform, handoff):
    root = Path(__file__).resolve().parents[1]
    cross_runner = load_module(
        root, "tools/phase1_mgba_cross_backend_observability.py",
        "phase1_mgba_cross_backend_observability_contract",
    )
    platform_runner = load_module(
        root, "tools/phase1_mgba_platform_observer_closure.py",
        "phase1_mgba_platform_observer_closure_contract",
    )
    handoff_runner = load_module(
        root, "tools/phase1_mgba_fault_observer_handoff.py",
        "phase1_mgba_fault_observer_handoff_contract",
    )
    cross_runner.validate_matrix_payload(cross)
    platform_runner.validate_matrix_payload(platform)
    handoff_runner.validate_matrix_payload(handoff)


def validate_ci_evidence(evidence, head_sha):
    if evidence is None:
        return False, [
            "missing_exact_head_pull_request_run",
            "missing_exact_head_push_run",
        ]
    require(isinstance(evidence, dict),
            "CI evidence must be an object containing pull_request and push")
    require(set(evidence) <= {"pull_request", "push"},
            "CI evidence contains unsupported event records")
    problems = []
    for event in ("pull_request", "push"):
        run = evidence.get(event)
        if not isinstance(run, dict):
            problems.append("missing_exact_head_%s_run" % event)
            continue
        require(set(run) == {
            "event", "head_sha", "branch", "workflow_id", "conclusion", "run_id"
        }, "CI run record has missing or unsupported fields: " + event)
        if run.get("event") != event:
            problems.append("wrong_event_for_%s_run" % event)
        if run.get("head_sha") != head_sha:
            problems.append("stale_or_wrong_head_%s_run" % event)
        if run.get("branch") != BRANCH:
            problems.append("wrong_branch_for_%s_run" % event)
        if run.get("workflow_id") != WORKFLOW_ID:
            problems.append("wrong_workflow_for_%s_run" % event)
        if run.get("conclusion") != "success":
            problems.append("unsuccessful_%s_run" % event)
        run_id = run.get("run_id")
        if type(run_id) is not int or run_id <= 0:
            problems.append("invalid_%s_run_id" % event)
    if isinstance(evidence.get("pull_request"), dict) and isinstance(
        evidence.get("push"), dict
    ):
        if evidence["pull_request"].get("run_id") == evidence["push"].get("run_id"):
            problems.append("pr_and_push_must_be_distinct_runs")
    return not problems, problems


def _license_caveat(item):
    if item["path"] == "src/platform/libretro/libretro.h":
        return (
            "The pinned API header carries its MIT notice; preserve it alongside "
            "the repository-level mGBA MPL-2.0 notice in combined distributions."
        )
    if item["path"] == "src/platform/python/_builder.py":
        return (
            "No embedded notice is present; the source matrix records the "
            "repository-level MPL-2.0 license."
        )
    return (
        "Preserve the pinned file's MPL-2.0 notice and repository license when "
        "redistributing; no upstream source is copied into this report."
    )


def build_report(manifest, cross, platform, handoff, head_sha, ci_evidence=None):
    validate_manifest(manifest)
    validate_source_matrices(cross, platform, handoff)
    require(cross.get("pinned_revision") == PIN,
            "cross-backend source matrix has the wrong upstream pin")
    require(platform.get("pinned_revision") == PIN,
            "platform matrix has the wrong upstream pin")
    require(handoff.get("pinned_revision") == PIN,
            "observer handoff has the wrong upstream pin")
    require(isinstance(head_sha, str) and re.fullmatch(r"[0-9a-f]{40}", head_sha),
            "an exact 40-character lowercase head SHA is required")
    files = cross.get("reviewed_new_files")
    require(isinstance(files, list) and len(files) == 16,
            "expected exactly 16 previously reviewed complete-file records")
    paths = [item.get("path") for item in files]
    require(len(set(paths)) == len(paths) and None not in paths,
            "source review records must be distinct and path-addressable")
    ci_ok, ci_problems = validate_ci_evidence(ci_evidence, head_sha)
    records = []
    for item in sorted(files, key=lambda source: source["path"]):
        require(item.get("review_disposition") == "reviewed_source_only",
                "unsupported source disposition: " + str(item.get("path")))
        edges = [
            edge for edge in cross["edges"]
            if item["path"] in edge.get("source_refs", [])
        ]
        objections = [
            "No independent per-file GitHub review attribution is present.",
            "The record is a pinned-source review, not runtime or persistence evidence.",
        ]
        if not ci_ok:
            objections.extend(ci_problems)
        if any(edge.get("execution") == "source_review_only" for edge in edges):
            objections.append(
                "At least one linked observer edge is source-only; frontend "
                "delivery remains NEEDS_EVIDENCE."
            )
        records.append({
            "path": item["path"],
            "source_identity": {
                "upstream_revision": PIN,
                "git_blob_sha": item["git_blob_sha"],
                "source_sha256": item["source_sha256"],
                "dossier_row_sha256": item["dossier_row_sha256"],
                "dossier_archive_sha256": cross["machine_dossier"]["sha256"],
            },
            "coverage": "complete_file_bytes_hash_and_anchored_source_review",
            "license": item["license"],
            "licensing_caveat": _license_caveat(item),
            "dependency_closure": {
                "observer_edges": [
                    {
                        "id": edge["id"],
                        "classification": edge["classification"],
                        "execution": edge["execution"],
                        "source_refs": edge["source_refs"],
                    }
                    for edge in edges
                ],
                "reused_sources": [
                    source["path"] for source in cross["reused_prior_sources"]
                    if any(
                        source["path"] in edge.get("source_refs", [])
                        for edge in edges
                    )
                ],
            },
            "substantive_objections": objections,
            "reviewer_attribution": {
                "reviewer": "Copilot",
                "review_scope": "per_file_source_only",
                "independent": False,
                "github_independent_review_id": None,
            },
            "source_review_status": RECEIPT_STATUS,
            "receipt_eligible": False,
            "eligibility_blockers": [
                "independent_per_file_attribution_missing",
                *([] if ci_ok else ci_problems),
            ],
            "independent_approval": False,
        })

    frontend_paths = [
        {
            "id": item["id"],
            "status": "NEEDS_EVIDENCE",
            "source_review_result": item["result"],
            "execution": item["execution"],
            "objection": item["objection"],
        }
        for item in handoff["path_objections"]
        if item["id"] in {"qt", "sdl", "libretro", "python", "headless"}
    ]
    platform_paths = [
        {
            "id": item["id"],
            "status": "NEEDS_EVIDENCE",
            "observer_route": item["observer_route"],
            "shutdown_route": item["shutdown_route"],
            "classification": item["classification"],
            "selected_vfile_backend": item["selected_vfile_backend"],
            "execution": "pinned_source_only_no_platform_runtime",
        }
        for item in platform["platform_paths"]
    ]
    all_eligible = bool(records) and all(record["receipt_eligible"] for record in records)
    return {
        "schema": "phase1.mgba.observer-receipt-eligibility-report.v1",
        "repository": "mgba-emu/mgba",
        "upstream_revision": PIN,
        "branch": BRANCH,
        "head_sha": head_sha,
        "source_records": records,
        "unresolved_frontend_observers": frontend_paths,
        "unresolved_platform_observers": platform_paths,
        "ci_evidence": {
            "required_events": ["pull_request", "push"],
            "same_exact_head": True,
            "descriptor_consistent_with_contract": ci_ok,
            "runs": ci_evidence if ci_ok else None,
            "blockers": ci_problems,
        },
        "eligibility": {
            "status": "COPILOT_REVIEWED/PASSED" if all_eligible else "FAIL_INCOMPLETE",
            "candidate_records": len(records),
            "eligible_records": sum(record["receipt_eligible"] for record in records),
            "independent_approvals_claimed": 0,
            "historical_gate_mutated": False,
        },
        "evidence_limits": {
            "native_class": handoff["native_witness"]["native_class"],
            "github_api_evidence_source_authenticated": False,
            "native_frontend_delivery_observed": False,
            "dirty_to_clean_is_persistence_acknowledgment": False,
            "persistence_result_observed": False,
            "physical_flash_or_power_loss_evidence": False,
            "stock_game_or_save_file_claim": False,
            "external_human_review_claimed": False,
        },
    }


def validate_report(report, manifest, cross, platform, handoff, head_sha,
                    ci_evidence=None):
    expected = build_report(
        manifest, cross, platform, handoff, head_sha, ci_evidence
    )
    require(report == expected,
            "receipt report contains unsupported or mismatched eligibility claims")
    return True


def verify_sources(source_root, repo_root, checkout_identity):
    root = Path(repo_root)
    cross = load_module(
        root, "tools/phase1_mgba_cross_backend_observability.py",
        "phase1_mgba_cross_backend_observability_for_receipts",
    )
    platform = load_module(
        root, "tools/phase1_mgba_platform_observer_closure.py",
        "phase1_mgba_platform_observer_closure_for_receipts",
    )
    handoff = load_module(
        root, "tools/phase1_mgba_fault_observer_handoff.py",
        "phase1_mgba_fault_observer_handoff_for_receipts",
    )
    cross_matrix = load_json(root / CROSS_MATRIX)
    platform_matrix = load_json(root / PLATFORM_MATRIX)
    handoff_matrix = load_json(root / HANDOFF_MATRIX)
    cross.verify_sources(
        source_root, root, root / CROSS_MATRIX, checkout_identity
    )
    platform.verify_sources(
        source_root, root, root / PLATFORM_MATRIX, checkout_identity
    )
    handoff.verify(
        source_root, root, root / HANDOFF_MATRIX, checkout_identity
    )
    return cross_matrix, platform_matrix, handoff_matrix


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkout", help="exact pinned mGBA source checkout")
    source.add_argument("--source-dir", help="individually verified source files")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--head-sha", required=True, help="exact XGBA PR branch head")
    parser.add_argument("--ci-evidence", help="JSON with exact-head PR and push runs")
    parser.add_argument("--output", help="optional path to write deterministic JSON")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    source_root = args.checkout or args.source_dir
    cross, platform, handoff = verify_sources(
        source_root, root, bool(args.checkout)
    )
    manifest = load_json(root / MANIFEST)
    evidence = load_json(args.ci_evidence) if args.ci_evidence else None
    report = build_report(
        manifest, cross, platform, handoff, args.head_sha, evidence
    )
    validate_report(
        report, manifest, cross, platform, handoff, args.head_sha, evidence
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()

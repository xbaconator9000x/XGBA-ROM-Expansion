# Phase 1 review-readiness packets — machine-only handoff

The packet generator consumes exact-pinned, source-verified machine-triage shards and requires their upstream integrity manifest, including per-shard SHA-256 hashes. It produces a deterministic P0-first queue of review obligations. Source hashes, line counts, lexical include anchors and risk flags are carried through without asserting whole-file semantic understanding.

An include edge is a **candidate lexical match**, not proof of actual preprocessor resolution. Ambiguous, invalid and unresolved include names are preserved for review. A match cannot establish cross-repository compatibility, runtime behaviour, external consumers, build variants or source-code correctness.

After the source-verification workflow has committed the complete 2,000-file integrity manifest, run:

```sh
python3 -m unittest discover -s tests -p test_phase1_review_packets.py -v
python3 tools/phase1_bulk_triage_integrity.py
python3 tools/phase1_review_packets.py --max-packets 100 --output docs/phase1-review-readiness/packet-0000-0099.json
```

The ten positive/negative controls cover duplicate identities, wrong source hashes, fabricated approvals, unverified sources, invalid offsets, ambiguous include resolution and missing/tampered integrity evidence. The generator fails closed when the required upstream reconciliation has not completed. The output must not be committed or reported as source-verified without checking the complete manifest and exact-head CI.

## Consolidated Phase 1 PR checks

The `phase1-pr-checks.yml` entry point invokes the 40 Phase 1 checks that previously ran as separate PR workflows for this stacked branch, plus the pinned-source census as a reusable workflow. Their validation jobs and read-only permissions are unchanged; the census checks out the exact PR head. The forty child workflows no longer have duplicate direct PR or branch-push triggers. Five unrelated path-filtered workflows are not part of this consolidation. The entry point runs for pull requests targeting `phase1/firered-layout-writers-20261026`.

This only consolidates CI orchestration. It does not approve the run, waive GitHub's workflow-approval requirement, count as semantic review, or bypass repository rules. Before merging this change, maintainers must verify the protected branch's required status checks: if it requires former individual check names, update that requirement through the normal protected-branch process to require the consolidated entry point. Do not merge if the new check is not enforced equivalently. Review and merge this workflow change through the existing protected PR process; do not treat it as trusted before merge.

**Counting:** review packets are not substantively prepared whole-file dispositions, independent approvals or a Phase 1 pass. At this checkpoint, the last confirmed baseline is **113/14,834 prepared (0.7618%)**, **0/14,834 approved (0.0000%)**, **14,834/14,834 inventoried (100%)**, gate **FAIL_INCOMPLETE**. Machine triage is separate. A qualifying reviewer must examine each complete pinned file and resolve or explicitly bound its dependencies.

## Evidence-qualified Copilot receipts

The [Phase 1 mapping gate](../../tools/phase1_mapping_gate.py) reads optional per-file Copilot receipts from `copilot-semantic-review-receipts.jsonl`. No receipt file is currently present, and no approval is inferred. Legacy CSV dispositions require independently verifiable GitHub review provenance; a reviewer-name string alone is not an approval.

Each JSONL object must use schema `xgba.phase1.copilot_semantic_review_receipt.v2` and contain `source`, `machine_dossier_sha256`, `review`, `target`, and `attestation`. `source` binds one inventory item to its immutable repository, revision, path, Git blob SHA-1, and source SHA-256. `review` must contain an `APPROVED` semantic decision, source-grounded findings and substantive rationale, complete whole-file line coverage, a verified dependency closure, cleared licensing with pinned evidence, six distinct evidence states, per-item dossier/substantive-evidence file hashes and GitHub-authenticated authorship, and no unresolved objections. Dependency and licensing references use the same pinned source-identity shape. `target` binds a PR number and exact head SHA.

The six `review.evidence_distinctions` categories are `source`, `synthetic`, `compiled_native`, `runtime_gameplay`, `save_restart`, and `physical_flash`. Each non-source category must explicitly be `VERIFIED`, `NOT_APPLICABLE`, `NOT_CLAIMED`, or `NOT_RUN`; non-source `VERIFIED` claims currently fail closed until a trusted verifier can retrieve immutable artifact bytes and recompute their hashes. A not-run/unclaimed category needs a reason.

The durable GitHub review is the attribution: before the review, set `attestation.receipt_sha256` to the canonical SHA-256 of the receipt with the `attestation` property omitted. A **COMMENTED** review by the GitHub `Copilot` actor must target the exact current PR head and include both `XGBA-Phase1-Receipt-SHA256: <digest>` and `XGBA-Phase1-Decision: APPROVED`. The gate independently verifies the GitHub PR author/reviewer identities, per-item evidence file hashes/authors, original source and dossier bytes, and a successful exact-head `Phase 1 consolidated PR checks` run that references the pinned-source census reusable workflow. The consolidated run's success is not semantic approval; the receipt must independently pass validation in the gate. A GitHub review does not itself approve the PR's code.

Because a workflow run cannot attest to its own completed success, the initial exact-head consolidated run may leave a complete receipt uncounted. Re-run the consolidated workflow at the unchanged head after that run completes successfully; a new commit makes the review stale. The validator fails closed on missing identity/attestation, wrong or stale hashes, partial coverage, unresolved dependencies/licensing/objections, unsupported or unverified evidence claims, reviewer/dossier-author conflict, duplicate dispositions, or missing exact-head validation.

Legacy CSV dispositions also require a `reviewer_provenance` JSON field binding the reviewer login, repository, PR, review ID, reviewed head, and canonical disposition hash to a **COMMENTED** GitHub review containing `XGBA-Phase1-Legacy-Disposition-SHA256: <digest>` and the explicit decision marker. Existing historical records are not rewritten; records without this independently verifiable attribution do not count as approvals.

Tests: `python3 -m unittest discover -s tests -p test_phase1_copilot_receipts.py -v` and `python3 -m unittest discover -s tests -p test_phase1_mapping_gate.py -v`.

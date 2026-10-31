# Phase 1 Copilot review receipt verifier v1 — standalone proposal

**Status: proposal/test infrastructure only. It is not integrated into a Phase 1 gate, does not create a review, and cannot change any approval count or `FAIL_INCOMPLETE` decision.** The synthetic positive fixture is a validator test, not a source review.

## Policy source and branch boundary

This proposal was specified against the cross-branch policy text at:

- PR #8 head `3aec481a15bd821122314bc441e7bb7954d65b40`
- `docs/PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md`
- Git blob `16382c1146a191f3027347644696b9444251303b`

That protocol was observed on PR #8, not on live `main` or PR #2's base. Its policy is therefore recorded here as an explicitly cross-branch proposal input, not represented as merged repository policy. A separate integration change must reconcile and review the policy source at its then-current base before this verifier can affect any gate.

The verifier is deliberately separate from `phase1_mapping_gate.py` and `phase1_review_attestations.py`. It does not reinterpret `APPROVED`, replace or weaken external Ed25519 signatures, edit audit snapshots, or count receipts. A future integration must remain fail-closed and separately validate real receipts against an immutable source-pin registry.

## Version 1 validation boundary

`tools/phase1_copilot_receipts_v1.py` accepts one canonical per-file JSON receipt, a separately supplied immutable source-pin JSON record, the original whole-file source bytes, and the original compressed machine-dossier bytes. It verifies:

- Source repository/path/revision, Git blob SHA-1 and whole-file SHA-256 against the separate pin record and supplied bytes.
- The exact compressed dossier SHA-256 and its decompressed provenance against the pinned source identity.
- The canonical receipt SHA-256, full-file coverage, completed dependency closure, licensing scope, and absence of unresolved objections.
- Hashed whole-source evidence must match the pinned source bytes. Compiled/native/runtime evidence must be downloaded from an unexpired GitHub Actions artifact tied to a successful exact-head run and an allowed kind-specific workflow; the selected archive member must hash correctly and cannot be a byte-for-byte source/dossier copy.
- The evidence-commit analyst identity is fetched from GitHub and must differ from the protocol's verified Copilot login, numeric user ID, node ID and Bot type.
- A GitHub review API record with the exact receipt marker as a visible, unquoted standalone line and the exact validated PR head. It must be a `COMMENTED` review, not a GitHub `APPROVED` review.
- An API-attributed evidence-commit author matching the recorded analyst identity and distinct from the Copilot reviewer.
- An evidence commit that is the direct parent of the receipt commit, the canonical receipt bytes stored at the receipt path in that commit, and the receipt commit as an ancestor of the PR head. The containing receipt commit is passed separately to avoid an impossible self-referential commit hash inside the committed receipt.
- Authenticated GitHub Actions run and job API records for the exact PR head: the dedicated `.github/workflows/phase1-copilot-receipts-v1.yml` on both `pull_request` and `push`, current attempts, runs created after the receipt commit, and non-empty job lists where every job and at least one of its steps actually ran and completed successfully. `action_required`, skipped jobs, stale attempts and wrong heads fail closed.
- Compiled/native/runtime artifacts are bound to an exact run attempt by verifying the artifact metadata, exact source head, attempt start/end timestamps, successful attempt jobs and downloaded member hash.
- Duplicate per-source and duplicate-digest receipts among sibling JSON records.

GitHub evidence is fetched live using `GH_TOKEN` or `GITHUB_TOKEN`; offline fixtures do not substitute for it. The CLI must run against a complete Git history and requires API access to the repository's pull requests, actions and contents.

The separately supplied pin record is a trust input. A caller must obtain it from the independently maintained immutable Phase 1 source/dossier inventory. This proposal does not yet bind a pin-record path/hash into a merged gate. Therefore, a passing standalone invocation is only `COPILOT_RECEIPT_VALIDATED`; it is not authorization to count a review.

## Proposed input shape

The pin JSON has schema `xgba.phase1.source_pin.v1` and contains `repository`, `path`, a `source` object (`repository`, `path`, `revision`, `git_blob_sha`, `sha256`), and a `dossier` object (`path`, `compressed_sha256`). The receipt uses schema `xgba.phase1.copilot_review_receipt.v1` and binds those same source and dossier fields. Its classification is exactly:

```json
{"status":"COPILOT_REVIEWED","verdict":"PASSED"}
```

The receipt also records a `review` object (`coverage: whole_file`, `whole_file: true`, semantic summary, dependency closure, licensing, objections, hashed evidence and claims), `reviewer`, `authorship`, `ancestry.evidence_commit`, `receipt_path`, and `github` fields (`pull_request`, `review_id`, `head_sha`, and two `{event, run_id, attempt}` CI references). The exact containing receipt commit is supplied separately using `--receipt-commit`; it must have the evidence commit as its direct parent and contain the canonical receipt bytes. The `canonical_sha256` value is SHA-256 over UTF-8 canonical JSON of the receipt with that field omitted, sorted keys, compact separators, ASCII escaping, and one trailing newline.

Source evidence is `{kind: "source", artifact: "source", sha256}` or a committed path whose bytes exactly match the pinned source file. Compiled/native/runtime evidence records `{kind, artifact_id, run_id, run_attempt, artifact_path, sha256}`; the validator downloads the specific artifact through authenticated GitHub Actions APIs and hashes the selected archive member. The allowed evidence workflow is kind-specific (`compiled-*`, `compiled-mgba-semantics.yml`, or `archive-v28-runtime-rom.yml`). Claims cite evidence array indexes. Evidence and receipts must never be copied from the synthetic tests into production review paths.

Example invocation (for future proposal validation only):

```sh
GH_TOKEN=... python3 tools/phase1_copilot_receipts_v1.py \
  --receipt semantic-snapshots/independent-reviews/copilot/example.json \
  --source-pin /path/to/independently-verified-source-pin.json \
  --source-bytes /path/to/original-whole-source-file \
  --dossier-bytes /path/to/original-compressed-machine-dossier.gz \
  --repo xbaconator9000x/XGBA-ROM-Expansion \
  --receipt-commit "$RECEIPT_COMMIT" \
  --repo-root .
```

## Validation evidence and remaining work

`tests/test_phase1_copilot_receipts_v1.py` exercises a synthetic positive fixture and negative controls for tampering, missing source/dossier bytes, source identity mismatch, partial coverage, unresolved dependencies/licensing/objections, reviewer spoofing/self-authorship, quoted markers, legacy approval state, stale/wrong-head/action-required CI, missing or skipped jobs, ancestry errors, duplicate receipts, and unsupported runtime claims. Passing those tests proves only that the fixture validator behaves as coded. It does not create a real receipt or review.

The dedicated workflow runs only syntax and these synthetic controls. Before any integration, separately review the policy source and validator, bind source-pin inputs to the authoritative inventory, validate actual attributed Copilot receipts and their evidence, and confirm fresh exact-head push/PR jobs. Keep all existing approvals and totals unchanged until that separate work is accepted.

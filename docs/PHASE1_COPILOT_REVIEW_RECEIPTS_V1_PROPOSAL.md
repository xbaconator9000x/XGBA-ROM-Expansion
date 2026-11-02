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

## 2026-11-02 executed evidence reconciliation: historical v5 and current v6 (non-approving)

This append-only implementation checkpoint documents **observed GitHub objects**, not a gate/policy merge or new source-semantic approval. The four historical source-only Copilot receipts were validated at immutable PR2 commit `2aec2ff18f40604cc72f8899d35f92d0364570cd` by exact-head **push** run [41337689699](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41337689699), attempt 1. The GitHub REST run has workflow ID `402985021`, name `Phase 1 standalone Copilot receipt verifier v1`, event `push`, branch `phase1/verified-review-attestation-gate-20261026`, conclusion `success`, and **four completed successful jobs**: real v5 source/API job `124940882056` plus synthetic/adversarial jobs `124940882242`, `124940882318`, `124940882421`. Every job step executed successfully, including `Execute real four-receipt v5 validator (fail closed)`. The historical workflow Git blob is `60b422a086e6bb7f9c03a9d4e251cf66c9689573`; the v5 adapter blob is `cb64da41dd7d28d305916b60ec5b8a93590bd92d`. **Historical success is not current-head validation.**

Copilot's subsequent existing-branch commit `809f9d6b5a1546020867931b354d2b7e7986d59b` introduced an **explicit** v5 historical-replay adapter and negative controls, preserving the default fail-closed current-head semantics. Its initial exact-head push run [41375078680](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41375078680) was `action_required` with **zero executed jobs**. The historical replay code is therefore **implemented but not yet independently CI-executed** at that head. It checks immutable old PR2 ancestry/blobs, original PR8 four-receipt and compressed 14,834-dossier identities, pinned mGBA source/dependency/licensing bytes, and exact original successful Actions run/job/step identities. A later successful run must be observed before claiming its execution.

Current seven-record PR8 receipt register was introduced by Copilot in `487da72f27dfc4e634cecc11b4dbdd596ec05e00`; original four lines remain unchanged. PR8 CI retry head `4c7c09b6257d2e88a2e19bab524e9d7174d3023e` has **executed successful** [PR run 41374267141](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41374267141) (41/41 jobs) and [push census 41374245209](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41374245209) (1/1 job), both at that exact SHA.

**Real v6 attestation blocker, not a CI failure:** Copilot [PR8 comment 6567183970](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6567183970) contains **five** unquoted `XGBA-Phase1-Attestation: BEGIN/END` pairs inside **one** bot-authored GitHub comment: decoder and emitter appear twice, Thumb once. The original pinned `tools/phase1_copilot_receipts.py::_attestation_section_is_valid` requires **exactly one** pair per comment, with unique receipt/intro/evidence/decision markers, so that comment must **fail closed** for all three newer receipts. Its narrative source/dossier checks and matching hashes do not cure the format defect. Bounded correction was requested in [PR8 comment 6567744583](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6567744583): three distinct attributable top-level comments, one exact unquoted block each (or one Thumb-only comment if separate posting is unavailable). Do **not** relax the original parser, count duplicate/bundled blocks, or forge an attestation. The current v6 validator must remain red until authentic distinct receipt-bound comments and real exact-head CI satisfy every control.

All this evidence is **source-only**, not proof of native linked emulator, stock gameplay, `.sav` restart, physical Flash or combined-distribution licensing. Authoritative main gate blob `dab5789433dc55cf325a917a220d060088bf1d29` remains `FAIL_INCOMPLETE`, with **0/338 P0 and 0/14,834 historical external approvals**. The four historical user-defined Copilot reviews are not historical external/human approvals. No main/audit/gate edits or Phase 2 work are authorized here.


## 2026-11-02: v6 stale-head negative vs v6 historical replay vs v7 current live

**Phase 1 only; non-approving; user-authorized throughput/CI repair on existing draft PR #2.** PR8's current exact head is `b455f218537f7aad7876f51ced2542486835c3bf`; the original seven-receipt v6 snapshot is `4c7c09b6257d2e88a2e19bab524e9d7174d3023e`. The unchanged v6 current-head validator MUST reject the old checkout once PR8 has advanced. Actual [run 41401562587, job 125134279863](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41401562587) emitted seven `BLOCKED` records, all with exact blocker `Pull request head differs from exact validation head`, and exited 2. This is an expected anti-staleness result, not seven failed semantic reviews.

The workflow now tests that rejection **as a strict negative control**, without modifying the v6 validator: the wrapper requires exit code 2, exactly seven distinct original pinned source identities, exact blocker text and no extra or validated statuses. Nine synthetic/adversarial unit controls reject success, infrastructure errors, duplicates, missing/malformed records, unexpected blockers, fabricated passes and extra fields. A separate v6 **historical replay** checks the original immutable successful seven-receipt run; the separate v7 **live** job must pass all eight current receipts. Neither the historical replay nor the stale-head negative may be counted as a current v7 pass.

The immediately preceding Copilot-authored PR2 commit `b5946fa4c35460e8e8286418c7aeb2ae2e5170c7` had only [push run 41402635118](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41402635118), `action_required` with zero jobs. No live v7 success is claimed until an actual exact-head job and all its steps execute successfully. Original historical external approvals remain 0/338 P0 and 0/14,834 total; the authoritative gate remains `FAIL_INCOMPLETE`. This change does not modify source pins, original dossiers, signed-review gate, main or audit.


## 2026-11-02: bounded repair of v6 historical replay against a moving live PR

Real owner-triggered exact-head [Actions run 41423016906](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41423016906), job `125202864646`, failed in the new v6 historical replay with `Pull request head differs from exact validation head`. The v6 current-head negative job `125202864698` **passed**: all seven stale-head rejections were checked against exact source identities, rather than misreported as semantic failures. The historical replay had inadvertently invoked the original live-head-bound `verifier.validate_receipt` against an archived PR8 checkout; this necessarily fails after PR8 advances.

The replay now **does not synthesize or replace a live GitHub PR head**. It independently rechecks each original pinned mGBA source checkout revision, Git blob, SHA-256, original compressed machine dossier/queue identities, canonical receipt scope/line coverage, independent evidence authorship, authenticated individual Copilot comment, immutable introduction ancestry, and the original historical successful PR2 and PR8 Actions runs with exact job and step execution. The original v6 current-head validator remains unmodified and continues to reject stale heads; the separate v7 live validator remains the only current eight-receipt lane. New negative tests reject altered source bytes, wrong revision/blob and unsafe path. This is a historical evidence replay, not a new review or an external approval.

This checkpoint is a code repair on existing draft PR2 only. Its own exact-head CI result is pending until a new run executes. Main, gate, audit, source pins, historical 0/338 P0 and 0/14,834 external approvals remain unchanged.


## 2026-11-02: historical Actions nested-PR metadata is mutable

The subsequent exact-head [Actions run 41423298130](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41423298130), job `125203766971`, advanced through original source and attestation verification but failed the historical PR8 Actions check. Fresh REST GET of immutable PR8 [run 41374267141](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41374267141) confirms its **run-level `head_sha` is the correct historical `4c7c09b...`**, while the nested `pull_requests[0].head.sha` now points to PR8's later `b455f218...` current head. GitHub returns live PR metadata in that nested field; it is not a historical run identity.

The historical replay now requires immutable run-level `head_sha`, run ID, workflow ID/path, attempt, event, successful executed job/step census, plus PR number and original branch ref. It deliberately does **not** treat the mutable nested PR head as a historical SHA. Adversarial tests accept a changed nested SHA only when the immutable run SHA remains pinned, and reject wrong PR branch/number or altered run SHA. No GitHub response is fabricated, no live validator is bypassed, and no historical success is counted as current v7 approval.

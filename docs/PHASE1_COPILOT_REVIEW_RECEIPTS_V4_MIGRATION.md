# Phase 1 Copilot v4 receipt migration plan

**Status: documentation-only proposal.** This does not validate or create a review, change any approval count, integrate a Copilot lane, or alter the strict external Ed25519 gate. Phase 1 remains `FAIL_INCOMPLETE`: 0/338 P0 and 0/14,834 legacy independent approvals.

## Policy and branch boundary

The v4 format described here is present at PR #8 head `3aec481a15bd821122314bc441e7bb7954d65b40`; its protocol is blob `16382c1146a191f3027347644696b9444251303b`. This is a pinned cross-branch proposal source, not policy merged to `main` (`3d8455edb1d26b462881c8a79096e5832fcf4457`). PR #2's current head is `e69d9329ac94381b423f113c3891e5cbf25da703`. Keep the v1 proposal at `tools/phase1_copilot_receipts_v1.py` and its v1 schema unchanged.

## Observed v4 format and evidence

The PR #8 register is `docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl`, blob `b5dcfad9a428a9838cf5e29e3b44f390d491c360`. It contains three records using `xgba.phase1.copilot_semantic_review_receipt.v4`, `attestation.mode = "conversation_comment"`, and `attestation.receipt_sha256`. The receipt digest is SHA-256 over the canonical JSON receipt with the `attestation` property excluded. Recomputing this digest against each complete register record matched the digest in its Copilot comment:

| Pinned source (revision/path) | Git blob SHA-1 | Source SHA-256 | Canonical dossier SHA-256 | Receipt digest | Comment / receipt-introduction commit | Evidence commit |
| --- | --- | --- | --- | --- | --- | --- |
| `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b:include/mgba/internal/arm/debugger/cli-debugger.h` | `70f9b188572137479cb3e9bf26ab12f40707e1f9` | `27ef2fed80894cc662aae2793cb6459b2aac86b3d5a7dd410282411f83bd05a5` | `ebcf0db23dc12aa3f58016584e81ddea8adcc3701c1f52a51759fcd8909bbdcf` | `49924b5437aecfc88ebdf335fbd6fe05a68fa13987f61d87e0a7ee62809f0c64` | [#6537324570](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6537324570) / `9204256b66558864efb32884d5b8228543f0bf97` | `4ea9dbd09118530a986f9bf5828b6c258f279d40` |
| `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b:include/mgba/internal/arm/debugger/memory-debugger.h` | `1ec675992e79d37321c358ffd0ff1c691118993d` | `7ba8c726198d604bcfcd85d97b9aab4087e44e5355fcae8407d02235b58d0da3` | `413ba90e50188b2356db3617be4022a75bbe3f22a5e1fbb1343035cf13cd6182` | `2d30b0f6d533f5091f0e0b58233032707c3fdb07b81984cc8aa85a5a6516cc53` | [#6540744914](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6540744914) / `e349407d5e2cdfeb030f976ab716545875e0f3eb` | `e16cd30e0a302824a8626279531de44b240dc138` |
| `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b:src/arm/CMakeLists.txt` | `a86f0bea1f38aeb88222fb5b532b4ea9e256767f` | `37d9b15aa461a72eba64465856d9377085d6dde56b8ba888e3a4e30f6859390e` | `821659a5c9436e3472b409a43e08f66e703a8daff07e0b6cf70d46eaed1d491a` | `e410f88c79a6b3dfb2612f1228c6f7ae0bda83e4eb7d896fbc6221aa2903a0d0` | [#6547559949](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6547559949) / `3aec481a15bd821122314bc441e7bb7954d65b40` | `724a8e0bfa48a8d8f7826f13b120cb9a383d7d9a` |

All three source Git blob IDs and source SHA-256 values match the files retrieved from the pinned mGBA revision. The comment API records show login `Copilot` and numeric user ID `198982749`. A future verifier must authenticate the complete GitHub user object against the protocol's immutable identity (`BOT_kgDOC9w8XQ`, type `Bot`, and only the verified aliases `Copilot` and `copilot-swe-agent[bot]`); a display name or copied comment text is insufficient.

The v4 validator at PR #8 head (blob `c68a11e0de846a12179cf71171b3c3a15fc65764`) checks pinned source identity and bytes, dossier binding, whole-file line coverage, dependencies, licensing scope, evidence distinctions, objections, reviewer identity, comment markers, receipt ancestry, and expected-head validation. I matched each receipt's source SHA-256 to its dossier entry and independently recomputed its canonical dossier digest; all three also match the queue's `evidence_sha256`. The pinned compressed files are `semantic-snapshots/current/candidate_review_dossiers.jsonl.gz` (SHA-256 `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`) and `semantic-snapshots/current/semantic_review_queue.csv.gz` (SHA-256 `c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff`). In v4, `machine_dossier_sha256` binds the canonical per-file dossier object. It is **not** the SHA-256 of the entire compressed dossier archive. Never substitute one digest for the other.

The unquoted comment block binds the canonical receipt digest, receipt-introduction commit, earlier evidence commit, and `APPROVED` decision. The validator also requires the receipt introduction and evidence ancestry and exact-head GitHub validation. Its tests are at `tests/test_phase1_copilot_receipts.py` (blob `8862f416b1b922ecb94aa42338e56d6fb64d9690`).

## Why v1 cannot consume v4

The PR #2 v1 proposal expects its own per-file JSON schema and a GitHub pull-request review object with `state = COMMENTED` plus its own standalone marker. The observed v4 records instead use a JSONL register and conversation issue comments with `XGBA-Phase1-Attestation: BEGIN/END`, receipt digest, receipt commit, evidence commit, and decision markers. Mapping between these formats would discard provenance distinctions and risks treating a comment as an external Ed25519 signature. Neither the v1 verifier nor the external signature gate should accept v4 records implicitly.

## Additive integration sequence

Only after the proposed protocol is reviewed and separately integrated:

1. Add a separately versioned v4 adapter. Keep v1 and external Ed25519 verification unchanged; do not make either adapter write to the legacy approval register.
2. Load the exact pinned original compressed dossier bytes and verify their archive SHA-256, then resolve each v4 per-file canonical dossier digest to exactly one record. Verify original whole-file source bytes, Git blob ID, source SHA-256, and any required licensing/dependency evidence.
3. Fetch the canonical comment URL using authenticated GitHub API data. Require the exact Bot ID, node ID, type, permitted login alias, unique unquoted/unfenced markers, matching digest and commit IDs, and a single unambiguous attestation. Reject owner self-review, quoted echoes, duplicates, spoofed authors, missing evidence, and stale or mismatched commits.
4. Verify append-only introduction ancestry, evidence ancestry, exact target PR/head, and independently observed successful PR **and** push workflows with executed jobs. `action_required`, zero-job, missing, stale, or wrong-head runs fail closed.
5. Preserve source-only scope. Reject unsupported compiled/native/runtime claims and unresolved substantive objections. The validator must never infer semantic understanding from a green workflow.
6. Add positive format/lifecycle controls and negative controls for every rejection above. Label all synthetic fixtures as tests only; neither fixtures nor green CI mint real reviews. Do not increment counts until a separately authorized integration validates actual receipts end to end.

## Verification checkpoint

The v4 unit suite from the pinned PR #8 head passed locally: 39 tests, including positive lifecycle controls and negative controls for wrong authors, duplicate/quoted/fenced attestations, bad digest/commit markers, stale evidence, and broken ancestry. Those tests use isolated synthetic fixtures and are not themselves reviews. The three actual register records were separately checked against source bytes, compressed dossier contents, queue entries, canonical digests, and corresponding comment markers as listed above. This follow-up did not run the v4 validator end to end against the real receipts; this document is a migration plan, not an integration or count-changing validation.

For exact PR #8 head `3aec481a15bd821122314bc441e7bb7954d65b40`, PR run `#41194426346` attempt 2 completed 41/41 jobs successfully, and push census run `#41194422805` attempt 2 completed 1/1 successfully. The census and machine-dossier byte-verification logs explicitly retain `FAIL_INCOMPLETE`, 0/338 approved P0, and 0/14,834 approved total. These runs are evidence for their exact head only; they do not integrate this PR #2 proposal or change counts.

The prior PR #2 v1 workflow run `#41232472820` ended `action_required` with zero jobs and no failed-job logs. This is a permissions/dispatch blocker, not a successful v1 CI run and not a code failure. No workflow changes are proposed here.

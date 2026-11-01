# XGBA Phase 1 semantic review policy v2 — Copilot-qualified lane (2026-11-01)

**Status: versioned change proposal on EXISTING draft PR #2; not merged or activated.** Owner instruction on 2026-11-01: **a human reviewer is NOT required for XGBA project completion**. This supersedes any *future completion expectation* of recruiting an external human, but does not retroactively rewrite the historic Ed25519 gate or grant approval to unreviewed files. The canonical main gate is still `FAIL_INCOMPLETE`.

## Policy decision and scope

* A **distinct human/external-human signature is not a mandatory precondition** for future XGBA Phase 1 completion.
* An independently attributable **GitHub Copilot** semantic review may satisfy the **new versioned semantic-review gate**, but only when the original pinned **whole-file** source and **original machine dossier bytes/SHA-256**, dependency closure, licence scope, required evidence and tests, objections and provenance are validated independently.
* The existing Ed25519/external-human gate is retained as a **historical, legacy metric**, not silently changed to accept bot comments or substituted signatures. Its current counts are 0/338 P0 and 0/14,834 total; the main `semantic-snapshots/current/phase1_mapping_gate.json` remains unchanged until an authorised merge and reproducible migration.
* `COPILOT_REVIEWED/PASSED` is an independently reviewable *source-level disposition*, not a claim that XGBA works, that every required compatibility gate passed, or that hardware was tested. Existing three PR #8 records are candidate inputs, **not automatically approved under the new gate**.

## Required validation for a v2 qualifying disposition

1. **Source and dossier trust:** immutable original upstream repository/revision/path/Git blob/whole-file SHA-256, exact original compressed machine-dossier archive SHA-256, canonical per-file dossier SHA-256 and original packet index; verify the bytes, not only declared hashes. No source-pin replacement or dossier regeneration.
2. **Whole-file substantive review:** line coverage and actual semantic rationale, dependency and consumer/producer closure, explicit unresolved edges, source-versus-compiled/native/runtime distinction, applicable licence/third-party obligations, and no unresolved substantive objections. An analyst partial, green CI, generic comment, bot-generated summary or copied receipt does not qualify.
3. **Distinct authenticated reviewer:** validate the GitHub API user object, numeric Bot ID `198982749`, node ID `BOT_kgDOC9w8XQ`, type `Bot`, and the two previously observed aliases `Copilot` and `copilot-swe-agent[bot]`; never rely on a display name alone. Reject the source/evidence author self-review, quoted markers, ambiguous duplicates, missing API provenance and author conflicts. Any new identity requires a separately reviewed versioned policy change.
4. **Durable receipt:** canonical v4 receipt digest, original receipt bytes, independently fetched GitHub comment with unquoted attestation markers, immutable evidence and receipt-introduction commits, append-only ancestry and verified exact-head CI with executed jobs. Reject stale, zero-job, `action_required`, mismatched-head and unexecuted checks. A GitHub comment is an attributable receipt **only after** all checks pass; it is not an Ed25519 signature.
5. **Evidence boundaries:** classify source, synthetic, host, compiled, native, stock gameplay, `.sav` restart and physical Flash separately. A source-only review cannot imply runtime/Flash clearance. Required tests missing or blocked remain `NEEDS_REVIEW`.
6. **Fail-closed negatives:** tampered source/dossier/receipt hashes; incomplete line scope; unresolved dependencies/licensing; reviewer spoof or self-review; copied/quoted markers; duplicate receipts; missing provenance; missing/stale CI; unsupported evidence claims; altered source pins; incomplete inventory. All must fail closed.

## Proposed machine-facing outputs

Versioned namespace: `xgba.phase1.semantic_review_policy.v2`.

* `COPILOT_REVIEWED/PASSED`: only a qualifying whole-file semantic receipt satisfying the above checks. Keep source-level claims explicitly scoped.
* `NEEDS_REVIEW`: any substantive source objection, missing required evidence, or incomplete review; no approval count.
* `BLOCKED`: unavailable original source/dossier, GitHub identity/Actions API, permission-gated workflows, or infrastructure; no approval count.
* `legacy_external_independent_approved`: historical Ed25519-only count, preserved separately and **not** used as the v2 completion blocker.
* `v2_qualified_semantic_review_count`: number of unique pinned files passing the new validator; never sum duplicate receipts or synthetic fixtures.
* `v2_completion_gate`: remains `FAIL_INCOMPLETE` until inventory parity and all mandatory Phase 1 review and compatibility requirements are satisfied under the reviewed policy. The presence of three existing receipts alone cannot make it pass.

The separately versioned prospective upstream-congruence lane is specified in [Phase 1 upstream-congruence lane v1](PHASE1_UPSTREAM_VERIFIED_POLICY_V1_20261101.md). It emits `UPSTREAM_VERIFIED/PASSED` only for immutable exact-byte evidence under that policy; it does not reinterpret Copilot receipts or legacy signatures. Future prospective completion reporting uses a deduplicated union of qualified Copilot and upstream source identities, while retaining the legacy external counters separately. The new lane is not activated by this proposal.

## Required implementation sequence

1. Reconcile current PR #8 protocol/receipt register and PR #2 adapter; avoid merging incompatible v1 and v4 schemas by assumption. Preserve the old gate for historical reporting.
2. Implement a **separate** v2 fail-closed evaluator over verified v4 receipts. It must not write to `semantic-snapshots/current` or treat user/owner assertions as reviewer evidence. Keep it read-only until an authorised integration.
3. Add deterministic positive and adversarial tests for every negative above; test against original pinned source and dossier bytes and authenticated GitHub provenance. If network is blocked, report `BLOCKED`, not `PASSED`. Avoid adding workflow YAML solely to bypass GitHub's approval security.
4. Only after exact-head validation and normal protected-branch integration, change the authoritative completion policy through a separately versioned, auditable migration. Record both old and new counters; never fabricate a historical external signature.
5. Prioritise reuse of existing pinned mGBA, Porymap, Poryscript, FireRed and original compiler/toolchain components. Licence and technical compatibility remain mandatory.

## PR2 implementation checkpoint

The standalone evaluator is `tools/phase1_semantic_dispositions_v2.py`. It accepts only the pinned PR #8 worktree and pinned-source checkout, delegates receipt/provenance/CI validation to `tools/phase1_copilot_receipts_v4_adapter.py` and the validator pinned by that adapter, and prints a read-only JSON report. It does not accept a receipt JSON file, write snapshots, or update either gate.

```sh
python3 tools/phase1_semantic_dispositions_v2.py \
  --pr8-root /path/to/full-history-pr8-worktree \
  --source-root /path/to/pinned-upstream-checkouts
```

Each pinned receipt is reported as `COPILOT_REVIEWED/PASSED` only after the live adapter validates it; substantive gaps become `NEEDS_REVIEW`, while provenance, source/dossier, API, CI, or infrastructure failures remain `BLOCKED`. The report keeps `legacy_external_independent_approved` and `legacy_p0_external_independent_approved` separate from `v2_qualified_semantic_review_count`, and hard-fails if the historical 0/338 P0 and 0/14,834 total baseline changes. `v2_completion_gate` remains `FAIL_INCOMPLETE`; the policy remains `PROPOSAL_NOT_ACTIVATED` until reviewed and integrated through the normal protected-branch process.

`tests/test_phase1_semantic_dispositions_v2.py` uses synthetic fixtures only to test report projection and fail-closed classification. No synthetic fixture is an input to the CLI or evidence of a source review. The earlier three PR #8 receipts remain candidate inputs and do not count unless independently revalidated end to end under this evaluator.

**Non-claims:** The evaluator does not activate the policy, alter current main/audit or legacy counts, certify ROM expansion, or waive technical/licensing/test requirements. The live attempt on the three pinned PR #8 records returned `BLOCKED` because anonymous GitHub API requests received HTTP 403 from the DNS-monitoring proxy; no receipt was qualified or counted. No additional scheduler or human reviewer is requested.

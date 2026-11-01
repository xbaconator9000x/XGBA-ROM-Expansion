# Phase 1 upstream-congruence lane v1 — 2026-11-01

**Status: prospective proposal on draft PR #2; not merged or activated.** This lane is separate from the historical Ed25519 metric and the Copilot receipt lane. It does not edit the current mapping snapshot or make a Phase 1 completion claim.

## Prospective completion criteria

For a pinned file, `UPSTREAM_VERIFIED/PASSED` is allowed only when an immutable, versioned evidence record is present in the separately hash-pinned PR2 proposal register and the evaluator independently verifies every referenced source artifact against one of the already configured upstream pins:

1. The target's exact pinned repository/revision/path/Git blob and whole-file SHA-256, plus the original compressed dossier archive SHA-256 and canonical per-file dossier SHA-256.
2. Exact whole-file byte equality between the target and a distinct upstream implementation. This v1 proof mode supports C/C++ sources only, computes the transitive quoted/angled include closure from the pinned trees, and requires every dependency in both closures to be pinned and byte-identical.
3. Full line coverage, a pinned specification, test sources named by the pinned workflow, and a public GitHub Actions run at that exact pinned test revision with all jobs successful and at least one executed step per job.
4. A source-grounded semantic dependency/consumer inventory, SPDX license evidence for every repository in scope, and an empty unresolved-objection list.
5. The evidence record's canonical digest and the proposal register's own pinned SHA-256/Git blob. PR8 bulk-index output is not an evidence record: its pinned triage tool marks records `MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW` and sets approval flags false.

The evaluator emits `NEEDS_REVIEW` for partial scope, changed dependencies, missing semantic/test/license evidence, objections, unsupported include forms, and behavioral-equivalence claims. It emits `BLOCKED` for missing or changed source/dossier bytes, invalid immutable identities, unavailable provenance, duplicate records, or stale/failed/unexecuted Actions runs.

### Proof-mode boundary

`exact_bytes` is the only mode that can qualify under v1. A distinct upstream implementation must have the same complete source bytes and a byte-identical pinned include closure. `behavioral_equivalence` is reported as `NEEDS_REVIEW`: no approved, pinned conformance harness in this branch can establish that broader claim. A future equivalence lane needs a separately versioned harness, pinned specification/test matrix, counterexample policy, licensing review, and negative controls; it cannot be enabled by adding a boolean or receipt field.

## Versioned evidence formats

- Report: `xgba.phase1.upstream_verified.v1`
- Register: [`semantic-snapshots/proposals/upstream_verified_evidence_v1.json`](../semantic-snapshots/proposals/upstream_verified_evidence_v1.json), schema `xgba.phase1.upstream_congruence_register.v1`. Each row is a `xgba.phase1.upstream_semantic_mapping.v1` record with a canonical `record_sha256` calculated over the record with that field omitted. The whole register is pinned by SHA-256 `df0e37cbc42df1cb3b10ed008ca8b8a6a73656dd4cb9fd82a76934f7976851fd` and Git blob `911b009ec64ee3ecbb72a81b44ffe00c9caaa44d`; records cannot be supplied on the command line.
- A mapping record binds target identity, dossier hashes, implementation identity, proof mode, whole-file coverage, dependency pairs/digest, semantic dependencies, licensing evidence, test/spec references and Actions run, and objections. `scope.claim_level` must be `source` and `scope.semantic_claim` must be `exact_pinned_bytes_and_include_closure`; coverage must be exactly `[[1, source_line_count]]`. Dependency kinds are limited to `build`, `consumer`, `producer`, and `specification`. The evaluator resolves all code/spec/test/license references from configured immutable upstream revisions and checks their content hashes. The CLI accepts no evidence-register path or offline fixture; any register change requires a separately reviewed version/pin update.

Run against the existing snapshot and full-history source checkouts:

```sh
python3 tools/phase1_upstream_verified_v1.py \
  --source-root /path/to/pinned-upstream-checkouts
```

The report includes separate `upstream_verified_passed_count`, `needs_review_count`, `blocked_count`, and `inventory_remaining`. Synthetic test records are injected only into unit tests and never enter the CLI's live evidence path.

## Migration and audit checkpoint

At proposal time, the immutable historical baseline is still 14,834 files, 338 P0 candidates, 0/338 legacy P0 external approvals, and 0/14,834 legacy external approvals. The current snapshot's original dossier archive is pinned by SHA-256 `c47d1fea819e7df59f67bfe8d1bc4dc2650483d03563957145f7331ed099005b` and Git blob `143c373f9aae5b9cb24af39abb7d8244362d23b5`; the queue archive is separately pinned by SHA-256 `b2e418f75645714ad780d004203dc3ce67189eb956db0cfd48f670997b8afb5d` and Git blob `777901c5f714764978de3f0623abd35ec21889f7`.

The separately pinned PR2 proposal register is empty, and PR8 machine-index output is not eligible. The actual upstream-qualified count is therefore **0**; all 14,834 files remain. The evaluator reports `PROPOSAL_NOT_ACTIVATED` and `FAIL_INCOMPLETE`. This is a prospective audit entry only: no legacy counts, source pins, machine dossiers, queue, gate snapshot, or main-branch policy were changed.

The future prospective semantic total is the cardinality of unique pinned source identities accepted by either the already separately validated Copilot lane or this upstream lane. A file accepted by both counts once. This union never changes or adds to `legacy_external_independent_approved`; all remaining compatibility, licensing, inventory-parity and Phase 1 requirements still apply.

**Limit:** v1 verifies exact bytes, pinned structure, hashes, and CI execution; it cannot infer semantic correctness merely from an index, filename, successful build, license label, or test run. The immutable mapping artifact and source-grounded scope are required, and no existing artifact is accepted automatically.

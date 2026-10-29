# Phase 1 independent semantic review queue

Status: ACTIVE QUEUED WORKSTREAM; **no approvals inferred**. This is separate from the 30/30 evidence re-verification queue and must not modify its receipts.

## Priority and throughput
Start immediately with the 338 pinned P0 candidates, first the 29 curated source-interpreted files, then remaining P0, then other 14,834 inventory entries by dependency/risk. Review independent files in parallel, grouping by module without bypassing dependencies. Every execution should take the largest safe batch the runtime permits, checkpoint unfinished work, and select the next eligible candidates. Do not count a review as approved simply because a batch completed.

## Per-file immutable review record
Use `semantic-snapshots/independent-reviews/` for review records keyed by exact repository, source path and Git blob SHA. Each record must include: source identity and blob SHA; machine dossier SHA; precise responsibilities and behavior; callers/callees and dependency contracts; runtime/compiler/linker/save/editor implications as applicable; evidence references with exact line ranges and hashes; source-interpreter identity; *distinct* independent reviewer identity; reviewer objections and resolution; explicit verdict APPROVED / REJECTED / NEEDS_EVIDENCE; validation command/results; date and audit trail.

A reviewer must independently inspect pinned source and evidence, not merely endorse the first interpretation. An automated second pass is not automatically independent approval. If no genuine separate reviewer is available, leave NEEDS_REVIEW and queue the next item. Never manufacture a reviewer or mark APPROVED without review evidence.

## Scheduling and checkpoints
Persist a machine-readable queue and per-batch receipts on GitHub; use exclusive claims or disjoint deterministic partitions, lease expiry and idempotent writes to avoid duplicate review. A crash must preserve accepted records and safely retry uncommitted work. Failed/changed source hashes invalidate stale approvals. Use existing XGBA watchdog and GitHub Actions infrastructure; do not create a competing uncoordinated watchdog.

## Required gates
Only independently verified, source-hash-pinned APPROVED records count toward 14,834. Maintain P0 approval count separately. All existing inventory, compiler/linker, emulator/runtime, save/asset, editor interoperability and regression gates remain fail-closed. No Phase 2 implementation authority follows from an evidence-verification receipt.

## Initial queue
1. Curated 29 P0 candidates: independent source interpretation and verification.
2. Remaining 309 P0 candidates: source-grounded disposition, then independent verification.
3. Other 14,496 inventory files: dependency-aware, risk-prioritized disposition and review.
4. Reconcile source changes, resolve rejected records, and evaluate final cross-file gates.

**Completion is measured in independently approved semantic dispositions, not file scans, queue receipts or documentation volume.**

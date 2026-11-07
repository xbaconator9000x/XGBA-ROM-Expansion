# PR #27 Phase 1 hybrid execution queue (non-approving)

Status: dispatch protocol, not evidence of an agent scheduler or completed review. Governing protocol is on existing PR #8 at `docs/PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md`; fetch it from PR #8, not necessarily this checkout. No new PRs/branches, merges, protected changes, source-pin changes, Phase 2 or paid overages.

## Immutable scope and guardrails

Only existing PR #27 branch `phase1/porymap-full-qt-project-roundtrip-20261028`. Porymap original `26b919d7`; source identity requires original Git blob SHA-1, full source SHA-256, and original machine-dossier row/archive SHA-256. Inventory-only identity is not semantic approval. Preserve Qt translations/SQLite licensing and whole-file caveats, actual native/compiled vs host/synthetic distinctions, explicit negative controls and `NEEDS_EVIDENCE` on unresolved claims. The 40-file vendor inventory and QtGifImage native fault witness are previously delivered: never recount them as new work. Check exact-head push AND PR runs after each atomic expected-head commit; no false approvals.

## Ordered nonoverlapping substantial stages

1. **FEX archive ownership/error semantics** — Execute existing assignment issuecomment-6693833360. Establish original full-source FEX archive implementation, direct Porymap callers, lifetime/ownership/error paths, build/notice closure; select only justified unreviewed files. Deliver original source/dossier hashes, machine-readable per-file objections, negative controls and bounded executable checks where possible. Commit and verify both CI event types.
2. **OrderedJson read/write contract** — Existing assignment issuecomment-6695016071. Start ONLY after stage 1 has delivered or has a documented, precise `BLOCKED` state and HEAD has been reconciled. Do not overlap FEX sources. Trace serialization, parser error contracts, actual callers, tests and license edges. Deliver separate machine-readable receipts and fail-closed tests. Commit and verify CI.
3. **Qt translation/SQLite licensing boundary** — Existing assignment issuecomment-6696317544. Start ONLY after stages 1–2 are delivered or precisely blocked and HEAD is reconciled. Scope unreviewed original translation catalogues, build/install packaging, Qt and SQLite linkage/notice/whole-file licensing caveats. Do not promote semantic review from metadata-only checks. Commit and verify CI.
4. **Independent attribution / remaining QtGifImage closure** — Only after checking whether previously pending assignment is still unresolved. Do not redo delivered native fault witness. Require reviewer independence and source-grounded objection evidence; leave `NEEDS_EVIDENCE` otherwise.

## Handoff contract for each stage

Post `STAGE <n> DELIVERED|BLOCKED`, exact HEAD, newly reviewed source paths/count, original Git blob/full-byte SHA-256/dossier hashes, substantive new findings, negative controls, actual test commands and result provenance, push/PR run IDs and conclusions, remaining blockers. Stage completion means durable artifacts plus verified CI, not a comment. If blocked, identify precise unavailable source/permission/tool. Do not claim autonomous sequencing: a PR comment or this queue file does not create a GitHub agent trigger. An already active Copilot session may proceed through ordered stages only while it can safely reconcile HEAD and obtain the required evidence; otherwise stop and let the existing hourly supervisor dispatch the next stage.

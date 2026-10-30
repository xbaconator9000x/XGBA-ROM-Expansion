# Phase 1 — system-batched semantic mapping and review protocol

Status: **PROCEDURE ONLY / FAIL_INCOMPLETE**. This document does not certify any source file, runtime result, or compatibility gate.

## Scheduling unit: a dependency-connected subsystem

Select the next subsystem from the existing architecture-aware queue, preserving the original 14,834-file inventory and all 338 lexical P0 priorities. Prefer high-fanout source owners (native producers/consumers, toolchain, emulator, editors) over arbitrary isolated files. The original priority is immutable; scheduling tier is supplementary.

For each subsystem, work continuously through these stages without asking for user confirmation between routine steps:

1. **Pin and reconcile.** Read current branch head and exact upstream repository commit/blob IDs. Stop or rebase safely if the head changed; never overwrite concurrent work.
2. **Build the dependency closure.** Trace declarations, callers, writers, readers, build rules, generated assets, serialized representation, and external tool boundaries. Explicitly record untraced edges, including negative evidence.
3. **Record semantics in one subsystem dossier.** Separate source-proven invariants from inferred hazards and compiled/runtime observations. Include precise file paths, source revision and blob hashes, call-site preconditions, and counterexamples.
4. **Generate per-file review records from the dossier.** Each file gets its own identity, whole-file coverage scope, known dependencies, unresolved conditions, reviewer questions and evidence pointers. Partial-file investigations must not be marked whole-file candidates.
5. **Check fail-closed compatibility gates.** Inventory parity, source identity, semantic coverage, compiler/linker, emulator/runtime, save/asset, editor interoperability and regression evidence are separate gates. Missing evidence remains FAIL_INCOMPLETE, even when other CI passes.
6. **Commit a reproducible checkpoint.** Use small, auditable commits on an existing draft branch only when the head is current. Verify CI against the exact resulting SHA; do not reuse older green runs as proof for a newer commit.
7. **Continue immediately to the next unresolved dependency** when no user decision is necessary. Prefer substantive source coverage over repeating already-green peripheral tests.

## Counting and approval invariants

- Inventory count = unique pinned upstream source identities, **not** the number of files mentioned in dossiers.
- Analyst-prepared count = distinct complete-file review records with explicit scope and source identity, **not** partial investigations or repeated references.
- Independent approval count = an explicit, attributable independent semantic review decision tied to immutable original source and machine dossier evidence. Under the user-authorized 2026-10-31 policy amendment, GitHub Copilot is an eligible independent semantic reviewer, provided its review is substantively separate from dossier authorship and satisfies all requirements below. Neither a Copilot comment alone nor CI success constitutes approval. Never approve a reviewer’s own authored changes without a separate review.
- A qualifying Copilot review MUST include a per-file immutable source revision/blob identity, original machine dossier bytes and SHA-256, full-file semantic coverage, dependency closure, licensing assessment, applicable native/compiled/runtime evidence distinctions, unresolved-objection disposition, exact-head validation and an attributable durable receipt. Record unsupported evidence as missing and keep NEEDS_REVIEW.
- The semantic approval gate may count qualifying Copilot receipts, but only after its validator is updated with fail-closed negative controls for missing/wrong hashes, incomplete scope, reviewer/author conflicts, unresolved dependencies or licensing, unsupported tests, missing receipt, and stale exact-head evidence. Do not alter existing approval totals or FAIL_INCOMPLETE until actual qualifying receipts pass that validator.
- Never convert unknown, skipped, inferred or unavailable tests to PASS. Preserve **FAIL_INCOMPLETE** until every mandatory gate is satisfied.
- A subsystem dossier may span many files; its presence alone does not imply all those files are reviewed or approved.

## Immediate dependency order

1. FireRed mapjson generator: authored connection include order -> actual generated include bytes -> linker-visible tables -> runtime consumers; distinguish the debug-iterator fixture from full generator execution.
2. Porymap project identity and multi-map connection persistence: source JSON -> editor mirror/update/save/reload -> generated native connections -> runtime; do not infer Qt round-trip evidence from static code.
3. Poryscript map-script ABI: emitted bytes -> FireRed reader table widths/sentinels -> compiler/linker output -> runtime malformed-table handling.
4. Extend the closure to mGBA and agbcc when native representation, code placement, reset/save or runtime mapping crosses their boundaries.

## Stop conditions

Continue within the current invocation while tools and evidence permit. Stop for a genuine user decision, missing immutable source, unsafe concurrent-write conflict, or inability to obtain required compiled/runtime evidence. Scheduled future work is performed only by an explicitly enabled automation or GitHub Actions, not by this document.

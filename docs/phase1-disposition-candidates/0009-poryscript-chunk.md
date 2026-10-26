# Phase 1 whole-file semantic candidate 0009 — Poryscript emitter/chunk.go

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** Analyst-authored complete-file disposition candidate only. This file is a script-emitter control-flow helper, not a ROM banking implementation.

## Immutable identity and whole-file inventory

- Repository: huderlem/poryscript; commit c32481161c767b25a3425fa9f1f8729927ff3d55.
- [Exact emitter/chunk.go](https://github.com/huderlem/poryscript/blob/c32481161c767b25a3425fa9f1f8729927ff3d55/emitter/chunk.go); Git blob SHA-1 bb3a6514988eb2699022551d3dbfe2bdce260377.
- Entire 144-line Go source: package emitter; imports fmt, strings, ast and parser; one private chunk struct with id, returnID, useEndTerminator, statements and branchBehavior fields; ten functions listed below. No C/assembly pointer arithmetic, ROM access, binary serialization, I/O or exported declarations occur in this file.

## All declarations and execution paths

1. **getLabel:** chunk 0 uses the script's base label; nonzero chunks use scriptName plus numeric suffix.
2. **renderLabel:** the entry label is global only when both chunk 0 and the script's isGlobal flag are true; otherwise a local label is emitted.
3. **renderStatements:** iterates the entire chunk statement slice. CommandStatement emits optional line marker and rendered command; LabelStatement checks collision against generated chunk and text label sets, emits optional marker and authored label. Any other AST statement type returns an error. This file does not independently prove duplicate authored-label detection outside those sets.
4. **renderBranching:** delegates to branchBehavior if present; otherwise emits the terminator for returnID -1, emits a registered goto for nonadjacent returnID, or allows physical fallthrough when the destination is the next chunk.
5. **getTerminatorCommand:** chooses end when useEndTerminator is true, return otherwise. Caller provenance for this flag is in emitter.go.
6. **splitChunkForBranch:** a branch at the final statement inherits the existing returnID. An earlier branch allocates a post-logic chunk from the trailing statements, appends it to the pending list and changes the current chunk's returnID.
7. **isLastStatement:** exact comparison to len(statements)-1; an empty statement slice does not match a nonnegative index.
8. **createPostLogicChunk:** copies the prior returnID and references the trailing statement slice. It does not deep-copy AST statements.
9. **renderCommandStatement:** renders command name and comma-separated argument strings, without resolving their final native opcode/operand sizes.
10. **renderLabelStatement:** chooses global double-colon versus local single-colon authored labels.

## Source-grounded dependency and expansion relevance

- emitter/emitter.go constructs, schedules and renders chunks; optimization changes physical ordering and whether generated labels/gotos appear. emitter/branch.go provides brancher and native comparison/switch text. parser.NewParseError supplies collision errors. ast.Statement concrete types determine accepted chunk statements.
- The source-level map-script ABI join with FireRed is documented in [the pinned cross-repository dossier](../PHASE1_P0_PORYSCRIPT_FIRERED_MAP_SCRIPT_ABI_2026-10-27.md). This file's labels and implicit return/end behaviour matter for preserving control-flow semantics across relocated resources, but this file alone does not define binary pointer widths or compiled bytecode.
- Do not treat optimized chunk labels, textual source formatting, source-line markers, compiler flags or authored structured conditions as recoverable from final ROM bytes without separate provenance.

## Reviewer obligations and unresolved evidence

An independent reviewer must inspect every line at the pinned blob, resolve all constructors/callers and parser/AST paths, assess generated-label collision coverage and returnID -1 paths, inspect optimized and unoptimized compiled outputs, and verify actual script interpreter return/end behaviour. Record reviewer identity, evidence hashes, decision and date before ingestion into the machine gate. No independent signoff, compiled ABI/runtime execution or editor round trip is claimed.

**Whole-file analyst preparation: one unique file. Gate contribution: zero. Phase 1: FAIL_INCOMPLETE; 0/14,834 approved.**

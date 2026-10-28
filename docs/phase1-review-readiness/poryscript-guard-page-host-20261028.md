# Phase 1 — source-extracted FireRed map-script missing-sentinel guard boundary (2026-10-28)

**Status: exact-head CI required; FAIL_INCOMPLETE; independent approvals 0.**

## Source, scope and observed mechanism

Pinned FireRed \`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982\`, \`src/script.c\` Git blob \`d0433bdda062b138e53d1a1d3184b4566ad7d9dc\`. The unchanged source-extracted complete C bodies \`MapHeaderGetScriptTable\` and \`MapHeaderCheckScriptTable\` have \`while (1)\` loops, sentinel checks and five-/eight-byte strides, but receive no explicit table-length argument. The earlier Poryscript CLI/GNU ARM emitted-table and bounded-host-reader evidence remains green and is not rerun as new evidence.

The new separate host-C executable places a single nonmatching five-byte outer entry at the end of a writable page, with the next page \`PROT_NONE\`. It repeats with an eight-byte unmatched conditional entry and no two-byte terminator. Each child process has a \`SIGSEGV\` handler that reports a fault **only when \`si_addr\` lies inside the protected next page**; any other crash, unexpected return or signal fails the test. Two matched valid controls add the correct outer or conditional sentinel and require a normal NULL result. The actual original function bodies are extracted from the immutable source, not reimplemented.

This demonstrates a **bounded host guard-page fault under deliberately malformed tables**, conditional on the test-only page mapping and pointer translator. It does **not** establish a stock ROM malformed table, actual mGBA/ARM execution, universal native safety/unsafety, GBA memory fault semantics, or exploitability. The host \`T2_READ_PTR\` and \`VarGet\` implementations are explicit test shims.

## Fail-closed evidence and per-file record

Four source-semantic mutations and eight output-transcript mutations must be rejected. The test pins the exact source commit and blob, records the extracted function SHA-256, and archives JSON only (no ROM or ELF). Per-file candidate: \`src/script.c\`, **partial function-level coverage only**; the remainder of the file and transitive callers, map loader, Poryscript producer and editor inputs are not whole-file dispositions. No count or independent approval increment.

## Reviewer questions

1. Can the original-agbcc linked reader be entered with a deliberately bounded malformed table in mGBA, with explicit ROM location, state and instruction telemetry?
2. What actual memory region follows the malformed record in a stock or expanded ROM, and does the CPU read it without trapping?
3. Can source-proven editor/producer paths emit missing sentinels, or is this limited to synthetic corruption?
4. Are any other table consumers missing a length precondition, and how are those dependencies represented in the independent review register?

Keep all gates \`FAIL_INCOMPLETE\` pending independent whole-file review and the remaining compiler/runtime/editor evidence.

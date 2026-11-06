# Phase 1 analyst handoff — pinned mGBA ARM instruction-dispatch header (2026-11-01)

**Status: INDEPENDENT ANALYST EVIDENCE ONLY; NEEDS_REVIEW.** This document is a non-Copilot source investigation for a distinct Copilot semantic reviewer. It does not constitute an approval, native execution, runtime compatibility, or licensing clearance.

## Immutable original identities

- Source: `mgba-emu/mgba` at `fd9dc5c2cbf234365068855851107e762fc6211b`, `include/mgba/internal/arm/isa-arm.h`, **22 complete lines**.
- Original source Git blob: `fb347cd89f97482e0dbbf5fafed129f1679952df`; packet source SHA-256: `619d6208fdbee4f15a7120c3e6f8300cc24c4390373d83586b8c883d83b9f65f`.
- Original machine-review packet: `docs/phase1-review-readiness/packet-0000-0099.json`, index **30**, dossier SHA-256 `ff5d84cb5f4abb74c841d8050e3cea786be27d99c8acc50ea00f3e9fdff3b24e`. The independent reviewer MUST verify original compressed machine dossier bytes, not only this packet summary.
- Priority: original `P0`; no previously approved review for this item.

## Original pinned whole-file reading and source-grounded findings

- Lines 1–5: copyright and MPL-2.0 source notice. This establishes source notice identity only, not XGBA redistribution clearance.
- Lines 6–7 and 21–22: `ISA_ARM_H` guard. Lines 9–11 and 19: import `mgba-util/common.h` and C/C++ linkage guards; verify their actual definitions and conditional compilation before claiming ABI compatibility.
- Line 13: `ARM_PREFETCH_CYCLES` expands to `(1 + cpu->memory.activeSeqCycles32)`. The free identifier `cpu` is a caller-scope precondition, not a side-effect-free standalone function; its field layout and timing semantics belong to `ARMCore` and the instruction executor.
- Lines 15–17: incomplete `struct ARMCore`, function pointer `ARMInstruction(struct ARMCore*, uint32_t opcode)`, and external `_armTable[0x1000]`. This declares a **4096-entry dispatch-table ABI** but does not establish initialization, table completeness, bounds, runtime correctness, or all platform configurations.

## Pinned producer/consumer and build observations (NOT whole-program closure)

- `src/arm/isa-arm.c` pinned Git blob `af697fa0866fd7511cc430d4a2261704918e15bf` includes this header and defines `const ARMInstruction _armTable[0x1000] = { DECLARE_ARM_EMITTER_BLOCK(_ARMInstruction) };`; the instruction-definition macro uses `ARM_PREFETCH_CYCLES`.
- `src/arm/arm.c` pinned Git blob `0b92d7f55f1fb853d4b1b9c9163ee086126066e2` includes this header. Its ARM-step code indexes `_armTable[((opcode >> 16) & 0xFF0) | ((opcode >> 4) & 0x00F)]`, an expression with a syntactic range 0–4095; failed ARM conditions add `ARM_PREFETCH_CYCLES`. This is a source-level bound, not a native test.
- `src/arm/CMakeLists.txt` pinned Git blob `a86f0bea1f38aeb88222fb5b532b4ea9e256767f` lists both `arm.c` and `isa-arm.c` and exports the ARM source set. Actual inclusion into all build variants, table-emitter expansion, linker resolution, platform ABI and external consumers remain for independent verification.
- `include/mgba/internal/arm/arm.h` pinned Git blob `5ef2da96519ac3f429b65fd6d323be0775f3b3cf` defines `ARMCore` and its memory layout; no safety guarantee about arbitrary pointers follows from the header alone.
- Original packet lists two lexical incoming includes and one unresolved `mgba-util/common.h` include. These are **lexical candidates**, not compiler-confirmed complete dependency closure. The separate PR2 configured compiler graph is evidence for a particular build only; do not silently transplant its conclusions.

## Reviewer obligations / explicit nonclaims

Independently fetch and read **all 22 original source lines**, verify Git blob and SHA-256 against original compressed dossier bytes, trace `common.h` / CXX guards, table-emitter generation, the actual declaration/definition/linker consumers, active sequential-cycle field, conditional build configuration and relevant upstream tests. Verify MPL-2.0 source notice and file-scoped review scope; future combined distribution is NOT CLEARED. Check any native/compiled evidence against its exact source/configuration and distinguish source, synthetic, native, stock gameplay, save/restart and physical Flash. Resolve every substantive objection or leave `NEEDS_REVIEW`. An independent Copilot reviewer may append an attributable v4 receipt and attestation ONLY after all fail-closed validator requirements, exact-head PR/push executed CI and reviewer/analyst separation pass. No legacy external-human approval, gate change or Phase 2 is authorized.

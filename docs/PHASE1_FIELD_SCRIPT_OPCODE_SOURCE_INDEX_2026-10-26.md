# Phase 1 — full pinned field-script opcode source index (26 October 2026)

**Decision: FAIL_INCOMPLETE. Zero independently approved whole-file semantic dispositions.**

This additive source interpreter indexes the complete pinned `asm/macros/event.inc` assembler macro file against the native `data/script_cmd_table.inc` runtime dispatch table, resolves each handler definition in `src/scrcmd.c`, and pins the bytecode interpreter in `src/script.c`. All four sources use the exact FireRed revision `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and exact Git blob SHA-1 identities.

**Source-index findings:** 257 named assembler macros; 213 contiguous native runtime opcode entries (0x00–0xD4); 213 runtime handler definitions; 209 direct opcode-producing macros; 48 non-opcode helper macros. Four alternate opcodes (0x50, 0x52, 0x54, 0x56) are **not missing handlers or missing encodings**: they are conditionally emitted by the existing `applymovement`, `waitmovement`, `removeobject` and `addobject` macros when an explicit map argument is supplied (event.inc:597–653).

The index classifies **177 fixed-width direct macros** (only when every body statement is a single-operand byte/halfword/word directive) and **32 conditional or delegating direct macros**, including variable-length `trainerbattle` and map-dependent movement/warp paths. The latter deliberately have **no claimed fixed byte width**. Each opcode record includes the assembler macro and literal source line, dispatch table line, runtime handler definition line, and classification.

Reproduce via `python3 tools/phase1_event_opcode_semantic_index.py upstream/pokefirered` after checking out the exact pinned FireRed revision. The source index verifies four Git blobs and nine fail-closed negative controls and emits SHA-256-bound deterministic JSON under `audit-output/`. The existing cross-repository CI archives this evidence alongside the v6 40-candidate review queue.

**Unresolved:** recursively expand all helper/conditional macros; prove every runtime argument consumer and length for every variant; test compiler/linker outputs and executable pointer bounds; obtain independent whole-file review; certify editor/emulator compatibility. Source-index coverage is not a semantic signoff and does not authorize Phase 2.

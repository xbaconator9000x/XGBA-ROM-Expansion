# Analyst complete-file candidate 0046 — FireRed map-script type constants

**State: ANALYST-PREPARED ONLY; independent review pending.** Source: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, path `include/constants/map_scripts.h`, Git blob SHA-1 `1353de360cf1e00b6efbb26ec59c4822c99b59bf`. Complete **12-line** file inspected, not a sampled snippet. Original lexical priority is preserved by the machine queue; this manual candidate does not modify it.

## Complete file disposition

| Lines | Full-file contents and role |
| --- | --- |
| 1–2 | `GUARD_CONSTANTS_MAP_SCRIPTS_H` include guard opens |
| 3 | Blank separator |
| 4 | `MAP_SCRIPT_ON_LOAD = 1` |
| 5 | `MAP_SCRIPT_ON_FRAME_TABLE = 2` |
| 6 | `MAP_SCRIPT_ON_TRANSITION = 3` |
| 7 | `MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE = 4` |
| 8 | `MAP_SCRIPT_ON_RESUME = 5` |
| 9 | `MAP_SCRIPT_ON_DIVE_WARP = 6`, annotated `Unused` |
| 10 | `MAP_SCRIPT_ON_RETURN_TO_FIELD = 7` |
| 11 | Blank separator |
| 12 | Include guard closes |

The seven distinct numeric values are contiguous **1–7**, nonzero and fit the FireRed map-script header's one-byte type tag. **Zero is not a valid type in this header**: `src/script.c` (blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`, lines 382–399) uses a zero byte to terminate the tag/pointer list and advances five bytes per entry. The native `map_script` macro (blob `83ef472c926ce767c9133ab9bd6922280b38bb2d`, `asm/macros/map.inc` lines 9–20) emits one byte of type and a four-byte pointer. Table types 2 and 4 use the separate `map_script_2` records (two-byte variable, two-byte comparison, four-byte pointer), consumed by `MapHeaderCheckScriptTable` in `src/script.c` lines 409–435.

`src/script.c` lines 438–483 has wrappers for all seven defined tags: load, transition, resume, return-to-field, dive-warp, frame-table and warp-into-map table. The header's **type-6 `Unused` annotation is not the same as the absence of a wrapper**: `RunOnDiveWarpMapScript` explicitly calls `MapHeaderRunScriptType(MAP_SCRIPT_ON_DIVE_WARP)` at lines 458–461. The [pinned dive fallback trace](../PHASE1_P0_FIRERED_DIVE_SCRIPT_FALLBACK_2026-10-27.md) now identifies a concrete source caller: `SetDiveWarp` in `src/overworld.c` invokes the type-6 wrapper when no matching dive/emerge connection exists, with a separate non-null map-header connection-pointer precondition. This establishes a callable native fallback, **not** an authored type-6 table entry or observed gameplay execution.

Poryscript's `emitMapScriptStatement` (pinned `emitter/emitter.go` blob `d35843ef29929ead47351646d7a33dd5c692b850`) emits the symbolic type labels into FireRed assembler records; it does not replace the numeric ABI. An XGBA extension must preserve type IDs, zero sentinel and two distinct record widths, or supply a versioned reader/translator with explicit provenance.

## Dependencies and unresolved questions

**Direct dependencies:** C preprocessor inclusion of this header; Poryscript-emitted `MAP_SCRIPT_*` symbolic types; FireRed `map_script` / `map_script_2` assembler macros; `MapHeaderGetScriptTable`, `MapHeaderRunScriptType`, `MapHeaderCheckScriptTable` and their callers; map header pointer and generated map script assets. **Unresolved:** exact include-site census and any alternate build flags; type-6 authored-table and null-header caller reachability; malformed tag/table lengths; compiled assembler byte fixture; editor round trip and runtime variants. This record is complete with respect to the **12-line source file**, not the transitive subsystem.

## Acceptance boundary

An independent reviewer must verify the complete pinned blob, macro/header consumers, actual call-site reachability and applicable build/runtime evidence before an authenticated whole-file approval can be recorded. This analyst record **does not** change the authoritative mapping gate, claim a compiled/runtime pass, or authorize Phase 2. **FAIL_INCOMPLETE; independent approvals 0/14,834.**

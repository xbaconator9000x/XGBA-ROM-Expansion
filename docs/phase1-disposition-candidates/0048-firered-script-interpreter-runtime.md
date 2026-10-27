# Analyst whole-file candidate 0048 — FireRed script interpreter and map-script readers

**ANALYST-PREPARED ONLY; independent review pending.** Pinned source: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c), Git blob SHA-1 `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`. Inspected all **583 authored lines** (584 split lines including trailing newline), including failure and RAM-script paths.

## Complete-file semantic disposition

| Lines | Role and relevant conditions |
| --- | --- |
| 1–43 | Includes, external helpers, RAM-script magic 51, mode/status enums, EWRAM return pointer/timer, two static contexts, UI/quest flags and table symbols |
| 45–81 | Context setup, bytecode/native selection and stop; `InitScriptContext` resets pointers, mode, stack depth, locals and return stack but **does not explicitly reset `comparisonResult`** |
| 82–141 | Stopped/native/bytecode dispatcher; null pointer stops, special `gNullScriptPtr` HALTs, opcode byte indexes the handler table, end check precedes handler call, handler return yields |
| 142–196 | Call/return stack, jumps and little-endian byte readers; push rejects when `stackDepth + 1 >= ARRAY_COUNT(stack)` and `ScriptCall` does not inspect push failure |
| 197–303 | Field control lock, quest-log input, message cancel/walkaway and signpost state |
| 305–380 | Global context running/waiting/shutdown lifecycle and synchronous immediate context loop |
| 382–437 | Map-script list reads **type byte + 32-bit pointer**, terminated by type zero; conditional frame/warp tables read **two 16-bit variables + 32-bit pointer**, terminated by zero first variable |
| 438–485 | Seven map-script wrappers including type-6 dive fallback; frame table uses global context with quest-log suppression; other wrappers can execute immediately |
| 486–583 | RAM-script checksum, clearing, size/magic/location/object checks, save substitution and wonder-card validation; oversized `InitRamScript` input returns false **after clearing** the existing area |

## Dependencies and boundaries

The [dispatch table](0047-firered-script-command-dispatch-table.md) binds opcodes `0x00`–`0xd4` to handlers; [public header](0049-firered-script-context-abi-header.md) defines context field order and API; [map-script constants](0046-firered-map-script-type-constants.md) define the separate 1–7 map-header tags; [map macros](0027-firered-map-assembly-macros.md) emit native records. The [type-6 dive fallback dossier](../PHASE1_P0_FIRERED_DIVE_SCRIPT_FALLBACK_2026-10-27.md) traces its conditional caller and connection-pointer precondition. Save data and CRC depend on the save block and mystery-gift code.

## Outstanding verification

The missing explicit comparison-result reset and ignored stack-full return are **source-level review questions**, not demonstrated gameplay faults. A malformed map-script list has no local length bound beyond its sentinel. Require reachable-caller analysis, compiled symbol/structure offsets, both compiler variants, valid/invalid opcode and stack-depth tests, immediate-context lifetime, RAM-script/save-state compatibility, editor translation and independent whole-file review. No approval or Phase 2 change. **FAIL_INCOMPLETE.**

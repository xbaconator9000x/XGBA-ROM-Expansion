# Analyst whole-file candidate 0050 — FireRed event-variable and flag API

**ANALYST-PREPARED ONLY; no independent review.** Pinned source [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/event_data.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/event_data.h), Git blob SHA-1 `285b4cc83ca23f96ce0d5bee46ce2e902011d6b6`. All **58 authored lines** inspected (59 split lines including final newline).

## Complete-file disposition

| Lines | Source semantics |
| --- | --- |
| 1–4 | Include guard and `global.h` dependency |
| 6–24 | Twelve `u16` extern special variables `0x8000`–`0x800B` plus seven named `u16` externs (facing, result, last-talked, box ID/position and text colors) |
| 26–37 | Event-data init/clear, National Pokédex, Mystery Event/Gift, RTC toggles and state queries |
| 38–46 | `GetVarPointer`, `VarGet`, `VarSet`, graphics-ID lookup, flag pointer/set/clear/get API; IDs are `u16`, values/flags have distinct return types |
| 47–56 | Repeated compatible declarations of `GetVarPointer`, `IsMysteryGiftEnabled`, `IsNationalPokedexEnabled`, `ClearTempFieldEventData`, plus reset and RSE-specific helpers |
| 58 | Closing include guard |

This header **declares** symbols and their types; it does not define variable ID ranges, storage banking, persistence, pointer validity or setter failure semantics. Repeated prototypes do not create additional symbols.

## Dependencies and open evidence

Pinned [`src/script.c`](0048-firered-script-interpreter-runtime.md) calls `VarGet` in the conditional map-script table reader; `ScrCmd_*` handlers consume variable and flag APIs. The underlying event-data implementation, saved/temporary variable address resolution, script opcode semantics, map-editor mapping and build variants remain to be traced and tested. No compiled ABI, runtime verification or independent approval. **Phase 1 FAIL_INCOMPLETE.**

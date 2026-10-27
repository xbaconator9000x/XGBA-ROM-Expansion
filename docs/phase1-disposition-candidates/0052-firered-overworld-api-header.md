# Analyst whole-file candidate 0052 — FireRed overworld, warp and callback ABI

**ANALYST-PREPARED ONLY; no independent review.** Pinned source [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/overworld.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/overworld.h), Git blob SHA-1 `b4f56bee63cca43c8696b49e13558fd8a99fac6c`. All **192 authored lines** inspected (193 split lines including final newline).

## Complete-file disposition

| Lines | Source semantics |
| --- | --- |
| 1–4 | Guard and `global.h` / `main.h` dependencies |
| 6–28 | Link-key protocol constants `0x00`, `0x11`–`0x1d`; movement modes free/frozen/scripted = 0/1/2 |
| 30–45 | Four-byte `LinkPlayerObjectEvent` field declaration, three signed 16-bit credit command fields, map-music change modes 0/1/2 |
| 47–61 | Direction vectors, four link-player event records, callbacks, last-used warp and link/field globals |
| 63–91 | Object-template setters, signed 8-bit map/warp/coordinate destinations, dynamic/fixed dive/hole/escape warp setters, map-type/music/flash API |
| 93–128 | Link state, map-header lookup, field entry/return callbacks, game stats, current map layout setter taking `u16`, transition and saved-game functions |
| 130–176 | More field/quest-log callbacks, map type and link checks, reset/whiteout/music helpers and warp destination/query functions |
| 177–181 | `SetDiveWarpEmerge` and `SetDiveWarpDive` take `u16` coordinates; `ClearFieldCallback` declaration exists only under `REVISION >= 0xA` |
| 183–192 | External tilemap buffers, held-key variable and guard closure |

This file is an **interface**, not implementation proof. `IsMapTypeOutdoors` appears twice with return spellings `u8` and `bool8`; inspect the underlying typedef before asserting a signature mismatch. Signed 8-bit warp parameters are a distinct representability boundary from `u16` map layout IDs and `u16` dive coordinates.

## Dependencies and unresolved checks

Pinned `src/overworld.c` implements conditional dive fallback, fixed-warp lifetime and map layout selection, as traced in [the dive dossier](../PHASE1_P0_FIRERED_DIVE_SCRIPT_FALLBACK_2026-10-27.md). [`src/script.c`](0048-firered-script-interpreter-runtime.md) executes map-script wrappers; [fieldmap API](0051-firered-fieldmap-public-contract.md) reads native connections/collision. Require caller reachability, source build revision branches, compiled struct offsets and signed conversion, save/warp state, editor interoperability, runtime and independent whole-file review. **Phase 1 FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0053 — FireRed field input and dive trigger interface

**ANALYST-PREPARED ONLY; no independent review.** Pinned source [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_control_avatar.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_control_avatar.h), Git blob SHA-1 `a6631493d7eb2cb59d4883566ed1f2df0fb2c232`. All **40 authored lines** inspected (41 split lines including final newline).

## Complete-file disposition

| Lines | Source semantics |
| --- | --- |
| 1–4 | Guard and global type import |
| 6–24 | `FieldInput` declares **13 one-bit `bool8` flags** (buttons, directional state, movement, wild encounter and four unnamed-state flags) followed by `u8 dpadDirection`; packing and `sizeof` depend on compiler ABI |
| 26 | External `gFieldInputRecord` state declaration |
| 28–38 | Wild encounter/poison-step resets, cable-club warp, boulder interaction, `dive_warp(MapPosition *, u16 behavior)`, directional stairs, link-player/coordinate event scripts, input clearing/processing, key capture and Victory Road boulder switch |
| 40 | Closing guard |

The bitfields are **not** a portable serialized 13-bit layout without compiler/ABI verification. The `dive_warp` prototype proves a field-control API surface, not that any authored map can execute the type-6 map script. Event scripts, native warp records and collision behavior are distinct consumers.

## Dependencies and open checks

Pinned `src/field_control_avatar.c` must be traced through `SetDiveWarpDive` / `SetDiveWarpEmerge` and [the dive fallback dossier](../PHASE1_P0_FIRERED_DIVE_SCRIPT_FALLBACK_2026-10-27.md); [overworld interface](0052-firered-overworld-api-header.md) and [fieldmap interface](0051-firered-fieldmap-public-contract.md) supply adjacent contracts. Pending: native `sizeof`/`offsetof` across compiler variants, bitfield packing, key-state transitions, map-header connection nullability, authored/runtime dive reachability and independent review. **Phase 1 FAIL_INCOMPLETE.**

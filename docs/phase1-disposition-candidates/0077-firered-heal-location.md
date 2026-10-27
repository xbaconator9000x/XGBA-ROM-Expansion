# Analyst whole-file candidate 0077 — Whiteout respawn location record ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/heal_location.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/heal_location.h); exact pinned Git blob SHA-1 `4c64def01b91c05593f1b88fe2e01adc2ea61450`. Inspected the **entire 17-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

HealLocation stores signed 8-bit mapGroup/mapNum and signed 16-bit x/y; GetHealLocation(u32) returns a const pointer and SetWhiteoutRespawnWarpAndHealerNpc accepts a mutable WarpData pointer.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_HEAL_LOCATION_H`
- L2: `#define GUARD_HEAL_LOCATION_H`
- L4: `#include "global.h"`
- L6: `struct HealLocation`
- L7: `{`
- L8: `s8 mapGroup;`
- L9: `s8 mapNum;`
- L10: `s16 x;`
- L11: `s16 y;`
- L12: `};`
- L14: `const struct HealLocation *GetHealLocation(u32 loc);`
- L15: `void SetWhiteoutRespawnWarpAndHealerNpc(struct WarpData * warp);`
- L17: `#endif // GUARD_HEAL_LOCATION_H`

## Dependencies, expansion relevance and independent review

Check struct packing and sign conversions, valid heal-location indices, map-group limits, coordinates and warp/save persistence; no source-level evidence here proves respawn target validity. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0088 — Special save-warp flag and postgame state API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save_location.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save_location.h); exact pinned Git blob SHA-1 `2d2cb197494b663dcb8e687f9f7267576bdc3c34`. Inspected the **entire 16-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header defines five save-warp bit flags (bits 0,1,2,3,7) and four functions for map save-warp status, Pokémon Center detection and Pokédex/postgame flags.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SAVE_LOCATION_H`
- L2: `#define GUARD_SAVE_LOCATION_H`
- L5: `#define CONTINUE_GAME_WARP           (1 << 0)`
- L6: `#define POKECENTER_SAVEWARP          (1 << 1)`
- L7: `#define LOBBY_SAVEWARP               (1 << 2)`
- L8: `#define UNK_SPECIAL_SAVE_WARP_FLAG_3 (1 << 3)`
- L9: `#define CHAMPION_SAVEWARP            (1 << 7)`
- L11: `void TrySetMapSaveWarpStatus(void);`
- L12: `bool32 IsCurMapPokeCenter(void);`
- L13: `void SetUnlockedPokedexFlags(void);`
- L14: `void SetPostgameFlags(void);`
- L16: `#endif // GUARD_SAVE_LOCATION_H`

## Dependencies, expansion relevance and independent review

Trace flag persistence, map type classification, dynamic warp ID bounds and replay after save load; note the unexplained bit-3 name is not proof of unused behavior. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

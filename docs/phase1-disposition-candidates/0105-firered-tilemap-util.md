# Analyst whole-file candidate 0105 — Tilemap utility geometry and movement ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/tilemap_util.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/tilemap_util.h); exact pinned Git blob SHA-1 `b8388c6f599fee49933deb9ef7a70ffc83b5d901`. Inspected the **entire 12-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The seven APIs allocate/free tilemap IDs, attach background and tilemap pointer with u16 dimensions, set position and rectangle, move by signed 8-bit delta and update.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_TILEMAP_UTIL_H`
- L2: `#define GUARD_TILEMAP_UTIL_H`
- L4: `void TilemapUtil_Init(u8 numTilemapIds);`
- L5: `void TilemapUtil_Free(void);`
- L6: `void TilemapUtil_SetTilemap(u8 tilemapId, u8 bg, const void *tilemap, u16 width, u16 height);`
- L7: `void TilemapUtil_SetPos(u8 tilemapId, u16 destX, u16 destY);`
- L8: `void TilemapUtil_SetRect(u8 tilemapId, u16 x, u16 y, u16 width, u16 height);`
- L9: `void TilemapUtil_Move(u8 tilemapId, u8 mode, s8 param);`
- L10: `void TilemapUtil_Update(u8 tilemapId);`
- L12: `#endif //GUARD_TILEMAP_UTIL_H`

## Dependencies, expansion relevance and independent review

Check tilemap ID bounds, pointer lifetime, width/height multiplication, BG tile buffer limits, clipping and signed movement; this header omits global.h. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

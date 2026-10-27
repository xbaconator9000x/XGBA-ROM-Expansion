# Analyst whole-file candidate 0103 — Tileset animation scheduler and named maps

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/tileset_anims.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/tileset_anims.h); exact pinned Git blob SHA-1 `b85f6ecd5c9b3b65670d5a01dc34fbc5cead5d91`. Inspected the **entire 16-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header exposes animation init, secondary init, update, VRAM transfer and six named tileset animation initializers (general, Celadon City/Gym, Vermilion Gym, Silph Co, Mt Ember).

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_TILESET_ANIMS_H`
- L2: `#define GUARD_TILESET_ANIMS_H`
- L4: `void InitTilesetAnimations(void);`
- L5: `void InitSecondaryTilesetAnimation(void);`
- L6: `void UpdateTilesetAnimations(void);`
- L7: `void TransferTilesetAnimsBuffer(void);`
- L9: `void InitTilesetAnim_General(void);`
- L10: `void InitTilesetAnim_CeladonCity(void);`
- L11: `void InitTilesetAnim_VermilionGym(void);`
- L12: `void InitTilesetAnim_CeladonGym(void);`
- L13: `void InitTilesetAnim_SilphCo(void);`
- L14: `void InitTilesetAnim_MtEmber(void);`
- L16: `#endif // GUARD_TILESET_ANIMS_H`

## Dependencies, expansion relevance and independent review

Trace primary/secondary tileset selection, DMA transfer size, VRAM ownership, map transition cleanup, per-map animation IDs and frame timing. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0079 — Dungeon map preview graphics and metadata ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/map_preview_screen.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/map_preview_screen.h); exact pinned Git blob SHA-1 `7fbcc675e82d6bc41bd4cebc2217f74643fb703a`. Inspected the **entire 64-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The preview enum enumerates named locations ending at MPS_COUNT; three preview type constants distinguish cave, forest and any. MapPreviewScreen stores u8 mapsec/type, u16 flagId and three const void pointers for tiles, tilemap and palette. Public APIs manage preview selection, flags, durations, BG graphics and unload.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_MAP_PREVIEW_SCREEN_H`
- L2: `#define GUARD_MAP_PREVIEW_SCREEN_H`
- L4: `enum MapPreviewScreenId`
- L5: `{`
- L6: `MPS_VIRIDIAN_FOREST = 0u,`
- L7: `MPS_MT_MOON,`
- L8: `MPS_DIGLETTS_CAVE,`
- L9: `MPS_ROCK_TUNNEL,`
- L10: `MPS_POKEMON_TOWER,`
- L11: `MPS_SAFARI_ZONE,`
- L12: `MPS_SEAFOAM_ISLANDS,`
- L13: `MPS_POKEMON_MANSION,`
- L14: `MPS_ROCKET_HIDEOUT,`
- L15: `MPS_SILPH_CO,`
- L16: `MPS_VICTORY_ROAD,`
- L17: `MPS_CERULEAN_CAVE,`
- L18: `MPS_POWER_PLANT,`
- L19: `MPS_MT_EMBER,`
- L20: `MPS_ROCKET_WAREHOUSE,`
- L21: `MPS_MONEAN_CHAMBER,`
- L22: `MPS_DOTTED_HOLE,`
- L23: `MPS_BERRY_FOREST,`
- L24: `MPS_ICEFALL_CAVE,`
- L25: `MPS_LOST_CAVE,`
- L26: `MPS_ALTERING_CAVE,`
- L27: `MPS_PATTERN_BUSH,`
- L28: `MPS_LIPTOO_CHAMBER,`
- L29: `MPS_WEEPTH_CHAMBER,`
- L30: `MPS_TDILFORD_CHAMBER,`
- L31: `MPS_SCUFIB_CHAMBER,`
- L32: `MPS_RIXY_CHAMBER,`
- L33: `MPS_VIAPOIS_CHAMBER,`
- L34: `MPS_COUNT`
- L35: `};`
- L37: `#define MPS_TYPE_CAVE   0`
- L38: `#define MPS_TYPE_FOREST 1`
- L39: `#define MPS_TYPE_ANY    2`
- L41: `struct MapPreviewScreen`
- L42: `{`
- L43: `u8 mapsec;`
- L44: `u8 type;`
- L45: `u16 flagId;`
- L46: `const void *tilesptr;`
- L47: `const void *tilemapptr;`
- L48: `const void *palptr;`
- L49: `};`
- L51: `u16 MapPreview_CreateMapNameWindow(u8 id);`
- L52: `void MapPreview_SetFlag(u16 a0);`
- L53: `u16 MapPreview_GetDuration(u8 id);`
- L54: `bool8 MapHasPreviewScreen(u8 mapsec, u8 type);`
- L55: `bool32 ForestMapPreviewScreenIsRunning(void);`
- L56: `const struct MapPreviewScreen * GetDungeonMapPreviewScreenInfo(u8 mapsec);`
- L57: `bool32 MapHasPreviewScreen_HandleQLState2(u8 mapsec, u8 type);`
- L58: `void MapPreview_InitBgs(void);`
- L59: `void MapPreview_LoadGfx(u8 mapsec);`
- L60: `bool32 MapPreview_IsGfxLoadFinished(void);`
- L61: `void MapPreview_Unload(s32 windowId);`
- L62: `void MapPreview_StartForestTransition(u8 mapsec);`
- L64: `#endif //GUARD_MAP_PREVIEW_SCREEN_H`

## Dependencies, expansion relevance and independent review

Verify enum-to-table cardinality, map section and type matching, graphics pointers and lengths, load/unload async completion, window IDs, quest-log state and expanded asset relocation. This header does not include global.h despite fixed-width types. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

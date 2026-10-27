# Analyst whole-file candidate 0095 — Region-map naming and fly-map callback ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/region_map.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/region_map.h); exact pinned Git blob SHA-1 `fec528e1bb7219b7ccc235ee2251a57ff5d1c343`. Inspected the **entire 20-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The enum defines normal, wall and fly region map types plus count; three GetMapName variants return u8 destination pointers, while InitRegionMapWithExitCB stores a void callback and CB2_OpenFlyMap enters Fly map.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_REGION_MAP_H`
- L2: `#define GUARD_REGION_MAP_H`
- L4: `#include "global.h"`
- L5: `#include "bg.h"`
- L7: `enum {`
- L8: `REGIONMAP_TYPE_NORMAL,`
- L9: `REGIONMAP_TYPE_WALL,`
- L10: `REGIONMAP_TYPE_FLY,`
- L11: `REGIONMAP_TYPE_COUNT`
- L12: `};`
- L14: `u8 *GetMapName(u8 *dest, u16 mapsec, u16 fill);`
- L15: `u8 *GetMapNameGeneric(u8 *dest, u16 mapsec);`
- L16: `u8 *GetMapNameGeneric_(u8 *dest, u16 mapsec);`
- L17: `void InitRegionMapWithExitCB(u8 type, void (*callback)(void));`
- L18: `void CB2_OpenFlyMap(void);`
- L20: `#endif // GUARD_REGION_MAP_H`

## Dependencies, expansion relevance and independent review

Verify destination string buffer capacity, map section index bounds, callback lifetime, map ID expansion and exit/warp consistency; includes global.h and bg.h. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

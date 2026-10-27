# Analyst whole-file candidate 0102 — Pokédex species area marker API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/wild_pokemon_area.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/wild_pokemon_area.h); exact pinned Git blob SHA-1 `f1d67fd8603ad13e910cab331537d4ab67c0cd5b`. Inspected the **entire 6-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header declares GetSpeciesPokedexAreaMarkers(u16 species, Subsprite*) returning signed 32-bit, without defining the output buffer size or including global.h.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_WILD_POKEMON_AREA_H`
- L2: `#define GUARD_WILD_POKEMON_AREA_H`
- L4: `s32 GetSpeciesPokedexAreaMarkers(u16 species, struct Subsprite * subsprites);`
- L6: `#endif //GUARD_WILD_POKEMON_AREA_H`

## Dependencies, expansion relevance and independent review

Verify species ID bounds, subsprite destination capacity, encounter-to-area mapping and map section expansion; include-order dependencies remain. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

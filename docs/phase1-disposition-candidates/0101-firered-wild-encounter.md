# Analyst whole-file candidate 0101 — Wild encounter table shapes and map lookup ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/wild_encounter.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/wild_encounter.h); exact pinned Git blob SHA-1 `b730103069f14a7d7147547d5bfad82bf082a6de`. Inspected the **entire 53-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

Constants fix land=12, water=5, rock=5 and fishing=10 slots, with nine Altering Cave tables. WildPokemon packs min/max level and species, WildPokemonInfo holds rate and pointer, and WildPokemonHeader contains u8 map group/number and four encounter table pointers. DisableWildEncounters and SweetScentWildEncounter are each declared twice with compatible signatures.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_WILD_ENCOUNTER_H`
- L2: `#define GUARD_WILD_ENCOUNTER_H`
- L4: `#include "global.h"`
- L6: `#define LAND_WILD_COUNT     12`
- L7: `#define WATER_WILD_COUNT    5`
- L8: `#define ROCK_WILD_COUNT     5`
- L9: `#define FISH_WILD_COUNT     10`
- L11: `#define NUM_ALTERING_CAVE_TABLES 9`
- L13: `struct WildPokemon`
- L14: `{`
- L15: `u8 minLevel;`
- L16: `u8 maxLevel;`
- L17: `u16 species;`
- L18: `};`
- L20: `struct WildPokemonInfo`
- L21: `{`
- L22: `u8 encounterRate;`
- L23: `const struct WildPokemon *wildPokemon;`
- L24: `};`
- L26: `struct WildPokemonHeader`
- L27: `{`
- L28: `u8 mapGroup;`
- L29: `u8 mapNum;`
- L30: `const struct WildPokemonInfo *landMonsInfo;`
- L31: `const struct WildPokemonInfo *waterMonsInfo;`
- L32: `const struct WildPokemonInfo *rockSmashMonsInfo;`
- L33: `const struct WildPokemonInfo *fishingMonsInfo;`
- L34: `};`
- L36: `extern const struct WildPokemonHeader gWildMonHeaders[];`
- L38: `void DisableWildEncounters(bool8 disabled);`
- L39: `bool8 StandardWildEncounter(u32 currMetatileAttrs, u16 previousMetaTileBehavior);`
- L40: `bool8 SweetScentWildEncounter(void);`
- L41: `bool8 DoesCurrentMapHaveFishingMons(void);`
- L42: `void FishingWildEncounter(u8 rod);`
- L43: `u16 GetLocalWildMon(bool8 *isWaterMon);`
- L44: `u16 GetLocalWaterMon(void);`
- L45: `bool8 UpdateRepelCounter(void);`
- L46: `void DisableWildEncounters(bool8 state);`
- L47: `u8 GetUnownLetterByPersonalityLoByte(u32 personality);`
- L48: `bool8 SweetScentWildEncounter(void);`
- L49: `void SeedWildEncounterRng(u16 randVal);`
- L50: `void ResetEncounterRateModifiers(void);`
- L51: `bool8 TryStandardWildEncounter(u32 currMetatileAttrs);`
- L53: `#endif // GUARD_WILD_ENCOUNTER_H`

## Dependencies, expansion relevance and independent review

Critical map/editor interface: verify array lengths and terminators, encounter rate and level bounds, map-group index width, pointer placement, fishing/repel state, RNG and saved encounter modifiers. Duplicated declarations are not independent definitions. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

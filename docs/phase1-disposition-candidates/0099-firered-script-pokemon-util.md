# Analyst whole-file candidate 0099 — Scripted Pokémon gift, party and wild spawn ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_pokemon_util.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_pokemon_util.h); exact pinned Git blob SHA-1 `5f7dc43065d78425fe5202d6c483f80fdac8b205`. Inspected the **entire 11-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The six functions give a mon or egg, set a party move slot, heal/reduce party and create scripted wild mon. Species and move IDs are u16, level and party indices u8, with two opaque u32 parameters for gifts.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SCRIPT_POKEMON_UTIL_H`
- L2: `#define GUARD_SCRIPT_POKEMON_UTIL_H`
- L4: `bool8 ScriptGiveMon(u16 species, u8 level, u16 item, u32 unk1, u32 unk2, u8 unk3);`
- L5: `bool8 ScriptGiveEgg(u16 species);`
- L6: `void ScriptSetMonMoveSlot(u8 partyIdx, u16 move, u8 slot);`
- L7: `void HealPlayerParty(void);`
- L8: `void ReducePlayerPartyToThree(void);`
- L9: `void CreateScriptedWildMon(u16 species, u8 level, u16 item);`
- L11: `#endif //GUARD_SCRIPT_POKEMON_UTIL_H`

## Dependencies, expansion relevance and independent review

Verify species/move table bounds, party capacity, PC fallback, move-slot bounds, item encoding and save persistence; opaque gift arguments require implementation inspection. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

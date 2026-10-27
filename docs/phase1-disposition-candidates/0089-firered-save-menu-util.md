# Analyst whole-file candidate 0089 — Save-screen stat field encoding

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save_menu_util.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save_menu_util.h); exact pinned Git blob SHA-1 `7085520b4ee4c235ada2ee8b405c035fde788f4a`. Inspected the **entire 16-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The enum names player name, Pokédex, time, location, badges and right-aligned hour display; SaveStatToString accepts a u8 stat selector, output pointer and a third u8 argument.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SAVE_MENU_UTIL_H`
- L2: `#define GUARD_SAVE_MENU_UTIL_H`
- L4: `enum SaveStat`
- L5: `{`
- L6: `SAVE_STAT_NAME = 0,`
- L7: `SAVE_STAT_POKEDEX,`
- L8: `SAVE_STAT_TIME,`
- L9: `SAVE_STAT_LOCATION,`
- L10: `SAVE_STAT_BADGES,`
- L11: `SAVE_STAT_TIME_HR_RT_ALIGN`
- L12: `};`
- L14: `void SaveStatToString(u8 a0, u8 *a1, u8 a2);`
- L16: `#endif //GUARD_SAVE_MENU_UTIL_H`

## Dependencies, expansion relevance and independent review

Verify enum-to-switch coverage, destination buffer size, time formatting, map-name lookup and unvalidated stat IDs; no global.h include is present despite u8 types. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

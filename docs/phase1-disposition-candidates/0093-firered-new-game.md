# Analyst whole-file candidate 0093 — New-game save identity initialization

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/new_game.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/new_game.h); exact pinned Git blob SHA-1 `bf048718a63441d6da464bc46b3fa39f630c7c3c`. Inspected the **entire 14-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header exposes gDifferentSaveFile and functions to set/copy 32-bit trainer ID into byte buffers, initialize new-game data, reset menu/mon globals and set SaveBlock2 defaults.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_NEW_GAME_H`
- L2: `#define GUARD_NEW_GAME_H`
- L4: `#include "global.h"`
- L6: `extern bool8 gDifferentSaveFile;`
- L8: `void SetTrainerId(u32 trainerId, u8 *dst);`
- L9: `void CopyTrainerId(u8 *dst, u8 *src);`
- L10: `void NewGameInitData(void);`
- L11: `void ResetMenuAndMonGlobals(void);`
- L12: `void Sav2_ClearSetDefault(void);`
- L14: `#endif // GUARD_NEW_GAME_H`

## Dependencies, expansion relevance and independent review

Check trainer ID byte order and destination capacity, initial save version, encryption keys, RNG state, heap pointer lifetime and different-save-file transitions. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

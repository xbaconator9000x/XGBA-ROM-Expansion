# Analyst whole-file candidate 0069 — Flash and barn-door screen transition interface

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_screen_effect.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_screen_effect.h); exact pinned Git blob SHA-1 `e6736298ac657350963eaf6647f037c1065176e2`. Inspected the **entire 15-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The file exports flash animation, scanline-buffer write, safari/whiteout callbacks, outward barn-door wipe, a task callback with u8 ID and const signed 32-bit maximum flash level.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_SCREEN_EFFECT_H`
- L2: `#define GUARD_FIELD_SCREEN_EFFECT_H`
- L4: `#include "global.h"`
- L6: `void AnimateFlash(u8);`
- L7: `void FieldCB_SafariZoneRanOutOfBalls(void);`
- L8: `void DoOutwardBarnDoorWipe(void);`
- L9: `void Task_BarnDoorWipe(u8 taskId);`
- L10: `void FieldCB_RushInjuredPokemonToCenter(void);`
- L11: `void WriteFlashScanlineEffectBuffer(u8 flashLevel);`
- L13: `extern const s32 gMaxFlashLevel;`
- L15: `#endif // GUARD_FIELD_SCREEN_EFFECT_H`

## Dependencies, expansion relevance and independent review

Check scanline buffer bounds, flash-level validation, transition task ownership, IRQ/DMA interaction, fade completion and duplicate callback declaration with field_fadetransition.h. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

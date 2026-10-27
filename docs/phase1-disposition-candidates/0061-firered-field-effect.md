# Analyst whole-file candidate 0061 — Field-effect dispatch and shared callback state

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect.h); exact pinned Git blob SHA-1 `23f309fe503bb0bb432f921b6ec79705ae541f88`. Inspected the **entire 31-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header exports an eight-element u32 argument array, two callback function-pointer globals and effect dispatch/active-list management; other declarations cover teleport, warp, trainer/mon sprites, palette tint and resource destruction. Effect IDs depend on constants/field_effects.h.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_EFFECTS_H`
- L2: `#define GUARD_FIELD_EFFECTS_H`
- L4: `#include "global.h"`
- L5: `#include "constants/field_effects.h"`
- L7: `extern u32 gFieldEffectArguments[8];`
- L8: `extern void (*gPostMenuFieldCallback)(void);`
- L9: `extern bool8 (*gFieldCallback2)(void);`
- L11: `u32 FieldEffectStart(u8);`
- L12: `bool8 FieldEffectActiveListContains(u8 id);`
- L13: `void CreateTeleportFieldEffectTask(void);`
- L14: `void FieldEffectActiveListRemove(u8 id);`
- L15: `void StartEscapeRopeFieldEffect(void);`
- L16: `void FieldEffectStop(struct Sprite *sprite, u8 id);`
- L17: `u8 CreateTrainerSprite(u8 trainerSpriteID, s16 x, s16 y, u8 subpriority, u8 *buffer);`
- L18: `void FieldCB_FallWarpExit(void);`
- L19: `void StartEscalatorWarp(u8 metatileBehavior, u8 priority);`
- L20: `void StartLavaridgeGymB1FWarp(u8 a0);`
- L21: `void StartLavaridgeGym1FWarp(u8 a0);`
- L22: `void ApplyGlobalFieldPaletteTint(u8 paletteIdx);`
- L23: `void FreeResourcesAndDestroySprite(struct Sprite *sprite, u8 spriteId);`
- L24: `u8 CreateMonSprite_PicBox(u16 species, s16 x, s16 y, bool8 unused);`
- L25: `void ReturnToFieldFromFlyMapSelect(void);`
- L26: `void MultiplyInvertedPaletteRGBComponents(u16 i, u8 r, u8 g, u8 b);`
- L27: `void SpriteCB_PopOutOfAsh(struct Sprite *sprite);`
- L28: `void SpriteCB_AshLaunch(struct Sprite *sprite);`
- L29: `void FieldEffectActiveListClear(void);`
- L31: `#endif //GUARD_FIELD_EFFECTS_H`

## Dependencies, expansion relevance and independent review

Check effect-ID bounds, argument ownership and lifetime, task/sprite destruction, palette allocation and callback reentrancy. Function declarations do not establish runtime behavior or resource safety. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

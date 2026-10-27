# Analyst whole-file candidate 0062 — Field-effect sprite helpers and bob-state enum

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect_helpers.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect_helpers.h); exact pinned Git blob SHA-1 `9347483c67c6ec5894e586876c48e5e69209ed82`. Inspected the **entire 44-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

Three bob states encode none, player+mon and mon-only. The exported helpers manage warp arrow, surf blob, ash, disguise, reflections, tall grass and numerous sprite update callbacks; coordinates and sprite IDs use mixed s16/u8 widths.

## Exhaustive non-comment source-line inventory

- L5: `#ifndef GUARD_FIELD_EFFECT_HELPERS_H`
- L6: `#define GUARD_FIELD_EFFECT_HELPERS_H`
- L8: `#include "global.h"`
- L10: `enum {`
- L11: `BOB_NONE,`
- L12: `BOB_PLAYER_AND_MON,`
- L13: `BOB_MON_ONLY, // when player has jumped / flown off`
- L14: `};`
- L16: `u8 CreateWarpArrowSprite(void);`
- L17: `void SetSurfBlob_BobState(u8 spriteId, u8 bobState);`
- L18: `void SetSurfBlob_DontSyncAnim(u8 spriteId, bool8 value);`
- L19: `void StartAshFieldEffect(s16, s16, u16, s16);`
- L20: `void StartRevealDisguise(struct ObjectEvent *);`
- L21: `bool8 UpdateRevealDisguise(struct ObjectEvent *);`
- L22: `void SetUpReflection(struct ObjectEvent *, struct Sprite *, u8);`
- L23: `u32 StartFieldEffectForObjectEvent(u8, struct ObjectEvent *);`
- L24: `u8 FindTallGrassFieldEffectSpriteId(u8 localId, u8 mapNum, u8 mapGroup, s16 x, s16 y);`
- L25: `void ShowWarpArrowSprite(u8 spriteId, u8 direction, s16 x, s16 y);`
- L26: `void SetSpriteInvisible(u8 spriteId);`
- L27: `void SetSurfBlob_PlayerOffset(u8 spriteId, bool8 hasOffset, s16 offset);`
- L28: `void UpdateJumpImpactEffect(struct Sprite *sprite);`
- L29: `void UpdateShadowFieldEffect(struct Sprite *sprite);`
- L30: `void UpdateBubblesFieldEffect(struct Sprite *sprite);`
- L31: `void UpdateSparkleFieldEffect(struct Sprite *sprite);`
- L32: `void UpdateTallGrassFieldEffect(struct Sprite *sprite);`
- L33: `void WaitFieldEffectSpriteAnim(struct Sprite *sprite);`
- L34: `void UpdateAshFieldEffect(struct Sprite *sprite);`
- L35: `void UpdateSurfBlobFieldEffect(struct Sprite *sprite);`
- L36: `void UpdateFootprintsTireTracksFieldEffect(struct Sprite *sprite);`
- L37: `void UpdateSplashFieldEffect(struct Sprite *sprite);`
- L38: `void UpdateShortGrassFieldEffect(struct Sprite *sprite);`
- L39: `void UpdateLongGrassFieldEffect(struct Sprite *sprite);`
- L40: `void UpdateSandPileFieldEffect(struct Sprite *sprite);`
- L41: `void UpdateDisguiseFieldEffect(struct Sprite *sprite);`
- L42: `void UpdateHotSpringsWaterFieldEffect(struct Sprite *sprite);`
- L44: `#endif //GUARD_FIELD_EFFECT_HELPERS_H`

## Dependencies, expansion relevance and independent review

Trace all sprite callback registrations, sprite IDs and object-event lifetime, surf blob state transitions, map-group/local-ID lookup, coordinate sign behavior and animation ownership. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

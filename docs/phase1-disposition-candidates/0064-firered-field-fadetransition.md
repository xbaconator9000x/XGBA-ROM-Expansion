# Analyst whole-file candidate 0064 — Warp fade and field callback interface

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_fadetransition.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_fadetransition.h); exact pinned Git blob SHA-1 `7bfdbb6e8888e827aec16a94ac2ae9f0b56f3064`. Inspected the **entire 38-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header declares warp, dive, door, fall, teleport, stair, escalator, union-room and wireless/cable return callbacks, with transition completion predicates. DoTeleportWarp and FieldCB_ContinueScriptHandleMusic are each declared twice identically.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_FADETRANSITION_H`
- L2: `#define GUARD_FIELD_FADETRANSITION_H`
- L4: `#include "global.h"`
- L6: `void FieldCB_RushInjuredPokemonToCenter(void);`
- L7: `void DoWarp(void);`
- L8: `void DoDiveWarp(void);`
- L9: `void DoDoorWarp(void);`
- L11: `void DoFallWarp(void);`
- L12: `void DoTeleportWarp(void);`
- L13: `void DoTeleport2Warp(void);`
- L14: `void FieldCB_DefaultWarpExit(void);`
- L15: `void WarpFadeOutScreen(void);`
- L16: `void FieldCB_ContinueScriptHandleMusic(void);`
- L17: `void FadeInFromBlack(void);`
- L18: `void FadeTransition_FadeInOnReturnToStartMenu(void);`
- L19: `void WarpFadeInScreen(void);`
- L21: `void FieldCB_ContinueScriptUnionRoom(void);`
- L23: `bool32 FieldFadeTransitionBackgroundEffectIsFinished(void);`
- L24: `void palette_bg_faded_fill_black(void);`
- L25: `void DoStairWarp(u16 metatileBehavior, u16 delay);`
- L26: `void DoEscalatorWarp(u8 a0);`
- L27: `void DoLavaridgeGymB1FWarp(void);`
- L28: `void DoLavaridgeGym1FWarp(void);`
- L29: `void DoTeleportWarp(void);`
- L30: `void DoUnionRoomWarp(void);`
- L31: `void FieldCB_ReturnToFieldWirelessLink(void);`
- L32: `void FieldCB_ReturnToFieldCableLink(void);`
- L33: `bool8 FieldCB_ReturnToFieldOpenStartMenu(void);`
- L34: `void FieldCB_ContinueScript(void);`
- L35: `void FieldCB_ContinueScriptHandleMusic(void);`
- L36: `void FieldCB_WarpExitFadeFromBlack(void);`
- L38: `#endif // GUARD_FIELD_FADETRANSITION_H`

## Dependencies, expansion relevance and independent review

Reconcile callback ordering and duplicate declarations with definitions, script continuation, saved warp state, map collision and rendering, asynchronous fades, link mode and diving fallback. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0074 — Field move effect pointer storage and dispatch ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/fldeff.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/fldeff.h); exact pinned Git blob SHA-1 `de0fd2f03705bada2894134fd7b540928ba763eb`. Inspected the **entire 56-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

Two macros store a function pointer by splitting its u32 cast into two u16 task-data slots and later reconstructing a void(void) callback. The remaining declarations expose facing position, Flash/Cut/Dig/Rock Smash/Strength/Teleport/Soft-Boiled/Sweet Scent and poison effect APIs.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FLDEFF_H`
- L2: `#define GUARD_FLDEFF_H`
- L4: `#define FLDEFF_CALL_FUNC_IN_DATA() ((void (*)(void))(((u16)gTasks[taskId].data[8] << 16) | (u16)gTasks[taskId].data[9]))();`
- L6: `#define FLDEFF_SET_FUNC_TO_DATA(func)                     \`
- L7: `gTasks[taskId].data[8] = (u32)func >> 16;                 \`
- L8: `gTasks[taskId].data[9] = (u32)func;`
- L10: `extern struct MapPosition gPlayerFacingPosition;`
- L12: `bool8 CheckObjectGraphicsInFrontOfPlayer(u8 graphicsId);`
- L13: `u8 CreateFieldEffectShowMon(void);`
- L16: `u8 MapTransitionIsExit(u8 lightLevel, u8 mapType);`
- L17: `u8 MapTransitionIsEnter(u8 mapType1, u8 mapType2);`
- L18: `bool8 SetUpFieldMove_Flash(void);`
- L19: `void CB2_DoChangeMap(void);`
- L22: `bool8 SetUpFieldMove_Cut(void);`
- L25: `bool8 SetUpFieldMove_Dig(void);`
- L26: `bool8 FldEff_UseDig(void);`
- L29: `bool8 SetUpFieldMove_RockSmash(void);`
- L30: `bool8 FldEff_UseRockSmash(void);`
- L33: `void nullsub_56(void);`
- L36: `void FldEffPoison_Start(void);`
- L37: `bool32 FldEffPoison_IsActive(void);`
- L40: `bool8 SetUpFieldMove_Strength(void);`
- L41: `bool8 FldEff_UseStrength(void);`
- L44: `bool8 SetUpFieldMove_Teleport(void);`
- L45: `bool8 FldEff_UseTeleport(void);`
- L48: `bool8 SetUpFieldMove_SoftBoiled(void);`
- L49: `void ChooseMonForSoftboiled(u8 taskId);`
- L50: `void Task_TryUseSoftboiledOnPartyMon(u8 taskId);`
- L53: `bool8 SetUpFieldMove_SweetScent(void);`
- L54: `bool8 FldEff_SweetScent(void);`
- L56: `#endif // GUARD_FLDEFF_H`

## Dependencies, expansion relevance and independent review

This is a high-priority 32-bit executable-pointer and task-lifetime boundary. Verify ARM/Thumb pointer low bit, taskId validity, data[8]/data[9] integrity, function signature compatibility, reset/warp lifetime and expanded ROM code addressing; no arbitrary pointer-width compatibility is inferred. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

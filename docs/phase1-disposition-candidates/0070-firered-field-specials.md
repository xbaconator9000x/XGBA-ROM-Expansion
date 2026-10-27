# Analyst whole-file candidate 0070 — Field script specials and quest-state services

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_specials.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_specials.h); exact pinned Git blob SHA-1 `b5d1f5c7ff1e7f3029fc77a6b62623575acc9914`. Inspected the **entire 31-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header exports utilities for lead mon/starter, integer formatting, PC destination, hidden item attributes, Sevii area state, trainer ID, Cut door scripts, counters, cycling-road state and quest-log departure recording. It declares functions only, not the script opcode binding table.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_SPECIALS_H`
- L2: `#define GUARD_FIELD_SPECIALS_H`
- L4: `#include "global.h"`
- L6: `u8 GetLeadMonIndex(void);`
- L7: `s32 CountDigits(s32 number);`
- L8: `void TV_PrintIntToStringVar(u8 varidx, s32 number);`
- L9: `u16 GetStarterSpecies(void);`
- L10: `void StopPokemonLeagueLightingEffectTask(void);`
- L11: `void FieldCB_ShowPortholeView(void);`
- L12: `u8 ContextNpcGetTextColor(void);`
- L13: `void SetPCBoxToSendMon(u8);`
- L14: `u16 GetPCBoxToSendMon(void);`
- L15: `bool8 IsDestinationBoxFull(void);`
- L16: `bool8 ShouldShowBoxWasFullMessage(void);`
- L17: `u16 GetHiddenItemAttr(u32 hiddenItem, u8 attr);`
- L18: `u8 GetUnlockedSeviiAreas(void);`
- L19: `u32 GetPlayerTrainerId(void);`
- L20: `bool8 CutMoveRuinValleyCheck(void);`
- L21: `void CutMoveOpenDottedHoleDoor(void);`
- L22: `void RunMassageCooldownStepCounter(void);`
- L23: `void IncrementResortGorgeousStepCounter(void);`
- L24: `void IncrementBirthIslandRockStepCount(void);`
- L25: `void ResetCyclingRoadChallengeData(void);`
- L26: `void ResetFieldTasksArgs(void);`
- L27: `bool8 UsedPokemonCenterWarp(void);`
- L28: `void QuestLog_CheckDepartingIndoorsMap(void);`
- L29: `void QuestLog_TryRecordDepartedLocation(void);`
- L31: `#endif // GUARD_FIELD_SPECIALS_H`

## Dependencies, expansion relevance and independent review

Verify hidden-item encoding and bit widths, PC box index bounds, save-state lifetime, script special dispatch, cooldown counters and quest-log event ordering. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

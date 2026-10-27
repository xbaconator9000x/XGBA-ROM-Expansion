# Analyst whole-file candidate 0076 — Object and player freeze/unfreeze sequencing

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/event_object_lock.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/event_object_lock.h); exact pinned Git blob SHA-1 `43ce9717343a6b597d9ed893f56bf95d5787b280`. Inspected the **entire 14-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The seven APIs distinguish player freeze completion, selected-object-plus-player completion, wait helpers, unfreezing, stationary detection and union-room partner unlock. bool8 return types express completion checks, not timeouts.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_EVENT_OBJECT_LOCK_H`
- L2: `#define GUARD_EVENT_OBJECT_LOCK_H`
- L4: `#include "global.h"`
- L6: `bool8 IsFreezePlayerFinished(void);`
- L7: `void FreezeObjects_WaitForPlayer(void);`
- L8: `bool8 IsFreezeSelectedObjectAndPlayerFinished(void);`
- L9: `void FreezeObjects_WaitForPlayerAndSelected(void);`
- L10: `void ClearPlayerHeldMovementAndUnfreezeObjectEvents(void);`
- L11: `bool8 walkrun_is_standing_still(void);`
- L12: `void UnionRoom_UnlockPlayerAndChatPartner(void);`
- L14: `#endif // GUARD_EVENT_OBJECT_LOCK_H`

## Dependencies, expansion relevance and independent review

Trace task waits and object selection lifetimes across scripts, warps and link sessions; validate that every freeze path has a corresponding unfreeze path. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0098 — Scripted object movement and unfreeze ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_movement.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_movement.h); exact pinned Git blob SHA-1 `a6f3e7c3c52d518d35036de6e1ba198eb1e9a244`. Inspected the **entire 10-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The three APIs start an object movement script from a const u8 byte stream, query completion using three u8 identifiers and unfreeze object events.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SCRIPT_MOVEMENT_H`
- L2: `#define GUARD_SCRIPT_MOVEMENT_H`
- L4: `#include "global.h"`
- L6: `bool8 ScriptMovement_StartObjectMovementScript(u8, u8, u8, const u8 *);`
- L7: `bool8 ScriptMovement_IsObjectMovementFinished(u8, u8, u8);`
- L8: `void ScriptMovement_UnfreezeObjectEvents(void);`
- L10: `#endif // GUARD_SCRIPT_MOVEMENT_H`

## Dependencies, expansion relevance and independent review

Verify movement bytecode termination, object map-group/local-ID identity, task lifetime and player/selected-object freeze/unfreeze coordination. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

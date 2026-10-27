# Analyst whole-file candidate 0060 — Door metatile and animation interface

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_door.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_door.h); exact pinned Git blob SHA-1 `777afffce2810060a6bd5ad7321d6a43911e1bda`. Inspected the **entire 13-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The six declarations distinguish direct open/closed metatile writes from asynchronous open/close animations, global animation-active polling and coordinate-dependent door sound selection. Animation functions return signed 8-bit results.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELDDOOR_H`
- L2: `#define GUARD_FIELDDOOR_H`
- L4: `#include "global.h"`
- L6: `void FieldSetDoorOpened(int x, int y);`
- L7: `void FieldSetDoorClosed(int x, int y);`
- L8: `s8 FieldAnimateDoorClose(int x, int y);`
- L9: `s8 FieldAnimateDoorOpen(int x, int y);`
- L10: `bool8 FieldIsDoorAnimationRunning(void);`
- L11: `u16 GetDoorSoundEffect(int x, int y);`
- L13: `#endif`

## Dependencies, expansion relevance and independent review

Trace animation return-value meaning, door coordinate bounds, tile replacement and collision refresh, asynchronous completion and map warp sequencing. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

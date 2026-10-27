# Analyst whole-file candidate 0071 — Per-step callback activation and field task setup

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_tasks.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_tasks.h); exact pinned Git blob SHA-1 `b037e382d4152be6c326d4335a380b16faf4e99e`. Inspected the **entire 9-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The complete header exposes ActivatePerStepCallback(u8) and SetUpFieldTasks(void), depending on global.h for fixed-width types.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_TASKS_H`
- L2: `#define GUARD_FIELD_TASKS_H`
- L4: `#include "global.h"`
- L6: `void ActivatePerStepCallback(u8);`
- L7: `void SetUpFieldTasks(void);`
- L9: `#endif // GUARD_FIELD_TASKS_H`

## Dependencies, expansion relevance and independent review

Trace callback-ID dispatch bounds, scheduler lifetime, task setup after warp and interaction with map event, weather, poison and player movement. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

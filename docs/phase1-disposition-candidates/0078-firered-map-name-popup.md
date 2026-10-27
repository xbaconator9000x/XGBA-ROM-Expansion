# Analyst whole-file candidate 0078 — Map name popup display API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/map_name_popup.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/map_name_popup.h); exact pinned Git blob SHA-1 `3058489f79bba58faef41fe925ac96740923df9b`. Inspected the **entire 9-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The complete header exports ShowMapNamePopup(bool32 palIntoFadedBuffer) and DismissMapNamePopup(void), with a global.h dependency.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_MAP_NAME_POPUP_H`
- L2: `#define GUARD_MAP_NAME_POPUP_H`
- L4: `#include "global.h"`
- L6: `void ShowMapNamePopup(bool32 palIntoFadedBuffer);`
- L7: `void DismissMapNamePopup(void);`
- L9: `#endif //GUARD_MAP_NAME_POPUP_H`

## Dependencies, expansion relevance and independent review

Verify palette buffer selection, task/window ownership, map name lookup bounds and lifecycle during map transitions and reloads. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

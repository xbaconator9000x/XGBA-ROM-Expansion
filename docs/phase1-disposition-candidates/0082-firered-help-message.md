# Analyst whole-file candidate 0082 — Help-message window graphics and text API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/help_message.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/help_message.h); exact pinned Git blob SHA-1 `b75abc77eeeafbe3ca917b70b341c526784cc709`. Inspected the **entire 12-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header exports an unsized const u8 graphics array and functions to create/destroy a window, print u8 text, set dummy map-name popup window ID and draw tiles by window ID.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_HELP_MESSAGE_H`
- L2: `#define GUARD_HELP_MESSAGE_H`
- L4: `extern const u8 gHelpMessageWindow_Gfx[];`
- L6: `void DestroyHelpMessageWindow(u8 a0);`
- L7: `u8 CreateHelpMessageWindow(void);`
- L8: `void PrintTextOnHelpMessageWindow(const u8 * text, u8 mode);`
- L9: `void MapNamePopupWindowIdSetDummy(void);`
- L10: `void DrawHelpMessageWindowTilesById(u8 windowId);`
- L12: `#endif //GUARD_HELP_MESSAGE_H`

## Dependencies, expansion relevance and independent review

Verify graphics size and palette provenance, window ID allocation and lifetime, text pointer termination, draw bounds and popup/window interactions; the header does not include global.h. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

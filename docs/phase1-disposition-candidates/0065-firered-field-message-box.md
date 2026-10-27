# Analyst whole-file candidate 0065 — Field message box state API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_message_box.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_message_box.h); exact pinned Git blob SHA-1 `430f2baf0d370cddc8877d0547dd1666db68a25c`. Inspected the **entire 20-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The four-state enum includes hidden, unused, normal and auto-scroll; six APIs expose message display, hide, initialization, visibility and state queries. The header does not define ownership of passed u8 string data.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_MESSAGE_BOX_H`
- L2: `#define GUARD_FIELD_MESSAGE_BOX_H`
- L4: `#include "global.h"`
- L6: `enum {`
- L7: `FIELD_MESSAGE_BOX_HIDDEN,`
- L8: `FIELD_MESSAGE_BOX_UNUSED,`
- L9: `FIELD_MESSAGE_BOX_NORMAL,`
- L10: `FIELD_MESSAGE_BOX_AUTO_SCROLL,`
- L11: `};`
- L13: `bool8 ShowFieldMessage(const u8 *message);`
- L14: `bool8 ShowFieldAutoScrollMessage(const u8 *message);`
- L15: `void HideFieldMessageBox(void);`
- L16: `bool8 IsFieldMessageBoxHidden(void);`
- L17: `u8 GetFieldMessageBoxType(void);`
- L18: `void InitFieldMessageBox(void);`
- L20: `#endif // GUARD_FIELD_MESSAGE_BOX_H`

## Dependencies, expansion relevance and independent review

Verify text pointer lifetime, active-state transitions, auto-scroll task ownership and interaction with script interpreter and warp transitions. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

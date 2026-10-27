# Analyst whole-file candidate 0097 — Script menu choice and picture callback ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_menu.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script_menu.h); exact pinned Git blob SHA-1 `d3ce18b327f6e0fd861d952b58e5343a7be1d437`. Inspected the **entire 20-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header exposes an unsized standard string-pointer array and multi-choice, default, yes/no, grid, Pokémon picture and PC menu APIs. ScriptMenu_HidePokemonPic returns a pointer to a bool8(void) callback, rather than a bool8 value.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SCRIPT_MENU_H`
- L2: `#define GUARD_SCRIPT_MENU_H`
- L4: `#include "global.h"`
- L6: `extern const u8 *const gStdStringPtrs[];`
- L8: `bool8 ScriptMenu_Multichoice(u8 left, u8 top, u8 var3, u8 var4);`
- L9: `bool8 ScriptMenu_MultichoiceWithDefault(u8 left, u8 top, u8 var3, u8 var4, u8 var5);`
- L10: `bool8 ScriptMenu_YesNo(u8 var1, u8 var2);`
- L11: `bool8 ScriptMenu_MultichoiceGrid(u8 left, u8 top, u8 multichoiceId, u8 a4, u8 columnCount);`
- L12: `bool8 ScriptMenu_ShowPokemonPic(u16 var1, u8 var2, u8 var3);`
- L13: `bool8 CreatePCMenu(void);`
- L14: `void ScriptMenu_DisplayPCStartupPrompt(void);`
- L16: `bool8 (*ScriptMenu_HidePokemonPic(void))(void);`
- L17: `void QL_DestroyAbortedDisplay(void);`
- L18: `void PicboxCancel(void);`
- L20: `#endif //GUARD_SCRIPT_MENU_H`

## Dependencies, expansion relevance and independent review

Trace menu ID and grid bounds, script result variables, picture sprite lifetime, returned callback invocation and text-pointer table sizes. UI functions are asynchronous in potential, not proven by prototypes. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

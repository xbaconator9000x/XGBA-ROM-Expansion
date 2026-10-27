# Analyst whole-file candidate 0100 — Shop item list, transaction and task UI ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/shop.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/shop.h); exact pinned Git blob SHA-1 `5e6d07783ded04feabf277887d2583bf9568572f`. Inspected the **entire 24-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header defines INDEX_CANCEL=-2 and shop menu/transaction APIs using u16 item IDs and quantities, plus buy-menu window/text functions, task callbacks and YesNoFuncTable pointer.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SHOP_H`
- L2: `#define GUARD_SHOP_H`
- L4: `#include "global.h"`
- L5: `#include "menu_helpers.h"`
- L7: `#define INDEX_CANCEL -2`
- L9: `void CreatePokemartMenu(const u16 *itemsForSale);`
- L10: `void CreateDecorationShop1Menu(const u16 *);`
- L11: `void CreateDecorationShop2Menu(const u16 *);`
- L12: `u8 GetMartFontId(void);`
- L13: `void RecordItemTransaction(u16 itemId, u16 quantity, u8 logEventId);`
- L16: `void BuyMenuInitWindows(bool32 isSellingTM);`
- L17: `void BuyMenuDrawMoneyBox(void);`
- L18: `void BuyMenuPrint(u8 windowId, u8 font, const u8 *text, u8 x, u8 y, u8 letterSpacing, u8 lineSpacing, u8 speed, u8 color);`
- L19: `void BuyMenuDisplayMessage(u8 taskId, const u8 *text, TaskFunc callback);`
- L20: `void BuyMenuQuantityBoxNormalBorder(u8 windowId, bool8 copyToVram);`
- L21: `void BuyMenuQuantityBoxThinBorder(u8 windowId, bool8 copyToVram);`
- L22: `void BuyMenuConfirmPurchase(u8 taskId, const struct YesNoFuncTable *yesNo);`
- L24: `#endif // GUARD_SHOP_H`

## Dependencies, expansion relevance and independent review

Trace sentinel signedness, item-list termination, price/quantity overflow, task callback lifetime, inventory/save transactions and UI resource cleanup. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

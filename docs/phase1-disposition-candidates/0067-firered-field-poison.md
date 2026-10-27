# Analyst whole-file candidate 0067 — Poison field-step result contract

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_poison.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_poison.h); exact pinned Git blob SHA-1 `a29cf1fd686584a6498c1a76a1c33c745453be64`. Inspected the **entire 14-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The enum has three successive values FLDPSN_NONE, FLDPSN_PSN and FLDPSN_FNT; DoPoisonFieldEffect returns signed 32-bit. No code here establishes whether the return maps directly to those enum values.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_POISON_H`
- L2: `#define GUARD_FIELD_POISON_H`
- L4: `#include "global.h"`
- L6: `enum {`
- L7: `FLDPSN_NONE,`
- L8: `FLDPSN_PSN,`
- L9: `FLDPSN_FNT`
- L10: `};`
- L12: `s32 DoPoisonFieldEffect(void);`
- L14: `#endif //GUARD_FIELD_POISON_H`

## Dependencies, expansion relevance and independent review

Trace field step caller, poison damage, faint handling and whether a return value triggers a warp or script; test save/reload and party status boundaries. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

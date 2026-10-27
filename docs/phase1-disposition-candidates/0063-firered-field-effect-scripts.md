# Analyst whole-file candidate 0063 — Field-effect bytecode script pointer table

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect_scripts.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_effect_scripts.h); exact pinned Git blob SHA-1 `fd3609d93691451e49acd93d3d68d4d72519600c`. Inspected the **entire 6-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The entire header is an include guard and a single extern declaration of an array of const u8 script pointers. The pointer array's element count and bytecode encoding are not defined here.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_EFFECT_SCRIPTS_H`
- L2: `#define GUARD_FIELD_EFFECT_SCRIPTS_H`
- L4: `extern const u8 *const gFieldEffectScriptPointers[];`
- L6: `#endif //GUARD_FIELD_EFFECT_SCRIPTS_H`

## Dependencies, expansion relevance and independent review

Resolve producer table length, effect-ID indexing and bytecode interpreter bounds; confirm native ROM pointer representation and linker placement for expanded resources. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

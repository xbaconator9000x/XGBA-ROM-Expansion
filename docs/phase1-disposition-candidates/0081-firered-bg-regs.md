# Analyst whole-file candidate 0081 — Overworld background register offset arrays

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/bg_regs.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/bg_regs.h); exact pinned Git blob SHA-1 `e16cf311984408a3db832d305ec297b5f73f852d`. Inspected the **entire 7-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The header exports two const arrays: u8 BG control register offsets and u16 background-layer flags. It contains no array lengths or include of global.h.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_BG_REGS_H`
- L2: `#define GUARD_BG_REGS_H`
- L4: `extern const u8 gBGControlRegOffsets[];`
- L5: `extern const u16 gOverworldBackgroundLayerFlags[];`
- L7: `#endif //GUARD_BG_REGS_H`

## Dependencies, expansion relevance and independent review

Trace array lengths, indexing, MMIO register offsets, layer mask semantics, C/assembly aliasing and include-order type dependencies. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

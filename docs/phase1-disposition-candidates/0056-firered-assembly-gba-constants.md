# Analyst whole-file candidate 0056 — FireRed assembly GBA hardware constants and C ABI correspondence

**ANALYST-PREPARED ONLY; independent review pending.** Exact pinned source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/gba_constants.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/gba_constants.inc), Git blob SHA-1 **`3ff857ee8dfb1f4e2dfaf8ac98373bac5dfdb25c`**. The complete **513-line assembly include** (514 split elements including terminal empty line) was read. It defines **464 distinct `.set` symbols**, with no repeated names in this file, and no executable instructions or build-condition branches.

## Whole-file semantic disposition

| Source lines | Full section semantics |
| --- | --- |
| 1–11 | ARM PSR mode identifiers and T/F/I flags; mode mask. |
| 12–32 | EWRAM/IWRAM start/end, palette/VRAM/OAM bases, sound/IRQ RAM aliases, interrupt vector/check addresses. These values are fixed GBA hardware/RAM assumptions, not ROM expansion pointers. |
| 33–48 | Fourteen interrupt-flag bit masks, plus scanline and VBlank constants. |
| 49–52 | `REG_BASE = 0x04000000`, the hardware I/O register base. |
| 53–240 | **177 `OFFSET_REG_*` definitions** for display, sound, DMA, timers, serial, keypad, IRQ and WAITCNT, including intentional byte/halfword aliases. |
| 241–428 | **177 `REG_*` assembly-address constants** formed from `REG_BASE + OFFSET_REG_*` (the 178th `REG_*` symbol is `REG_BASE` at line 51). All referenced offset names exist in this file; unlike the C header these are numeric assembler symbols, not typed volatile lvalues. |
| 429–448 | Seventeen DMA mode, trigger, width, IRQ and enable constants. No DMA count/bounds validation is defined. |
| 449–491 | Thirty-two OAM attribute-mode, affine, flip, shape and size constants. Size macros combine high/low attribute-bit placements, not independent buffer sizes. |
| 492–513 | Eighteen BLDCNT target/effect masks. |

The **remaining 31 symbols** outside the PSR (11), offsets (177), addresses (177), `REG_BASE` (1), DMA (17), OAM (32) and blend (18) families comprise memory/RAM aliases, IRQ masks and scanline constants. Counts sum to **464**; every `REG_*` address expression's named offset resolves in the pinned include.

## Cross-language source evidence

The paired pinned C header `include/gba/io_reg.h` (blob `a8a36f7e295855dbc4281f5f9a9f223ddda34a16`) defines 167 `REG_OFFSET_*` constants, 151 address expressions and typed volatile accessors. Normalizing assembler `OFFSET_REG_X` to C `REG_OFFSET_X` yields **158 shared offset names**; all 158 have identical directly comparable numeric literal values at this pinned revision. There are **19 assembler-only offset aliases** (including `SOUND1CNT` aliases, wave RAM halfwords and FIFO halfwords) and **9 C-only offset aliases** (full BG2/BG3 X/Y, SOUNDBIAS low/high and generic timer aliases). These asymmetric *names* are not evidence of differing underlying hardware addresses.

Pinned source search identifies `constants/gba_constants.inc` consumers through `constants/constants.inc`, `src/crt0.s`, `src/libagbsyscall.s` and `src/m4a_1.s`. Search hits are not a complete transitive dependency graph. The companion analyst [C I/O register candidate 0055](0055-firered-gba-io-register-contract.md) separately records typed access widths, including `REG_SIODATA8` and `REG_SIOMLT_RECV` caveats.

## Expansion and independent-review obligations

- Preserve GBA CPU mode bits, RAM IRQ vector addresses, fixed hardware I/O base, register widths, DMA and wait-state bit meanings across compiler/assembler modes; do not reinterpret these constants as widened ROM pointers.
- Independently reconcile all 464 assembler symbols with C declarations and consumers, including the nonshared aliases, ARM/Thumb calling context, OAM attribute packing and potential conflicting macro names.
- Compile/disassemble pinned original agbcc and modern variants and verify emitted absolute addresses; test IRQ, DMA, serial, audio and graphics behavior in mGBA. No compiled address, actual register side effect or runtime equivalence is established by this source-only document.
- Confirm assembler include order and symbol collision/override behavior in all build variants; a successful lexical name/value comparison alone is insufficient.

**Disposition:** complete-file analyst semantic preparation, hash-pinned; independent reviewer approval **not supplied**. Phase 1 **FAIL_INCOMPLETE**.

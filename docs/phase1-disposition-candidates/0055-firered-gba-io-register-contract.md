# Analyst whole-file candidate 0055 — FireRed GBA I/O register address and bitfield contract

**ANALYST-PREPARED ONLY — independent reviewer verdict pending.** Pinned source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/io_reg.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/io_reg.h); exact Git blob SHA-1 **`a8a36f7e295855dbc4281f5f9a9f223ddda34a16`**. The complete **776-line header** (777 newline-split elements including trailing empty line) was inspected. It contains **683 valued macro definitions**, one include-guard definition, comments and blank lines; no authored C functions, variables, or build-conditioned branches. The structural census covers all macro families, not only a P0 excerpt.

## Complete-file semantic disposition

| Source range | Complete-file role and source-proven behavior |
| --- | --- |
| 1–5 | `GUARD_GBA_IO_REG_H` include guard and `REG_BASE = 0x04000000`; no direct type include. |
| 6–184 | **167 `REG_OFFSET_*` constants** for display/affine/window/blend, sound/PSG/FIFO, DMA, timers, serial/multiplayer, keypad, interrupts and wait-state control. Some offsets intentionally alias byte/halfword/word views. |
| 185–347 | **151 `REG_ADDR_*` expressions** add `REG_BASE` to their named offsets. All 151 references resolve. The 16 offset names without address macros are DMA source/destination low/high halfword aliases on four channels; no missing hardware register is inferred. |
| 348–500 | **139 `REG_*` volatile lvalue accessors**: 23 `vu8`, 87 `vu16`, 28 `vu32`, one `vu64`. All named `REG_ADDR_*` references resolve. `REG_TMCNT(n)` and halfword variants compute `+4*n` without bounds checks. |
| 501–529 | Display modes 0–5, object/window/background enables, DISPSTAT status and IRQ-enable masks. |
| 530–546 | Background priority, character/screen base shifts, mosaic, palette depth, wrap, text/affine sizes; parameters are not range-checked. |
| 547–584 | WININ/WINOUT two-bank layer masks; `WIN_RANGE` and `WIN_RANGE2` pack high/low bytes without masking arguments. |
| 585–613 | BLDCNT target-layer masks and effect selection; BLDALPHA packing. |
| 614–640 | PSG/direct-sound mixing, timer selection, FIFO reset and master enable. |
| 641–660 | DMA source/destination addressing, repeat, width, trigger, interrupt and enable bits. This section does not validate transfer lengths. |
| 661–696 | Timer prescalers/enable, serial modes, baud rates, multiplayer ID/status and IRQ bits; aliases are mode-dependent. |
| 697–730 | Keypad masks and 14 IRQ flag positions (VBlank through Game Pak). |
| 731–776 | SRAM/ROM wait-state, prefetch, clock-output and platform-mode masks; guard closes at 776. |

The remaining **225 valued macros** after `REG_BASE`, 167 offsets, 151 addresses and 139 accessors encode the field controls above. No duplicate macro names were found. The macro census is not proof that every bit definition agrees with physical hardware or every consumer.

## Dependency closure, hazards and independent-review obligations

- Pinned `include/gba/gba.h` (blob `4b5f2de954eea62e21c62c12d49536fcd7e65b7d`) includes `io_reg.h` after `defines.h` but before `types.h`. Pinned `types.h` defines `vu8`, `vu16`, `vu32` and `vu64`. Accessor macro expansion timing and translation-unit include order must be checked, not assumed.
- Source search finds example consumers: `REG_IME` in `src/gpu_regs.c`, `REG_WAITCNT` in `src/main.c` and `src/agb_flash.c`, and `REG_SIOMLT_RECV` in `src/link.c` and `src/ereader_helpers.c`. This is **not** an exhaustive consumer census.
- `REG_SIODATA8` expands to a `vu16` lvalue despite its name. `REG_SIOMLT_RECV` is a `vu64` lvalue spanning multiplayer receive registers. Neither declaration proves an atomic byte or 64-bit hardware access; generated instruction widths and mGBA register behavior need validation.
- Expansion must preserve the original 0x04000000 memory-mapped I/O register window, native access widths, interrupt acknowledgement, DMA and wait-state semantics. ROM address banking is not interchangeable with hardware I/O addressing.
- **Outstanding independent checks:** enumerate all direct and transitive consumers, reconcile `constants/gba_constants.inc` aliases, compare original agbcc versus modern compiler volatile accesses, and run mGBA/native tests for DMA, timer, serial, IRQ and WAITCNT behavior. Record read-only/write-only registers and mode-dependent side effects. No such compiled, emulator or hardware verification is claimed here.

**Disposition:** complete-file source preparation only; cross-compiler and runtime access semantics unresolved; **0 independent approvals credited**. Phase 1 **FAIL_INCOMPLETE**.

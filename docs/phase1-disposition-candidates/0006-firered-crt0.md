# Phase 1 semantic disposition candidate 0006 — FireRed startup and IRQ assembly

**Review state: PENDING_INDEPENDENT_REVIEW — NOT APPROVED.** This is a whole-file analyst candidate, not a reviewer decision, accepted gate input, or runtime certification.

## Pinned identity and complete source scope
- Repository: `pret/pokefirered`, commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Entire file: [`src/crt0.s`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s); exact Git blob SHA-1 `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14`, confirmed from the pinned GitHub file response. 126 source lines plus terminal empty split field.
- Direct assembly includes: `constants/gba_constants.inc` (blob `3ff857ee8dfb1f4e2dfaf8ac98373bac5dfdb25c`), `constants/misc_constants.inc` (blob `621ba2af89d25f44fee3c8507c50b34cd584ccc1`), and `constants/version.inc` (blob `c5bef93d867c66816f73616e0136125c5aca6cd7`). All three were fetched at the same pinned commit.
- Two exported entry labels: `start_vector` and `intr_main`. Other local labels: `sp_usr`, `sp_irq`, `loop`, `jump_intr`, `intr_return`. The file also emits literal pools and explicit alignment directives; it does not define the referenced C globals.

## Complete functional/assembly disposition candidate
1. **Reset entry (`start_vector`):** selects IRQ CPSR mode and loads IRQ stack pointer from `sp_irq`; selects system mode and loads system stack pointer from `sp_usr`. The two embedded words are `IWRAM_END - 0x1C0` and `IWRAM_END - 0x60`, respectively. It stores the address of `intr_main` at `INTR_VECTOR`, calls `AgbMain` through a register, then branches back to `start_vector` if that call returns. The source does not prove reset-time RAM contents or final compiled addresses.
2. **IRQ prologue:** `intr_main` constructs a register pointer from `REG_BASE + OFFSET_REG_IE`, reads IE/IF and IME, captures SPSR, saves `r0-r3,lr` plus SPSR on the IRQ stack, disables IME, and computes pending-and-enabled bits by `and r1, r2, r2, lsr #16`.
3. **Priority and callback offsets:** tests `VCOUNT, SERIAL, TIMER3, HBLANK, VBLANK, TIMER0, TIMER1, TIMER2, DMA0, DMA1, DMA2, DMA3, KEYPAD, GAMEPAK` in that source order, advancing `r12` by 4 bytes for each preceding unmatched test. The first thirteen matches branch to `jump_intr`. This yields offsets 0,4,...,48 for those matches, corresponding to the **same fourteen-position order** of `gIntrTableTemplate` in pinned `src/main.c` (blob `542b0f5d16dd93107523d11163bfcb70a42b707a`; entries at lines 52–68). It is a *priority order*, not numerical hardware flag order.
4. **Special last branch and fallthrough:** the GAMEPAK test instead uses `strbne` to `REG_SOUNDCNT_X` and `bne loop` (a spin branch), not the normal `bne jump_intr`. When no tested bit is set, the assembly text falls through to `jump_intr` with the final `r12` offset. Do **not** infer whether that zero-pending fallthrough is reachable during a real IRQ, nor assert GAMEPAK invokes the normal callback. These paths need targeted execution/IRQ-model validation.
5. **Dispatch and return:** `jump_intr` acknowledges the selected IF bit, adjusts IE, reads `gSTWIStatus` and a byte at offset `0xA` to derive a timer mask, preserves selected IE bits, changes CPSR to system mode, indexes `gIntrTable + r12` and calls the selected function through `bx r0`. `intr_return` restores system/IRQ context, IE, IME and SPSR, then returns with `bx lr`. This is source-level control flow; no interrupt latency, nested-IRQ safety, pointer validity, or timer-shift bounds have been established.
6. **Remaining authored content:** ARM syntax/mode directives, four-byte alignment with zero fill, two `.pool` directives, the stack-address words, and a final explicit zero-filled alignment. The copied handler must include required literal-pool references; the compiled IRQ-copy checker verifies an object-level extent, not live execution.

## Cross-file evidence and XGBA implications
- [Pinned boot and RAM-lifetime chain](../PHASE1_P0_FIRERED_BOOT_IRQ_RAM_LIFETIME_2026-10-26.md): ROM header branches to `start_vector`; `AgbMain` subsequently copies `intr_main` by DMA into a 2,048-byte IWRAM buffer and repoints the IRQ vector.
- [Pinned FireRed↔mGBA IRQ bridge](../PHASE1_P0_FIRERED_MGBA_IRQ_BRIDGE_2026-10-26.md): native vector address `0x03007FFC` and emulator BIOS trampoline mirrored access require consistent IWRAM alias semantics.
- [Compiled relocation contract](../PHASE1_P0_FIRERED_COMPILED_IRQ_COPY_2026-10-26.md): linked ROM source, IWRAM destination, 56-byte callback table and copied literal-pool extent are separately checked in original and modern builds. This is not an IRQ execution test.
- Expansion compatibility obligations: preserve initial ROM fetch and subsequent IWRAM code lifetime; do not bank-switch/remap the source before its DMA copy or assume copied code/pools and IRQ callbacks remain coherent without explicit proof. Preserve the priority/acknowledgement and special GAMEPAK behaviour. The file contains no generic external-ROM resource manifest.

## Independent reviewer obligations and outcome
- Reconfirm all blob identities and **entire** 126-line source, including literal pools and conditional dependencies introduced by included constants.
- Independently check `gIntrTableTemplate` ordering and C initialization; compiled symbols/relocations and reset-vector offsets for all supported build variants; `gSTWIStatus` lifetime and index; zero-pending and GAMEPAK special-path runtime behaviour; and emulator/full-BIOS differences.
- Record reviewer identity, date, source anchors, a whole-file verdict (`approved`, `needs_changes`, or `blocked`), and rationale. Do not equate an automated PASS or this candidate with independent approval.
- **Current verdict:** `PENDING_INDEPENDENT_REVIEW`. **Gate contribution: zero.** Do not manually alter the gate's approved count.

**Checkpoint: Phase 1 `FAIL_INCOMPLETE`; 0/14,834 independently approved.**

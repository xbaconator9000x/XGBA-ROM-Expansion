# Phase 1 — whole-file semantic review candidate: FireRed `src/crt0.s` (27 October 2026)

**Status: SOURCE-INSPECTED CANDIDATE / BLOCKED FOR INDEPENDENT SIGNOFF.** This is a complete-file *review preparation record*, not a disposition accepted by an independent reviewer. The authoritative gate remains `FAIL_INCOMPLETE` and independently approved whole-file dispositions remain **0/14,834**. No Phase 2 work is authorized.

## Immutable identity and evidence scope

- Repository: `pret/pokefirered`; commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Entire file inspected: [`src/crt0.s`, lines 1–126](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s); **Git blob SHA-1 `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14`**, returned by the pinned GitHub file read and required by the existing [compiled IRQ checker](../tools/phase1_compiled_irq_relocation.py).
- Direct assembler includes: [`constants/gba_constants.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/gba_constants.inc), blob `3ff857ee8dfb1f4e2dfaf8ac98373bac5dfdb25c`; [`constants/misc_constants.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/misc_constants.inc), blob `621ba2af89d25f44fee3c8507c50b34cd584ccc1`; [`constants/version.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/version.inc), blob `c5bef93d867c66816f73616e0136125c5aca6cd7`.
- Consumer/cross-check: [`src/main.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/main.c), blob `542b0f5d16dd93107523d11163bfcb70a42b707a`, contains the matching 14-entry `gIntrTableTemplate`, `gIntrTable`, `IntrMain_Buffer`, and DMA3 copy; [`include/gba/defines.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/defines.h), blob `5521e942c00cc2c263b842ae7608dfb7ac881a76`, declares the IRQ vector at `0x03007FFC`.
- Existing evidence: [boot/IRQ/RAM source trace](PHASE1_P0_FIRERED_BOOT_IRQ_RAM_LIFETIME_2026-10-26.md), [compiled IRQ relocation checker and limits](PHASE1_P0_FIRERED_COMPILED_IRQ_COPY_2026-10-26.md), and [mGBA IRQ bridge](PHASE1_P0_FIRERED_MGBA_IRQ_BRIDGE_2026-10-26.md). The [compiled workflow run #40332557084](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40332557084) completed successfully on commit `58e7a7ed2fabaae4497ee28bea634f102fc938be`; that is **not** a run at this document's future commit.

## Entire-file control-flow inventory (pinned line anchors)

| Lines | Role and source-proven effect | Review caveat |
| --- | --- | --- |
| 1–8 | Three assembly constant includes; unified ARM syntax and alignment. | The three included files and assembler/build flags are separate dependencies; this record does not disposition them. |
| 9–23 | Exported `start_vector`: enters IRQ mode, loads IRQ SP, enters System mode, loads user/System SP, installs ROM `intr_main` in `INTR_VECTOR`, branches to external `AgbMain`; a fallback branch returns to `start_vector` if `AgbMain` returns. | No bounds/stack-safety or reset-timing proof from this file alone. |
| 25–29 | Literal stack words: `sp_usr = IWRAM_END - 0x1C0 = 0x03007E40`, `sp_irq = IWRAM_END - 0x60 = 0x03007FA0`; first literal pool. | Both lie in the top 512-byte reserved IWRAM region; do not model that region as free RAM. |
| 31–44 | Exported ARM `intr_main`: obtains IE/IF combined register word and IME, saves SPSR and registers on IRQ stack, masks IME, computes `IE & IF`, initializes table offset `r12 = 0`. | Register/MMIO interpretation is tied to pinned `gba_constants.inc`; actual hardware interrupt entry is not executed here. |
| 45–85 | Ordered flag tests with a four-byte `r12` increment after each unsuccessful test: VCOUNT, SERIAL, TIMER3, HBLANK, VBLANK, TIMER0, TIMER1, TIMER2, DMA0, DMA1, DMA2, DMA3, KEYPAD. `r12` is the byte offset into a table of 32-bit callback pointers. | This is **priority dispatch**, not a loop invoking all simultaneous pending callbacks. IME is explicitly written to 1 before the SERIAL test. |
| 86–90 | Last test is GAMEPAK. If its flag is set, the conditional sound-control byte write occurs and `bne loop` spins. If no tested flag is set, the conditional branch is *not* taken and execution falls through to `jump_intr` with `r0 = 0` and `r12 = 13 * 4`. | **New review-relevant branch:** an empty `IE & IF` mask reaches the final callback slot, while a set GAMEPAK flag enters the spin rather than calling that slot. Do not infer that either condition occurs in normal gameplay or is a demonstrated defect. |
| 90–101 | Acknowledges the chosen IF flag, adjusts the temporary IE mask using `gSTWIStatus` via a pointer load and byte at offset `0xA`, then writes IE. | No local null/range check for the `gSTWIStatus` pointer or its timer-selector byte is visible. Its producer, initialization order and permitted values need separate source and runtime evidence. |
| 102–112 | Changes CPSR to System mode, loads `gIntrTable[r12/4]`, branches via callback pointer, returns to `intr_return`. | The 14-entry table in `main.c` matches offsets 0–52; pointer validity and callback execution are not proved here. |
| 113–122 | Restores callback LR, switches to IRQ mode, restores saved registers and SPSR, restores IE/IME and returns via IRQ LR. | Interrupt nesting, latency and prefetch coherency remain runtime obligations. |
| 124–126 | Final literal pool and zero alignment padding. | Copied handler extent must include its trailing literal pool, not merely instructions preceding it. |

**Callback index contract:** `main.c` initializes indices 0–13 in exactly this order: VCountIntr, SerialIntr, Timer3Intr, HBlankIntr, VBlankIntr, IntrDummy (Timer0), IntrDummy (Timer1), IntrDummy (Timer2), IntrDummy (DMA0), IntrDummy (DMA1), IntrDummy (DMA2), IntrDummy (DMA3), IntrDummy (Keypad), IntrDummy (GamePak). This is a source-table correspondence, not a runtime callback trace.

## Expansion-specific dependency and decision boundary

A ROM-banking implementation cannot assume all interrupts execute from ROM: boot installs a ROM entry first, then `InitIntrHandlers` copies `intr_main` and its literal pool into a 2,048-byte IWRAM buffer and replaces the vector. The handler nevertheless dereferences live callback and RFU status pointers, so relocating ROM assets cannot be judged solely by the handler's physical instruction location. The reserved upper 512 bytes of IWRAM include both boot stacks and the IRQ vector; preservation differs across machine reset, BIOS SWI reset and modern boot clearing. The linked original/modern ELF checks establish some address/size constraints, not execution.

**Additional semantic review obligations, fail closed:**
1. Independently verify the entire file against the exact blob and the assembler-expanded constants, including all 14 flag positions and branch condition flags; distinguish the empty-pending fallthrough and GAMEPAK spin from observed runtime behaviour.
2. Resolve `gSTWIStatus` ownership, initialization, pointer lifetime, offset `0xA` semantics and permitted shift values, including link/RFU startup and reset paths; inspect callback pointer mutation sites.
3. Confirm final linked instructions and literal pool across supported variants; examine stack layout/overlap and interrupt nesting against actual BIOS and mGBA behaviour.
4. Reproduce an IRQ execution trace (normal pending, multiple pending, no pending, GAMEPAK, save reload, full reset) with pinned ROM, BIOS selection and emulator build; do not equate synthetic checker mutations with hardware validation.
5. Require a separately identified independent reviewer to record an explicit whole-file verdict with evidence and feed it through the supported authoritative gate format. **Do not mark approved or alter gate counts based on this candidate.**

**Candidate disposition: `blocked` (awaiting independent review and the above dependency proofs). Gate: `FAIL_INCOMPLETE`; approvals: 0/14,834.**

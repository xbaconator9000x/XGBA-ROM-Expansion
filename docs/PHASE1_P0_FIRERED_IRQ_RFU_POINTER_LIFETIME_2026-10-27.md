# Phase 1 P0 — FireRed IRQ ↔ RFU status-pointer initialization boundary (27 October 2026)

**Decision: `FAIL_INCOMPLETE`.** This is a pinned cross-object source dependency trace, not evidence of a startup crash, emulator execution, hardware defect, editor compatibility, or independent semantic approval.

## Exact pinned inputs

All files belong to `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

| Source | Git blob SHA-1 | Observed role |
| --- | --- | --- |
| [`src/crt0.s`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s#L90-L111) | `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14` | Every path through `jump_intr` reads `gSTWIStatus`, then byte offset `0xA`, to construct an IE mask before invoking the selected callback. |
| [`src/librfu_stwi.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/librfu_stwi.c#L11-L54) | `7b3b486cae2f249adf652cfb6ceca7565e8fd2f6` | Defines `COMMON_DATA struct STWIStatus *gSTWIStatus = NULL`; `STWI_init_all` selects status storage; `STWI_init_timer` writes `timerSelect`. |
| [`include/librfu.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/librfu.h#L300-L342) | `fa57ac4a2efc527296db5223e20ef0428c37f18c` | `STWIStatus` starts with a four-byte `state`, six one-byte fields, then one-byte `timerSelect`: source-declared offset `0xA` under the expected ARM layout. `RfuIntrStruct` has `block1[0x960]` and `block2`. |
| [`src/librfu_rfu.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/librfu_rfu.c#L127-L168) | `76e2158e68428584abc2d75165fb9b495cacb25b` | `rfu_initializeAPI` validates buffer location/alignment/size and calls `STWI_init_all` only after early-return checks. |
| [`src/link_rfu_2.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/link_rfu_2.c#L303-L326) | `78087d76fd3b2869b2bedc5b6dc29840e7d7a55a` | `InitRFU` calls `InitRFUAPI`; API initialization requests RAM-resident serial handler and, on success, `rfu_setTimerInterrupt(3, &gIntrTable[2])`. |
| [`src/main.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/main.c) | `542b0f5d16dd93107523d11163bfcb70a42b707a` | `AgbMain` calls `InitIntrHandlers` (copy IRQ handler, repoint vector, set IME, enable VBlank) **before** `InitRFU`. |

The existing [source checker](../tools/phase1_firered_boot_irq_ram_lifetime.py) now pins these files along with the previously pinned boot, assembler constants, reset and linker inputs, and tests the initialization-order dependency with five additional fail-closed mutations (**25 total**). This checker establishes *source structure only*. Verify its latest exact-head CI separately.

## Resolved producer/consumer path

`crt0.s` does not contain a local null check before the double dereference `gSTWIStatus -> timerSelect`. The source producer is `STWI_init_all`, reached through `InitRFUAPI -> rfu_initializeAPI`. With `copyInterruptToRam = TRUE`, `STWI_init_all` DMA-copies the serial interrupt routine into `block1` and sets the pointer to `block2`; otherwise the pointer addresses `block1`. `STWI_init_timer` sets the field to the supplied timer number. The normal inspected `InitRFUAPI` success branch supplies **3**.

This closes the **symbol-owner and field-offset** question left by the initial `crt0.s` candidate. It does **not** close the pointer's lifetime/reachability question: the pinned boot sequence enables interrupts before calling `InitRFU`, while the pointer's source initializer is NULL. A hypothetical interrupt reaching `jump_intr` in that interval would dereference an uninitialized status pointer. The existence, timing and effect of such an interrupt are **unproven**, and neither an emulator crash nor hardware fault is asserted. The RFU API can also reject invalid buffer arguments before installing the pointer; normal build buffer validity and all error paths still need independent verification.

The source includes two additional, distinct RAM-copy dependencies: `InitIntrHandlers` copies the primary IRQ dispatcher into IWRAM via DMA3, and `STWI_init_all` can copy the serial handler into its RFU buffer via DMA3. Their buffer lifetimes, address disjointness, callback-table mutations and possible DMA/prefetch interactions must be analyzed together for a future bank-aware ROM architecture.

## Open fail-closed obligations

1. Verify the compiled `STWIStatus.timerSelect` offset and the exact RFU buffer section/address/extent for legacy, modern and revision-10 variants; the struct prefix is source evidence, not an ABI measurement.
2. Trace all `gSTWIStatus` pointer writes, API failures, RFU soft resets, callback changes and save/reload paths; establish whether the pointer can become null or stale while IME/IE permit dispatch.
3. Capture deterministic emulator traces for the first enabled VBlank and VCount interrupts relative to RFU initialization, and for serial/timer callbacks after API setup. Pin BIOS selection and ROM identity.
4. Validate both IRQ and serial-handler RAM-copy windows, DMA3 arbitration, memory prefetch and snapshot/restore identity. Do not infer hardware compatibility from source-only checks.
5. Independently review each *entire* pinned source file and ingest real reviewer dispositions through the authoritative mapping gate. No source checker or documentation author may self-approve a disposition.

**Phase 1: `FAIL_INCOMPLETE`. Independent approvals: 0/14,834. Draft PR only; no Phase 2 implementation.**

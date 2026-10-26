# Phase 1 P0 — FireRed boot, IRQ-vector relocation and RAM lifetime (26 October 2026)

**Evidence class:** pinned source-level semantic dependency; **not** an ELF/map-file inspection, executable test, hardware timing proof, emulator certification, editor round trip or independent whole-file review. **Gate: `FAIL_INCOMPLETE`; approvals: 0/14,834.**

## Exact upstream source identities

All nine paths are pinned to `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Git blob identities are checked by [the reproducible verifier](../tools/phase1_firered_boot_irq_ram_lifetime.py), not merely inferred from a branch name.

| File | Git blob | Dependency |
| --- | --- | --- |
| [src/rom_header.s](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/rom_header.s) | `c98c89992a128b82ef3bc8f75c791cd1c6cbdcb9` | ROM entry branches to `start_vector` |
| [src/crt0.s](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s) | `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14` | Initial IRQ vector and call to `AgbMain` |
| [src/main.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/main.c) | `542b0f5d16dd93107523d11163bfcb70a42b707a` | Boot RAM clearing, DMA copy of IRQ handler, vector switch |
| [src/reset_save_heap.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/reset_save_heap.c) | `745270dc7415b869c302daaa7b9c2b2e5b2865f1` | `ReloadSave` resets EWRAM, not the boot-time IWRAM path |
| [include/gba/defines.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/defines.h) | `5521e942c00cc2c263b842ae7608dfb7ac881a76` | `INTR_VECTOR` at `0x03007FFC`, RAM bounds, common-data annotation |
| [include/gba/syscall.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/syscall.h) | `22fdf09facfaa812bf11b13d1f3ff86271598511` | BIOS reset flag definitions |
| [ld_script.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script.ld) | `9a4b45031e93c1e1da8186d8c697332710526048` | Legacy revision 0 boot objects in ROM, IWRAM NOLOAD |
| [ld_script_rev10.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script_rev10.ld) | `4eb3bc2eec749437be5797202442188972ac0693` | Legacy revision 10 equivalent ordering |
| [ld_script_modern.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script_modern.ld) | `e930243522bd21da40cc1a05de9a42b8ad409b46` | Modern boot objects in ROM, IWRAM NOLOAD |

## Resolved source-level chain

1. **Boot entry is ROM-addressed in every linker variant.** The ROM header branches to `start_vector`; all three linker scripts order the ROM header, `crt0`, then `main` in ROM `.text`. The reset stub configures stack pointers, writes `intr_main` to the IWRAM IRQ-vector slot via `INTR_VECTOR`, and transfers to `AgbMain`. These source relationships do not establish exact final linked symbol addresses.
2. **Modern and legacy RAM reset paths are intentionally different.** Legacy `AgbMain` requests `RegisterRamReset(RESET_ALL)`. Modern requests `RegisterRamReset(RESET_ALL & ~RESET_IWRAM)` and then performs an explicit ARM store loop starting at `0x03000000` and ending **exclusively** at `0x03007E00`, with a 128-byte stride. Therefore the last **512 bytes** of the 32 KiB IWRAM region—including the `0x03007FFC` vector slot—are **outside the modern manual clear loop**. This does not establish what the BIOS or other callers do to those bytes.
3. **The interrupt handler changes address during initialization.** `InitIntrHandlers` performs `DmaCopy32(3, intr_main, IntrMain_Buffer, sizeof(IntrMain_Buffer))` and then changes `INTR_VECTOR` to `IntrMain_Buffer` before enabling IME and VBlank interrupts. `IntrMain_Buffer` is declared `COMMON_DATA u32 [0x200]` (2 KiB). Its exact compiled address and the executed handler extent require ELF/runtime evidence.
4. **Save reload is not a repeat of boot.** `ReloadSave` masks IME, requests `RegisterRamReset(RESET_EWRAM)`, restores IME, then restores save/menu state. The inspected function does not re-copy `intr_main` or repoint `INTR_VECTOR`. This distinction matters when reasoning about RAM code lifetime across a save reload versus a full reset.
5. **The linker is part of the lifetime contract.** Each linker variant places `crt0` and `main` in ROM `.text`, but declares IWRAM as `NOLOAD`. A future bank/resource relocation manifest cannot treat all code references as persistent ROM pointers, nor infer runtime RAM initialization from a section name alone.

## Compatibility implications (requirements, not implemented features)

A future XGBA-aware loader or bank switch must account for **both** the early ROM-resident `intr_main` reference and the later IWRAM-resident handler. It must not assume that a save reload reinitializes the IRQ handler, that the modern boot clears all IWRAM, or that linker symbol names alone identify the final bytes. Remapping ROM before boot-time copying or while interrupts execute requires separately proved fetch/IRQ/DMA coherence; none is demonstrated by this source trace.

## Reproducibility and fail-closed limits

Run `python3 tools/phase1_firered_boot_irq_ram_lifetime.py --source <exact-pinned-pokefirered-checkout> --output phase1-evidence/firered-boot-irq-ram-lifetime.json`. The verifier checks the upstream commit and nine Git blob identities, verifies the ordering and RAM bounds, and runs **14 synthetic negative mutations** against the semantic relationships. CI archives JSON from the pinned source-check workflow.

**Do not claim a passing CI result until the final exact-head run has completed successfully.** Open proof obligations: linked ELF VMA/LMA and IRQ buffer location; instruction/DMA/IRQ runtime timing; emulator mapping and save reload behaviour; editor/patcher interoperability; independent file-by-file signoff.

**Phase 1 remains `FAIL_INCOMPLETE`. No Phase 2 implementation.**

## 27 October — full-file `crt0.s` review candidate and IRQ dispatch corner cases

The [exact-blob whole-file candidate](PHASE1_WHOLE_FILE_CANDIDATE_FIRERED_CRT0_2026-10-27.md) inventories all of pinned `src/crt0.s` (blob `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14`), including its assembly includes, both boot stack literals, IRQ handler and trailing literal pool. It remains **blocked for independent whole-file signoff**.

The handler prioritizes 14 `IE & IF` flags and advances its callback-table byte offset by four after each failed flag test. **Source-level edge case:** if no tested flag is set, the final GAMEPAK `ands` leaves Z set, so the `bne loop` spin is not entered; control falls into `jump_intr` with a zero acknowledge mask and the last callback-table offset (52 bytes, index 13). Conversely, when the GAMEPAK bit is set, the conditional sound-control byte store and `bne loop` spin prevent normal callback dispatch. The 14-entry table in pinned `src/main.c` has `IntrDummy` in its last slot. These are source-order conclusions, **not evidence that a no-pending IRQ or GAMEPAK IRQ is reachable or faulty in normal execution**.

The handler also dereferences the `gSTWIStatus` pointer and a byte at offset `0xA` when constructing a temporary IE mask; the inspected assembly contains no local pointer or shift-value bounds check. Producer initialization and runtime validity remain open. No approval or Phase 2 implementation follows from this addendum. **FAIL_INCOMPLETE; 0/14,834 independent approvals.**

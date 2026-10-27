# Phase 1 P0 — repeated native FireRed saves and checksum-corruption control (2026-10-28)

**Experiment pending exact-head CI; all gates FAIL_INCOMPLETE.** No independent approval. This is a focused save subsystem investigation, not a whole-file semantic disposition.

## Pinned source and ownership

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, agbcc `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`, mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`.
- FireRed `src/save.c` owns `TrySavingData`, sector counters, slot parity and checksum; `src/start_menu.c` owns controller Save dialog; `src/load_save.c` and `src/overworld.c` own cold-boot recovery and field control. Native symbol addresses are taken from the actual compiled ELF.
- mGBA `src/gba/savedata.c`, `include/mgba/internal/gba/savedata.h`, and `include/mgba/core/core.h` own Flash device, file flush and input APIs. Existing workflow pins their immutable source revision.
- Starting save is a **game-written first save** from green PR #28 CI #40601242124, but its *original playable player state* was a synthetic PalletTown fixture. This test does not establish human new-game progression.

## New source-grounded dependency tests

1. Copy the previously game-written counter-1 save; verify all 14 unique logical sector IDs, signature `0x08012025`, checksum and counter in physical slot 1.
2. Cold-start a fresh pinned emulator with that saved Flash; replay the already proven controller Save-menu schedule (3,200 frames), tracing real `StartMenuSaveCallback`, `SaveDialogCB_DoSave`, `TrySavingData` and actual caller-return `R0`. Require `SAVE_STATUS_OK=1`, counter **2**, nonzero Flash mutation, physical save SHA change and **14 valid sector IDs in physical slot 0**.
3. Assert second save preserves physical slot 1 unchanged; this tests alternating-slot overwrite isolation, not arbitrary crash safety.
4. Open a separate fresh emulator on the second game-written save, replay only Continue/field navigation (2,400 frames); require counter 2, RED name, PalletTown group 3/map 0/layout 78, field-input execution and no new save or physical Flash changes.
5. Negative control: flip one checksum bit in newly written physical slot 0 **after** save completion. Require offline sector checksum validator rejection; cold boot this altered file and record actual FireRed status/counter, player state and whether older-slot fallback occurs. Do **not** infer that this simulates a real mid-program power loss; the corruption timing is synthetic.

## Fail-closed boundaries and review questions

- A green first-save result from PR #28 does not certify the new repeated-save tests. Report native results only after exact-head CI passes.
- A checksum-corruption surrogate cannot establish actual Flash erase/program interruption, save atomicity on physical cartridges, or arbitrary malformed-sector memory safety.
- Remaining review: check source `save.c` slot parity, save error return propagation, mGBA file-flush behaviour, and the exact sector-selection status on damaged newest slot; then test real interrupted Flash commands if controllable without faking game execution.
- Preserve distinct analyst-prepared whole-file and independently approved counts; do not claim either from this partial subsystem dossier.

**Current Phase 1 decision: FAIL_INCOMPLETE. Phase 2 untouched.**

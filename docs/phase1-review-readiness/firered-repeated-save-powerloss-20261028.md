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

## Exact-head CI result and negative-control strengthening

At `ff6cc431841a4961853af530808100f47c7ca80b`, [CI #40604175206](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40604175206) **passed** (text artifact `12780755653`). Actual second controller-driven `TrySavingData` entry/return 1/1, return `SAVE_STATUS_OK=1`, counter 2, **862 Flash bytes changed**, physical `.sav` SHA changed, 14 checksum-valid rotated sectors in physical slot 0, prior slot 1 unchanged. A new emulator process recovered RED/PalletTown, counter 2 and 1,259 field-input hits without writing Flash. One-bit post-save checksum corruption produced native status **255**, counter **1**, older-slot recovery and 1,018 field-input hits. This is **not** actual in-flight power loss. Pinned FireRed `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`; pinned mGBA `src/gba/savedata.c` blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`.

This follow-up makes the observed older-slot fallback an **asserted regression requirement**, adds a Python syntax check and includes the new test/dossier paths in the workflow trigger list. **New head requires its own exact-head CI** before promotion; the previous green run remains valid for its immutable commit. All Phase 1 gates `FAIL_INCOMPLETE`, no independent approval.

## Third genuine game save — in-flight emulator-process interruption experiment

**New experiment; exact-head CI not yet verified.** Source-built pinned
FireRed/agbcc/mGBA starts from the already game-written counter-2 Flash
save and navigates the real Save menu via controller input. The test
observes checksum-valid counter-3 sectors in the mGBA mapped Flash1M
image during actual `TrySavingData`, polling every 2,048 instructions.
After 1, 7 or 13 complete new sectors in physical slot 1, the test
immediately calls `_exit(86)` **before the game save returns**.
There are no host Flash bus writes and no graceful emulator deinit.

The runner independently reads the resulting physical .sav, requires
counter-2 physical slot 0 byte-for-byte unchanged, verifies the new
sector count matches the in-memory observation, then cold-boots each
interrupted file in a new emulator process. The expected fallback is
counter 2, RED in Pallet Town, playable field input and no new writes.
A threshold of 14 is deliberately rejected as a negative control,
because a completed 14-sector save is not an in-flight interruption.

**Limit:** abrupt emulator process exit is not hardware power loss or
a filesystem durability guarantee. Pinned mGBA `src/gba/savedata.c`
blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` maps Flash
with writable VFile mapping and can later sync through
`GBASavedataClean`. Host OS page-cache writeback can persist mapped
changes even when the emulator exits abruptly. Pinned FireRed
`src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`
defines rotating sectors and the game-save call path.

Do not infer results from successful compilation alone. No new
complete-file analyst review or independent approval; all Phase 1
gates remain FAIL_INCOMPLETE. Phase 2 untouched.

### Pinned mGBA flush lifecycle and durability boundary

Additional pinned source closure:
`mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`
`src/gba/gba.c` blob `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e`
calls `GBASavedataClean` from `GBAFrameEnded`.
`include/mgba/internal/defines.h` blob
`67b8ec8fd2f51ee2c0c6231443af752158397b03`
defines `mSAVEDATA_CLEANUP_THRESHOLD=15`: a newly dirty save
is marked seen, then `mSavedataClean` requests cleanup only after
**more than 15 frames** without a new dirty write. Pinned
`src/gba/savedata.c` blob
`fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`
calls `vf->sync` only on that cleanup path with a writable mapping.
The in-flight hook now records the actual mGBA `dirty` flags and
`dirtAge` at interruption, without asserting that those flags prove
or disprove physical durability. This differentiates emulated Flash
programming, emulator-managed sync eligibility, host shared-memory
mapping persistence, and real power-failure durability.

**Unresolved:** no actual storage power cut, no proven sync-success
callback from VFile, no fsync guarantee, and no independent review.

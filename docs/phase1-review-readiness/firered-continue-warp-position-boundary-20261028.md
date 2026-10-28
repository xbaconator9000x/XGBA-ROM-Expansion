# Phase 1 — Continue-warp avatar and player-position save boundary (2026-10-28)

Status: **FAIL_INCOMPLETE / pending exact-head CI**. No independent approval.

## Reconciled native evidence

At exact HEAD `34581be824fa53ee3c2f0f0510dff7c7611961ff`, [Actions #40633561895](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40633561895) completed **failure**. The source-built FireRed/agbcc/mGBA job passed immutable checkouts, pinned builds, all prior save/error/interruption controls, and a NEW Continue-warp controller movement experiment. Text artifact: `12792936222`.

The new `pallet_continue_warp` fixture (synthetic, never human-generated) set pinned `SaveBlock2.specialSaveWarpFlags` bit0 and `SaveBlock1.continueGameWarp` for Pallet Town. Actual compiled runtime observed `CB2_LoadMap` 1, `LoadMapInStepsLocal` 17, `InitObjectEventsLocal` 1, `InitPlayerAvatar` 1, 1,770 active player-object frames, 158 controllable frames and 1,612 changed-position frames, from (11,10) to (12,16). No `TrySavingData` call or Flash changes occurred in this unsaved movement control.

The same run's **old** position-roundtrip harness instead loaded a first game-written save derived from `pallet_valid` without the Continue-warp precondition. It observed `InitPlayerAvatar` 0, 192 directional `player_step` calls, 0 active player-object frames and unchanged (11,10); its strict assertion correctly failed. This is a **fixture precondition mismatch**, not a controller-input registration failure and not evidence of real game progression.

## New fail-closed test design

The corrected position-roundtrip harness uses the **separate source-pinned synthetic Continue-warp fixture** in both matched paths. Without saving, actual controller movement must alter runtime x/y, leave physical Flash byte-for-byte unchanged, and a fresh emulator must recover the original (11,10). With saving, the same controller movement must reach `StartMenuSaveCallback`, `SaveDialogCB_DoSave` and genuine `TrySavingData` with `SAVE_STATUS_OK=1`; game-written physical slot1 counter1 must contain all 14 checksum-valid sectors and the new x/y in sector ID1. A fresh emulator must recover that exact x/y from physical Flash without writing Flash or entering `TrySavingData`. The old `pallet_valid` fixture remains an explicit negative check for the missing warp flag.

These are **test assertions, not results**, until exact-head CI passes. A synthetic warp-initialized fixture does not prove full new-game progression, arbitrary save corruption safety, cartridge power-loss durability or expanded ROM interoperability.

## Immutable pinned upstream provenance

- FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- agbcc `da598c1d918402c42c0c0d7128ba14567f3175e9`.
- mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`.
- `include/global.h` blob `77155b09014aa854fcf87260e6ad2969e222da53`.
- `include/save_location.h` blob `2d2cb197494b663dcb8e687f9f7267576bdc3c34`.
- `src/load_save.c` blob `8b723dd044c6024b3671bb890b25b56a53f99ec5`.
- `src/overworld.c` blob `339014da46ae8543143edc99ab72bf7496203a0d`.
- `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`.

## Independent reviewer questions

1. Does source-defined Continue-warp setup correctly model the preconditions of normal in-game Continue, or does the synthetic fixture omit other player-state initialization?
2. Does game-written sector ID1 x/y exactly correspond to the live SaveBlock1 coordinates after movement and survive a truly fresh emulator?
3. Are there unsaved runtime-only movement fields that affect camera/player reconstruction on the subsequent boot?
4. Which additional game-created new-game fixture would remove the remaining synthetic-state limitation?

All Phase 1 gates remain **FAIL_INCOMPLETE**; independent approvals remain **zero**. No Phase 2 work.

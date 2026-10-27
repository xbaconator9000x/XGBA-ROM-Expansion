# Phase 1 P0 — FireRed Trainer Tower temporary opponent-index lifecycle (26 October 2026)

**Status: FAIL_INCOMPLETE. This is a source-only, exact-pinned dependency trace, not a runtime proof or independent whole-file signoff.**

## Source-grounded chain

At immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, both `LoadMapFromCameraTransition` and `LoadMapFromWarp` call `ClearTempFieldEventData()` **before** `RunOnTransitionMapScript()`. The clearing routine zeroes the temporary-variable area; `VAR_TEMP_1` is `TEMP_VARS_START + 1`. This establishes a zero-initialized opponent index on these two inspected map-entry paths, not on every possible field/script continuation path.

All eight pinned `data/maps/TrainerTower_{1..8}F/scripts.inc` files dispatch to the shared `TrainerTower_OnTransition`, `TrainerTower_OnResume`, and `TrainerTower_OnFrame` labels and contain no direct `VAR_TEMP_1` reference. In the shared `data/scripts/trainer_tower.inc`, the knockout path switches over indices **0, 1, 2** and increments `VAR_TEMP_1` twice by one. The single/double battle script branches do not explicitly set `VAR_TEMP_1`; the two inspected map-entry clear paths therefore explain the expected **zero** initial value, while knockout progresses to **1** and **2**. This is an authored-flow explanation, not a universal input bound.

The C consumers are separate: `InitTrainerTowerBattleStruct` reads `VAR_TEMP_1` to select `CURR_FLOOR.trainers[trainerId]` and, in double battles, `trainers[trainerId + 1]`. `BuildEnemyParty` and `PlayTrainerTowerEncounterMusic` also consume it. `ShowResultsBoard` separately reuses `VAR_TEMP_1` to hold a window ID; the `ttower_showresults` macro is annotated unused and has no invocation in the inspected shared Trainer Tower script. That reuse must not be silently interpreted as a battle-index producer.

## Reproducibility

`tools/phase1_firered_tower_temp_index_lifetime.py` pins **14 exact upstream Git blobs**: `src/overworld.c`, `src/event_data.c`, `src/trainer_tower.c`, `include/constants/vars.h`, `data/scripts/trainer_tower.inc`, `asm/macros/trainer_tower.inc`, and all eight floor script files. It validates source bytes, both checked map-load call orders, all eight floor script dispatches, authored knockout cases/progression, C index consumers and the results-board reuse. Five negative mutations must fail closed. Output retains zero independent approvals and `FAIL_INCOMPLETE` even on successful source verification.

## Open gates

- Establish all map-load/continuation and script entrypoint paths, not merely the two checked entrypoints.
- Prove or refute any out-of-range `VAR_TEMP_1` producer on battle-entry paths, including interaction with the separate saved `floorsCleared` index.
- Verify compiled script and battle dispatch behaviour; execute controlled emulator negative cases.
- Complete whole-file semantic dispositions, editor round trips and broader cross-repository compatibility.

**No Phase 2 work, crash claim, independent signoff or emulator certification.**

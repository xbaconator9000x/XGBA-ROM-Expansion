# Phase 1 — pinned Trainer Tower stock lobby script to original FALSE stub (2026-10-29)

**SOURCE-ONLY / exact-head CI pending / FAIL_INCOMPLETE / 0 of 14,834 independent approvals.** This is a new stock script dependency closure, not a repeat of the already-green compiled C caller evidence or original-agbcc ARM direct-entry Flash sector30/31 execution.

Immutable FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Five pinned source blobs:
- `data/maps/TrainerTower_Lobby/scripts.inc` `b2543ec3f7fe3481bb43ebe3bf783e33b668c9c5`: player lobby challenge choice routes to `TrainerTower_Lobby_EventScript_BeginChallenge`, which invokes `ttower_startchallenge`.
- `asm/macros/trainer_tower.inc` `94d9efe775658c7865d74f8819b9c5bfb74db893`: macro sets `VAR_0x8004 = TRAINER_TOWER_FUNC_START_CHALLENGE` then `special CallTrainerTowerFunc`.
- `data/specials.inc` `d880bf6b9dc9fd765f0b85e6d698411e3da81d5d`: original script-special registry includes `CallTrainerTowerFunc`.
- `src/trainer_tower.c` `732b3f2ed31ed95d6476b9e111d53f759c448d81`: `CallTrainerTowerFunc` calls `SetUpTrainerTowerDataStruct`, dispatches `sTrainerTowerFunctions[gSpecialVar_0x8004]`, and frees state; start-challenge dispatch maps to `StartTrainerTowerChallenge`. Setup checks `ReadTrainerTowerAndValidate()==TRUE` before loading external data; false path uses local Trainer Tower header/floors. Start challenge calls the same function and sets `TRAINER_TOWER.validated = TRUE` when it returns false.
- `src/cereader_tool.c` `395be0bcbed8454e645a9f5670cde3024eda508e`: original `ReadTrainerTowerAndValidate` is a stock `return FALSE;` stub.

**Implication:** there is an original authored lobby script and registered special that source-connect to the stock stub, and the source-proven FALSE branch selects local data. This does **not** prove the script path was reached in native gameplay, that external e-Reader data can be loaded, or that the original ARM Flash-sector routines are invoked by this stock path. The previous original-agbcc direct-entry native Flash test is separate evidence.

Verifier `tools/phase1_tower_stock_script_reachability.py` pins all five blobs, checks ordered source anchors, and requires every anchor mutation to be rejected. Only source class is reported; no complete-file dispositions or independent approvals are created.

Partial per-file reviewer handoff: lobby scripts — actual map/script binding and NPC trigger; macro file — expansion and argument constants; specials registry — index and compiled script dispatch; trainer_tower.c — full state lifetime and callers; cereader_tool.c — complete stub/loader semantics. All whole-file review and external approval outstanding. Preserve original FireRed/agbcc/mGBA licensing obligations. No upstream/main/audit edits or Phase 2.

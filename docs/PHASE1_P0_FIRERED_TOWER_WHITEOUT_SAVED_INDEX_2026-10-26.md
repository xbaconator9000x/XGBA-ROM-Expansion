# Phase 1 P0 — FireRed Trainer Tower whiteout saved-index boundary (26 October 2026)

**Decision: FAIL_INCOMPLETE.** This is a source-backed conditional array-index proof obligation, **not** an observed crash, save-corruption finding, compiled-ROM proof, or independent whole-file semantic signoff.

## Newly identified consumer outside the Trainer Tower dispatcher

At immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/heal_location.c` in `SetWhiteoutRespawnWarpAndHealerNpc` tests `VarGet(VAR_MAP_SCENE_TRAINER_TOWER) == 1` and then immediately reads `gSaveBlock1Ptr->trainerTower[gSaveBlock1Ptr->towerChallengeId].spokeToOwner`. There is **no local bounds check before this read**. The `#ifdef BUGFIX` block lower in the function protects a different `healLocationIdx` path in the `else` branch; it does **not** guard the Trainer Tower saved-ID array read.

The pinned `include/global.h` defines `towerChallengeId` as `u32` and `trainerTower[NUM_TOWER_CHALLENGE_TYPES]`; `include/constants/global.h` defines that count as **4**. Therefore, **conditional on** the scene variable being 1 and the saved ID being 4 or greater, this expression would index beyond the four-element array. Whether that joint state is possible during normal gameplay, after save loading, or following corruption is **not established**.

This path is separate from the already documented `src/trainer_tower.c` setup-before-dispatch index. `StartTrainerTowerChallenge` clamps its saved ID, but that local normalization cannot establish a guard on the earlier whiteout function. The pinned source check also retains the existing dispatcher-order and setup-table expressions to prevent conflation.

## Reproducible evidence and review boundary

`tools/phase1_firered_tower_whiteout_boundary.py` verifies the exact upstream HEAD and **working-tree Git blob hashes** of:

- `src/heal_location.c` — `80700d49a328bd46e620c30071976375d6f748ce`
- `include/global.h` — `77155b09014aa854fcf87260e6ad2969e222da53`
- `include/constants/global.h` — `21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9`
- `src/trainer_tower.c` — `732b3f2ed31ed95d6476b9e111d53f759c448d81`

The checker asserts the whiteout scene condition, direct saved-ID read, save-array extent, distinct later BUGFIX path and Trainer Tower setup/normalization ordering. Three synthetic negative controls must reject a changed scene predicate, a substituted constant index and an inserted pre-read bounds check. Its JSON evidence is explicitly `FAIL_INCOMPLETE` with zero independent approvals.

**Verification boundary:** These predicates were compared against the four pinned upstream files through the connected GitHub source interface before the checker was committed. The new Python checker and its workflow require exact-head GitHub Actions execution before claiming CI verification. No other repository is modified.

**Next obligations:** inspect saved-ID initialization and save-load validation, trace scene-variable lifecycle and whiteout callers, then exercise conditional states in compiled ROM/emulator tests. Do not assert practical exploitability or Phase 1 completion from this source-only finding.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions. No Phase 2 implementation.**

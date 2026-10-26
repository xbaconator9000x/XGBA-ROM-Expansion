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


## Addendum — pinned save-sector load and whiteout caller boundary

This follow-up examines the **save-data ingress path**, rather than assuming that a checksum validates the semantics of each field. The exact upstream commit is still `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Four additional whole-file Git blobs are pinned by the checker:

| Upstream source | Git blob | Bounded role |
| --- | --- | --- |
| `src/save.c` | `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` | Save-sector validity and data copy |
| `src/load_save.c` | `8b723dd044c6024b3671bb890b25b56a53f99ec5` | Post-load serialized party/object restoration |
| `src/new_game.c` | `3768b3ccb98cdad514b858cbc59244f21bedb7b0` | New-game save initialization |
| `src/overworld.c` | `339014da46ae8543143edc99ab72bf7496203a0d` | Whiteout respawn caller |

**Source-grounded sequence.** In `src/save.c` lines 423–459, `TryLoadSaveSlot` obtains save validity status and calls `CopySaveSlotData`; that copy requires the sector signature and checksum to match before copying the sector payload into save-block memory. The normal `LoadGameSave` branch at lines 803–821 invokes `TryLoadSaveSlot` followed by `LoadSerializedGame`. In `src/load_save.c` lines 202–206, `LoadSerializedGame` restores the player party and object events. **These inspected functions do not apply a range check to `towerChallengeId`**. That is a bounded observation about these source bodies, **not proof that no other game initialization or resume path can normalize it**.

**Initialization contrast.** `src/new_game.c` lines 115–151 clears SaveBlock1 through `ClearSav1` and resets Trainer Tower record times through `ResetTrainerTowerResults`; `src/trainer_tower.c` lines 1087–1095 shows that record-time reset loops over the four challenge records. These operations should not be conflated with validation of a loaded, pre-existing save. `src/overworld.c` lines 627–630 calls `SetWhiteoutRespawnWarpAndHealerNpc`, which has the previously pinned scene-gated saved-ID array access.

**Interpretation.** Sector signature/checksum integrity is distinct from semantic validation of a saved challenge ID. The source evidence now links the save-sector copy, limited post-load restoration, new-game initialization and whiteout consumer. It does **not** prove an out-of-range value can survive every continuation path, or that the Trainer Tower scene predicate can coincide with it. Those remain runtime/lifecycle and save-corruption test obligations. No exploit, crash, independent approval, compiled proof or Phase 2 implementation is claimed.

**Reproducibility.** The pinned-source checker verifies all eight exact Git blobs, these bounded contracts and three additional mutation controls. It records `FAIL_INCOMPLETE` and zero independent whole-file approvals regardless of the result. GitHub Actions must pass at the exact resulting commit before this extension is described as CI-verified.

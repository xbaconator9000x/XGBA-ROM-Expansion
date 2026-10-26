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


## Addendum — authored scene-flag lifecycle and challenge-start ordering

The pinned source-level whiteout predicate can now be connected to the **authored** Trainer Tower lobby script, without assuming a runtime crash. Three additional immutable FireRed source blobs are checked against the actual working-tree bytes:

| Source | Git blob | Verified contract |
| --- | --- | --- |
| `data/maps/TrainerTower_Lobby/scripts.inc` | `b2543ec3f7fe3481bb43ebe3bf783e33b668c9c5` | Challenge entry sets scene 1 before `ttower_startchallenge`; lobby challenge-exit path resets scene 0 |
| `data/maps/SevenIsland_TrainerTower/scripts.inc` | `b357537593138b61bb43e399d70fca17fd991f0f` | Exterior map-transition script resets scene 0 |
| `data/maps/TrainerTower_Lobby/map.json` | `bc3221e5c44e960804fa565e93e3828544722e84` | Lobby coordinate event (9,7,elevation 3) invokes the entry trigger only when the scene variable equals 0 |

**Temporal dependency:** `TrainerTower_Lobby_EventScript_BeginChallenge` copies the selected challenge mode into `VAR_0x8005`, writes `VAR_MAP_SCENE_TRAINER_TOWER = 1`, heals the party, and only then executes `ttower_startchallenge`. In the separately pinned C dispatcher, setup reads the saved challenge ID before `StartTrainerTowerChallenge` assigns/clamps it. Thus the authored scene flag is already 1 during challenge-start dispatch, and the whiteout consumer's scene-1 predicate is not merely a hypothetical constant. This establishes a source-level **potential overlap in the state lifecycle**, not that a malformed saved ID is reachable or survives normal challenge initialization.

The lobby's exit-challenge script and the exterior's map-transition script both reset the scene to 0; the whiteout function can also reset it if `spokeToOwner` is false. The two authored script files have exactly three explicit scene-setting instructions between them. **This is not a game-wide writer census** and does not prove the order or reachability of all runtime transitions.

`tools/phase1_firered_tower_whiteout_boundary.py` now checks the three additional blobs, the challenge-entry ordering, both reset sites and the map coordinate-event condition. Five synthetic negative controls cover scene-value drift, assignment after challenge start, missing/altered resets, and the coordinate trigger's scene value. The evidence JSON retains `FAIL_INCOMPLETE` and zero independent approvals.

**Verification boundary:** The authored source texts and their Git blob identities were inspected through the pinned GitHub source interface. Exact-head GitHub Actions verification of this new checker revision is required before calling these five controls CI-passed. Compiled scripts, save-load state survival, whiteout runtime execution, emulator behaviour and whole-file semantic approvals remain unverified.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent whole-file dispositions.**

**Post-change CI verification (26 October 2026, 05:33 UTC):** [GitHub Actions run #40274858217](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40274858217), job `121415340765`, completed **successfully** at source/checkpoint head `0790c606eb84fe423cfa8ac07aae46a90e4aa111`. Logs report `PINNED_TOWER_WHITEOUT_SOURCE_PASS array_extent=4 negative_controls=3 scene_lifecycle_controls=5` and `PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0`. The uploaded evidence artifact is `12629229159` (GitHub-reported ZIP SHA-256 `1d9d808b3b3bb89e63543d346f068735b87f1d5b064091e43fd63a252e2ff632`). This verifies the pinned-source regression, **not** compiled/runtime reachability or independent semantic approval.

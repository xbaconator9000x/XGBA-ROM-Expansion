# Phase 1 P0 — FireRed Trainer Tower saved floor-progress table index (26 October 2026)

**Gate: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions.** This is a pinned, source-level conditional bounds obligation. It is not an observed crash, proof that a malformed save reaches battle entry, compiled/emulator evidence, or an XGBA implementation.

## Pinned upstream dependencies

All source evidence is from immutable pret/pokefirered commit ce6406d8c2eaf46d543c8a2606de0c3cb1951982:

| File | Git blob SHA | Relevant source |
| --- | --- | --- |
| src/trainer_tower.c | 732b3f2ed31ed95d6476b9e111d53f759c448d81 | lines 399–433, 733–755, 769–784, 988–1024 |
| include/global.h | 77155b09014aa854fcf87260e6ad2969e222da53 | struct TrainerTower saved u8 floorsCleared; saved challenge record array |
| include/constants/trainer_tower.h | ea0039ea1408c06b8c968cfde8e2628213b2a0dc | MAX_TRAINER_TOWER_FLOORS = 8, MAX_TRAINERS_PER_FLOOR = 3 |

Three separate static const u8 floor-selection tables in src/trainer_tower.c each have **eight initialized rows**: sSingleBattleChallengeMonIdxs[8][2], sDoubleBattleChallengeMonIdxs[8][2], and sKnockoutChallengeMonIdxs[8][3] (the first dimension is declared using MAX_TRAINER_TOWER_FLOORS). The widths 2/2/3 describe selection slots, not the number of possible saved floor values.

StartTrainerTowerChallenge resets TRAINER_TOWER.floorsCleared = 0. The separately dispatched TrainerTowerAddFloorCleared increments that **saved u8 field** with ++ and no local clamp. DoTrainerTowerBattle calls BuildEnemyParty before scheduling the transition. BuildEnemyParty sets its local u8 floorIdx = TRAINER_TOWER.floorsCleared and directly indexes the single, double, or knockout selection table by floorIdx, without a local pre-index bounds check.

Consequently, **if** saved floorsCleared is 8–255 at BuildEnemyParty entry, the first dimension of each selected table is exceeded. This is distinct from the **map-layout-derived** sTrainerTowerState->floorIdx used by CURR_FLOOR. An authored eight-floor progression may constrain normal gameplay, but no all-path reachability or saved-state validation proof is provided here. The separate trainer-index (VAR_TEMP_1) obligation is recorded in [opponent-index evidence](PHASE1_P0_FIRERED_TOWER_OPPONENT_INDEX_2026-10-26.md).

## Reproducible negative controls

[Source-only checker](../tools/phase1_firered_tower_floor_progress.py) verifies the exact upstream commit and three Git blob identities; checks saved-field type, challenge reset, increment, all three table declarations and eight-row initializer cardinalities, battle entrypoint, and all four indexed read expressions. Nine independent mutation fixtures must fail closed when changing: saved field width, floor extent, index source, increment guard, knockout consumer, double consumer, battle entrypoint, knockout table row count, or a newly inserted pre-index guard.

[Dedicated CI workflow](../.github/workflows/phase1-firered-layout-writers.yml) compiles and executes the checker against the pinned FireRed checkout and archives a JSON evidence result. **CI status must be checked against the exact head commit before claiming the checker passed.** A passing source test remains explicitly FAIL_INCOMPLETE, with zero semantic signoffs.

## Open proof obligations

Trace every floor-clear producer and all authored battle paths, including transitions/resume; determine whether save-load integrity or gameplay can yield floorsCleared >= 8 at battle entry; compile and execute controlled malformed-save negative cases; separately resolve VAR_TEMP_1, challenge-ID and map-derived floor index bounds; complete independent whole-file review, editor/emulator interoperability and all Phase 1 gates.

**No other repository is modified by this evidence work.**

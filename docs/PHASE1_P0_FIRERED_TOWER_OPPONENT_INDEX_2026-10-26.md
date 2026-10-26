# Phase 1 P0 — FireRed Trainer Tower opponent-index dependency (26 October 2026)

**Gate: FAIL_INCOMPLETE. No independent whole-file approvals, compiled proof, emulator result or Phase 2 implementation.**

## Pinned source interpretation

All evidence is from immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. The exact upstream Git blob identities are enforced by `tools/phase1_firered_tower_opponent_index.py`.

| Pinned file | Git blob | Dependency |
| --- | --- | --- |
| `src/trainer_tower.c` | `732b3f2ed31ed95d6476b9e111d53f759c448d81` | Trainer index and double-battle second trainer access |
| `src/battle_util2.c` | `8a5fbccf67942b9bc55d460cea07a2744c9a2b14` | Battle-resource initialization calls Trainer Tower opponent setup |
| `data/scripts/trainer_tower.inc` | `6a526e9fc97c431321fe11e8ca20068e7af2c085` | Authored knockout battle index cases and progression |
| `include/constants/trainer_tower.h` | `ea0039ea1408c06b8c968cfde8e2628213b2a0dc` | Three trainers per floor; eight floors |
| `include/constants/vars.h` | `5c7bbf8a3356606af13e744ac24de806c1b0869e` | `VAR_TEMP_1` is a map-load-cleared temporary variable |

### Dependency trace

`AllocateBattleResources` invokes `InitTrainerTowerBattleStruct` when `BATTLE_TYPE_TRAINER_TOWER` is set. That initializer first calls `SetUpTrainerTowerDataStruct`, which has its separately documented saved challenge-ID lookup. It then obtains `trainerId = VarGet(VAR_TEMP_1)` and accesses `CURR_FLOOR.trainers[trainerId]` without a local bounds check before the first access.

For `CHALLENGE_TYPE_DOUBLE`, it additionally accesses `CURR_FLOOR.trainers[trainerId + 1]`. The per-floor trainer extent is three, so this requires `trainerId <= 1` for that additional access. That is an arithmetic proof obligation, **not** a finding that `trainerId == 2` reaches this branch.

The authored knockout script switches on `VAR_TEMP_1` with cases 0, 1 and 2, and advances it twice with `addvar VAR_TEMP_1, 1`. These cases match the three-trainer extent for the authored knockout progression. However, the same variable is also used by other Trainer Tower functions, including the results-board window ID, encounter music and enemy-party construction. The full producer/consumer lifetime across battle entry, map transitions, results-board UI and saved state has not been proven. Do not assume the knockout script constrains every battle path.

### Reproducibility and fail-closed review

The checker validates the pinned commit and five exact working-tree Git blobs, the battle-resource entrypoint, the base and second-trainer indexing, the three-trainer extent, temporary-variable declaration and knockout script cases/progression. Five mutation controls must reject drift in extent, second index, local bounds guard, battle entrypoint and knockout case. It emits JSON with `FAIL_INCOMPLETE` and zero independent approvals regardless of source-check success.

The dedicated `phase1-firered-layout-writers.yml` workflow executes this checker alongside the existing source contracts and archives the JSON. **A passing exact-head Actions run is required before calling this new checker CI-verified.** This document does not claim a crash, exploit, malformed-save reachability, independent review or runtime certification.

## Outstanding obligations

Trace all `VAR_TEMP_1` producers and consumers, especially how battle entry and UI teardown interact; establish which double-battle indices are possible; audit the `TRAINER_TOWER.floorsCleared` indexing of the floor-specific mon-selection tables; obtain compiled and emulator evidence before any safety or compatibility certification. Broader source-semantic and editor interoperability gates remain incomplete.

**Phase 1: FAIL_INCOMPLETE; independent whole-file approvals: 0/14,834.**

# Phase 1 P0 — Trainer Tower script-switch fallthrough and battle-index boundary (26 October 2026)

**Gate: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions.** This is a source-level script dispatch finding. It is not proof that invalid outcomes, challenge types or temporary indices occur in normal gameplay, nor a compiled-script or emulator certification.

## Exact pinned sources

The checker [`tools/phase1_firered_tower_script_fallthrough.py`](../tools/phase1_firered_tower_script_fallthrough.py) verifies seven Git blobs from `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

| Upstream file | Exact Git blob |
| --- | --- |
| `data/scripts/trainer_tower.inc` | `6a526e9fc97c431321fe11e8ca20068e7af2c085` |
| `asm/macros/event.inc` | `142ad979d7d3093244087a247fa2b4883424f77f` |
| `src/scrcmd.c` | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` |
| `src/trainer_tower.c` | `732b3f2ed31ed95d6476b9e111d53f759c448d81` |
| `asm/macros/trainer_tower.inc` | `94d9efe775658c7865d74f8819b9c5bfb74db893` |
| `include/constants/trainer_tower.h` | `ea0039ea1408c06b8c968cfde8e2628213b2a0dc` |
| `include/constants/global.h` | `21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9` |

The assembler's `switch` macro copies a value into `VAR_0x8000`. Each `case` compares it and conditionally jumps. The runtime `ScrCmd_goto_if` executes `ScriptJump` only on a satisfied comparison; a nonmatching case proceeds to the following script command. Thus the consecutive script labels matter: **unmatched values do not implicitly terminate or reject a switch**.

## Five source-verified unmatched-value edges

| Dispatch label | Explicitly handled values | Source-adjacent unmatched continuation |
| --- | --- | --- |
| `TrainerTower_EventScript_TriggerBattle` | single, double, knockout | `DoSingleBattle` |
| `TrainerTower_EventScript_DoKnockoutBattle` | `VAR_TEMP_1` = 0, 1, 2 | `DoKnockoutBattle1` |
| `TrainerTower_EventScript_DoBattle` | won, lost, drew | `WonBattle` |
| `TrainerTower_EventScript_WonBattle` | single, double, knockout | `CheckNextKnockoutBattle` |
| `TrainerTower_EventScript_CheckNextKnockoutBattle` | `VAR_TEMP_1` = 0, 1, 2 | `DoSecondKnockoutBattle` |

The last unmatched edge enters a script that increments `VAR_TEMP_1` and loops back to knockout dispatch. The normal 0 → 1 → 2 knockout progression is intentional; **the unmatched-index path is a distinct conditional behavior**. The knockout introduction uses `VAR_TEMP_1` to request opponent speech, while native battle setup reads `VAR_TEMP_1` and indexes trainer data (including `trainerId + 1` for double battles). These cross-language dependencies must be preserved and bounded when evaluating save/temporary-variable and expanded-engine compatibility.

**Do not equate these conditional source paths with observed faults.** They require an actual unmatched input to reach them. A compiled test and complete producer/consumer lifecycle are still needed. The absence of a local default branch is not evidence that an invalid value is naturally produced.

## Additional P0 cross-language boundary — floor initialization precedes script fallback

The pinned `ttower_initfloor` assembler macro sets `VAR_0x8004 = TRAINER_TOWER_FUNC_INIT_FLOOR` and invokes `CallTrainerTowerFunc`. The native function table dispatches that selector to `InitTrainerTowerFloor`. This happens **before** the remaining commands in `TrainerTower_OnTransition` execute.

The native `sFloorLayouts` table has **eight rows and three columns**, explicitly `[MAX_TRAINER_TOWER_FLOORS][NUM_TOWER_CHALLENGE_TYPES - 1]`. Its columns correspond to floor challenge types SINGLE=0, DOUBLE=1 and KNOCKOUT=2. The fourth challenge ID, MIXED=3, is an overall challenge category; ordinary mixed floors are expected to contain one of the three per-floor types.

`InitTrainerTowerFloor` checks whether the current map layout lies beyond the configured floor count. On that branch it assigns `gSpecialVar_Result = 3` and switches to the roof layout. On its **other** branch, however, it assigns `gSpecialVar_Result = CURR_FLOOR.challengeType` and immediately reads `sFloorLayouts[sTrainerTowerState->floorIdx][gSpecialVar_Result]` **without a local column or row bounds check**. The authored transition script subsequently switches on 0/1/2; an unmatched result hides all four trainer objects and disables both battle triggers. That script fallback cannot protect a preceding native array access.

**Conditional risk, not an observed fault:** If a malformed floor record or other state makes `CURR_FLOOR.challengeType` equal 3 or greater while the native normal-floor branch executes, the table's second dimension is exceeded *before* the script fallback. An invalid `floorIdx` presents a separate first-dimension obligation. Neither malformed state nor its runtime reachability has been demonstrated. The legitimate roof sentinel 3 follows the other C branch and is **not** evidence of this error.

The exact-pinned checker now verifies the seven upstream blobs, 8×3 initializer, enum/dimension values, script-to-native dispatch, native branch/index order and transition default commands. **Six additional fail-closed mutations** cover native index substitution, roof sentinel, table row, transition hide behavior, mixed enum and macro dispatch, bringing the checker to **12** negative controls. These are synthetic source controls, not compiled ROM tests.

**Checkpoint commit:** `ddba78a8eeb49d0f6fc95ff87a71c68499bf20c3`. **Verified exact-head CI PASS:** [run #40303500581](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40303500581) at commit `a40ab818c7458d3c7c0c7352d554f32f6bfb9919`; the job completed successfully and the earlier checker job log at `ddba78a8` explicitly records `PINNED_TOWER_SCRIPT_FALLTHROUGH_SOURCE_PASS edges=5 floor_layout=8x3 negatives=12`. The new documentation-only checkpoint commit must not be treated as separately verified until its own workflow completes. The authoritative Phase 1 gate remains **FAIL_INCOMPLETE; 0/14,834 independent whole-file approvals**.

## Reproducibility and negative controls

The checker validates exact pinned blob identities, the script macro expansion contract, runtime conditional comparison/jump behavior, label adjacency, the five dispatch tables, knockout progression and native index consumers. Twelve synthetic mutations must be rejected: six original script-dispatch/index-progression mutations plus six new native-floor-init/transition mutations. The original six reject: unconditional macro dispatch, unconditional runtime branch, changed outcome default, changed knockout case, changed knockout progression default and changed index increment.

CI compiles and runs the checker in [`phase1-firered-layout-writers.yml`](../.github/workflows/phase1-firered-layout-writers.yml) and archives the deterministic JSON evidence. **Check exact-head GitHub Actions status before claiming this new checker passed.** A green source-only check is not independent semantic approval.

## Remaining gates

Prove all relevant outcome and challenge-type producers, save/temporary-variable lifetimes, compiled script bytes and runtime entry reachability. Then test controlled boundary cases across compiled FireRed, mGBA and editor round trips. Keep broader Phase 1 compiler/linker, save/asset and cross-repository semantic gates fail-closed. No Phase 2 implementation or upstream source changes are part of this checkpoint.

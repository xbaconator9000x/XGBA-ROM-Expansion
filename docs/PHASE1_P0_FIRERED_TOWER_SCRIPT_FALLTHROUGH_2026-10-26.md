# Phase 1 P0 — Trainer Tower script-switch fallthrough and battle-index boundary (26 October 2026)

**Gate: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions.** This is a source-level script dispatch finding. It is not proof that invalid outcomes, challenge types or temporary indices occur in normal gameplay, nor a compiled-script or emulator certification.

## Exact pinned sources

The checker [`tools/phase1_firered_tower_script_fallthrough.py`](../tools/phase1_firered_tower_script_fallthrough.py) verifies four Git blobs from `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

| Upstream file | Exact Git blob |
| --- | --- |
| `data/scripts/trainer_tower.inc` | `6a526e9fc97c431321fe11e8ca20068e7af2c085` |
| `asm/macros/event.inc` | `142ad979d7d3093244087a247fa2b4883424f77f` |
| `src/scrcmd.c` | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` |
| `src/trainer_tower.c` | `732b3f2ed31ed95d6476b9e111d53f759c448d81` |

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

## Reproducibility and negative controls

The checker validates exact pinned blob identities, the script macro expansion contract, runtime conditional comparison/jump behavior, label adjacency, the five dispatch tables, knockout progression and native index consumers. Six synthetic mutations must be rejected: unconditional macro dispatch, unconditional runtime branch, changed outcome default, changed knockout case, changed knockout progression default and changed index increment.

CI compiles and runs the checker in [`phase1-firered-layout-writers.yml`](../.github/workflows/phase1-firered-layout-writers.yml) and archives the deterministic JSON evidence. **Check exact-head GitHub Actions status before claiming this new checker passed.** A green source-only check is not independent semantic approval.

## Remaining gates

Prove all relevant outcome and challenge-type producers, save/temporary-variable lifetimes, compiled script bytes and runtime entry reachability. Then test controlled boundary cases across compiled FireRed, mGBA and editor round trips. Keep broader Phase 1 compiler/linker, save/asset and cross-repository semantic gates fail-closed. No Phase 2 implementation or upstream source changes are part of this checkpoint.

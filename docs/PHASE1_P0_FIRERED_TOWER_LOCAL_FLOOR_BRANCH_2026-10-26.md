# Phase 1 P0 — FireRed Trainer Tower local-floor branch, 26 October 2026

**Gate: FAIL_INCOMPLETE. Zero independent whole-file semantic approvals.** This is a bounded, pinned source interpretation, not a reproduced runtime crash, malformed-save reachability proof, compiled ROM test, or XGBA architecture implementation.

## Source-backed finding

At immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `ReadTrainerTowerAndValidate(void)` in `src/cereader_tool.c` is a stub that **returns FALSE**. In `src/trainer_tower.c`, `SetUpTrainerTowerDataStruct` captures `gSaveBlock1Ptr->towerChallengeId` as `u32 challengeType`; the `TRUE` e-Reader branch would load external tower data, while the `else` branch uses `gTrainerTowerFloors[challengeType]` and copies eight floor pointers. With the pinned stub implementation, the local-floor `else` branch is selected by source logic. There is no local saved-ID bounds check before that index.

The actual `gTrainerTowerFloors` definition in `src/trainer_tower_sets.c` has four challenge-type rows (SINGLE, DOUBLE, KNOCKOUT, MIXED), each containing eight floor pointers. `include/constants/global.h` defines `NUM_TOWER_CHALLENGE_TYPES` as **4**. Therefore a saved challenge ID of 4 or greater would exceed the table's first dimension **if** the setup function is reached with that ID. This removes the previously unresolved e-Reader-versus-local-data branch ambiguity for this pinned FireRed revision. It does **not** establish how such an ID could arise or persist.

## Reproducible source identity and negative controls

`tools/phase1_firered_tower_local_floor_branch.py` requires the exact upstream commit and working-tree Git blob hashes:

| File | Git blob SHA |
| --- | --- |
| `src/cereader_tool.c` | `395be0bcbed8454e645a9f5670cde3024eda508e` |
| `src/trainer_tower_sets.c` | `a79580e10e5014c916e2f622cae24ef868381fa9` |
| `src/trainer_tower.c` | `732b3f2ed31ed95d6476b9e111d53f759c448d81` |
| `include/constants/global.h` | `21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9` |

The checker fails closed if the validator stub, branch order, table extent, challenge-type rows, pointer count, or absence of pre-index normalization changes. Four mutation controls must reject: stub returning TRUE; extent changed to five; fixed index substituted; and a new bounds clamp before indexing. It emits `FAIL_INCOMPLETE` regardless of passing source checks. The dedicated GitHub Actions workflow runs it alongside the existing layout-writer and whiteout tests and preserves JSON evidence.

**Verification status:** Source files and exact Git blobs were inspected through connected GitHub. [GitHub Actions run #40279325237](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40279325237), job `121428874283`, passed the new checker and all four negative controls at commit `8fba0059cb8d90ec51282c86ae4dd0393e37a966`. The log reports `PINNED_TOWER_LOCAL_FLOOR_BRANCH_PASS rows=4 pointers_per_row=8 negative_controls=4` and `PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0`. Artifact `12631296654` has ZIP SHA-256 `c24aef153bbc9ea96b5808d352ed5989cc205c0411dc13a38df2da2420473fb4`. The first CI attempt failed because the synthetic stub mutation targeted an unrelated earlier `return FALSE`; the matcher was narrowed to the exact function body and the corrected revision passed. No compiled or emulator verification is claimed. A subsequent documentation-only commit will require its own workflow result before claiming exact-head CI for that commit.

**Next obligations:** trace saved-ID ingress and full resume/map initialization paths; determine whether malformed ID and setup/whiteout can coincide; compile and run controlled save-state negative tests; complete independent whole-file dispositions and all Phase 1 gates. No other repository was modified.

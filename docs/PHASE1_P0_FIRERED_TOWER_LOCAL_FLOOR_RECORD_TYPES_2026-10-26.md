# Phase 1 P0 — Trainer Tower built-in floor-record challenge types (26 October 2026)

**Gate: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions.** Source-only producer-to-consumer audit; no malformed-save reachability, compiled execution, emulator certification, or Phase 2 implementation is claimed.

## Exact pinned source and dependency

At `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/trainer_tower_sets.c` has Git blob `a79580e10e5014c916e2f622cae24ef868381fa9`. The existing local-floor checker also pins `src/trainer_tower.c` (`732b3f2ed31ed95d6476b9e111d53f759c448d81`), `src/cereader_tool.c` (`395be0bcbed8454e645a9f5670cde3024eda508e`) and `include/constants/global.h` (`21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9`).

The e-Reader validation stub returns FALSE, selecting the built-in `gTrainerTowerFloors[challengeType]` table. That table has four challenge rows and eight pointers per row, **32 references to 28 distinct floor-record definitions**. All 28 referenced definitions have exactly one `.challengeType` field in the three valid *per-floor* types: SINGLE (0), DOUBLE (1), KNOCKOUT (2). No referenced built-in floor definition uses MIXED (3) as its per-floor challenge type.

The MIXED *challenge row* is not a fourth native floor-layout column. Its eight pointer targets and effective per-floor types, in order, are:

| Floor position | Built-in floor record | Effective challenge type |
| --- | --- | --- |
| 1 | Mixed_1 | SINGLE |
| 2 | Mixed_2 | SINGLE |
| 3 | Mixed_3 | SINGLE |
| 4 | Double_8 | DOUBLE |
| 5 | Mixed_5 | DOUBLE |
| 6 | Knockout_8 | KNOCKOUT |
| 7 | Double_3 | DOUBLE |
| 8 | Knockout_2 | KNOCKOUT |

All referenced floor records also declare `.floorIdx = MAX_TRAINER_TOWER_FLOORS` in their source initializer. This field is recorded as source metadata, **not** interpreted as proof that the runtime `sTrainerTowerState->floorIdx` is within 0–7.

## Boundary resolved, boundary still open

This closes a **built-in authored-data** ambiguity in the earlier [8×3 native layout-index checkpoint](PHASE1_P0_FIRERED_TOWER_SCRIPT_FALLTHROUGH_2026-10-26.md): when setup uses the pinned, unmodified built-in floor definitions and the native floor index is valid, the selected per-floor `challengeType` belongs to the native `sFloorLayouts` column range 0–2. The global MIXED selection itself does not supply a per-floor type of 3.

It **does not** establish an all-path bound on `floorIdx`, saved `towerChallengeId`, saved `floorsCleared`, temporary opponent indices, modified or corrupted data, or alternate external-data paths. The local-floor table still lacks a saved-ID bounds check before selecting a challenge row. A source-level proof of valid built-in records is not a runtime proof of data integrity.

## Reproducible checker

The existing [local-floor checker](../tools/phase1_firered_tower_local_floor_branch.py) now resolves all 32 pointers, checks exact row order (including the eight MIXED aliases), verifies the 28 referenced definitions and their `.challengeType`/`.floorIdx` fields, and emits the MIXED effective type sequence in deterministic JSON. Four additional fail-closed mutations change a MIXED pointer, turn a referenced SINGLE record into MIXED, change a reused DOUBLE pointer, or change referenced floor-index metadata. Together with the prior four controls, the checker now requires **eight** negative controls to fail closed.

The dedicated [CI workflow](../.github/workflows/phase1-firered-layout-writers.yml) executes the checker against the exact upstream commit and preserves its JSON. **Verification status: pending exact-head GitHub Actions check for the new source-contract revision.** No approval, compiled/runtime test, or completed Phase 1 gate follows from a green checker.

**Remaining:** establish compiled map/script inclusion, save-load value validity and reachable native floor indexes, controlled malformed-state runtime tests, independent whole-file semantic dispositions and all cross-repository Phase 1 gates.

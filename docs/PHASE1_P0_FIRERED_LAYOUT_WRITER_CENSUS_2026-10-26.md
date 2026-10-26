# Phase 1 P0 — pinned FireRed layout-ID writers and authored alternate selectors (26 October 2026)

**Decision: FAIL_INCOMPLETE.** This is a bounded, source-backed writer/selector trace, **not** a compiled-ROM reachability proof, observed crash, or independent whole-file disposition.

## New semantic finding

The pinned FireRed sources contain four direct assignments to `gSaveBlock1Ptr->mapLayoutId` across two files:

- `src/overworld.c` lines 551–556: `LoadCurrentMapData` copies the selected map header's `mapLayoutId`. Lines 978–982: `SetCurrentMapLayout(u16)` directly stores its argument and calls `GetMapLayout`. The getter at lines 490–496 checks only whether the ID is nonzero before indexing `gMapLayouts[mapLayoutId - 1]`; it has no local table-length guard.
- `src/quest_log.c` lines 402–405, 753–761: `BackUpMapLayout` records the ID in `VAR_QLBAK_MAP_LAYOUT`; `QL_RestoreMapLayoutId` restores `VarGet(VAR_QLBAK_MAP_LAYOUT)` and substitutes the map-header ID **only when the restored value is zero**. Nonzero values are not range-checked in this function. `src/overworld.c` lines 815–829 subsequently reloads the saved-layout header during quest-log map setup.
- `src/scrcmd.c` lines 711–717: script command `ScrCmd_setmaplayoutindex` reads a halfword via `VarGet(ScriptReadHalfword(ctx))` and forwards the result to `SetCurrentMapLayout`. The command table and event macro identify opcode `0xA7` and its 16-bit operand; the setter itself does not validate the table bounds.
- `src/trainer_tower.c` lines 352–362, 544–556: the floor-layout matrix supplies 24 explicitly named layout constants, and the roof branch supplies one more. The matrix selection depends on tower state; this review does not prove the state indices are bounded.

**Authored explicit-selector result:** The four `setmaplayoutindex` uses under `data/maps/**/scripts.inc` select four different layout constants, and Trainer Tower names 25 more. All **29** explicit alternate layout constants resolve to distinct named entries with **2×2 borders** in the pinned 383-position authored layout table. **None selects one of the 28 authored 0×0 layouts.** This narrows the direct authored-selector path but does not rule out unexpected nonzero IDs from script variables, quest-log backup data, saved state, or malformed runtime inputs.

## Exact source identities and reproducibility

Upstream: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Pinned Git blobs: `src/overworld.c` `339014da46ae8543143edc99ab72bf7496203a0d`; `src/quest_log.c` `0a2f76f2c4019fa0938d5044da73fcea1b2b069c`; `src/scrcmd.c` `97b695ee2f6fca80a3b78f52f6a444f696fe5814`; `src/trainer_tower.c` `732b3f2ed31ed95d6476b9e111d53f759c448d81`; `data/layouts/layouts.json` `41d0eb1b5e51fa75d535b5a098bae2bd650f710d`; `asm/macros/event.inc` `142ad979d7d3093244087a247fa2b4883424f77f`; `data/script_cmd_table.inc` `c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1`. The four authored map-script blobs are pinned individually by the checker.

`tools/phase1_firered_layout_writer_census.py` validates the exact upstream commit **and actual working-tree file bytes**, all 11 source blob identities, the four direct writers, the four script selectors, the 24 floor selectors plus roof, their positional table IDs and their border dimensions. It scans all authored `data/maps/**/scripts.inc` for unmodeled `setmaplayoutindex` sites and emits a deterministic JSON evidence record with explicit `FAIL_INCOMPLETE` and zero approvals.

**CI verified PASS:** [PR workflow run #40259017096](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40259017096), job `121367080412`, completed 26 October 2026 at approximately 02:25 UTC. Its job log reports `PINNED_LAYOUT_WRITERS_PASS script_sites=4 tower_layouts=25 alternate_2x2=29` and `PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0`. [Evidence artifact #12624375177](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40259017096/artifacts/12624375177) was uploaded with GitHub-reported ZIP digest `sha256:d3181b0c150ee18db0c7c402439cfa6a6f8c843306fe6bfa95351ca02451b290`. This validates the pinned source-level checker, **not** compiled/runtime safety or independent review. Earlier [pinned census #40254421074](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40254421074) passed the *separate* prior layout-table producer/consumer checks. The parallel [authored map-header join PR #6](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/6) passed its source-only CI but remains unmerged; neither result certifies this new writer checker.

## Remaining obligations

Determine actual script operand values after compilation, enumerate any nonliteral `VarGet` sources and quest-log backup corruption/restore paths, prove Trainer Tower state index bounds, and inspect original/modern compiled table inclusion. Trace `GetBorderBlockAt` callers and coordinate ranges before asserting a reachable zero divisor or negative index. Preserve save/editor/emulator round-trip and independent whole-file review gates.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independently approved whole-file dispositions. No Phase 2 implementation.**

## Addendum — literal script operands versus quest-log variables

The pinned `src/event_data.c` (Git blob `da9391cf0ef74c1addf550def8616c81f16e89e3`) resolves `VarGet(idx)` through `GetVarPointer(idx)`. For `idx < VARS_START`, `GetVarPointer` returns `NULL` and `VarGet` returns the original 16-bit operand unchanged. The pinned `include/constants/vars.h` (blob `5c7bbf8a3356606af13e744ac24de806c1b0869e`) defines `VARS_START = 0x4000` and `VAR_QLBAK_MAP_LAYOUT = 0x40AE`.

**Narrowed finding:** Each of the four authored `setmaplayoutindex LAYOUT_...` sites uses a one-based layout-table position less than `0x4000`. Under the pinned source semantics, these four script operands are **immediate layout IDs**, not indirect variable references. The checker now pins both additional source blobs, asserts the `VarGet`/pointer-lookup contract, verifies each immediate value and archives the resolved operands in its JSON evidence.

**Separate unresolved path:** Quest-log `QL_RestoreMapLayoutId` calls `VarGet(0x40AE)`, which *is* in the variable range. That value is backed up from the mutable saved layout ID and can be restored as a nonzero value without a local upper-bound check. The source-only proof does not establish that invalid values arise during ordinary gameplay, nor that the saved data is corrupt. Trainer Tower state bounds, linked layout-table bounds, saved-state integrity, and actual runtime reachability remain unproven.

This addendum changes no independent approvals or Phase 1 verdict. **FAIL_INCOMPLETE.** CI must pass at the new exact commit before this checker extension can be described as CI-verified.

## Addendum — Trainer Tower authored floor index arithmetic

The same pinned `data/layouts/layouts.json` assigns consecutive one-based positions **297** to `LAYOUT_TRAINER_TOWER_LOBBY`, **298–305** to `LAYOUT_TRAINER_TOWER_1F` through `8F`, and **306** to the roof. The pinned `src/trainer_tower.c` initializes `floorIdx = gMapHeader.mapLayoutId - LAYOUT_TRAINER_TOWER_1F`; therefore, **if the normal authored 1F–8F header IDs are in effect**, the arithmetic produces **0–7**, the first dimension of the eight-row `sFloorLayouts` table. The checker pins the source expression and all ten positional IDs and archives the floor-by-floor arithmetic.

This is a conditional source-level result, **not** an unconditional memory-safety proof: the branch choosing a floor uses `data.numFloors`, while the second table index comes from `CURR_FLOOR.challengeType`, including e-Reader data paths. Validation of those values, dynamic map-header state, and compiled/runtime behavior remains outstanding. **FAIL_INCOMPLETE.**

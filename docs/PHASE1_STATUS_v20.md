# Phase 1 semantic checkpoint v2.0 — 2026-10-25

**Current decision: FAIL_INCOMPLETE.** The source inventory is comprehensive; **independent file-level semantic approval is not**.

## Fully reproducible source and mapping evidence

- All 5 immutable upstream repositories and **14,834 tracked files** verified against canonical Git blobs; 4,685 source/config text files read, 2,612 CRLF-normalized palette blobs compared to canonical Git bytes.
- Imported [v1.5 mapping workpack](../imports/XGBA_Phase1_v1.5_Complete_Workpack.zip) retains **29,068 historical and candidate source-link records**, zero original source-anchor mismatches.
- Per-file source-hash-pinned review dossiers for **14,834 files** plus **163 module semantic review dossiers**, accounting for all 14,834 source inventory entries. 26 modules contain P0 files; 53 have AST errors; 47 unresolved include candidates.
- Unified call/include/generated asset/assembly/module references are *candidate dependency graphs*, not complete executed paths. [Earlier architecture contracts](SEMANTIC_DEPENDENCIES_v16.md).
- All **461** FireRed script opcode handlers were matched to dispatch tables and pinned definitions. The detailed operand/cursor/source review identifies 210 branching battle cursor handlers, 70 field handlers requiring pointer/branch/side-effect review and 8 previously classified as unexplained cursor movement. Those eight have now been **source-explained** as delegated effects (2), stack PC restoration (1) and action/selection/turn endings (5), but no path-complete approval.
- Source-backed sprite/audio/VRAM and battle bytecode constraints: [v1.7](RESOURCE_AND_BATTLE_SEMANTICS_v17.md) and [v1.8](BUILD_ASSET_AND_OPCODE_SEMANTICS_v18.md).
- All 425 FireRed maps' typed event and source-to-generated data were compiled by the original pinned mapjson translator. All **nine** out-of-layout clone events have verified target maps and target-local object IDs; none is an invalid normal object. They intentionally represent border-crossing object templates. See [v2.0 cross-map clone compatibility contract](CLONE_CROSSMAP_SEMANTICS_v20.md).
- Unmodified mGBA C core previously compiled successfully with **173 translation units**, 3,126 compile-proven header selections and 1,403 linked object-symbol dependency edges in the headless CMake configuration.
- All 25 exact upstream source-contract checks passed, plus upstream Poryscript Go test/build.
- Exact pipeline evidence and release preservation: [permanent v1.9 GitHub Release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v1.9), later successful GitHub Actions checks [FireRed clone map audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40176887229) and [module/handler dossier run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40177421442).

## New compiler experiment

A separate original FireRed ARM/agbcc compilation experiment is running under [compiled FireRed ARM ABI workflow](../.github/workflows/compiled-firered-arm-abi.yml). It builds original source without publishing a game ROM and inspects true ELF/linker addresses and resource symbols. A clean compile alone does not prove XGBA streaming or ROM expansion.

## Required unfinished semantic work

1. Complete 14,834 individually evidenced dispositions or document narrow justified whole-file exclusion classes; none may be auto-approved from file extensions or absent keyword hits.
2. Resolve conditional C/C++ macros, generated dependencies and all source-to-binary linker bindings across classic/modern FireRed, Porymap and mGBA configurations, not just a sampled 173-unit headless mGBA build.
3. Review remaining 461 handler control/data paths, indirect callbacks, graph false positives, ownership and lifetime, load/save-state invariants and resource-table ABI widths.
4. Establish or test editor round-trip fidelity for heterogeneous maps, script pointers, borders, layers, sprite and music resources; distinguish semantic Phase 1 mapping signoff from later expansion runtime release testing.

**0/14,834 independent file dispositions approved; no actual unlimited-ROM / sidecar runtime implemented.** This report is not a project-completion declaration. All automated evidence stays source-pinned and machine-readable; unsupported or ambiguous relationships remain flagged.

# Phase 1 P0 — controller-driven FireRed save transaction observation (28 October 2026)

**Status: INSTRUMENTED EXPERIMENT / FAIL_INCOMPLETE.** This does not certify a game-initiated save or a cold-boot player-state round trip.

## Immutable sources and dependency closure

- Parent: PR #26 `1dfe0906687fbca6d0e356e7332f8940eef76981`, exact-head successful CI #40562863462. Do not rerun its native save-loader fixture evidence as new findings.
- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, agbcc `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`, mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`.
- Source owners: FireRed `src/start_menu.c` save-dialog path to `TrySavingData` in `src/save.c`; mGBA `include/mgba/core/core.h` `setKeys` and `include/mgba/internal/gba/savedata.h` `GBASavedataSize` and `dirty`; external persistent `.sav` bytes.
- New native probe uses `core->setKeys` and `core->runFrame` only. It **never** writes Flash over the host bus. It records the initial Flash snapshot, later changes, dirty flag, source-built ROM save status, screen fingerprints, and persistent file hashes before/after emulator shutdown.
- Four deterministic 2,400-frame input schedules: no-input negative control, title Continue attempts, repeated A confirmations, and menu navigation attempts. All begin with the known checksum-valid but **synthetic** slot0 fixture, not a real player save.

## Evidence and limits

The probe cannot currently prove entry into `TrySavingData`, user navigation to a playable world, or preservation of named player state across cold boot. A modified Flash image is only a **candidate** game-executed write; absent a callsite witness and second-boot payload checks, never promote it to a verified save transaction. A lack of changes is negative evidence only for the precise schedule and frame budget.

The controller run is deliberately separate from PR #24 host-driven Flash programming and PR #26 synthetic load recovery. Exact pinned upstream revisions, build commands and text-only evidence are in `.github/workflows/phase1-real-firered-mgba-rom-save.yml`.

**Next:** inspect screenshot/frame evidence to build a deterministic playable title/Continue/menu input sequence; add native `TrySavingData` entry/return witness and full save sector verification; cold-boot with new player-state markers. Then test Porymap Editor GUI save action and dirty-state propagation.

## Counting and gate

New distinct machine-indexed source files: **0** (historical 14,721/14,721; 1,000 target shortfall 1,000). Newly registered complete-file reviews: **0**. Historical analyst-prepared candidates: **113** pending authoritative register reconciliation. Independent approvals: **0**. All Phase 1 gates **FAIL_INCOMPLETE**.

## Exact-head PR #28 controller observation and next compiled callsite test

CI [#40571479967](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40571479967) **passed at exact head** `7112f70f8d403d2078046c038caeb73edfcfbffd`. Each of the four deterministic 2,400-frame controller schedules preserved the physical save SHA256 and changed **zero** Flash bytes; all retained `gSaveFileStatus=1` and `gSaveCounter=0`. This is **negative evidence for these schedules only**, not a general failure of FireRed's save mechanism. It does not establish that the title menu was successfully navigated into the overworld.

The next experiment retains all four input schedules, adds an instruction-level trace for the `menu_navigation` case from frame 181 to 2,400, and pins three actual compiled ELF entrypoints: `StartMenuSaveCallback`, `SaveDialogCB_DoSave`, `TrySavingData`. The trace uses the pinned mGBA `ARMCore` executing-PC convention (Thumb PC−4, ARM PC−8), counts entries, records first frame and the first `TrySavingData` argument, and has a fail-closed 400-million-instruction limit. It does not inject a save call or perform any host Flash write. If all counts are zero, the evidence supports only that the specific input schedule did not reach these entrypoints within the traced interval. A nonzero entry count alone does not prove successful Flash programming, sector integrity or a cold-boot player-state round trip.

Additional pinned upstream identity: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982:src/start_menu.c` Git blob `88cc377cea556d3663aa5ea5f5bd4537cb29ea72`, alongside the existing pinned `src/save.c` blob. This is a focused partial dependency trace, **not** a new complete-file analyst review. The authoritatively published main-branch gate remains `FAIL_INCOMPLETE` with zero independently approved dispositions.

## Native controller-callsite CI result and next menu-state boundary

Exact-head [CI #40580100968](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40580100968) **passed** for commit `7e9dd4264a7226586c9a6c21a021a7a9b9c40a5a`. In the `menu_navigation` schedule, pinned mGBA executed **233,121,219 individually traced instructions** after frame 180 through frame 2,400. The compiled `StartMenuSaveCallback`, `SaveDialogCB_DoSave`, and `TrySavingData` entrypoint hit counts were all **zero**. All four schedules again changed **zero** Flash bytes and did not change physical save hashes. This establishes **no observed save-dialog entry in this one scripted navigation**, not a general failure to save.

The next source-pinned trace adds `Task_TitleScreenMain`, `CB2_InitMainMenu`, `Task_ExecuteMainMenuSelection`, `CB2_ReturnToField`, and `CB2_ContinueSavedGame` as additional compiled ELF entrypoints. These distinguish title-screen navigation, main-menu selection and actual field entry, without guessing from screen hashes. Source Git blob identities: `src/title_screen.c` `75f0e6743a2a84c906090df230bac7accb8dbe84`, `src/main_menu.c` `5cef7c46ea5dcaccbdb3698909e9fc23e7d00b9c`, `src/overworld.c` `339014da46ae8543143edc99ab72bf7496203a0d`. No claim of a playable save or cold-boot recovery is made. Zero new machine-triaged files, zero newly registered complete-file reviews, zero independently approved dispositions; all gates remain `FAIL_INCOMPLETE`.

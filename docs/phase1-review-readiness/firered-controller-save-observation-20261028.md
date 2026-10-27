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

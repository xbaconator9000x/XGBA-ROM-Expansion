# Phase 1 P0 — FireRed Trainer Tower authored map topology and saved progress (26 October 2026)

**Verdict: FAIL_INCOMPLETE. Independent whole-file approvals: 0/14,834.** This is an exact-pinned source-level topology/dispatch dependency map, not a proof that any particular battle can be skipped, that malformed state is reachable, or that compiled ROM/editor/emulator behavior is safe.

## Source identity and reproducibility

The checker [`tools/phase1_firered_tower_authored_topology.py`](../tools/phase1_firered_tower_authored_topology.py) requires the immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` checkout and validates **17 exact Git blobs**: eight `TrainerTower_{1..8}F/map.json` files, the lobby/roof/elevator map JSON files, lobby/elevator script files, shared Trainer Tower script and macro definitions, `src/trainer_tower.c`, and the Trainer Tower constants header. It emits an 8-row, source-identified manifest and fails closed on **seven** targeted mutations: stair destination, battle-trigger script, elevator selection, saved-floor increment, battle-trigger coordinate, first-floor trigger elevation, and stair coordinate.

## Verified authored topology

- **Eight floor map headers** declare `LAYOUT_TRAINER_TOWER_1F` through `LAYOUT_TRAINER_TOWER_8F`. Each has an upward warp (next floor, or roof from 8F) at `(15,6,3)` and downward warp (previous floor, or lobby from 1F) at `(4,6,3)`. Floors **2–8** additionally have a warp to the elevator at `(13,5,0)`; 1F does not. The checker now pins these source coordinates/elevations, not only destination labels.
- **Twenty-four authored floor coordinate triggers** are present: each floor has a single-battle trigger gated by `VAR_TEMP_E == 0` and two double-battle triggers gated by `VAR_TEMP_F == 0`. The source-pinned trigger positions `(x,y,elevation)` are single `(10,13,3)`, double-top `(9,12,3)` and double-bottom `(9,13,3)` on floors 2–8. **Floor 1's double-top trigger uniquely uses elevation 0**, rather than 3. The checker now pins these coordinates/elevations and preserves them in the JSON evidence manifest. This is the map-data trigger census, not a guarantee all are executable.
- The lobby has warps to 1F, the exterior and the elevator. The roof has warps to 8F and the elevator. The elevator map declares a **dynamic return warp**.
- The inspected elevator selection script's **roof** branch goes straight to the close-menu label, without issuing a warp. Its **lobby** branch sets a dynamic lobby warp and contains an explicit lobby warp. This is an authored-script fact, not a complete engine/UI reachability proof.

## Cross-boundary saved-progress chain

The lobby entry script copies the selected challenge to `VAR_0x8005` and calls `ttower_startchallenge`; the pinned C start function resets saved `TRAINER_TOWER.floorsCleared` to zero. The shared battle script routes the recognized win result to `TrainerTower_EventScript_WonBattle`, then routes the single/double/knockout completion paths to the one `TrainerTower_EventScript_SetFloorCleared` label. That label invokes `ttower_clearedfloor`, which dispatches the C `TrainerTowerAddFloorCleared` increment. The shared floor-entry script also queries `ttower_isfloorcleared` and sets the single/double trigger-disabling variables on its already-cleared branch.

The C battle builder uses **saved `floorsCleared`**, rather than the map-layout-derived `floorIdx`, as the first dimension of all three eight-row Pokémon-selection tables. The normal authored map chain has eight floor destinations and a roof destination; however, **authored topology alone cannot prove `floorsCleared < 8` at every battle entry**. It does not establish whether repeat entry, malformed saves, alternate callbacks, unexpected battle outcomes, or scripts outside the inspected chain can violate the invariant. The separate `VAR_TEMP_1` opponent-index obligation remains open.

## Authoring / runtime interoperability significance

This dependency crosses **map JSON authoring → map/script assembly → runtime variable and table consumers**. Any XGBA-compatible editor or format extension must preserve the authored warp graph, coordinate trigger gates, dynamic elevator warp semantics, shared script dispatch and saved-progress contract. Reconstructing only map tiles or collision cannot establish behavioral round-trip equivalence. The manifest now includes per-floor `trigger_positions` and `warp_positions`, giving future Porymap/Poryscript/editor round-trip tests a coordinate/elevation-sensitive pinned reference. **No editor round trip or compiled/emulator test is claimed here**.

## Unresolved proof gates

1. Establish compiled map-header/script inclusion and evaluate all battle-outcome/default fallthrough and repeat-entry paths; do not infer all-path bounds from authored floor count.
2. Prove or refute saved `floorsCleared` and `VAR_TEMP_1` constraints on every battle-entry path, including save continuation and elevator transitions.
3. Execute controlled compiled/runtime tests and editor round trips against pinned assets.
4. Obtain independent whole-file semantic dispositions and complete the broader Phase 1 compiler/linker, emulator, save/asset and interoperability gates.

**Coordinate/elevation checkpoint:** At the source-check commits `ac8d096d` and `d4641bf9`, the audit gained three additional fail-closed mutation fixtures (seven total) and a coordinate/elevation-sensitive manifest. This specifically closes a checker blind spot: previously, moving a battle trigger or stair warp without changing its script/destination could pass. The first-floor upper double trigger's elevation-0 exception is pinned separately. **This is source-only and introduces no Phase 2 code or independent approvals.** Exact-head CI status must be checked before describing this revised checker as CI-verified.

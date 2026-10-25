# Phase 1 P0 — collision/elevation semantics differ between editor and runtime tile-writing APIs

**26 October 2026. Source-pinned semantic interpretation; independent review and compiled ROM execution still pending.** Cross-source contract IDs `PMAP-COLLISION-001` to `PMAP-COLLISION-005`.

### Pinned evidence

| Producer/consumer | Commit | Git blob SHA | Lines |
| --- | --- | --- | --- |
| Porymap `src/core/maplayout.cpp` | `26b919d7ff4b54152de010abd5bf344af2ebe116` | `44616ab6c9c3ea9b04eff011586b7ec29183588f` | 141–154 |
| FireRed `include/global.fieldmap.h` | `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` | `e2828ec0cb1439718e830fbef4366770b3b77b1c` | 4–14 |
| FireRed `src/fieldmap.c` | same FireRed pin | `41567772299000ba5855419e5c39ad9373a34c20` | 401–427 |
| FireRed `src/scrcmd.c` | same FireRed pin | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` | 2103–2118 |

### Critical semantic difference

Under the native packed grid masks (ID: `0x03FF`; collision: `0x0C00`; elevation: `0xF000`), these operations are **not equivalent**:

| Operation | Metatile ID | Collision | Elevation |
| --- | --- | --- | --- |
| Porymap `Layout::setMetatileId` | Set requested ID using `Block` constructor | **Preserves previous value** | **Preserves previous value** |
| FireRed `MapGridSetMetatileIdAt` | Replaces with bits from supplied `metatile` | **Replaces collision with supplied word's collision bits** | **Preserves previous elevation** |
| FireRed `MapGridSetMetatileEntryAt` | Replaces raw 16-bit word | **Replaces** | **Replaces** |
| FireRed `MapGridSetMetatileImpassabilityAt` | Preserves | Sets **all two collision bits to 1** for impassable, clears both for passable | Preserves |
| FireRed script `ScrCmd_setmetatile` | Replaces through `MapGridSetMetatileIdAt` | Explicitly sets all collision bits to 1 if `isImpassable` is nonzero; otherwise passes metatile's bits | Preserves |

**Example:** Existing cell `metatile ID=9, collision=2, elevation=5` is raw `0x5809`. Changing its metatile ID to 10 via Porymap `setMetatileId` produces `0x580A`. Doing the seemingly equivalent runtime `MapGridSetMetatileIdAt(x,y,10)` produces `0x500A`: **collision goes from 2 to 0**. A script call with `isImpassable=1` instead produces `0x5C0A`: collision becomes **3**. All retain elevation 5. These results are arithmetic consequences of pinned source expressions; no emulator runtime test is claimed.

Consequences:
1. Do not collapse editor tile edits and runtime script tile writes into a single generic `setMetatile` resource operation.
2. Distinguish the **render layer type**, which is stored separately in 32-bit metatile attribute bits 29–30, from the packed 16-bit grid collision/elevation fields.
3. An editor/exporter must attach per-operation overwrite/preserve semantics; importing an altered native map script or applying a runtime patch cannot use the editor's preserve-collision rule.
4. Live script changes to map grid cells and the authored project map are distinct state layers; preserve source/collision provenance before merging compiled ROM edits.
5. Unknown or custom-configured masks require compile-source verification and fail-closed conversion; these native expressions are only valid for the pinned default ABI.

### Required review/tests

- Verify source expressions with exact pinned blobs and produce machine evidence for every operation role.
- Test all 65,536 packed cell words against the three replacement formulas; include collision values 0–3, elevation 0–15, out-of-bounds coordinates and script `isImpassable` branches.
- Confirm runtime `MapGridSetMetatileIdAt` state persistence, map reload, door/warp events and saved `mapView` behaviour in an actual compiled FireRed emulator.
- Cross-reference generated mapjson, Porymap configured block masks and Poryscript opcode assembly before any stable extension plugin.
- Do not mark a source file independently approved on the strength of this derived contract alone.

**Gate remains `FAIL_INCOMPLETE`; XGBA runtime does not yet exist.**

# Phase 1 P0 — FireRed saved map-view scan crosses its declared array boundary

**27 October 2026 · EXACT-PINNED SOURCE + SYNTHETIC MODEL · NOT APPROVED.** Source: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This is a new dependency-connected save/fieldmap investigation, **not** a complete-file review of `src/fieldmap.c` or a ROM/emulator failure claim. Phase 1 remains **FAIL_INCOMPLETE**; independent approvals **0/14,834**.

## Source identities and dependency closure

| File | Exact Git blob SHA-1 | Relevant lines / role |
| --- | --- | --- |
| `include/global.h` | `77155b09014aa854fcf87260e6ad2969e222da53` | 327–359, `SaveBlock2` layout and following fields |
| `include/fieldmap.h` | `639e329a9a0f721abd7e40001228859cb9466005` | 6–23, virtual-map and view dimensions |
| `src/fieldmap.c` | `41567772299000ba5855419e5c39ad9373a34c20` | 17–20 map buffer, 90–126 initialization, 452–516 save/reload, 518–571 camera-shift copy, 660–680 transition |
| `Makefile` | `8b454dbd18eb0069fa5851d788697190890a5b37` | 78–93, passes `-DMODERN=$(MODERN)` to the C preprocessor |
| `include/config.h` | `db131b2717ab739e62e41c5054a798f045c0631d` | 65–74, automatically defines `UBFIX` and `BUGFIX` when `MODERN` is true |

**Producer:** `SaveMapView` copies the player's `MAP_OFFSET_W × MAP_OFFSET_H = 15 × 14 = 210` metatile halfwords from `gBackupMapData` into `gSaveBlock2Ptr->mapView` (fieldmap.c:452–466). **Native storage:** `SaveBlock2.mapView` is exactly `u16[0x100]` = **256 halfwords**, at offsets **0x898–0xA97** (global.h:352). The 46 remaining halfwords are not written by this producer; `ClearSavedMapView` separately clears the entire 256-halfword array (fieldmap.c:489–492).

**Reader and conditional:** `SavedMapViewIsEmpty` (fieldmap.c:469–487) performs a bitwise-OR emptiness scan. Without `UBFIX`, it reads **0x200 = 512 halfwords**, twice the declared array length. With `UBFIX`, it uses `NELEMS(gSaveBlock2Ptr->mapView)`, i.e. **256 halfwords**. The non-`UBFIX` scan therefore crosses **256 halfwords / 512 bytes** past the end of the map-view array, through offsets **0xA98–0xC97** within the surrounding `SaveBlock2` object. It overlaps the declared `linkBattleRecords`, `berryCrush`, `pokeJump`, `berryPick` fields and part of `filler_B20` (global.h:353–357). This is **out-of-bounds relative to the C array**, even though the address range is within the enclosing struct's declared byte extent.

**Consumer:** `InitMapFromSavedGame` initializes the virtual map then calls `LoadSavedMapView` (fieldmap.c:96–100). If the scan reports nonempty, `LoadSavedMapView` copies the 210 halfwords back to `gBackupMapData` and clears the saved array (494–515). A camera-transition path calls `SaveMapView` and then loads the next map (660–680); `MoveMapViewToBackup` uses the saved window and clears it (518–571). These paths are **not interchangeable with persistent save-sector writes**; additional save lifecycle tracing is required.

## SAVIEW-001 — compiler mode selects different source-level scan bounds

`include/global.h:4` includes `config.h`, and `include/config.h:65–74` **forces `UBFIX` when `MODERN` is nonzero**. The Makefile passes `-DMODERN=$(MODERN)` (Makefile:79); the normal original-compatible mode has `MODERN=0`, whereas the modern build uses `MODERN=1`. Thus **the modern configuration selects the 256-halfword corrected scan at source level**, while the original-compatible configuration does not receive that automatic definition and selects the 512-halfword legacy scan unless an external override defines `UBFIX`. This is a concrete **build-variant semantic difference**, not merely a hypothetical compile flag. Actual preprocessed/compiled output and runtime observations remain to be captured.

## SAVIEW-002 — a neighboring field can change the legacy emptiness result

The synthetic halfword model in [`tools/verify_firered_mapview_save_boundary.py`](../tools/verify_firered_mapview_save_boundary.py) sets all 256 map-view halfwords to zero and the immediately following halfword to one. The **256-word `UBFIX` scan returns empty**, whereas the **512-word legacy scan returns nonempty**. This demonstrates a possible **data-dependent branch difference** under a controlled model; it does **not** establish that the corresponding native saved field is nonzero in a reachable stock-game state, or that an actual ROM reads/overwrites invalid data. The pinned source itself labels the extended loop a bug (fieldmap.c:475).

A separate condition remains: `SaveMapView` writes only 210 of the 256 map-view words, so whether the other 46 words are zero depends on the surrounding clear/reset lifecycle. The corrected `UBFIX` scan is in bounds but is not, by itself, a proof that the 46-word tail is always zero. Preserve the distinction between **array-boundary safety**, **semantic emptiness**, and **camera/field reload behaviour**.

## Reproducible fail-closed witness

Run `python3 tools/verify_firered_mapview_save_boundary.py --self-test` for synthetic controls. In a checkout of the **exact** FireRed pin, run `python3 tools/verify_firered_mapview_save_boundary.py --root upstream/pokefirered` to require the pinned HEAD, verify the three Git blob identities and the producer/reader/consumer source anchors, and emit `audit-output/fieldmap_save_boundary.json`. Missing anchors or changed source identities fail closed. The synthetic model is **not** compiled GBA code, a save-file test, or an emulator run.

## Remaining gates

1. **Source configuration now resolved:** modern `MODERN=1` automatically defines `UBFIX`; original-compatible `MODERN=0` does not. Capture the actual original, revision10 and modern preprocessed `SavedMapViewIsEmpty` and native object disassembly to verify those selected paths and detect any external build overrides.
2. Trace `SaveBlock2` initialization, save-sector persistence, camera transition and quest-log reload to establish whether neighboring fields can be nonzero while `mapView` is empty. Do not equate synthetic model reachability with gameplay reachability.
3. Verify the `MAP_OFFSET_W × MAP_OFFSET_H` buffer window and player-coordinate preconditions under map boundaries and connections. This source trace does not certify map-size, offset or pointer bounds.
4. Compare original agbcc and modern builds, then run controlled save/reload and camera-transition scenarios under mGBA with explicit save snapshots and register/memory evidence.
5. Obtain independent complete-file review of each source file and its dependencies before granting any approval. **No new whole-file candidate or signoff is claimed by this dossier.**

**Disposition: source-level cross-array scan and synthetic branch divergence established; native/runtime reachability and compiler/save/editor compatibility remain OPEN. Phase 1 FAIL_INCOMPLETE.**

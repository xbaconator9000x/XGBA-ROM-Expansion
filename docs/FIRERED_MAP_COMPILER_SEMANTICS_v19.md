# Phase 1 v1.9 — compiled FireRed map authoring semantics

**Status:** native source-to-assembler compilation **PASS**. This verifies authored maps and explicit typed events, not recovery of authoring structures from arbitrary binary ROMs.

## Pinned source and compiler

- [FireRed pinned repository](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982), SHA `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- [Original mapjson implementation](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.cpp), SHA `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5`
- [Original rules for generation and dependencies](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/map_data_rules.mk), SHA `b32b85a91d9460642345ca983c37d165e820741f`
- [Passing GitHub run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40174716437); use artifact `xgba-phase1-all-425-maps-semantics`

A real pinned `g++ -std=c++11` build of the original mapjson tool generated all map headers, connections, events, layout tables and global event constants.

## Verified map topology, geometry and event representation

| Category | Verified source volume |
| --- | ---: |
| Map groups | 43 |
| Maps successfully compiled | 425 |
| Layout table slots | 383 (365 populated, 18 empty) |
| Object events | 1,648 |
| Warp events | 1,294 |
| Coordinate events | 228 |
| Background events | 702 |
| **All typed events** | **3,872** |
| Generated assembler/header outputs | 1,284 |
| Genuine generated-event count mismatches | 0 |
| Genuine layout byte/dimension mismatches | 0 |

### Important source-compatible exceptions

**28 maps with zero-dimension borders and eight-byte border blobs.** The source declares `border_width=0` and `border_height=0` while preserving a four-tile `border.bin`. This is *not* a file corruption to clean up. The compiler accepts those entries and the eight bytes are part of source provenance. They must be retained through edits and future rebuilds; their runtime display impact is determined by zero declared border dimensions.

**19 intentional `MAP_DYNAMIC` warp targets.** These are dynamic destinations, **not missing maps**. Do not replace them with a fixed map or treat them as broken links.

**9 object events outside their declared map geometry.** Negative coordinates and out-of-bounds objects appear in original source, including authored positions in Celadon City, Route 7 and Route 21 North. A source-preserving editor **must not silently clamp or delete them**. An optional visibility warning is safer than mutating data.

## Source/compiled representation contract

[mapjson.cpp:212–352](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.cpp#L212-L352) emits four typed event arrays: `object_event`/`clone_event`, `warp_def`, `coord_event`/`coord_weather_event`, and `bg_sign_event`/`bg_hidden_item_event`/`bg_secret_base_event`. It combines references through `map_events`. [mapjson.cpp:122–183](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.cpp#L122-L183) generates the map header with pointers to the layout, map events, scripts and connections; shared events and scripts are explicit references.

[mapjson.cpp:590–648](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.cpp#L590-L648) writes layout dimensions, compressed/compiled file pointer targets, tileset references and border dimensions. Layout `map.bin` and `border.bin` are **two-byte block arrays** whose lengths were validated against occupied geometry, with the explicitly separated zero-border exceptions.

### Mandatory behavior for XGBA-aware editors and tools

1. Never flatten object, warp, coordinate and background events into merely visible tiles.
2. Preserve source map IDs, event order, `local_id` hints, event scripts, flags, elevations, map connections, dynamic warps and shared event/script references.
3. Treat `metatileId`, collision and elevation as structured metatile/block state. Derive displayed layers from tileset/metatile definitions, not a saved screenshot.
4. Preserve zero-border placeholders and out-of-bounds authored objects, with warnings rather than destructive auto-correction.
5. Treat missing authoring-only labels in a compiled ROM as an information-loss problem; do not claim a binary ROM provides all the original JSON properties.
6. For import of arbitrary ROM hacks without source JSON, present inferred/certain/unknown fields separately and preserve opaque bytes for round-trip.

## Reproduction and artifacts

Run `tools/mapjson_semantic_proof.py` via [the pinned native mapjson workflow](../.github/workflows/compiled-firered-maps.yml).

Artifact outputs include:
- `map_event_semantics.csv` — every source event with map ID, layout, exact source blob and position/script/warp semantics.
- `map_references.csv` — typed warp, connection, shared-event and shared-script graph.
- `layout_binary_verification.json` — source file hashes, dimensions and raw byte expectations.
- `generated_map_file_hashes.json` — compiled assembler/header output hashes.
- `compiled_map_includes.tar.gz` — actual generated assembler and header files.
- `map_semantics_summary.json` and fifty-map progress checkpoints.

**Boundary:** This is high-confidence semantic verification of 425 *source project* maps using their real compiler. It is **not** proof that unmodified third-party binary ROMs can be losslessly re-expanded into an editable source-object scene. Phase 1 full-file semantic gate remains `FAIL_INCOMPLETE`.

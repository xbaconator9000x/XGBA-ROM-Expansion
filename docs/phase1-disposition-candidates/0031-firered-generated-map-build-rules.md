# Phase 1 whole-file analyst candidate — FireRed generated map-data build rules

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, exact path `map_data_rules.mk`, verified Git blob `b32b85a91d9460642345ca983c37d165e820741f`. [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/map_data_rules.mk).

## Whole-file authored rule inventory
- `MAPS_DIR` and `LAYOUTS_DIR` derive from `DATA_ASM_SUBDIR`; output directories point to those same trees; `INCLUDECONSTS_OUTDIR` is `include/constants`.
- Three **generated** C headers are appended to `AUTO_GEN_TARGETS`: `map_groups.h`, `layouts.h`, and `map_event_ids.h`. They are generated products, not guaranteed tracked source blobs. In particular, `include/constants/event_objects.h` includes `constants/map_event_ids.h`, which is **absent as a tracked file at the pinned commit** and is produced by the rule below. The absence of a Git blob is not a broken include or missing semantic coverage of a tracked file.
- `MAP_DIRS` enumerates `*/map.json` directories under `MAPS_DIR`; `MAP_CONNECTIONS`, `MAP_EVENTS`, `MAP_HEADERS` and `MAP_JSONS` project those directory names to generated includes and JSON source paths. This wildcard-derived inventory can change with map source files.
- `$(DATA_ASM_BUILDDIR)/maps.o` depends on the map assembler source, layout includes/tables, map group/header/connection includes and each map's connection/header include. Its recipe pipes `PREPROC`, `CPP`, `PREPROC -ie` and `AS`, including `charmap.txt`. `map_events.o` similarly depends on map events source, aggregate events include and each per-map events include.
- Each per-map `header.inc`, `events.inc` and `connections.inc` is generated from that map's `map.json` by `$(MAPJSON) map firered`, with `layouts.json` also passed.
- Aggregate `connections.inc`, `groups.inc`, `events.inc`, `headers.inc` and generated `map_groups.h` depend on `map_groups.json` and are produced by `$(MAPJSON) groups firered`.
- Generated `layouts.inc`, `layouts_table.inc` and `layouts.h` depend on `layouts.json` and are produced by `$(MAPJSON) layouts firered`.
- `include/constants/map_event_ids.h` depends on **all** discovered `MAP_JSONS` and is generated with `$(MAPJSON) event_constants firered $^`; the second recipe line prints an abbreviated command for logs.

## Semantic map and expansion implications
The build graph explicitly separates authored JSON, generated assembler includes, generated C constants and final object files. Map-event local IDs and map group/layout identities can change when JSON changes; a ROM-expansion source map must preserve generated-artifact provenance and source dependencies rather than require a tracked Git blob for `map_event_ids.h`. A compatibility layer cannot safely treat generated constants as immutable across edits or substitute ROM extraction for authoring data. This source establishes Make dependency edges, **not** generated content determinism, race-free parallel builds, compiled addresses or runtime semantics.

## Independent review requirements
Verify Makefile inclusion and variable expansion under each supported compiler/revision variant; enumerate actual generated files from clean pinned builds; inspect mapjson command implementations, collision/overflow behaviour and output stability; check incremental rebuild after add/remove/rename of map JSON and editor round trips. The exact pinned file and Git blob were read in full; build execution and independent review are outstanding. Reviewer **none**; verdict **pending**; gate credit **0 / FAIL_INCOMPLETE**.

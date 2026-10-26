# Phase 1 whole-file analyst candidate — FireRed map assembly root

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, exact path `data/maps.s`, verified Git blob `fc88d8fc2521e92db22264bf6cf33966fda977ba`. [Pinned whole file](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/maps.s). This record covers the **entire 16-line assembly root**, not only the connection include.

## Whole-file authored directive disposition

1. **C-preprocessor constants** (lines 1–7): `constants/global.h`, `layouts.h`, `maps.h`, `region_map_sections.h`, `songs.h`, `items.h`, `weather.h`. These make generated layout/map identities and native constant names available before assembler expansion. The actual generated headers and include chains remain separate source/provenance nodes.
2. **Assembler macro and constant tables** (lines 8–9): `asm/macros.inc` and `constants/constants.inc`. The former supplies the `map` and `connection` macros from `asm/macros/map.inc`; do not mistake the C `#include` stage for the assembler `.include` stage.
3. **Section selection** (line 11): `.section .rodata`. The subsequent generated data are emitted in the active read-only-data section, subject to assembler alignment and linker placement.
4. **Generated include sequence** (lines 13–17): `data/layouts/layouts.inc`, `data/layouts/layouts_table.inc`, `data/maps/headers.inc`, `data/maps/groups.inc`, `data/maps/connections.inc`. The sequence is authored and matters to label placement and section layout. `data/maps/events.inc` is **not included here**; map-event object production is separately wired in `map_data_rules.mk` through `data/map_events.s`. No executable function bodies or direct map IDs are defined by this root itself.

## Producer → build → runtime dependencies

The pinned `map_data_rules.mk` declares `maps.o` dependencies on this root, generated layout/map includes and per-map header/connection includes; its recipe runs preprocessor, C preprocessor, preprocessor and assembler. The pinned `tools/mapjson/mapjson.cpp` produces `groups.inc`, `headers.inc` and `connections.inc` from authored `map_groups.json`, while per-map `map.json` produces each map's header and connection data. The pinned `src/overworld.c` consumes `gMapGroups[mapGroup][mapNum]`; `src/fieldmap.c` and `src/overworld.c` consume compiled map connection entries. Group/index constants and connection include placement have distinct provenance.

The [compiled pinned generator witness](../PHASE1_P0_FIRERED_MAPJSON_COMPILED_AUTHORED_ORDER_WITNESS_2026-10-27.md) establishes a debug-iterator failure in the authored connection include sorter; it also establishes that the 362 omitted maps have `connections: null` and all 63 nonempty maps retain their authored order in the optimized generated include list. That witness does **not** prove equal `maps.o` bytes. A separate controlled modern-build native object comparison is pending.

## Unresolved full-file review obligations

Independently verify all direct and transitive includes, generated-asset provenance, macro expansion and section alignment in original/modern/revision variants; compare compiled `maps.o` and linked map pointer bytes under authored and synthetic connection order; validate ROM runtime lookups and editor round trips. Source-level whole-file coverage is analyst-prepared, **not** an independent reviewer verdict. **Approval credit 0; Phase 1 FAIL_INCOMPLETE; Phase 2 not started.**

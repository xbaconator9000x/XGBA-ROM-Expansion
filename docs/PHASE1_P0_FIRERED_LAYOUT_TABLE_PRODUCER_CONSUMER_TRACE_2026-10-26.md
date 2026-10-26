# Phase 1 P0 — FireRed layout-table producer → consumer boundary (26 October 2026)

**Decision: FAIL_INCOMPLETE. Source-grounded generated-table model only. No compiled ROM, runtime execution, map-header reachability, or whole-file semantic approval is established.**

## Pinned upstream evidence

All sources are from `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

- `data/layouts/layouts.json` (Git blob `41d0eb1b5e51fa75d535b5a098bae2bd650f710d`): 383 positional entries, 18 empty placeholders, 365 named layouts, including 28 with 0×0 border dimensions.
- `tools/mapjson/mapjson.cpp` (blob `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5`, lines 589–653): `generate_layout_headers_text` skips only empty objects, emits each named layout's border dimensions as FireRed `.byte` values, and `generate_layouts_table_text` emits one table pointer per JSON entry, using `NULL` for empty placeholders. Layout constants count positions from 1, including placeholders.
- `src/overworld.c` (blob `339014da46ae8543143edc99ab72bf7496203a0d`, lines 490–496 and 978–982): `GetMapLayout` reads a saved `u16 mapLayoutId` and indexes `gMapLayouts[mapLayoutId - 1]` when nonzero; `SetCurrentMapLayout` updates that ID and reloads the pointer. No upper-bound check appears in this pinned getter.
- `src/fieldmap.c` (blob `41567772299000ba5855419e5c39ad9373a34c20`, lines 39–63): out-of-grid reads select `GetBorderBlockAt`, which takes remainder by both border dimensions.

**New semantic finding:** Under the pinned `mapjson` producer, the 28 authored 0×0 layouts are *not* omitted from the generated layout-table model. They occupy non-NULL positions. For example, `LAYOUT_LITTLEROOT_TOWN_MAYS_HOUSE_2F` is the fourth JSON/table entry, so its modeled 1-based layout ID is 4. The producer also writes zero dimension bytes into that layout's generated structure. This narrows the previous uncertainty from “authored only” to “included by the pinned generator's table-emission logic.” It does **not** prove that the generated assembly was linked into a specific ROM or that an in-game map/script selects ID 4 or any other zero-border ID.

## Reproducible fail-closed model

`tools/verify_p0_additive_source_contracts.py` now pins the two additional upstream Git blobs, checks the generator's emission/placeholder/one-based-ID semantics and runtime table indexing, models all 383 table slots, and records all 28 zero-border slot IDs in its JSON evidence. It rejects source identity or contract drift and preserves the previous 16 additive source checks and exhaustive map-cell reference. The checker change was committed in `77a5630f4a10a753bc5b59f48f9fdb92b33cace2`; its Python raw-regex escape correction was committed in `e1841c70a206edcd1ea5d210b50cb9977d2eb38a`.

The producer/consumer predicates and 383-slot/28-zero-slot model were independently checked against the pinned upstream file contents during this review. **GitHub Actions verification of the corrected checker is pending; the last confirmed passing census remains run #40250082483, which predates this new test.**

## Remaining Phase 1 obligations

Trace `data/maps/map_groups.json` and the corresponding authored map JSON layout IDs to establish actual map-header references, then verify generated assembly/linker inclusion in both compiled FireRed variants. Only after that, trace gameplay/script call sites and border-fallback coordinate domains; instrument compiled execution before claiming a reachable division by zero, negative border index, or out-of-bounds table lookup. Preserve the Phase 1 fail-closed gate and **0/14,834 independent whole-file approvals**.

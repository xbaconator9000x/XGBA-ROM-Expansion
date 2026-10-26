# Phase 1 whole-file analyst candidate — FireRed authored layout slots and intentional NULL holes

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, exact path `data/layouts/layouts.json`, verified Git blob `41d0eb1b5e51fa75d535b5a098bae2bd650f710d`. [Pinned full authored layout table](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/layouts/layouts.json). This analyst record structurally parses **all 383 layout array slots** and dispositions the complete two-field top-level schema.

## Entire authored schema and cardinality

- The only two top-level fields are `layouts_table_label="gMapLayouts"` and the `layouts` array. The latter has **383 ordered slots**, of which **365 are nonempty layout objects** and **18 are explicit empty `{}` placeholders**. The 18 holes are at **1-based positions 22, 23, 29, 38–45, 56, 58–61, 76 and 175**. They must not be compacted or renumbered without reviewing every consumer and save reference.
- Each of the **365 populated records** has exactly the same ten fields: `id`, `name`, `width`, `height`, `border_width`, `border_height`, `primary_tileset`, `secondary_tileset`, `border_filepath`, `blockdata_filepath`. All four dimensions/border dimensions are integers and all six identifiers/path fields are strings. Populated layout IDs and names are each unique (**365/365**); file path fields are also unique among populated records. The apparent 17 duplicate ID/name/path values in an unfiltered list are only the repeated missing properties of the 18 empty placeholders, not authored duplicate records.
- Populated layout width spans **1–144**, height **1–160**, border width is **0, 2 or 3**, border height **0 or 2**. Three primary tileset names occur (`gTileset_Building`, `gTileset_General`, `NULL`), and **61** secondary tileset names occur. These are authored data values; this review does not infer that all combinations are safe or that every referenced binary has been validated.

## Exact pinned generator and native consumer semantics

- `tools/mapjson/mapjson.cpp` lines 589–619 (`generate_layout_headers_text`) **skips empty objects** and emits border `.incbin`, blockdata `.incbin`, alignment, dimensions, tileset pointers and FireRed-specific border dimensions for each populated slot.
- Lines 622–636 (`generate_layouts_table_text`) emit **one pointer entry for every one of the 383 array slots**. For empty objects, `json_to_string(layout, "name", true)` returns empty and the emitted pointer becomes **`NULL`**. The generated table therefore retains holes.
- Lines 639–654 (`generate_layouts_constants_text`) use a **1-based slot counter**, incremented even for empty objects; `#define LAYOUT_… <slot>` is emitted only for populated slots. The highest populated ID position is **383**. This is a **sparse 1-based layout-ID ABI**, not a dense 365-element enumeration.
- `data/maps.s` includes generated `layouts.inc` and `layouts_table.inc` before map headers. `src/overworld.c` lines 490–496 retrieves a saved `mapLayoutId` using `gMapLayouts[mapLayoutId - 1]` after checking only that the ID is nonzero. This source function does not itself check the upper bound or NULL hole. That is a **caller/data invariant obligation**, not proof that normal game code ever supplies an invalid ID.

## Expansion/editor/save implications and remaining gates

Any expansion that repacks layouts, extends native layout-ID widths, imports map layouts from a ROM or round-trips Porymap authored projects must preserve the 18 empty positions and distinguish the 383 table slots from 365 valid layouts. Do not compress empty slots, assign consecutive IDs to populated records, or treat `NULL` tileset names as missing JSON fields. The saved map layout ID and map-header layout references require source, compiled and runtime validation before a new representation can be called compatible.

Pending gates: verify all 365 `.incbin` source binaries and dimensions against actual file lengths, tile/border encoding and Porymap model; assemble original and modern table bytes; test saved-layout hole/upper-bound handling with controlled fixtures and negative cases; independently review this complete pinned source and all downstream consumers. **No independent approval, no Phase 2 implementation, Phase 1 FAIL_INCOMPLETE.**

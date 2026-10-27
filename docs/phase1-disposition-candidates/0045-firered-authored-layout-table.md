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

## Actual pinned generator validation (passing CI #40421978391)

The [compiled pinned layout-slot witness #40421978391](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421978391) at workflow commit `b8853dd462e09f98fa20e5106aa302b7aff59881` built the unmodified `mapjson` executable and ran `layouts firered` on the original authored JSON and a separately labeled synthetic control with the 18 empty slots compacted. It verified the actual generated assembler and C header output:

- Authored input: **383 `gMapLayouts` pointer entries**, exactly **18 NULL positions** matching the pinned holes; **365 numeric `LAYOUT_*` constants** at their original **1-based slot IDs**; **730 `.incbin` directives** (border and blockdata for each populated layout).
- Synthetic hole-compacted control: **365 table pointers**, no NULL slots, **365 numeric constants**, with **344 of the 365 named layout constants assigned a different numeric ID**. This is a controlled compiler-generator observation, not a suggestion to compact holes.
- The test did not assemble the layouts into native `maps.o`, link a ROM, run an emulator, or verify save/editor behaviour. The output archive contains generated assembler/header files and a JSON report.

**Concrete compatibility conclusion:** even though only 18 placeholders are removed, compaction changes **344 layout IDs**. A ROM expansion or editor merge that collapses these holes would break numeric identity for most populated layouts in this exact pin.

## All 365 pinned binary path and size census (passing CI #40422108349)

The [pinned asset census #40422108349](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40422108349) at workflow commit `d9637a5ef2783aa36661e3ca13a617b0074ecd73` opened **all 730 referenced map/border binaries**, produced a per-layout SHA-256 manifest, and compared actual file lengths to the simple 16-bit-cell expectations:

- **365/365 blockdata binaries exist and match `width × height × 2` bytes.**
- **365/365 border binaries exist; 337/365 match `border_width × border_height × 2` bytes, and 28 differ.** This is an **observed file-size discrepancy against the simple expectation**, not a finding that the source is invalid or that the game renders incorrectly. The 28 cases require exact size/dimension and border-encoding review; a follow-up census is classifying them.
- A synthetic width+1 negative control was detected without modifying any pinned source or asset. The census does not verify metatile collision, palette, layout border wrapping, native decompression or editor rendering.

## Border-size exception classification and conditional native division obligation

The [passing detailed census #40422166952](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40422166952) resolves **all 28** border-size exceptions to the **same exact pattern**: authored `border_width=0`, `border_height=0`, a nonempty **8-byte** `border.bin` (equivalent to four 16-bit cells), versus the naive `0 × 0 × 2 = 0` expectation. There are **no other border-size mismatches**. Thus the 28 are not arbitrary truncation or corrupted-length evidence; they are a distinct zero-dimension metadata class whose meaning and reachability must be investigated.

The pinned `src/fieldmap.c` lines **39–55** defines `GetBorderBlockAt` using `xprime %= mapLayout->borderWidth` and `yprime %= mapLayout->borderHeight` **without a local zero-dimension guard**. Line 59 selects that macro when coordinates fall outside the virtual map bounds, and line 372 calls it in an out-of-bounds metatile lookup path. If a zero-dimension layout reaches that path, modulo by zero is a source-level undefined-behaviour hazard. **No actual runtime reachability, divide-by-zero crash, or compiled variant behaviour is established.** A follow-up check is tracing all 425 authored map header layout references against the 28 zero-dimension layouts to distinguish dormant source assets from normally reachable map layouts.

## Cross-check against every authored map header (passing CI #40422231819)

The [pinned all-map reference census #40422231819](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40422231819) inspected the `layout` field in **all 425 authored `map.json` files**. Those maps reference **309 distinct layout IDs**. Crucially, **none of the 28 zero-border-dimension layouts is referenced by any of the 425 authored map headers**; all 28 are unreferenced in this exact pinned map corpus. This explains why the source-level modulo-zero hazard cannot be assumed reachable through an ordinary authored map header. It does **not** rule out forced/synthetic save layout IDs, unused legacy assets, editor imports or future modifications that make such layouts reachable.

A subsequent exact-pin regression assertion now **passed** in [CI #40422282772](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40422282772): it fails closed if any authored map references an unknown layout ID or a zero-border layout. This proves the asserted invariants for the pinned input, not all possible save/runtime inputs.

## Expansion/editor/save implications and remaining gates

Any expansion that repacks layouts, extends native layout-ID widths, imports map layouts from a ROM or round-trips Porymap authored projects must preserve the 18 empty positions and distinguish the 383 table slots from 365 valid layouts. Do not compress empty slots, assign consecutive IDs to populated records, or treat `NULL` tileset names as missing JSON fields. The saved map layout ID and map-header layout references require source, compiled and runtime validation before a new representation can be called compatible.

Pending gates: verify all 365 `.incbin` source binaries and dimensions against actual file lengths, tile/border encoding and Porymap model; assemble original and modern table bytes; test saved-layout hole/upper-bound handling with controlled fixtures and negative cases; independently review this complete pinned source and all downstream consumers. **No independent approval, no Phase 2 implementation, Phase 1 FAIL_INCOMPLETE.**

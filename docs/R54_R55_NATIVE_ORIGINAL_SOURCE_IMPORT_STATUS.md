# R54–R55: original three-ROM field-map admission and 16-bit NPC graphics

> **Status:** source implementation and tests underway on draft PR #123 (13 November 2026). The original Emerald→Rocket→Heart & Soul→Emerald **Fly journey has NOT passed**. Source-only compilation, map indexes, partial graphic readers, authored fixtures, and ordinary Emerald/Flash smoke are not interchangeable with that acceptance.

## Real original engine hooks

- R54 hooks **the actual** `pret/pokeemerald` `src/overworld.c` `LoadMapInStepsLocal` case 0, after its native map fade and **before** `LoadMapFromWarp`→`LoadCurrentMapData`→`LoadObjEventTemplatesFromHeader`. The preloader uses R51 source grid, R52 version-specific layout, R50 original event templates, and R53 authenticated graphics. The real case-1 original `MoveSaveBlocks_ResetHeap` is moved to case 0 **only for an actually pending authenticated source warp**. This is not a simulated source selector.
- Original previous-map BG DMA must finish and its source-owned metatiles, palette backing and original sprite registries must be released **before** resetting the original game heap. A later second reset would invalidate the imported source image pointers. Ordinary Emerald native warps retain their original case-1 heap-reset path.
- The no-pending-Fly destination sentinel is initialised on the **actual** first original field load; GBA EWRAM is zero-cleared and `EWRAM_DATA = 0xff` alone was insufficient. The first pinned native mGBA boot exposed the bug (Littleroot not active), and this was corrected. No foreign traversal success can be claimed from fixing ordinary boot.
- R54 also gates **every 16-bit terrain and border metatile ID** against the number of *physically authored* source definitions (512/640 primary split vs sparse original tables). It rejects maps referring to undocumented slots before introducing corrupt source graphics.

## Exact private original graphics evidence

The user's authenticated **retail Pokémon Emerald** is SHA-256 `a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`. An **unpublished private-only** R54 source graphics pack was generated from it: 73 unique descriptors, 365 SHA-verified XGBA resources, and all **518/518** original Emerald maps plus borders checked against actual authored source tileset ranges with **zero** out-of-range metatiles. Example true original Littleroot 0:9: primary 512 authored metatiles; secondary **144** authored metatiles, **159** decoded secondary 4bpp tiles. Copying an imagined 512 secondary definitions would accidentally read unrelated original ROM data. Empty reserved tiles/metatiles must remain empty, never padded with authored replacements.

The **exact user-owned** Team Rocket Edition English 3.06 and Heart & Soul v2.0.6 source ROM bytes are not readable in this workspace. Their R49 original map-event, R51 original map-grid and R52 original layout source packs are available privately, but **their original full graphics have not been rendered in Emerald**. Modern source compressed tile data uses GBA LZ77 *and* pokeemerald-expansion Smol 1–6; both decoders have independent tests. The source object-sprite compression/OAM/palette installer is separate unfinished work.

## Real source NPC IDs (original private R49 2,856-map index)

| Original source ROM | Maps | Original NPC objects | Different source sprite IDs across game | Max distinct on a single original map | 16-bit IDs above 255 |
|---|---:|---:|---:|---:|---:|
| Emerald | 518 | 2,941 | 166 | 24 | 0 |
| Team Rocket Edition | 1,778 | 9,410 | 427 | 27 | 257 |
| Heart & Soul | 560 | 4,738 | 497 | 57 | 477 |
| **Total** | **2,856** | **17,089** | source-qualified, not pooled | **57** | must not truncate |

R55 introduces a source-qualified *per-map* registry of 59 **candidate** Emerald `u8` object-graphics slots 180–238, sufficient for the observed peak of 57 distinct original IDs on one source map without installing all 497 global HnS sprites simultaneously. Source original IDs `0x4000`, `0x4001`, `607` and ordinary ID `1` remain distinct by `(world,original_id)`. Native `GetObjectEventGraphicsInfo` is hooked to return only **genuinely installed, original-frame-and-palette-authenticated** graphics info. The ordinary original Emerald object-graphics path remains unchanged when no such source asset is active. The allocator and native C pointer interface are **not themselves** a sprite importer or proof of visible NPCs. Slots 180–238 are a candidate reservation: actual native player/field graphics collision and palette ownership must also be validated before enabling foreign-world loading.

## Required acceptance not yet passed

1. Use the **exact** original Rocket 3.06 and HnS 2.0.6 assets to build private SHA/CRC-backed sprite sheets, OAM/animation descriptors and palettes, with source-aware 16-bit IDs and validated GBA lifetime. Refuse unknown compressed/relocated sources.
2. Extend the original *player-selected* Emerald Fly UI to expose foreign region destinations, queue a source-qualified pending Fly only when destination assets and conditions are preflighted, and bind actual source map/game world after a real source map warp.
3. Original source scripts/quest flags/items/trainers/battles must execute safely, including original 0:9 Rocket NPC and HnS Goldenrod 0:4 object ID7. Quarantined foreign script pointers are **not** supported dialogue.
4. Native original Emerald→Rocket→HnS→Emerald Fly, authentic 240×160 original LCD frames, physical NPC interaction and cross-world game state, Flash and full emulator cold restart. No fake screenshot, surrogate source-switching, substitute dialogue or mislabeled workflow pass.
5. Larger original source maps (250/2,856 exceed current in-memory 5,600-byte R51 staging) still need bounded grid streaming. Native GBA 256KiB EWRAM ceiling remains enforced; any future RAM expansion is a separate architecture track.

No copyrighted owner ROM, extracted original asset page or proprietary original sprite image is committed to the public repo or uploaded as a public CI artifact.

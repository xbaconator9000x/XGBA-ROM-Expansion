# R50 — Original Emerald map events and real 256 KiB EWRAM integration

**13 November 2026. Status: work in draft PR #122; original cross-world Fly gameplay remains unverified.**

## Actual implementation

R50 takes the intact, source-keyed original R49 event pages and stages each selected map's object events for Emerald's original MapHeader and MapEvents engine structures. It preserves original source ID, NPC IDs, 16-bit source sprite IDs, original script-address provenance, coordinates and original object counts, with explicit mapping of source sprites into native Emerald-compatible installed sprite slots. Bad geometry, duplicated NPC IDs, missing sprite mappings, corrupted pages and source namespace mistakes fail closed. Original event scripts, foreign flags, warp destinations, coordinate callbacks and background triggers remain preserved in R49 source storage but cannot be executed as unrelated native Emerald pointers.

The hook is installed in the pinned source-built Emerald original map header/layout resolution, original A-button interaction and original Fly callback. **Actual Rocket and Heart & Soul terrain/sprites, collision, live NPC spawning and cross-world Fly arrival are not yet running through these hooks.**

## Native EWRAM overflow and correction

The first original Emerald ARM linker test failed because adding an independent 16 KiB EWRAM buffer brought the total to 271,904 bytes, overflowing real 256 KiB EWRAM by **9,760 bytes**.

The R50 correction removes the extra 16 KiB buffer and explicitly reuses the existing **single protected 16 KiB heap-tail arena**. A faded-warp phase fetches all necessary index/event pages into that borrowed arena, then deep-copies the bounded native object-event records. A later original graphics-loader phase may reuse the same arena for source-verified tiles, palettes, map grids and collisions. These two phases MUST NOT overlap or touch the live previous map; the event bridge refuses installation until both original graphics and the specific source map have been verified.

The repository memory planner now budgets these two stages as mutually exclusive. The actual source-built GBA linker and native mGBA test are required before considering this corrected design proven.

## Remaining concrete acceptance

An original-source foreign map renderer and source sprite registry must implement this paired API and genuine source-verified layout installation. The first real test is original Emerald player movement and A-button interaction with a real Rocket 3.06 Littleroot NPC at its original placement, executing that original bytecode and displaying original text. Then use actual original-game Fly departure/arrival into Heart & Soul Goldenrod, interact with an original HnS NPC, return to Emerald, Flash save, cold restart, verify state and record real LCD GIFs.

These initial witness maps are **not a reduced content scope**: all 2,856 maps, 17,089 original object records and 7,146 source warps remain in the retained 3-ROM external store. Original ROM binaries, saves, original script bytes, and derived proprietary resource pages are private; public CI uses authored event-format fixtures only.

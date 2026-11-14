# R51 — Authentic three-original-ROM map cells staged for the ORIGINAL Emerald field engine

**13 November 2026. Implemented and exact-head CI verified; original interworld Fly gameplay not yet demonstrated.**

## What really ran
1. The private original-source importer verified exact complete user-owned ROM SHA-256 values, recovered every original map group/table and emitted all **2,856 populated map grids** and **935 Heart & Soul null map holes** without renumbering or dropping a byte.
2. The source namespace is part of the key `(world<<16)|(group<<8)|original_map`, distinguishing Emerald 0:9 from Rocket 0:9. Each R51 indexed row includes original width/height, original ROM map/header/border addresses, source-data byte offset and CRC of the exact original 16-bit grid plus original eight border bytes.
3. Private verified output was **4,689,512 unmodified original terrain bytes**, 6×16KiB index pages and 287×16KiB grid pages = **293 source resources**, checked by all manifest SHA-256 hashes. No Nintendo-derived source page or ROM was uploaded to GitHub.
4. The native original Emerald bridge adds `XgbaR51PrepareOriginalSourceGeometry` (source-keyed page reads using the existing 16KiB leased heap-tail arena), deep-copies only the live map into bounded 5,600-byte EWRAM, then feeds the *same source key* and exact dimensions into the R50 authentic NPC and event adapter. `XgbaR51CommitAfterOriginalSourceGraphics` is explicitly gated on verified source primary/secondary tilesets and palettes/collision, so no unrelated Emerald art may be represented as authentic Rocket/HnS art.
5. **Full original map intake is not restricted by GBA staging limits**. Source-grid pages remain in host resources for all maps; 250 maps currently exceed the bounded guest staging/backup-camera limits. These need tile-window/chunk-stream runtime support, not silent truncation. Current guest-eligible counts: Emerald **485/518**, Rocket **1,623/1,778**, Heart & Soul **498/560**, total **2,606/2,856**.
6. New public native ASan/UBSan tests run original-format source-keyed map-grid loading, 16KiB page crossing, error injection, CRC, dimensions and collision-like original 16-bit cells. Public Python tests cover complete source page architecture, per-world ID collisions, oversized map retention, private sidecar manifest integrity and bad source/bounds refusal. Native original Emerald was compiled with R48/R49/R50/R51 hooks, booted under patched pinned mGBA, and original Flash-save smoke remained green.

## Source-compatible graphics work still required

R51 is **not** original Rocket/HnS map rendering yet. A source-compatible tileset primary/secondary graphics/palette/metatile/collision loader must be implemented and installed in original Emerald at a genuinely faded map transition. Under the current source-ROM metadata:
- Emerald's original primary and secondary tile graphics have recognisable `0x10` GBA LZ77 headers.
- The inspected Team Rocket 3.06 Littleroot tileset pointers have `0x06`/ `0x01` leading bytes despite an isCompressed-like descriptor flag; treating them as ordinary Emerald LZ77 or uncompressed 4bpp tiles without validated decoding would produce corrupt graphics.
- Heart & Soul Goldenrod's graphics pointers can be inspected as raw 4bpp art, but rendering compatibility, metatile indices/attributes, palette banks, sprite slots and engine semantics remain unproven.

**Nothing in the present R51 emulator gate executes a source-ROM-derived foreign map or a foreign NPC.** Native CI validates genuine original Emerald integration *with dormant, fail-closed foreign-map preflight*, while the private original-ROM job independently verifies original source byte preservation.

## Required next real-world acceptance

Wire source tileset/VRAM installation into Emerald's actual warp/Fly transition and original field map-header/camera lifecycle, preserve original player/party location, import original source NPC graphics, execute verified original NPC script/dialogue through actual A-button interactions, then perform Emerald→Rocket→Heart & Soul→Emerald Fly with actual saved state and cold restart. Capture actual native LCD PNGs/GIFs at each step. All R47 complete-content requirements remain binding.

This is a **substantial real-source engine integration milestone**, not the user's requested completed three-game playable Fly acceptance. The R50 draft PR #122 remains an unfinished prerequisite and R51 builds on its exact source branch; avoid merging misleading `FLY_COMPLETE` status.

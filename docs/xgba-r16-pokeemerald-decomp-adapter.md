# R16: source-built Pokémon Emerald adapter — compatibility contract

**Status:** Source-integration bootstrap, not a full Emerald external map/tileset/save port. Native integration must pass GitHub Actions before any executed-result claim.

**Upstream:** [pret/pokeemerald](https://github.com/pret/pokeemerald), pinned at `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881` (1 October 2026). Build locally using `MODERN=1`. XGBA patch generator modifies only source files in that temporary checkout and restores upstream originals even when build fails. Do not distribute the resulting ROM or copyrighted game assets.

**Emulator:** existing XGBA-enabled [mGBA](https://github.com/mgba-emu/mgba), same `fd9dc5c2cbf234365068855851107e762fc6211b` source pin and **unchanged ABI v1** as FireRed R7–R15. No new memory extension, emulator plugin, proprietary base ROM, or new sidecar dialect.

## Emerald-specific differences identified in real source

| Feature | FireRed reference | Emerald pinned source | Adapter rule |
| --- | --- | --- | --- |
| Save pointer relocation | `SetSaveBlocksPointers(void)` | `SetSaveBlocksPointers(u16 offset)` incorporates trainer-ID bytes | **Never reuse a FireRed binary save-hook offset or function signature.** |
| Heap | `HEAP_SIZE = 0x1C000` | Same 0x1C000 value | Share phase-aware budget planner, but audit Emerald's real ELF and allocator/heap scratch before reserving any tail |
| EWRAM/linker | FireRed `ld_script_modern.ld` includes explicit heap-tail linker marker | Emerald uses `ewram 0x2000000 (NOLOAD)` and distinct linker layout | Generate Emerald-specific linker symbols; never paste the FireRed linker patch unverified |
| Map layouts | `GetMapLayout`, header-by-group in overworld | Same conceptual functions; map-group IDs, tilesets, events and script tables differ | Use symbolic map identifiers and inspect Emerald's own map engine and decompression callbacks |
| Save operations | `TrySavingData`, `LoadGameSave`, game-specific structures | Same exported names; internal structures, ASLR and save lifecycle may differ | A successful FireRed Flash test **does not** certify Emerald Flash restart |
| Resident assets | EWRAM + VRAM + palette hardware | Identical real GBA hardware capacity | Reuse source-independent XGBA memory model, with per-engine existing allocations |
| ROM source identity | Hash exact built FireRed ROM | Hash exact built Emerald ROM | Bind every sidecar to its own ROM SHA-256 and fail on mismatch |

## What the R16 initial fixture does

- Insert one **C source** hook into the original `src/main.c` after `InitHeap`; no hard-coded ROM addresses.
- Compile original Emerald with `MODERN=1`, verify the emitted ARM ELF symbol is actually in 256 KiB GBA EWRAM, ensure ROM stays within 32 MiB and does **not** embed the 64-byte test resource.
- Attach existing XGBA provider to an **actual native mGBA GBA core**; Emerald itself issues a synchronous `XgbaGuestFetch("emerald.bridge")` on guest MMIO. Verify the bytes by reading actual guest EWRAM, not host-injecting a result.
- Run the **same compiled Emerald ROM** with extension enabled and disabled. Disabled MUST produce **zero provider reads**, and the original sentinel bytes remain untouched.
- Continue running Emerald's original game loop for at least 180 video frames; capture authentic native 240×160 LCD PNGs for both modes, report source identity and exact commits.

This demonstrates **runtime protocol portability and source-level game integration only**. It does not establish external Emerald tiles, maps, Pokémon, animations, battles, party saves, graphical GUI performance or arbitrary third-party ROM compatibility. Those are follow-up integration gates.

## Proposed sequence after initial bootstrap

1. Integrate the common phase-aware memory allocator and actual Emerald linker guards; inspect Emerald's save-copy scratch sizes and trainer-ID relocation.
2. Source-patch real Emerald map layouts/tilesets (e.g. Littleroot Town and an adjacent interior), strip those bytes from the built ROM, and run normal movement in original Emerald engine with sidecar-backed tiles and collision.
3. Exercise original Emerald Flash save, complete emulator termination and fresh `CB2_ContinueSavedGame` with external assets and a deliberately bad-pack refusal.
4. Generalize resource-backed asset IDs into battle sprites/animations and world map/audio; keep low-level mGBA provider, hash verification and pack manifest unchanged.
5. Build source adapters for other decomp projects (FireRed, Ruby/Sapphire, other GBA titles). Separate platform ABI from engine-specific mapping code. Never promise arbitrary binary support without known revision signatures and executed tests.

**All milestones require native CI and original evidence before the README calls them verified.**

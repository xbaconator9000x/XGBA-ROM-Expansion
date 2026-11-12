# R28 — three connected maps with two physical EWRAM resource slots

**Status: VERIFIED and MERGED — 12 November 2026.** Original Emerald native **8/8**, portable production cache tests **16/16**, all **25/25** exact-head PR workflows green at source head `1d67b287450e42392fec9063057fb0655ef92423`. [Original native run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521) · [Five original LCD frames and proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521/artifacts/13916609021) · [Merged PR #85](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/85) · [main commit `9727de7`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/9727de794cc526f80fcd30b9915c31b64c66894b).

## Specific original-game problem

R19 and R22 keep original Littleroot Town (map group 0, map 9) and Route 101 (group 0, map 16) simultaneously resident in the shared, linker-reserved **16 KiB** guest EWRAM arena. R23 and R26 prove safe *map-vs-battle* phase reuse and scoped borrowed-source leases. R27 proves that external map geometry can be larger, but the original Emerald backup grid and 16 KiB transfer maximum remain bounded.

An emulator-targeted game with three connected source maps cannot retain three complete (~6 KiB) map/tileset packs simultaneously in the unchanged 16 KiB reserve. To demonstrate safe *live world* streaming, this R28 fixture adds **Oldale Town (group 0, map 10)**, genuinely connected north of Route 101, with its original 20×20 metatile grid and border. All three use the original Petalburg secondary tileset and are carried as individually addressed external SHA-256 resources beyond 32 MiB.

## Implemented source approach

- Portable fail-closed two-slot, three-key map cache in `integration/common/xgba_map_cache.h`, compiled as original game guest C: deterministic LRU, protected current-map identity, pending/loading state, read-only lookup, serial+generation checked borrowed-source pins and busy refusals for unsafe eviction or phase reset.
- Original Emerald `XgbaR19Load` uses the cache **only in opt-in R28 fixture builds**. Existing R19–R27 two-source and battle behaviour stays unchanged when `XGBA_R28_THREE_MAPS` is absent.
- Real source-backed Oldale pack and original compiled map/border bytes are stripped from the test ROM and externally sourced using the same production mGBA device and hash-checked manifest. The native original field camera and connected-map callbacks handle movement and map-copy semantics. No host teleportation or fabricated screenshots.
- Original-game append-only proof fields record cache resident slot IDs, generation, hits, misses, evictions, refused evictions and active physical slot.
- The existing R26 scoped phase ownership still protects the shared physical memory; this does **not** claim full DMA renderer-pointer lifetimes.

## Fail-closed native acceptance

The native suite must build pinned original Emerald `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`, patched pinned mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, and exercise original D-pad transitions:

**Littleroot (0:9) → Route 101 (0:16) → Oldale (0:10) → Route 101 → Littleroot**.

Native checks compare the original game's current backup-grid cells, real guest EWRAM byte-for-byte for both currently resident resource packs, background tile VRAM, the exact original compiled game data stripped from the ROM, cache evictions/reacquisitions and 5 actual 240×160 LCD PNG frames. The disabled provider must refuse before any external resource read.

`tests/test_xgba_r28_map_cache.c` has 16 separate deterministic portable safety cases (including a 1,000-iteration churn case), but **passing portable tests is not native acceptance**.

## Scope limits

R28 is a **two-slot LRU of three original 20×20 map packs**, not proof of unbounded adjacent map fan-out, arbitrary map dimensions, generalized cross-region scripts, arbitrary renderer DMA source safety, full background resource pinning, stock-emulator support or original physical GBA compatibility. A native failure must be recorded and fixed rather than represented as success.

## CI and evidence

- [R28 exact-source portable and native CI workflow](../.github/workflows/xgba-r28-three-map-cache.yml).
- [R28 native test source](../tests/test_xgba_r28_emerald_three_maps.py) and [emulator original-game verifier](../integration/mgba/xgba_r28_three_maps.h).
- **Executed exact-source native acceptance: 8/8 passed** after 100.449 seconds, with original 9→16→10→16→9 D-pad sequence, 5 actual 240×160 LCD PNGs, SHA-verified external resources and two simultaneous guest-resident packs in distinct physical slots. See [run #43159185521](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521) and [artifact #13916609021](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521/artifacts/13916609021).
- **Fixed initial acceptance mismatch:** the original draft accidentally reserved only 12,488 bytes of actual compressed/source payload instead of the promised 16,384-byte physical arena. Commit [`1d67b28`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/1d67b287450e42392fec9063057fb0655ef92423) creates two fixed 8,192-byte slots, independently bounds each pack and retains R19–R27 layouts when R28 is disabled. The first 7/8 native run was *not* misrepresented as a pass.
- Strict portable production map-cache lifetime cases **16/16 green**; all **25/25 original-game, regression and privacy workflow suites** succeeded at the final PR head. Genuine LCD artifacts are currently held by GitHub Actions with limited retention and should later be permanently archived with SHA-256 manifests; no commercial ROM or save is published.

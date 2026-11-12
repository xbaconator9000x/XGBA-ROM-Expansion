# R30 — original Emerald four connected externally backed maps, two real EWRAM slots

**VERIFIED / MERGED · 12 November 2026.** Original pinned source-built Emerald **9/9 native tests passed**; **27/27 exact-head PR workflows** passed at `2b5aa97433b190d05af6a6e91c55835e7853499a`. [Native run #43162597194](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43162597194) · [Seven actual LCD PNG frames and machine-readable proof, artifact #13918726949](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43162597194/artifacts/13918726949) · [Merged PR #88](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/88) · [main commit `5ea935d`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/5ea935ddee11c72c51ed2d10c4d7e379d986c550).

## Actual original-game achievement

Using the original Pokémon Emerald `pret/pokeemerald` pin `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881` running in pinned patched native mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, the game physically traverses by ordinary original **D-pad and original connected-map callbacks**:

1. Littleroot Town (group 0, map 9, 20×20)
2. Route 101 (group 0, map 16, 20×20)
3. Oldale Town (group 0, map 10, 20×20)
4. Route 102 (group 0, map 17, **50×20**)
5. Oldale Town (reacquired)
6. Route 101 (reacquired)
7. Littleroot Town (reacquired)

All four are independently addressed, external SHA-256 validated source packs beyond the 32 MiB ROM window. The original game source ROM has its compiled map grids and borders stripped in this native fixture; these cannot silently fall back to ROM copies. Each resource includes the complete Petalburg secondary tileset and fits a single **8,192-byte physical slot**. The actual guest EWRAM reservation is **16,384 bytes**, with exactly **two** simultaneously resident resource slots; four resources are never retained simultaneously.

## What original native execution verifies

- Original Emerald's actual memory, map headers, cameras, map transition callbacks and collision, without host-map teleportation or fabricated LCD screenshots.
- Independent sidecar file comparisons against byte-for-byte contents of the two currently resident original guest EWRAM source packs; original source identifiers and full resource pack hashes.
- Seven complete original Emerald backup grids (including the original 50×20 Route102 layout), checked against externally sourced original map bytes, plus original secondary tileset/BG VRAM evidence.
- Exact resident-slot identity, deterministic cache misses/evictions and original-game reacquisition on returning across the map chain.
- True **seven 240×160 mGBA LCD PNGs**, captured from original gameplay; no ROM, save, copyrighted raw game pack or sidecar file included in the evidence artifact.
- Disabled external provider runs without any successful or failed resource data fetch (fail-closed).

Native execution used the opt-in `XGBA_R30_FOUR_MAPS` guest fixture on top of the R28 flag, retaining R19–R29 source/portable behaviour when that flag is absent. Its original Oldale west gate is opened as a **test-only original-game story-state adjustment**, as R19 similarly bypassed compulsory Route101 plot sequencing; this is not an end-user universal patch.

The first genuine original-Emerald run **failed**, correctly, after reaching Route102 and returning to Oldale: the navigation harness tried to walk straight south from Oldale's **western entrance**. Native diagnostic was `R28_NAV_STALL wanted=16 got=10 x=0 y=11`. The fix introduced a bounded collision-aware route from Oldale's actual map grid between the west and south connections. This completed all seven original D-pad destinations on the next exact-head run. Failed runs must not be represented as acceptance.

## What is not yet achieved

R30 does **not** demonstrate arbitrary multiple simultaneous neighbor layout pointers, unrestricted map dimensions, arbitrary map/tileset packs larger than 8 KiB, chunked transfers and cross-region asset catalogs, general scripted quest integration, original GBA hardware compatibility, an unmodified emulator or automatic patching of arbitrary vanilla or already-modified ROMs. The 16 KiB guest EWRAM bound remains real. A nine-region mega-hack remains a **future application** of an expanded and generalized system, not a completed feature.

## Reproducibility

- [Native exact-head CI workflow](../.github/workflows/xgba-r30-four-original-maps.yml)
- [Actual source-built original guest map cache integration](../integration/emerald/xgba_r19_connected_maps.inc)
- [Genuine native patched mGBA verifier + original collision-aware Oldale pathfinder](../integration/mgba/xgba_r30_four_maps.h)
- [Native nine-case acceptance and evidence JSON source](../tests/test_xgba_r30_emerald_four_maps.py)
- [Original ROM source material extraction/stripping/manifest creation](../tests/test_xgba_r17_emerald_external_map.py)
- [Seven screenshot/proof artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43162597194/artifacts/13918726949) (GitHub Actions retention is time-limited; future permanent archival should retain exact PNG bytes/SHA-256, not generate replacement images).

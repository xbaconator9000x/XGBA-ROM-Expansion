# R35 — Binary-extracted ROM maps in the multi-source XGBA resource pool

**VERIFIED / MERGED · 12 November 2026** — [PR #98](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/98) · [merged source `07a2c32`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/07a2c32d947fb80eb4550e575f87ac29b357026f). Four exact-head GitHub Actions runs passed including **12/12 three-world synthetic tests**, **11,557 real Emerald source files + 504 synthetic binary resource segments = 12,061 combined addressable resources**, and native FireRed/Emerald non-regressions. Private exact user-provided Team Rocket Edition 3.06 ROM verification confirmed **1,778 original map identities**, **16,854 matching source-ROM segments** and **66 sharded packs**, without changing original ROM bytes. [Public full-source + binary-world integration CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43197146129) · [Counts-only artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43197146129/artifacts/13933377463). No user's copyrighted ROM or extracted bytes were committed or uploaded to public CI.


**Scope:** Real binary-extracted map resources should be addressable alongside
source-backed game resources without source map-ID rewriting, untrusted code
execution or mandatory full-game memory residency.

R34 demonstrated structure-validated extraction of map headers, layouts,
grids, event tables, NPC records, warps and tileset descriptors from an
Emerald-family binary; R33 demonstrated whole-source sharded resource
lookup for source-built game trees. The index formats were incompatible.

R35 adds **tools/xgba_mixed_world_pool.py**:
- **BinaryMapPool** mounts the complete R34 binary map index, checks every
  referenced manifest against its original-ROM source identity, checks the
  full shard SHA-256 with bounded reads, refuses missing and orphaned
  records, and validates every map's original header/layout/event/connection
  pointers against the exported segment positions. Its source-specific
  group/map identity and script pointers are retained unchanged.
- **MixedWorldPool** mounts both existing R33 full-source corpus indexes and
  R34 binary indexes behind a single source-aware handle. Source labels
  such as `emerald`, `rocket` and `heartsoul` remain distinct, so
  group 0/map 0 may exist in all three games without collision.
- **read_window** checks a complete resource SHA-256 before returning up to
  16 KiB, and **stage** atomically replaces verified bounded host buffers.
  The registry enforces one combined host staging budget across sources.
- **verify_original_rom** optionally rechecks every extracted resource
  against the exact original binary ROM (read-only), first verifying that
  the overall ROM SHA-256 matches the original extraction identity.

No Nintendo or fan-project binary asset is included in the repository.
The public CI uses synthetic binary fixtures and complete original
Emerald *source* produced locally in CI; it publishes aggregate counts
only. Private user-provided ROM tests must remain private.

## What is NOT yet implemented

The resolver is **host-side only**. It does not yet install a native
mGBA provider adapter for arbitrary R34 segment identities. It also
does not decode unknown-length scripts, integrate new Pokémon/moves/abilities
or battle logic, create Fly transitions, or persist cross-game events and
inventory. A resource being addressable and checksum-valid is NOT proof
it runs natively inside Emerald. The GBA guest's RAM is unchanged.

## Tests and links

- [Mixed pool code](../tools/xgba_mixed_world_pool.py)
- [Synthetic source + binary world tests](../tests/test_xgba_r35_mixed_pool.py)
- [Whole original Emerald + synthetic binary CI](../.github/workflows/xgba-r35-mixed-world-pool.yml)
- [Binary map extractor](../tools/xgba_r34_binary_maps.py)
- [Source-aware source corpus](../tools/xgba_corpus_pool.py)

Evidence and limitations will be updated only after exact-head CI success.

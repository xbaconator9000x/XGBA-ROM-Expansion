# R29 — many logical resource identities, unchanged bounded physical cache

**Status: PORTABLE VERIFIED and MERGED — 12 November 2026.** Original production C11 cache passed **10,003 loads / 10,001 evictions** in the two-slot fixed-memory structure; source regressions and original Emerald R28 were green in **8/8** exact-head PR workflow suites. [Merged PR #87](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/87) · [Portable source CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43160550764) · [merge commit `d58d245`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/d58d245204a2359c3973dbcf7a48b444069be84e).

R28 verified three distinct real Emerald map packs in two **8 KiB** slots within an actual reserved **16 KiB EWRAM** region. Its portable cache previously hard-coded three logical identities, conflating demonstration-fixture scope with architecture.

R29 makes the core cache accept any `uint32_t` resource ID other than the reserved `UINT32_MAX` sentinel. A GBA build may restrict keys by defining `XGBA_MAP_CACHE_KEYS`; the original R28 guest fixture and its negative tests still explicitly use three keys and preserve their previously verified source ABI, slot count, memory footprint, and native behaviours. The cache has **no array indexed by resource ID**, so its RAM overhead stays constant as the logical keyspace grows.

The R29 portable C11 test drives **10,003 logical resource loads**, **10,001 evictions**, sparse high-value IDs and invalid-sentinel rejection, while requiring two physical slots, unchanged live-map protection, refused pinned eviction, stale-release rejection and a compile-time **256-byte upper bound on the cache metadata**. The original R28 16-case portable suite and native original Emerald regression remain mandatory.

**Not established by R29 alone:** original-game dynamic map catalogs or four-map traversal, external resources exceeding one 16 KiB transfer, arbitrary scripted fan-out, editor adapters, physical GBA/stock mGBA support, or unlimited RAM. **R30 later independently verified four actual original Emerald map packs** over two 8 KiB slots, including a 50×20 real Route102 map ([R30 native proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43162597194)); that separate fixture does not prove unbounded arbitrary maps.

[Portable R29 workflow](../.github/workflows/xgba-r29-logical-cache.yml) · [source test](../tests/test_xgba_r29_logical_cache.c) · [existing native R28 proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521).

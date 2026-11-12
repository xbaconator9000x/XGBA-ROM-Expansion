# R29 — many logical resource identities, unchanged bounded physical cache

**Status: implementation submitted for source and portable CI; this alone is not an original-game multi-region proof.**

R28 verified three distinct real Emerald map packs in two **8 KiB** slots within an actual reserved **16 KiB EWRAM** region. Its portable cache previously hard-coded three logical identities, conflating demonstration-fixture scope with architecture.

R29 makes the core cache accept any `uint32_t` resource ID other than the reserved `UINT32_MAX` sentinel. A GBA build may restrict keys by defining `XGBA_MAP_CACHE_KEYS`; the original R28 guest fixture and its negative tests still explicitly use three keys and preserve their previously verified source ABI, slot count, memory footprint, and native behaviours. The cache has **no array indexed by resource ID**, so its RAM overhead stays constant as the logical keyspace grows.

The R29 portable C11 test drives **10,003 logical resource loads**, **10,001 evictions**, sparse high-value IDs and invalid-sentinel rejection, while requiring two physical slots, unchanged live-map protection, refused pinned eviction, stale-release rejection and a compile-time **256-byte upper bound on the cache metadata**. The original R28 16-case portable suite and native original Emerald regression remain mandatory.

**Not yet established by R29:** native original Emerald traversal beyond the three current R28 source maps, dynamic map-ID to sidecar-resource mappings, external resources exceeding a single 16 KiB transfer, arbitrary on-demand scripting or editor integrations, physical GBA / stock mGBA support, or unlimited game RAM. Further integration must test a fourth real original Emerald map and generalized source-name/index resolution in the actual guest engine.

[Portable R29 workflow](../.github/workflows/xgba-r29-logical-cache.yml) · [source test](../tests/test_xgba_r29_logical_cache.c) · [existing native R28 proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43159185521).

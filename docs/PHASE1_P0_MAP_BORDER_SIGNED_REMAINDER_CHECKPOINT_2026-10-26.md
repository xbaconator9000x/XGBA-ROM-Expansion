# Phase 1 P0 — FireRed map-border signed remainder / negative-index source counterexamples (26 October 2026)

**Gate: FAIL_INCOMPLETE. No independent whole-file semantic signoff or compiled runtime proof.**

## Source-grounded observation

Pinned FireRed revision `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:
- `src/fieldmap.c`, Git blob `41567772299000ba5855419e5c39ad9373a34c20`, lines 39–59: `GetBorderBlockAt(x,y)` subtracts `MAP_OFFSET`, adds eight border widths/heights, applies **C signed remainder** (`%=`), then indexes `mapLayout->border[xprime + yprime * borderWidth]`. `GetMapGridBlockAt` calls this fallback for out-of-grid coordinates.
- `include/fieldmap.h`, Git blob `639e329a9a0f721abd7e40001228859cb9466005`, lines 17–23: `MAP_OFFSET = 7`.
- `src/fieldmap.c`, lines 401–429: the three runtime grid setters guard against coordinates outside the current `VMap` dimensions. Their write-boundary behaviour is **not** the same as the read-side border fallback.

**Bounded arithmetic counterexample, not a demonstrated game crash:** With a hypothetical positive 2×2 border and coordinates `(-10, 7)`, the macro computes `xprime = (-10 - 7 + 8*2) % 2 = -1` under C's signed remainder rule, `yprime = 0`, and a border array index of **-1**. With `(7, -10)`, the index is **-2**. By contrast `(0, 0)` yields index 3, and `(7, 7)` yields index 0. Python's nonnegative modulo for positive divisors must **not** be substituted for C signed remainder when modelling these source expressions.

These are source-level examples of potential out-of-bounds reads **if** those coordinates reach the macro and the map uses such border dimensions. This checkpoint does not establish actual game-map dimensions, reachability, execution, or an observed out-of-bounds read. It also does not establish integer-overflow behaviour for extreme coordinates.

## Reproducible regression

Commit `f6c9f0ae2870241f620f783216350799cf37dc93` extends `tools/verify_p0_additive_source_contracts.py` with `verify_map_border_coordinate_reference`. It pins both source/header Git blobs, asserts the macro/guard/fallback expressions, checks C signed-remainder arithmetic for two valid-index controls and two negative-index witnesses, and writes a separate `map_border_coordinate_reference` evidence object into the existing additive P0 JSON output. It preserves the 25 historical baseline assertions, 16 additive source assertions, and the 458,752 map-cell arithmetic comparisons.

[Post-commit census run #40247291725](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40247291725) **completed successfully** (job 121331442074). Its actual job log reports `16/16 source assertions PASS; map-cell 65536 words x 7 operations PASS; pinned border signed-remainder counterexamples PASS`, ten curated negative guards PASS, and the authoritative Phase 1 gate `FAIL_INCOMPLETE`. This verifies the pinned source/reference checker only; it does not establish a compiled runtime out-of-bounds observation.

## Design obligations

- Reject or normalize unsupported negative coordinates at any XGBA/editor/emulator extension boundary **before** native border lookup, rather than silently assuming Python-style modulo.
- Trace every caller and event/script producer of `GetMapGridBlockAt` / `MapGridGetMetatileIdAt` to determine reachability, and test representative border sizes in compiled FireRed plus emulator memory instrumentation.
- Preserve the read fallback vs write no-op distinction in future editor/ROM round trips; do not infer semantic approval from this arithmetic reference.

**Phase 1 remains FAIL_INCOMPLETE, 0/14,834 independently approved whole-file dispositions.**

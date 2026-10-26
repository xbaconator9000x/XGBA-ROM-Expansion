# Phase 1 P0 — FireRed authored border dimensions and zero-divisor boundary (26 October 2026)

**Decision: FAIL_INCOMPLETE. This is source-pinned authoring metadata analysis, not compiled-layout reachability or runtime proof.**

## New pinned source evidence

- `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `data/layouts/layouts.json`, Git blob `41d0eb1b5e51fa75d535b5a098bae2bd650f710d`: 383 entries, of which 18 are empty placeholders and 365 have named layout IDs. Of the named entries, **330 declare a 2×2 border, seven declare 3×2, and 28 declare 0×0**.
- Representative declared 2×2 layout: `LAYOUT_PALLET_TOWN_PLAYERS_HOUSE_1F`. Representative declared 0×0 layout: `LAYOUT_LITTLEROOT_TOWN_MAYS_HOUSE_2F`. These are authored entries, not proof of inclusion in a particular linked ROM or gameplay accessibility.
- `include/global.fieldmap.h`, blob `e2828ec0cb1439718e830fbef4366770b3b77b1c`: `struct MapLayout` stores `u8 borderWidth` and `u8 borderHeight`. `src/fieldmap.c`, blob `41567772299000ba5855419e5c39ad9373a34c20`, lines 39–59: `GetBorderBlockAt` applies C signed remainder by both fields when a grid read falls back to border data.

**Interpretation:** The prior signed-remainder counterexample used hypothetical 2×2 dimensions. That dimension is now confirmed to occur in 330 *authored layout declarations*. Additionally, 28 authored declarations have zero divisors: invoking the native border macro with one of these layouts would attempt remainder by zero. Whether any such layout is compiled, bound to a reachable map header, or passed to the fallback remains **unproven**. This is not a claim of an observed crash or a confirmed reachable division by zero.

## Reproducible verification

`tools/verify_p0_additive_source_contracts.py` now pins both new source blob identities, asserts the native border-width field ABI, validates the exact 383-entry authoring table, rejects malformed/partially zero dimensions and duplicate IDs, and records the dimension distribution in `map_layout_border_metadata_reference`. The existing 16 additive source assertions, exhaustive map-cell comparisons and signed-remainder witnesses remain intact.

- Initial test commit: `293c9cea0d293dee3b2ee9601994b02db0ffdf7c`.
- Regex-escape correction: `19310b15f54fcc3c83a9b3e1f6732499615877a5`.
- Native C header member-comment-aware matcher correction: `c3296d403daa807a55b97c6800ebe4d5df3e2d30`.
- The final corrected post-commit census was triggered as [run #40250082483](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40250082483). **Completed successfully** (job 121339860555). The actual job log reports `16/16 source assertions PASS; map-cell 65536 words x 7 operations PASS; pinned border signed-remainder counterexamples PASS; authored border metadata 365 layouts PASS`, ten curated negative guards PASS, and the authoritative mapping gate `FAIL_INCOMPLETE` with 14,834 remaining. Prior intermediate runs #40250015817 and #40250025014 were triggered by earlier revisions and are not the final matcher verification. The earlier [run #40247291725](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40247291725) passed before this additional metadata check.

## Next required evidence

Trace the generated `gMapLayouts` table and map headers to identify which declared 0×0 layouts are compiled and referenced. Then trace actual callers and coordinate domains for `GetMapGridBlockAt` and `MapGridGetMetatileIdAt`. Exercise only validated, representative cases in instrumented compiled FireRed before claiming reachable undefined behaviour. Any XGBA/editor import path must reject unsupported zero border dimensions when native border fallback can be invoked.

**No independent whole-file dispositions approved (0/14,834); Phase 1 remains FAIL_INCOMPLETE.**

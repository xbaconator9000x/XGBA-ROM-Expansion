# Phase 1 P0 — FireRed complete authored map-header → layout-table join (26 October 2026)

**Decision: FAIL_INCOMPLETE. Verified authored-source join, not compiled reachability, native execution, or independent semantic signoff.**

## Verified finding

The complete pinned FireRed authoring census contains **43 map groups**, **425 map JSON headers** and a **383-position layout table** (365 named layouts and 18 empty placeholders). **28 named layouts declare a zero-width or zero-height border. None of the 425 authored map headers directly selects any of those 28 layouts.**

This materially narrows the earlier conditional border-remainder hazard: the authored map-header selection path does **not** supply a zero-border layout in this pinned revision. It does **not** establish that all other assignments to the saved `mapLayoutId` are bounded, that no script or runtime path can select a zero-border table slot, that the source is linked in any particular ROM, or that a zero-divisor operation is actually executed.

## Reproducible evidence

- Exact upstream revision: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Pinned `data/maps/map_groups.json` Git blob: `8c382f504d208286161903244772c93138cd7662`; includes `connections_include_order` metadata separate from the 43 group keys.
- Pinned `data/layouts/layouts.json` Git blob: `41d0eb1b5e51fa75d535b5a098bae2bd650f710d`.
- Pinned map-header producer `tools/mapjson/mapjson.cpp`: `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5`. The producer matches each authored map's `layout` field against exactly one layout `id` and emits its layout pointer and numeric ID.
- Pinned runtime consumer `src/overworld.c`: `339014da46ae8543143edc99ab72bf7496203a0d`. `GetMapLayout` reads `gSaveBlock1Ptr->mapLayoutId` and indexes `gMapLayouts[mapLayoutId - 1]` when nonzero, without a bound check in that getter.
- Pinned border fallback `src/fieldmap.c`: `41567772299000ba5855419e5c39ad9373a34c20`.
- `tools/phase1_firered_map_layout_join.py` verifies the upstream commit, five exact source Git blobs, producer/consumer expressions, complete group/layout counts, each of the 425 map JSON blobs and their unique layout resolutions. It outputs deterministic JSON with per-map blob SHA, group and positional layout IDs, border dimensions, zero-border references, and unused authored layouts.
- **[PASS run #40255555421](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40255555421)** at checker commit `dacbcf31ffa8eb10ac74729f1bfd32bd4f9e8c43`, job `121356520316`: `PINNED_AUTHORING_JOIN_PASS maps=425 layouts=365 zero_border_map_refs=0` and `PHASE1_GATE=FAIL_INCOMPLETE; independent approvals=0`.
- [Archived map-by-map evidence artifact #12622272862](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40255555421/artifacts/12622272862), GitHub-reported artifact digest `sha256:9732e2927065eaef4fb5f24f738c7b738c665013712d3ff52498a272e3519e7e`.

The first three PR CI attempts failed closed on overly specific source-expression matching and an omitted `connections_include_order` metadata key; these checker errors were corrected before the successful run. No failed attempt is represented as a source incompatibility.

## Outstanding Phase 1 obligations

1. Enumerate every runtime writer of `gSaveBlock1Ptr->mapLayoutId`, including map header load, save restore and script/callback mutation, and prove or reject bounds and zero-border reachability at each path.
2. Verify original/modern/revision-10 compiled layout-table inclusion and symbol/relocation identities, not just authored JSON output.
3. Prove coordinates reaching `GetBorderBlockAt` from each caller and instrument compiled execution before claiming an observed negative index or division by zero.
4. Preserve editor import/export collision and elevation semantics, whole-file semantic review, cross-emulator and save-state compatibility gates.

**No Phase 2 implementation; no independent whole-file approvals (0/14,834); Phase 1 remains FAIL_INCOMPLETE.**

# Phase 1 analyst candidate — Porymap `include/core/metatile.h`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `include/core/metatile.h`; Git blob SHA-1: `eba4afedbdd0ae682dca472d941a966df31285d3` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/metatile.h).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The complete header defines Metatile's public QList<Tile> and private QMap<Attr,uint32_t> attribute store, with default/copy/numTiles constructors, copy assignment, equality comparing both tiles and attributes, and negated inequality. LayerType enum is Normal/Covered/Split/Count; Attr enum is Behavior/TerrainType/EncounterType/LayerType/Unused. Declares attribute packing/unpacking and setters, convenience accessors, tileset-index mapping, coordinate conversion, default masks/sizes, configurable setLayout(Project*), ID and layer-name formatting. Geometry is 2×2 tiles per layer, 16×16 pixels per metatile, independent of how many tiles a particular instance stores.

## Expansion significance and unresolved obligations
Expansion relevance: attributes are represented as uint32_t and masks are project configurable, whereas displayed layer names cover three layers. Distinguish editable logical attributes from serialized game formats. Confirm caller handling of empty attributes, configuration reload and layer counts before approving.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

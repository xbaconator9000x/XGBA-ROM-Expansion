# Phase 1 analyst candidate — Porymap `src/core/tile.cpp`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `src/core/tile.cpp`; Git blob SHA-1: `88b98c505edb838fbde191acdac2150c32070b46` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/tile.cpp).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The complete implementation defines maxValue=0xFFFF and four BitPacker masks: tile ID 0x03FF, xflip 0x0400, yflip 0x0800, palette 0xF000. Constructors initialize fields to zero, accept component fields, or unpack the raw 16-bit word. rawValue() OR-combines each explicitly packed field; it does not reinterpret a C++ bitfield struct. orientation() delegates to Util::getOrientation; flip() returns for null QImage, calls QImage::flip on Qt >=6.9 and mirrored(xflip,yflip) on earlier Qt. getIndexInTileset() retains primary IDs below Project::getNumTilesPrimary(), subtracting that count for secondary IDs; no range check is shown here.

## Expansion significance and unresolved obligations
Expansion relevance: raw encoding and 10-bit ID limit are explicit, while the primary/secondary tileset split is runtime project configuration. Validate masks, out-of-range IDs, compiler bitfield assignment, Qt flip equivalence and downstream tile renderers before any format extension.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

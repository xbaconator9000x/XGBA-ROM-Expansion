# Phase 1 analyst candidate — Porymap `include/core/tile.h`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `include/core/tile.h`; Git blob SHA-1: `11fd6a99cfff18dc0d06185b3342a7b107acebb9` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/tile.h).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The complete header defines a Tile value with 10-bit tileId, 1-bit horizontal flip, 1-bit vertical flip and 4-bit palette fields. It declares default, component and raw-uint16 constructors; rawValue(), orientation(), image flip(), getIndexInTileset(), and maxValue. Geometry is fixed at 8×8 pixels, 64 pixels, two serialized bytes. The inline equality and inequality operators compare all four logical fields, not the C++ object representation. Includes QObject/QSize and uses Qt orientation and image types; the actual serialization semantics depend on src/core/tile.cpp and BitPacker, not on compiler-dependent C++ bitfield layout.

## Expansion significance and unresolved obligations
Expansion relevance: tile IDs are restricted to 10 bits, palettes to four, and the exposed raw form to 16 bits. Wider IDs require changing producer/consumer contracts, not just increasing the ROM size. Verify bitfield truncation behaviour across compilers, Qt version paths, all tileset consumers and round-trip tests before approval.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

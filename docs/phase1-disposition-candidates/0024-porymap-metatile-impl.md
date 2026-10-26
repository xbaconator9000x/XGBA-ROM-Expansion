# Phase 1 analyst candidate — Porymap `src/core/metatile.cpp`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `src/core/metatile.cpp`; Git blob SHA-1: `00fff2ba4bd1f3d85c7be3356fa6bf0bb0d8fc70` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/metatile.cpp).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The entire implementation defines vanilla FRLG masks (behavior 0x000001FF, terrain 0x00003E00, encounter 0x07000000, layer 0x60000000, unused 0x98FFC000) and RSE masks (behavior 0x00FF, unused 0x0F00, layer 0xF000). A mutable static attributePackers map governs project-specific getAttributes(), setAttributes(data), setAttribute() and clamps. The versioned setAttributes(data,version) instead unpacks vanilla masks. getDefaultAttributesSize returns 4 for FireRed, 2 otherwise; getMaxAttributesMask handles configured sizes 1,2,4 and returns 0 for others. setLayout(Project*) recomputes unused bits as complement of four configured masks AND maximum size, resets packers, validates mask capacities with warnings, and sets a global hex-ID display width from Block::getMaxMetatileId(). The file also implements construction of numTiles default tiles, primary/secondary index mapping, hex formatting, comma joining, three layer names, and pixel-to-metatile coordinate conversion.

## Expansion significance and unresolved obligations
Specific source-level boundary finding: coordFromPixmapCoord() performs integer truncation toward zero and then decrements on *every* negative coordinate. For pixelWidth()=16, x=-16 yields -2, whereas mathematical floor(-16/16)=-1. This is a negative exact-multiple boundary discrepancy; reachability in the editor and visible effect are unproven. The mutable static packers also mean correctness depends on setLayout initialization and reload order. Verify source-pinned reproducer, call sites, negative pixel coordinates, global mask changes and downstream serialized outputs before approval.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

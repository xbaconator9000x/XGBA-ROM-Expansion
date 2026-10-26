# Phase 1 analyst candidate — Porymap `src/core/mapconnection.cpp`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `src/core/mapconnection.cpp`; Git blob SHA-1: `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/mapconnection.cpp).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The complete implementation initializes static project=nullptr, opposite direction pairs up/down, left/right, dive/emerge, and cardinal list up/down/left/right. Constructor initializes null parent, target name, direction, signed offset. areMirrored() requires two non-null parent maps and inverse names, offsets and directions. findMirror() scans target map's connections and returns the first match; its comment explicitly disclaims stable pairing for duplicate identical connections. createMirror() allocates a reversed connection, negates offset, and attaches it to the target map without recursive mirroring. getMap()/targetMap() call project->loadMap when available. render()/renderImage() render a connected map or return empty pixmap. relativePixelPos() handles right/down from parent dimensions and left/up from negative target dimensions (or clipped connection rectangle), multiplying orthogonal offset by metatile pixel size; dive/emerge and unknown directions retain (0,0). setParentMap() may update an existing mirror's target, detach from old map, attach to new and emit signal; target, direction and offset setters mirror changes when requested, emit signals and mark parent map edited. The remaining functions classify direction strings.

## Expansion significance and unresolved obligations
Expansion relevance: mirrored link consistency and map-relative pixel offsets depend on mutable project state. Potential review hazards: duplicate mirrors are ambiguous; createMirror does not explicitly guard null target; setParentMap has no direct markMapEdited() call (unlike three other setters), which is not proof of unsaved changes because add/remove may mark edits. Verify these behaviours through actual Qt project tests and map save/reload before approval.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

# Phase 1 analyst candidate — Porymap `include/core/mapconnection.h`

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Whole-file source-grounded analyst preparation only. No gate credit.

## Immutable identity
- Repository: `huderlem/porymap`; pinned commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.
- Exact path: `include/core/mapconnection.h`; Git blob SHA-1: `40713d3a26157fce7a36465858e8273c78dc12f6` (fetched at pinned commit).
- [Pinned source](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/mapconnection.h).
- Cross-file dependency: the matching `include/core/` header or `src/core/` implementation, Qt and Porymap's Project/BitPacker contracts as applicable. External callers are **not exhaustively enumerated**.

## Whole-file analyst inventory
The complete QObject header declares MapConnection with target map name, direction and signed offset; optional parent Map*; QJsonObject custom data; a static QPointer<Project>; direction constants/classifiers; mirrored-connection find/create; target/parent getters and setters; image rendering and relative pixel position; edit notification; and Qt signals for parent, target, direction and offset changes. The inline oppositeDirection() returns its input when no mapping exists. The inline isCardinal/isHorizontal/isVertical/isDiving wrappers delegate to static overloads. No public API here guarantees that connections are paired uniquely.

## Expansion significance and unresolved obligations
Expansion relevance: map stitching depends on direction strings, signed metatile offsets and optional mirrored links, not only blockdata. Editor-only customData is not proven to survive native ROM export. Validate setter side effects, ownership, project reload and unrecognised directions before signoff.

**Evidence level:** exact pinned Git blob and complete source content were inspected; cited semantics are source observations, not compiled/runtime/editor-roundtrip proof. Required independent reviewer must verify external consumers, variant branches, complete-file scope and regression evidence, then record a separate authenticated verdict. Reviewer: **none**; verdict: **pending**; gate contribution: **0**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 independently approved.**

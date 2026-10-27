# Phase 1 whole-file candidate 0016 — Porymap BitPacker interface

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.**

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [include/core/bitpacker.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/bitpacker.h), Git blob `4e3767e48449a974bfe1d9c63c5bf63dd2826fe9`.

## Complete-file inventory
Include guard BITPACKER_H, QList dependency, and one class. Public default constructor; mask-taking constructor; setMask; inline mask() and maxValue() getters; pack, unpack and clamp methods, all returning uint32_t. Private members: `m_mask = 0`, `m_maxValue = 0`, and `QList<uint32_t> m_setBits`. No destructor, custom copy logic, virtual methods, filesystem operation, serialization format or bounds-validation contract is declared here. The default constructor leaves an empty mask-position cache and zero capacity until setMask.

## Cross-file dependency
[src/core/bitpacker.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/bitpacker.cpp) implements the methods; [src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp) owns three shared static instances, calls setMask and packs/unpacks native map-cell fields. The interface permits arbitrary uint32_t masks, whereas `Block::rawValue` and `Blockdata::serialize` ultimately use uint16_t records. Header type width is **not** proof of expanded serialized capacity.

## Review obligations
Verify every consumer, integer-width portability, mask lifecycle and configured-mask validation; distinguish method declarations from implementation effects. Independent reviewer identity/verdict/date absent. No approval or runtime claim.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

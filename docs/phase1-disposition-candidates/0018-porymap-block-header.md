# Phase 1 whole-file candidate 0018 — Porymap Block interface

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.**

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [include/core/block.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/block.h), Git blob `94c674c30ed5c20231d4501cd193c0cb25365d2c`.

## Complete-file inventory
Pragma once and BLOCK_H guard; QObject include; one Block class. Four constructors (default, uint16_t packed word, three uint16_t semantic fields, copy); copy assignment; equality/inequality; three field setters; three inline field getters; rawValue; static setLayout; three static maximum-field getters; static uint16_t maxValue; three private uint16_t fields. No per-instance layout identifier, mask storage, serialization version, pointer, buffer length or explicit overflow-reporting API exists in this declaration. The header alone does not establish whether setters clamp or constructors preserve out-of-range values; see implementation.

## Cross-file relevance and review boundary
[src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp) supplies shared static mask semantics, while [include/core/blockdata.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/blockdata.h) exposes a QVector<Block> serialized through Block::rawValue. The field type uint16_t is **not** proof that any configured mask can store all 16 bits for each field. Any extension adapter must retain source-project mask provenance and detect unrepresentable fields rather than infer semantic triples from rendered tiles.

## Reviewer obligations
Confirm all callers and configured mask sources, semantic equality versus raw equivalence, and complete-file ABI. No independent reviewer verdict/date or compiled/editor round trip is present.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

# Phase 1 whole-file candidate 0020 — Porymap Blockdata container

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.**

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [include/core/blockdata.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/blockdata.h), Git blob `a1e45b63783fa2aecceee6fadbb33f1e1935b6b8`.

## Complete-file inventory
Pragma once, BLOCKDATA_H guard, block.h, QByteArray and QVector includes. Defines `class Blockdata : public QVector<Block>` with one public `QByteArray serialize() const` method. No independent per-element dimensions, layout/mask metadata, extension marker, reader, bounds check or binary header is declared. QVector<Block> provides inherited container operations; those semantics belong to Qt and must not be guessed from this header.

## Cross-file contract
[src/core/blockdata.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/blockdata.cpp) writes each packed uint16_t as little-endian bytes. [src/core/maplayout.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp) handles binary reads, resizing, border dimensions and file writes. This type alone is not an authoritative project format and cannot reconstruct event scripts, map IDs, tilesets or custom editor layers.

## Reviewer obligations
Verify Qt container ABI and consumers, project-mask dependency and persistence boundaries. No independent reviewer identity/verdict/date. No approved disposition.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

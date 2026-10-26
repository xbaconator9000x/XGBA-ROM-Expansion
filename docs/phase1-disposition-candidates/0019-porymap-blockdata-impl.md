# Phase 1 whole-file candidate 0019 — Porymap Blockdata serializer

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.**

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [src/core/blockdata.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/blockdata.cpp), Git blob `5fcd4e32b115790f5a86b5cef5726cace8005017`.

## Complete-file inventory
Includes blockdata.h. The file implements one method, `QByteArray Blockdata::serialize() const`: create empty QByteArray; iterate every Block in the inherited QVector; obtain Block::rawValue as uint16_t; append low byte then high byte; return the array. There is no header, per-block metadata, mask identity, dimensions, checksum, length guard or error reporting in this method. Output size is two bytes per element, assuming QByteArray append succeeds; this file does not write to disk.

## Producer/consumer dependencies
[src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp) determines each raw word under active masks. [src/core/maplayout.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp) reads pairs of bytes into Blocks, resizes length-mismatched arrays and calls serialize before QFile::write. The layout writer returns true after file.write(data) without inspecting the returned byte count; **successful serialization does not prove complete file output**. The odd trailing byte on read is ignored. Those are separate source-level boundaries, not defects demonstrated at runtime.

## Reviewer obligations
Check all serialization consumers, project mask lifetime, QByteArray and QFile error handling, and no-op project round trips. Independent reviewer identity/date/verdict absent. No gate contribution.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

# Phase 1 whole-file candidate 0017 — Porymap Block implementation

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.**

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp), Git blob `fc4fe774ccd75673c549734055907eb7c79c0fc2`. Includes block.h, bitpacker.h, config.h.

## Complete-file inventory
- Static `maxValue = 0xFFFF`; three file-scope BitPackers default to metatile `0x03FF`, collision `0x0C00`, elevation `0xF000`.
- Four constructors: default initializes all semantic fields to zero; three-field constructor stores caller-supplied uint16_t values **without clamping**; raw-word constructor unpacks using the **current** static masks; copy constructor copies the semantic triple.
- Copy assignment copies the three fields; equality compares the three **stored semantic values**, not serialized raw words; inequality negates equality.
- `rawValue` ORs three independently packed fields and returns uint16_t. It does not check field representability, disjoint masks or mask coverage.
- `setLayout` replaces **all three process-wide static packer masks** from projectConfig; no per-Block mask provenance or conversion is performed here.
- `setMetatileId`, `setCollision`, `setElevation` each apply BitPacker::clamp (modulo capacity); `getMaxMetatileId`, `getMaxCollision`, `getMaxElevation` return the current packer maxima.

## Distinct lossy paths and exact witnesses
Under default masks, the three-field constructor `Block(1024,0,0)` retains metatileId 1024, but `rawValue()` is zero because pack ignores the eleventh bit. In contrast, a default Block followed by `setMetatileId(1024)` stores zero due to modulo clamping. Both serialize to the same 16-bit word but equality can distinguish their stored semantic values. This is a **direct consequence of the source**, not a verified compiled/editor test.

Changing masks with setLayout can change how a stored semantic triple serializes and how the same bytes decode; overlapping masks would alias fields because rawValue uses OR. There is no validation in this file proving masks partition 16 bits.

## Dependencies and reviewer obligations
BitPacker defines modulo, packing and mask handling; projectConfig provides mask values; Blockdata serializes rawValue, while Layout::readBlockdata constructs Block from each two-byte word. Independent reviewer must verify all constructor/setter callers, projectConfig constraints, mask-change timing, compiled variants and round-trip behaviour. No independent signoff or gate-count increment.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

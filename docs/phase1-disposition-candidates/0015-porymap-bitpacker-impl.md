# Phase 1 whole-file candidate 0015 — Porymap BitPacker implementation

**PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** Complete-file analyst interpretation, not compiler or editor certification.

## Exact source identity
huderlem/porymap @ `26b919d7ff4b54152de010abd5bf344af2ebe116`, [src/core/bitpacker.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/bitpacker.cpp), Git blob `34f86b4e3910021613a1d090746ae53a1c6782a2`. Includes bitpacker.h and climits. All five methods in the complete file are accounted for.

## Complete declaration / execution inventory
1. **BitPacker(uint32_t):** delegates to setMask; no independent validation.
2. **setMask:** stores the 32-bit mask, clears the list of set-bit positions, scans all mask bits from low to high, and stores one position bit for each set bit. Sets maximum unpacked value to UINT_MAX for 32 selected bits, otherwise computes `(1 << popcount) - 1`. No contiguity or overlap check occurs in this class.
3. **clamp:** returns input unchanged for UINT_MAX maximum; otherwise returns input modulo maximum+1, **not saturation or error**. A zero-bit mask maps every value to zero.
4. **unpack:** intersects with mask, enumerates selected bit positions into consecutive output bit positions. Noncontiguous masks are supported; an arbitrary 16-bit raw word is not necessarily preserved when its mask omits bits.
5. **pack:** maps low-order input bits to the stored set-bit positions, short-circuits when remaining input becomes zero, and silently discards bits above the mask's capacity. Does not call clamp or signal truncation.

## Dependencies and conditional hazards
The header declares a QList<uint32_t> mask-position cache and 32-bit values. `Block::setLayout` in block.cpp supplies project-configured masks; `Block::rawValue` ORs packed fields. For 31 selected mask bits, `(1 << 31) - 1` is a **signed-arithmetic portability/undefined-overflow concern** on conventional 32-bit int implementations; `1 << i` at the sign position also requires compiler/language-standard review. This is a source-level conditional, **not** a reproduced Qt crash or an established 16-bit map-file path. The normal 16-bit masks do not reach that branch.

## Independent reviewer work
Verify compiler standard and exact integer promotion behaviour, all mask callers, noncontiguous/overlap cases, and representative round-trip fixtures. Record separate reviewer identity/verdict/date and pinned evidence. No source approval, compiled proof or gate-count increment.

**Phase 1: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

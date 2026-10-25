# Phase 1 Porymap memoryview input boundary — 2026-10-26

**Gate:** FAIL_INCOMPLETE; no independent whole-file semantic approval.

The prior strict Python Porymap map-block reference accepted any `memoryview` as a binary stream. A non-contiguous byte view or a typed 16-bit-element view has different indexing/length semantics from the native 2-byte block stream. The original `len(data) == expected_count * 2` check counts elements rather than bytes for typed views and can accept incorrectly shaped inputs before decoding. This is a reference-adapter issue, **not a demonstrated defect in Porymap itself**.

Commit `c83eeaba1a227636ba68f2e6bccd868d8904a001` requires memoryviews to be one-dimensional, byte-sized, byte-formatted, and C-contiguous before native block decoding. Two negative fixtures cover stepped/noncontiguous byte views and a `cast('H')` typed view. The existing 65,536 raw-word round-trip and earlier 17 negative controls remain in the self-test; total negative fixtures are now 19.

**Verification status:** The earlier compiled Porymap workflow run [40209978387](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40209978387) completed successfully before this change. The new commit's CI status has not yet been confirmed; do not treat the previous run as verification of this commit. No compiled Qt editor round-trip or semantic signoff is claimed.

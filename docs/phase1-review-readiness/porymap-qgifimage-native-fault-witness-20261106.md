# Porymap QtGifImage/GIFLIB bounded native fault witness (2026-11-06)

## Status and source identity

This follow-up tests only the fault/ownership objections from the preceding
QtGifImage/FEX vendor dossier. It does not repeat that dossier's 40-file
inventory or treat its candidate rows as independent semantic receipts. The
new machine report records only the files compiled or their immediate
interface/notice dependencies, with original Porymap Git blob IDs, full-byte
SHA-256 values, candidate-row SHA-256 values, and the original workpack and
compressed-dossier hashes.

The source pin remains
`huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. The reproducible
report is `phase1-evidence/qgifimage-native-faults.json` in the exact-head
artifact from the existing **Phase 1 full pinned Porymap Qt project
save/reopen** workflow.

## Bounded native execution

The workflow compiles the unchanged pinned `qgifimage.cpp` and the six GIFLIB
C sources listed by the existing qmake fragment against the installed Qt6
Core/Gui libraries. GIFLIB is linked as a test DSO: GNU linker `--wrap`
counters observe open/slurp/spew and decoder-close entrypoints, while dynamic
symbol interposition observes GIFLIB's internal `EGifCloseFile` call from
`EGifSpew`. This is observation instrumentation only; no source body is
replaced. A controlled Qt `QIODevice` fixture supplies write failures, and
buffers supply a positive GIF and a one-byte-truncated version. The tests do
not launch the Porymap GUI.

The harness requires these bounded observations:

- Positive save/load round trip succeeds, `EGifSpew` and `DGifSlurp` return
  `GIF_OK`, and the GIFLIB close paths are observed.
- A `WriteOnly` input and `ReadOnly` output pass the pinned bitwise-OR
  predicates and enter original GIFLIB calls rather than being rejected by
  `QGifImage`'s mode predicates.
- On the injected output failure, original `EGifSpew` returns `GIF_ERROR`,
  while `QGifImage::save(QIODevice*)` returns `true`; no GIFLIB close call is
  observed on that error path.
- On the truncated GIF, original `DGifSlurp` returns `GIF_ERROR`,
  `QGifImage::load(QIODevice*)` returns `false`, and its GIFLIB close call is
  not observed.

The source trace explains the ownership boundary: `EGifSpew` calls
`EGifCloseFile` after successful output, but has earlier error returns; the
QtGifImage wrapper does not inspect the `EGifSpew` result. The decoder wrapper
returns immediately on `DGifSlurp` failure, before its success-path
`DGifCloseFile`. The test observes the missing close calls on these two
failure paths; it does **not** measure leaked allocations, leak rate, process
impact, or cleanup elsewhere.

## Non-approving findings and controls

The machine-readable objection matrix labels reproduced observations
`OBSERVED_NATIVE_BOUNDED`, and leaves allocator lifetime, full GUI behavior,
filesystem/user-facing behavior, and longer-running effects as
`NEEDS_EVIDENCE`. Every source record remains `NEEDS_EVIDENCE`; no approvals or
gate promotion are made.

The runner independently checks the exact pinned source, original Git object
and candidate-dossier row hashes (including the separate QtGifImage and GIFLIB
notice bytes), required source contracts, positive/fault runtime assertions,
and non-approving report boundary. Deterministic controls reject eight
source-contract/notice mutations, six candidate identity/review mutations,
and report mutations that would alter the pin, claim approval, or overstate
leak evidence. Those controls validate this test package only.

Evidence labels are limited to complete pinned source inspection and compiled
original QtGifImage/GIFLIB code with link wrappers and controlled QIODevice
fixtures. This is not a full GUI test, sanitizer leak report, physical
filesystem durability test, gameplay test, or independent semantic review.
Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.

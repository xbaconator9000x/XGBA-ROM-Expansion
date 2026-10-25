# Phase 1 status — 2026-10-25

- Pinned source census: **PASS** in GitHub Actions run 40158454510.
- Tracked files: **14,834**, five repositories, pinned commits.
- First run (40158369056) scanned 4,684 source/config files and found 5,711 lexical candidate occurrences but failed on a legacy encoded source file; the subsequent run passed after a lossless surrogateescape decoding fix.
- Existing prior workpack baseline: 11,024 mapping-register rows and 4,184 cross-reference links (historical workpack counts, **not** newly certified semantic dispositions).
- **Phase 1 mapping is NOT complete.** Lexical candidate occurrences and regex symbol references are not semantic analysis, signed per-file dispositions, or validated relocation decisions.
- Next gate: import the existing v1.4 mapping tools and consolidated contracts, run full-source audit on pinned Git checkouts, review and record each tracked file with source-hash-pinned evidence, verify dependency graphs and acceptance checks. Mapping completion is separate from Phase 2 emulator implementation.
- No ROM or emulator binary patch has been implemented or tested by this workflow.

## Reproduction

See [the workflow](../.github/workflows/phase1-census.yml) and [census script](../tools/pinned_source_census.py). GitHub Actions artifact `xgba-phase1-pinned-source-census` contains manifest, lexical candidates, include and symbol candidates, and 500-file checkpoints. The artifact is retained for 90 days; source scripts remain version controlled.

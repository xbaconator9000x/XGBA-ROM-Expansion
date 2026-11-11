# XGBA CI execution policy — 12 November 2026

## Reason for this change

Early R7–R14 pull-request workflows matched `integration/**`, so a single
edit to the shared mGBA MMIO bridge launched eight unrelated heavyweight
historical game-build jobs. During the R25 implementation, 222 Actions runs
were generated across 19 revisions; most nonterminal runs were cancelled by
newer commits. The R25 DMA tests could also launch once for a feature-branch
push and once for the same pull request.

## Reliable and economical checks

* **Every pertinent pull request:** fast source / MMIO boundary checks and the
  tests directly covering the touched subsystem. R7–R14 now watch their own
  milestone source, host execution implementation, adapters and tests rather
  than every file below `integration/`. R16 watches its actual boot adapter
  rather than unrelated Emerald R24/R26 files.
* **Before merging memory/device changes:** maintain the R24 FireRed/Emerald
  native transaction suites, R25 source-lifetime native and portable suites,
  and consolidated Flash/save/battle source-and-memory checks. Each workflow
  uses a PR trigger (and a main-branch push for post-merge validation), **not**
  a separate feature-branch push trigger for the same SHA.
* **Historical regression:** each of R7–R14, R16 retains
  `workflow_dispatch` for an operator to request a rerun and is also scheduled
  monthly on the first day (03:17 UTC for R7–R14, 03:37 for R16). A
  `schedule` executes from the default branch only; old source-pinned game
  tests are not deleted and remain available as evidence.
* **On a shared host-implementation change:** the consolidated gate and
  current relevant boundary suites are the required checks. Historical
  screenshot-producing tests are sampled periodically or explicitly invoked;
  don't require full GIF regeneration on every MMIO status or header edit.
* **On documentation-only edits:** no native game compilation unless a
  workflow source or actual test inputs also change.

This improves **when** tests execute; it does not assume old tests passed
without executing them, alter pinned upstream versions, or delete evidence.
A check on a particular SHA is considered verified only if its own job
completed successfully on that SHA. A passing historical run is not a claim
about the current code if its test did not run again.

## Watchpoints

Check `actions/runs` for paired `push`+`pull_request` runs at the same
head SHA, unintended legacy runs on shared-MMIO-only diffs, cancelled run
counts, and regression failures. Explicitly rerun the complete historical
suite before a major emulator ABI or rendering refactor when needed.

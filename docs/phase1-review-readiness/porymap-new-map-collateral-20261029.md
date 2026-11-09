# Phase 1 — Porymap new-map collateral writes and clean-state ordering (2026-10-29)

**Status: source checker CI pending. FAIL_INCOMPLETE, 0/14,834 independent approvals. Partial functions, not whole-file review.**

## New dependency closure

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`, `src/project.cpp` Git blob `d43b0949303433111d4478ad76117c2b3445dd13` and `include/project.h` blob `50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354`.

For **new, not-yet-persisted maps**, the existing `Project::saveMap` creates a map directory, calls `saveTextFile` for scripts, optionally calls it for text, and calls `appendTextFile` for `data/event_scripts.s`. **All three boolean return values are ignored.** Only afterwards does it open/write `map.json`, call `map->setClean()`, and attempt `saveLayout` unless skipped. Thus even an explicit text-file *open failure* can be ignored, and a later layout-save failure can be returned after the map dirty state has already been cleared. Actual downstream filesystem and UI consequences remain untested.

The two underlying `QFile` text helpers check open success, but not the byte count returned by `write`, flush, or close. This is distinct from the six JSON writer observations and the previous actual Qt `saveMap` /dev/full false-clean case. Source evidence alone cannot certify whether a specific new-map creation failure persists incomplete scripts.

When Poryscript mode is enabled, `getScriptFileExtension` returns `.pory`, while the event-scripts assembly text references `scripts.inc` (and optionally `text.inc`). **Do not call this an inconsistency or defect yet:** Poryscript may generate the `.inc` outputs. Verify the existing Poryscript generation rules, map-event include dependencies and native build path before drawing a conclusion.

## Maximum-reuse decision

Keep Porymap's `Project::saveMap`, existing text writer APIs, `Editor`, `MainWindow`, and Poryscript's generator and FireRed assembly path. The smallest eventual correction should check the existing return values, preserve the intended ordering/atomicity and make dirty-state clearing conditional on successful required persistence. Use Qt's existing QSaveFile where appropriate for replacement writes; **append-only `event_scripts.s` requires separate transactional semantics**, not an indiscriminate QSaveFile substitution. This is Phase 1 evidence and a review recommendation, not an upstream patch.

## Fail-closed controls and unresolved edges

A source-pinned checker validates the function declarations, three collateral writes, branch guards, script extension selection, JSON/clean/layout ordering, and text writer unchecked write results. Nine source mutations and nine output-evidence mutations must be rejected. The checker explicitly records no native new-map failed-write execution, no verified Poryscript generated-include dependency, no complete-file dispositions and no independent approvals.

Next: execute an actual Qt new-map save with controlled failures on scripts/text/event-scripts paths, inspect on-disk bytes and GUI dirty-state, verify generated `.pory` → `.inc` dependencies with the existing Poryscript toolchain, and ask an independent reviewer to assess whole-file source scope. Never alter main/audit or begin Phase 2.

**Gate: FAIL_INCOMPLETE; independently approved 0/14,834.**

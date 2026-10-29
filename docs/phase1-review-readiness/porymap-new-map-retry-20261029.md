# Phase 1 — pinned Porymap new-map retry/persisted-flag closure (2026-10-29)

**SOURCE-ONLY dependency proof verified at exact-head CI; FAIL_INCOMPLETE; 0/14,834 independent approvals.**

## Immutable dependencies

Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`: `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`, `src/core/map.cpp` blob `47b279919bd4afcc76b88f9eeecd459b3452989f`; `include/core/map.h` persisted flag inline accessors. The verifier checks original blob hashes and functions; no upstream modifications.

## Previously unclosed source dependency

On the `!map->isPersistedToFile()` path, `Project::saveMap` invokes two `saveTextFile` calls (scripts and optional text) and `appendTextFile` (global event_scripts.s) without checking their boolean returns. It then writes map JSON without inspecting `OrderedJsonDoc::dump` or close status, invokes `map->setClean()`, and only **after that** tests `saveLayout` if enabled. Original `Map::setClean()` clears the edit-history and unsaved-data state **and sets `m_isPersistedToFile = true`**. Original `Map::hasUnsavedChanges()` includes `!m_isPersistedToFile`.

Consequently, **conditional source-level retry hazard**: if the first new-map save reaches `setClean()` after a collateral failure (or before a later layout failure), the same Map object is now considered persisted, so a subsequent `saveMap` call skips the entire new-map collateral branch. This is a cross-file dependency, not an observed Qt GUI failed-write/retry result. A failure to open `map.json` returns before `setClean()`, which is a different case; do not generalize.

## Maximum-reuse decision and review questions

Reuse existing Qt QFile/QSaveFile, Project, Map, Editor and MainWindow, plus existing Poryscript generation rules. The smallest eventual correction should propagate existing collateral-write failures, preserve retryability and dirty state, and define atomicity/rollback for append-only `event_scripts.s` separately from replacement JSON files. Do not invent a new serializer or editor.

The original Porymap root LGPL-3.0 and bundled permissive third-party notices must be preserved; FireRed assets/code have separate licensing obligations. A source checker rejects 15 targeted mutations and records its source-only scope. Required next evidence: actual populated new-map Qt/GUI failure and retry, post-failure on-disk scripts and event_scripts.s bytes, file-watcher state, clean/persisted flag, fresh-process reopen, and independent whole-file reviewer decisions.

## Partial per-file records (not approvals)

| File | Scope inspected | Unresolved |
| --- | --- | --- |
| `src/project.cpp` `d43b0949` | new-map collateral calls, map JSON/clean/layout order | other functions, real failed-write, rollback, caller graph |
| `src/core/map.cpp` `47b27991` | setClean, hasUnsavedChanges, persisted state | full Map lifetime, layout/event interactions |
| `include/core/map.h` | persisted flag inline getter/setter | full header and all mutators |

**No whole-file disposition, no semantic approval, no Phase 2.**

## Executed source checkpoint

The original pinned `Project::saveMap`, `Map::setClean` and `Map::hasUnsavedChanges` source closure, with 15 scoped fail-closed mutations, passed exact-head PR CI at `b33db09f417157f6ebf2f4a2da336ee81066af7c` ([run #40789524754](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40789524754)). This remains a source-only contract; actual native Qt Project behaviour is independently recorded in `porymap-new-map-native-qt-retry-20261029.md`.

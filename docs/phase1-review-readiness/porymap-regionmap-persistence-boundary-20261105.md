# Phase 1 — pinned Porymap RegionMap save and dirty-state boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package examines the separate RegionMap editor save path. It does not repeat the map JSON / connection writer, five Project global JSON writer, external-script watcher, or new-map transaction experiments.

## Pinned source closure

The six newly inventoried whole source files are pinned to Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. The checker verifies each Git blob and full-byte SHA-256, records byte/line counts, licensing evidence, and a deterministic per-row hash. No earlier per-file dossier row/archive was found for these six files; those original-row/archive fields are explicitly `NEEDS_EVIDENCE`. All six source dispositions remain `NEEDS_EVIDENCE`.

| Pinned source | Git blob | Full-byte SHA-256 | Scope edge |
|---|---|---|---|
| `src/core/regionmap.cpp` | `94f686426e5ea8a84294dd1ac35617700c54e73f` | `a6b6717820ae1fbd04424283cf1cb4c057ec34eaff6935c5a3dc8f36f90ad44c` | Asset save order, tilemap/layout writes, undo-history clean state |
| `include/core/regionmap.h` | `c8afb1b2dd44b80ebfbf14d3793866b7764629ed` | `b723542988188a4bc4c1c7b02849baf10d8604199781c6fe21ca49f848451a84` | RegionMap file paths, layout mode and QUndoStack state |
| `src/core/regionmapeditcommands.cpp` | `f21f1d720ae22d4911ef71b984435ff66c0566f9` | `28950c048b96df25fb7525d84298e50c3d302105edf7cc6aff285572e6c92f13` | Edit command applies RegionMap mutations and drives undo history |
| `include/core/regionmapeditcommands.h` | `e47fdb7b9ed59ff523d9e5a91975c98bca68efb1` | `1645066c8a13ef544589516e76c5dc202f2605151bf0dc381270879b5137096e` | Command identities and old/new state snapshots |
| `src/ui/regionmapeditor.cpp` | `a96de606cc18469b558b1acfc7c787432b8dcfb4` | `43f433c1754cd25d4691491567e7be9ff48e47e89c485eb917a5b26e2e1eb4e2` | UI save wrappers and Project region-map section save caller |
| `include/ui/regionmapeditor.h` | `432eaab62cd897146d8f64fe9f9555ae3ce4c265` | `8ebab02239b042894fe0dcc7a644be8611316f2c505788544708271b0344753c` | Save method interfaces and undo-group ownership |

The pinned root `LICENSE.md` Git blob is `65c5ca88a67c30becee01c5a8816d964b03862f9`, full-byte SHA-256 `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`, and contains LGPL-3.0 text. This is not a redistribution determination. No SQLite or Qt translation source is in scope. `Project::saveRegionMapSections` and `OrderedJsonDoc` are reused context from the existing global JSON-writer package, not newly inventoried files.

## Source-grounded concern

The pinned `RegionMap::save()` calls `saveTilemap()`, then `saveLayout()`, then unconditionally calls `editHistory.setClean()`. Both helpers return `void`. In binary layout mode, `saveLayout()` logs a failed `QFile::open`, then still attempts `write` and `close`; it cannot report failure to `save()`. The `RegionMapEditor::saveRegionMap()` wrapper calls this void method and returns `true`. Separately, `saveRegionMapEntries()` copies entries into the Project, ignores the boolean from `Project::saveRegionMapSections()`, then returns `true`. UI save actions invoke these wrappers; their GUI behavior is not executed by this package.

The same pinned editor source defines `modified()` from the undo group's clean state and `configSaved`. Its `saveConfig()` marks configuration saved after the unchecked serializer call and close; only the initial open failure returns before that flag update. The close handler calls the RegionMap save action on “Yes” and accepts the close event after that handler, without checking its save wrappers' return values. This closes the source-level caller chain but does not establish a native modal/close result.

These are source observations, not a claim that every Project save or close path drops edits. They concern the RegionMap window's own asset/entry persistence and undo history, distinct from `MainWindow` map JSON dirty-state evidence.

## Bounded native Qt observation

The test extracts unchanged pinned bodies for RegionMap `save`, `saveTilemap`, and `saveLayout`, the `EditTilemap` constructor/redo, and the two RegionMapEditor save wrappers. They compile with real Qt6 `QFile`, `QUndoStack`, and `QProcess`, using test-only Project/RegionMap data shells.

1. A real undo command changes the tilemap; the original save wrapper persists tilemap and binary layout bytes, clears the stack, and a fresh OS process reads both files back.
2. The layout file is made read-only for a non-root test process. A matched Qt `QFile` control must observe Linux `EACCES` and the Qt `"Permission denied"` error text (Qt's error enum can vary by version). The next original save writes the edited tilemap, fails to open the layout, preserves that layout's bytes and inode, yet returns `true` through the RegionMapEditor wrapper and marks the undo stack clean. A separate child process observes this mixed on-disk state.
3. An injected false result from a test-only Project `saveRegionMapSections()` shell is ignored by the unchanged RegionMapEditor entries wrapper, which returns `true`.
4. A fresh-process readback control rejects deliberately incorrect expected tilemap bytes.

The result is native Qt behavior of these extracted original methods under a synthetic object model and Linux filesystem. It does **not** execute the original Project constructor, actual GUI actions, full FireRed project load, full Project cold reopen, or hardware durability. No application rollback is observed; the test demonstrates a partial save and false-clean state, not recovery.

The checker rejects seven pinned-source mutations (one for each selected source plus a close-dirty predicate mutation) and 23 evidence mutations, including missing licensing, wrong source/dossier hashes, a duplicate source overlap, fabricated review/approval, false full-project reopen claims, and incorrect native permission results. The machine record includes per-file source hashes, new dossier-row hashes, prior-dossier context hashes, and the deterministic dossier archive hash. Since no original per-file dossier/archive row exists for the six new files, those original identity fields remain unavailable and `NEEDS_EVIDENCE`.

## Remaining questions

- How does the actual RegionMapEditor UI present or retain a failed tilemap, binary layout, C-array, configuration, or Project section write?
- Does actual UI close/reopen preserve undo state after each mixed failure?
- What happens on short writes, ENOSPC, or failure of both files, and are there any rollback guarantees?
- How does the original FireRed project configuration load the RegionMap assets after this mixed state?

All six source rows remain `NEEDS_EVIDENCE`. No game behavior, independent review, approval, or Phase 1 gate transition is claimed.

# Phase 1 — pinned Porymap GUI new-map creation → explicit save source closure

**Source-only dependency investigation; new exact-head CI pending. FAIL_INCOMPLETE; independent approvals 0/14,834.**

## Immutable upstream identity and maximum reuse

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. Original source blobs:

| Source | Blob | Partial coverage |
|---|---|---|
| `src/mainwindow.cpp` | `08ce1a7a599ef825967717b69626984cdc6d772b` | New-map QAction, dialog launch, mapCreated handler, map selection, Save/Save Project |
| `src/ui/newmapdialog.cpp` | `c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e` | Dialog validation and accept only |
| `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | Map selection and save dispatch only |
| `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | New-map registration and saveMap only |
| `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | setClean persisted state only |

Reuse original Porymap Qt QAction/QDialog/Project/Editor/Map/QFile/OrderedJsonDoc, not a replacement editor or file writer. The existing native Project retry test is a separate, already-green execution witness; do not confuse it with this source-only GUI call-chain analysis.

## Source-grounded dependency path

1. `MainWindow` connects `action_NewMap` to `openNewMapDialog`, which opens `NewMapDialog`. `NewMapDialog::accept` validates, saves UI settings, calls `Project::createNewMap` and then `QDialog::accept`. **There is no direct `saveMap` or `saveAll` call in that dialog handler.**
2. `Project::createNewMap` registers the Map in memory, explicitly marks `isPersistedToFile(false)`, and emits `mapCreated`. `MainWindow::onNewMapCreated` updates list models and selects the map via `userSetMap`; `Editor::setMap` loads/selects and attempts to watch its JSON path. This selected call path does not directly save the new map.
3. The explicit `Save` action invokes `MainWindow::save(true)` → `Editor::saveCurrent` → `Project::saveMap` and `saveGlobalData`; `Save Project` invokes `save(false)` → `Editor::saveAll` → `Project::saveAll`. `MainWindow` displays a failure warning only if the downstream boolean is false.
4. On the new-map `saveMap` path, script/text creation and `event_scripts.s` append ignore their returns; map JSON `OrderedJsonDoc::dump` is unchecked; `Map::setClean` marks persisted before optional layout save. The separate native Qt Project evidence has already demonstrated missing-script retry and duplicate global includes under injected filesystem failures.

**Decision:** The smallest compatible remediation candidate would propagate existing Qt write/close errors through original Project and Editor booleans, defer `setClean` until required writes succeed, and make global includes idempotent or recoverable. This is a **Phase 1 design finding only**, not an upstream patch, final remediation decision or Phase 2 implementation.

## Fail-closed controls and reviewer questions

`tools/phase1_porymap_gui_newmap_save_boundary.py` checks exact pinned blobs and scoped original function anchors, refuses unexpected direct save calls during creation/selection, verifies serializer/clean/layout order, and mutates every required anchor independently. The workflow stores JSON hashes of inspected function bodies and text logs. This does not execute a MainWindow, emit a real QAction, validate file-watcher callbacks, exercise populated alternate settings, prove a fresh-process reload, or establish crash-safe multi-file atomicity.

Independent reviewer must inspect complete files, signal ordering (including direct vs queued connections), QDialog lifetime, new-map event side effects, save error propagation, file-watch registration and suppression, on-disk reopen, and applicable Porymap LGPL-3.0/embedded permissive notices. Pinned FireRed source/assets retain separate licensing caveats. No whole-file approval or gate promotion.

**Status: source checker CI pending; Phase 1 gate FAIL_INCOMPLETE.**

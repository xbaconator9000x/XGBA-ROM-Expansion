# Phase 1 — Porymap new-map file watcher and pending-warning lifecycle

**SOURCE-ONLY / FAIL_INCOMPLETE / independent approvals 0/14,834.** New cross-file partial-function closure, not actual Qt MainWindow/file-watcher execution.

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`:

- `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`: `watchFile`, `ignoreWatchedFileTemporarily`, `recordFileChange`. Original Qt `QFileSystemWatcher` attaches paths; missing files are not registered, and the failure is only tracked when the path already exists. A change callback may re-arm a replaced path, then applies a five-second timestamp suppression window before recording and emitting `fileChanged`.
- `src/editor.cpp` blob `34112f6355b13d9381de7188624c36e5efeba151`: `Editor::setMap` attempts `watchFile(map->getJsonFilepath())`, without checking the return. Existing source closure shows a new map can be selected before its JSON is created. Whether the watcher later re-attaches requires runtime observation.
- `src/mainwindow.cpp` blob `08ce1a7a599ef825967717b69626984cdc6d772b`: `onNewMapCreated` selects the map. `showFileWatcherWarning` copies and clears `modifiedFiles` **before** checking whether an existing warning is active. This is a source-proven ordering hazard: additional notifications during a modal warning can be discarded, but actual event delivery and lost-reload behaviour are not yet reproduced.

## Reviewer handoff and negative controls

The checker extracts six original function bodies from three immutable blobs, enforces signal/re-arm/suppression/warning ordering, and rejects one targeted mutation per scoped anchor. This is partial-file evidence only. A genuine GUI test must use original Qt event loop and MainWindow, create an unsaved map, verify the missing-path watch attempt, save it, inject an external replacement and concurrent file changes while the reload warning is open, and observe whether `modifiedFiles`/watch paths recover. It must also distinguish self-generated save events and the five-second suppression window.

No replacement watcher, save logic or upstream patch is justified by source inspection alone. Porymap LGPL-3.0 and bundled component notices, and separate FireRed source/assets restrictions, remain applicable. All Phase 1 compatibility gates stay **FAIL_INCOMPLETE**; no independent semantic approvals.

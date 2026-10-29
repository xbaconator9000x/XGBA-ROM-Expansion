# Phase 1 — original Porymap MainWindow GUI new-map and native Qt watcher registration (2026-10-29)

**EXPERIMENTAL / FAIL_INCOMPLETE / 0 of 14,834 independent approvals.** No green claim until exact-head CI passes. This is a separate native MainWindow investigation, not a repeat of the previously green Project-only new-map retry or source-only GUI/file-watcher analyses.

## Immutable producer/consumer closure

- Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`, unchanged original Qt6 project, licensed upstream; `src/mainwindow.cpp` blob `08ce1a7a599ef825967717b69626984cdc6d772b`; `src/ui/newmapdialog.cpp` blob `c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e`; `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`. Additional partial dependencies: `src/editor.cpp`, `src/core/map.cpp`, `include/project.h` (whole-file review unresolved).
- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, copied project fixture, no upstream modification. Test-only map name `XGBAPhase1GuiNewMapFailure`.
- Original MainWindow initialization loads a real copied FireRed project. The test triggers actual `action_NewMap`, locates the actual `NewMapDialog`, fills its original name/group/layout fields and calls its unchanged `accept()`. It checks map creation and UI selection without disk persistence. It then uses actual `action_Save` with a matched `QFile` /dev/full failure on the newly generated script, checks map.json and persisted flag, and checks the GUI retry leaves the missing script absent while global event include remains singular.
- Native `QFileSystemWatcher` child of original Project is inspected. The new map cannot be watched before map.json exists; the first GUI Save does not itself attach that new path; explicit `Project::watchFile` after persistence can attach it. This is registration evidence only, **not** an observed `fileChanged` event, concurrent modal warning or lost notification.
- Test-only entrypoint replaces `src/main.cpp` in a temporary copied qmake project file; all original Porymap sources and behaviour are reused. Qt6 offscreen is still real Qt code but not manual desktop interaction. Filesystem failures are synthetic, not real disk exhaustion, crash durability or production deployment.

## Fail-closed verification and reviewer handoff

`tools/phase1_porymap_gui_new_map_watch.py` pins original Git revisions and three source blobs; requires one strict native JSON transcript, ten true and two false scope flags, FAIL_INCOMPLETE/zero approvals, and mutates every asserted field to require rejection. Build, native execution and artifacts must be checked at the **exact** PR head.

Partial per-file records: `src/mainwindow.cpp` — GUI action registration, dialog lifecycle, map-created signal and Save QAction; `src/ui/newmapdialog.cpp` — input validation, `createNewMap` and signal propagation; `src/project.cpp` — `saveMap` collateral, ignored script write errors, persisted flag, watcher registration; `src/editor.cpp` — map selection/watch attempt; `src/core/map.cpp` — persisted/clean state. Each requires independent whole-file review and external approval; this dossier does not count as one.

Unresolved: GUI modal file-watcher warning concurrency, actual filesystem notification delivery, populated alternate settings, fresh-process reload, full multi-file rollback and fsync, stock ROM/runtime interoperability and all licensing/redistribution assessments. All gates remain FAIL_INCOMPLETE, independent approvals 0.

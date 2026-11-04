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

## Native QFileSystemWatcher event-loop extension (new, not yet green)

A test-only addition to the same original full MainWindow harness connects an observer to the unchanged original `QFileSystemWatcher::fileChanged` signal **after** explicit `Project::watchFile(json)` succeeds. It appends one legal JSON whitespace byte to the real watched `map.json`, flushes/closes the QFile, and processes native Qt events for at most four seconds. The test requires actual matching-path signal delivery and reports `file_changed_signal_tested=true` only after the assertion. The original Project and MainWindow handlers remain connected. At that stage, this extended registration evidence to native Qt event delivery but did **not** establish a simultaneous active modal warning, automatic rearm, or durable recovery. Existing green save-failure and watcher-registration checks remain intact; all exact-head workflows must pass before reporting this as verified. Per-file coverage remains partial and independent approvals remain zero.

## Atomic replacement, watcher rearm, and fresh-process reopen extension (2026-11-04; exact-head CI pending)

The native GUI harness is extended from its existing actual `MainWindow` new-map action and first save. After the previously observed failed-script retry, it manually registers the now-existing `map.json` (the first save still does **not** auto-register it), then uses Qt `QSaveFile` to atomically replace that watched file with semantically identical JSON plus legal whitespace. The test requires the original `QFileSystemWatcher::fileChanged` delivery, the original `Project::recordFileChange` rearm to restore the path, and a second file-change delivery after rearm. This exercises the cross-component file-replacement transition in the unchanged pinned app and Qt event loop; it does not claim that Porymap itself uses `QSaveFile`.

The harness also injects a Qt `QSaveFile::commit()` failure by renaming the target's parent directory after the temporary file has been opened. It requires the failed commit and preservation of the prior sentinel bytes after restoring the directory. This is a controlled host-filesystem failure at a test-only `QSaveFile` boundary, **not** a Porymap save failure, a measured failed `rename(2)` syscall, a permission-denial test, or a simulated `fsync` failure. The pre-existing `/dev/full` MainWindow save test remains the separate actual original-Porymap write-failure witness; its interpretation is unchanged.

After the native MainWindow test process exits, the same full pinned Qt app is launched in a **second OS process** with `--cold-reopen`. That process opens the same copied FireRed project through original `MainWindow::initialize`, selects the persisted synthetic new map, parses its disk JSON, and requires the original watcher to register the now-existing map path. The machine verifier requires one normal-run record and one cold-process record, both with exact field sets, and rejects mutations to every asserted field. The generated JSON records SHA-256 digests of both raw native transcripts; the artifact contains the machine dossier and the two text logs.

### Dependency and provenance boundary

| Dependency | Immutable source / blob | Role in this experiment |
|---|---|---|
| Porymap `src/project.cpp` | `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`, blob `d43b0949303433111d4478ad76117c2b3445dd13` | Original `Project::watchFile`, `recordFileChange`, save path and watcher ownership |
| Porymap `src/editor.cpp` | same pin, blob `34112f6355b13d9381de7188624c36e5efeba151` | Original map selection and initial watcher-registration attempt |
| Porymap `src/mainwindow.cpp` | same pin, blob `08ce1a7a599ef825967717b69626984cdc6d772b` | Original New Map action, Editor lifecycle, save path and watcher-warning state |
| Porymap `src/ui/newmapdialog.cpp` | same pin, blob `c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e` | Original dialog acceptance and `Project::createNewMap` lifecycle |
| FireRed project | `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` | Disposable project/map/assets fixture; no upstream edits |
| Qt `QFileSystemWatcher` / `QSaveFile` | CI-installed Qt 6 host libraries | Native filesystem notification, atomic replacement and controlled failed commit |

The whole pinned Porymap application and its resources are built in CI; the test entrypoint is the only substituted source file. The pinned project and game assets remain in the disposable runner checkout and are not uploaded. The Porymap root `LICENSE.md` is LGPL-3.0; the evidence artifact is limited to generated JSON and logs, not the application binary or upstream assets. The FireRed checkout has no root `LICENSE` file in the pinned tree inventory; this test makes no licensing or redistribution determination for its game-derived assets.

**Strict limits:** exact-head runtime results remain pending until both dedicated push and PR jobs pass. The test does not execute the simultaneous active modal-warning path or establish dialog/editor-state retention, does not inject permission or `fsync` failure, and does not establish power-loss durability. The rename-directory failure is not kernel-syscall attribution. No full-file approval, upstream change, gate update or Phase 2 work is implied; Phase 1 remains `FAIL_INCOMPLETE`, 0/14,834 independently approved.

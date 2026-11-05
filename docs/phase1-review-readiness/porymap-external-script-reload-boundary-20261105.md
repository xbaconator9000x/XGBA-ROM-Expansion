# Phase 1 — Porymap external-script reload boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package examines the pinned Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116` script-label cache, script-file watcher, disk line lookup, and detached-process startup boundary. It adds no new whole-file source inventory: all twelve rows are reused context from prior packages.

## Bounded source closure

The CI matrix records the exact pinned Git blob, full-byte SHA-256, byte/line counts, and role for each reused source:

| Source | Reused context |
|---|---|
| `include/core/map.h`, `src/core/map.cpp` | Per-map script cache, filepath, and `QFileSystemWatcher` invalidation |
| `include/core/parseutil.h`, `src/core/parseutil.cpp` | Raw-script label and line lookup APIs |
| `include/editor.h`, `src/editor.cpp` | Script navigation and detached-process startup |
| `include/project.h`, `src/project.cpp` | Project-level watcher/re-arm and pending file changes |
| `include/mainwindow.h`, `src/mainwindow.cpp` | External-change warning and reload handoff |
| `include/ui/message.h`, `src/ui/message.cpp` | Question dialog used by the warning |

The event-script consumer, new-map watcher, external-editor preference, and transaction dossiers are hashed as prior context. This package does not repeat those packages' tests or represent their files as new coverage. The Porymap root `LICENSE.md` identity and license text are also recorded. The selected files do not include SQLite or Qt translation files.

## Source-grounded behavior

In the pinned source, `Map::getScriptLabels` reads the selected scripts file and caches labels, then connects the map's file watcher to `Map::invalidateScripts`. The invalidation method clears the loaded flag, deletes/resets that watcher, and emits `scriptsModified`. `Editor::openScriptInFile` asks `ParseUtil::getScriptLineNumber` for the label's line; the parser reads the supplied file path at lookup time. `Editor::startDetachedProcess` returns Qt's detached-start result. Its caller does not retain a process handle or receive a later editor exit status.

The separate `Project` watcher and `MainWindow` warning/reload flow are included only as reused source context. They are not exercised by this package. In particular, this is not a test of the active-window/modal warning, pending-change retention, project reload, dirty map state, or an external editor's file replacement behavior.

## Native Qt observation

The checker extracts unchanged pinned function bodies from `src/core/map.cpp`, `src/core/parseutil.cpp`, and `src/editor.cpp`, then compiles them against Qt6 Core with test-only model/config/logging stubs. Its temporary test binary is placed under the checkout root and removed after execution, so detached launch does not depend on `/tmp` being executable. The native test uses an actual `QFileSystemWatcher` on a temporary `.inc` file:

1. It asks the original map method to load and cache an initial label and attach the watcher.
2. The harness overwrites that file in place. Before processing the watcher event, the original map method still returns its cached label, while the original editor/parser path immediately resolves current disk content and its changed line.
3. Processing the real Qt `fileChanged` event invokes the original map invalidation method. A subsequent label request sees the new label and establishes a watcher again.
4. It executes the original detached-process method with a temporary helper executable, verifies its launch result/PID and a helper-created marker, and rejects a missing-executable control.

This is native isolated Qt evidence of the original methods with controlled temporary files and a helper process. The helper is not a text editor, its exit status is not observed, and no external-editor save occurred. The writes are harness-controlled in-place writes, not an atomic replacement or a durability test. The negative controls reject stale cached labels before watcher delivery, missing labels, and missing process executables; they do not prove every filesystem backend or platform behaves identically.

## Limits and status

No Porymap GUI, `Project` watcher, `MainWindow` reload dialog, external text editor, editor-side save, dirty-state prompt, fresh-process project reopen, filesystem replacement, `fsync`, or hardware durability is tested. The native Qt compile and source/evidence mutation controls do not establish complete-file independent review. All source rows remain `NEEDS_EVIDENCE`; independent approvals remain `0/14,834`; Phase 1 remains `FAIL_INCOMPLETE`.

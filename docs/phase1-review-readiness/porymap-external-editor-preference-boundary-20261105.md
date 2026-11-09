# Phase 1 — Porymap external-editor preference boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This bounded package examines the pinned Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116` preference UI and its event-script external-editor handoff.

## Scope and prior coverage

Porymap does not contain an event-script text editing buffer in this path. Its event editor resolves a script label to a file and line, then delegates editing to a configured external process or desktop opener. Consequently, this package does not claim that Porymap itself edits script text or saves/reopens script contents. The native test below exercises only the original configuration writer used for preferences; it does not launch the preferences UI or external editor.

The three new source files are `include/ui/preferenceeditor.h`, `src/ui/preferenceeditor.cpp`, and `forms/preferenceeditor.ui`. The reused caller and persistence context comprises `include/editor.h`, `src/editor.cpp`, `include/config.h`, `src/config.cpp`, and `src/core/parseutil.cpp`. The editor/lookup files were already inventoried in the event-script consumer closure; the config files were already included in the transaction/persistence package. They are labeled as context, not new coverage. This is disjoint from PR #36's Poryscript emitter and FireRed script ABI work.

The machine-readable CI matrix records each original file's pinned Git blob, full-byte SHA-256, byte/line counts, and source-anchor line numbers. It includes the pinned root `LICENSE.md` identity and hashes the prior relevant dossiers. All file dispositions remain `NEEDS_EVIDENCE`; source identity and mutation checks are not independent semantic approval.

## Source-grounded behavior

The Preferences form documents `Goto Line Command`, `%F` (script filepath), `%L` (line number), and the fallback to the current map's scripts file when a requested script is not found. `PreferenceEditor::updateFields` loads the configured command; `saveFields` copies the UI field back to configuration, calls `porymapConfig.save()`, and emits `preferencesSaved()`. The accept path calls `saveFields()` and closes; Apply calls `saveFields()`, and Cancel closes without calling it. The save return is not checked at this UI boundary.

The previously inventoried `Editor` caller performs label-to-line lookup, substitutes the configured editor command, and invokes detached process launch, or uses `QDesktopServices` when no goto-line command is configured. The detached-launch result is discarded at this caller. This is source-level behavior only: process startup, editor interaction, editor-side saving, and script re-open are not exercised here.

## Compiled original-writer failure observation

The existing compiled-Porymap workflow compiles the unchanged pinned `KeyValueConfigBase::save()` function body from `src/config.cpp` against actual Qt6 Core, with test-only class and logging stubs. A normal file control verifies the expected config bytes; a controlled directory-as-file path verifies the original method returns `false` when `QFile::open` fails. A direct `QFile` control on Linux `/dev/full` observes the write failure; the unchanged original method nevertheless returns `true` after the same failed write because it does not inspect `QFile::write()`'s result or error state.

This is a native Qt observation of that isolated original method, not a full application or Preferences-dialog run. It does not show that configuration bytes were persisted after ENOSPC. The UI caller also ignores the method's return, so its `preferencesSaved()` signal is not proof of durable preference storage. The test does not establish fsync or hardware durability.

## Validation and licensing

The checker pins all sources to the original Porymap commit, checks the complete selected-file identity, and applies source and evidence mutation controls. A deterministic gzip-compressed tar packages the dossier and machine-readable matrix; CI emits the archive SHA-256. These controls reject the specific tested mutations and do not establish exhaustive soundness.

The pinned Porymap root `LICENSE.md` contains GNU LGPL text; CI records its source identity and full-byte hash. Qt6 Core is a system dependency for the isolated compile. This bounded source set does not include SQLite or Qt translation files.

## Limits

No Porymap-owned script buffer exists in this path, and no external editor process, text editing, script-content save/reopen, full GUI behavior, or fsync durability is tested. The full Porymap build in the existing workflow is not evidence that these interactions ran. The native isolated writer test is not a GUI observation, and neither it nor the source matrix constitutes complete-file independent review. Independent approvals remain `0/14,834`; Phase 1 remains `FAIL_INCOMPLETE`.

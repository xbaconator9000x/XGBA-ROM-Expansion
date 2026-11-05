# Phase 1 — pinned Porymap event-script consumer closure

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package traces the event-editor script dropdown and open-in-text-editor path in Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`. It is distinct from PR #36's Poryscript emitter / FireRed script ABI review.

## Bounded source closure

The checker inventories twelve complete pinned Porymap files. Six files are new to this package's source inventory; six are reused as prior context and are not counted as new coverage. Each row records the exact upstream Git blob, full-byte SHA-256, byte length, line count, role, and disposition. It rejects a different upstream revision or changed working-tree file.

| Source file | Role | Coverage |
|---|---|---|
| `include/editor.h` | Editor script navigation API | New |
| `src/editor.cpp` | Map request connection, script lookup order, line opening | New |
| `include/ui/eventframes.h` | Event-frame script dropdown and button declarations | New |
| `src/ui/eventframes.cpp` | Map/project label population, completer, open action | New |
| `include/ui/noscrollcombobox.h` | Editable dropdown API and completion signal | New |
| `src/ui/noscrollcombobox.cpp` | Combo activation/text-edit completion behavior | New |
| `include/core/map.h` | Script label and open-request interfaces | Reused prior context |
| `src/core/map.cpp` | Per-map labels, file selection, event labels, watcher invalidation | Reused prior context |
| `include/core/parseutil.h` | Script parser API and zero-on-not-found contract | Reused prior context |
| `src/core/parseutil.cpp` | Raw assembly/Poryscript label and line parsing | Reused prior context |
| `include/project.h` | Project-wide script label collection interface | Reused prior context |
| `src/project.cpp` | Project-wide event-script label collection | Reused prior context |

The reused files were already involved in transaction, watcher, and generated-script evidence. That prior presence does not constitute complete-file review; the matrix keeps them separate from the six newly inventoried UI/Editor sources. The three prior dossier byte hashes are also emitted in CI.

## Source-grounded consumer path

The pinned source anchors establish the following control flow:

1. `EventFrame::populateScriptDropdown` starts with labels for the current event group from the map. Depending on the autocomplete setting, it appends project-wide labels, then creates a case-insensitive, substring-filtering `QCompleter`.
2. The event frame's script button sends the selected combo text through `Map::openScript`; the map emits `openScriptRequested`, which the editor connects to its `openScript` handler.
3. The editor tries the current map's script filepath first, then the project's event-script files. A candidate is opened only when `ParseUtil::getScriptLineNumber` returns a nonzero line.
4. The parser chooses raw-label parsing for `.inc`/`.s` files and Poryscript label parsing for `.pory`; the API documents zero when the requested definition is absent.
5. `NoScrollComboBox` emits its editing-finished signal for dropdown activation and line-edit completion. This is a source contract, not evidence that a GUI interaction was run.

This package does not claim that every script reference is valid, that duplicate labels resolve uniquely, or that external editor launch succeeds. It does not duplicate the separate Poryscript compiler/FireRed ABI work.

## Validation and licensing

The existing compiled-Porymap workflow builds the pinned full Qt application, then checks the source closure. The checker has one source mutation per matrix row and eleven evidence-field negative controls. These prove that the checker rejects the tested mutations; they do not prove exhaustive semantic soundness.

The pinned Porymap root `LICENSE.md` contains GNU LGPL text. The CI JSON records its exact blob and full-byte SHA-256. A deterministic gzip-compressed tar contains the dossier and machine-readable matrix; CI emits the compressed archive's SHA-256 sidecar. These hashes are identity and artifact-integrity evidence, not approval or a redistribution conclusion.

## Limits

The workflow compiles the original application, but this package does **not** execute the GUI, interact with a real event dropdown, launch an external text editor, or independently exercise the parser with runtime fixtures. UI and parser observations remain source-level only. The archive, hashes, compilation, and mutation controls do not equal complete-file independent semantic review. All rows remain `NEEDS_EVIDENCE`; independent approvals remain `0/14,834`; Phase 1 remains `FAIL_INCOMPLETE`.

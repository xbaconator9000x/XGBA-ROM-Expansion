# Porymap editor map-switch undo-pruning closure

Status: **BOUNDED NATIVE Qt METHOD WITNESS / `FAIL_INCOMPLETE`**. This follow-up addresses the prior packet's explicit limitation: `Editor::unsetMap` and `Editor::setMap` were previously source-checked, not executed through the active `QUndoGroup`. It does not repeat the prior direct-stack/mirrored-command witness and does not certify the full editor GUI, project persistence, cold reopen, gameplay, or independent approval.

## Reconciliation and scope

- Exact starting PR #27 head: `2b0dfb856361965e49ea3d866339645278fb297e`.
- Porymap source pin: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.
- FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and Poryscript `c32481161c767b25a3425fa9f1f8729927ff3d55` are unchanged and not exercised.
- PR #36's 11 changed paths were reconciled; none is a Porymap source path.
- The prior cross-map packet's five new complete source files, all reused context, and direct `QUndoStack` witness were not re-inventoried. Two additional, genuinely unlisted Porymap UI source files are included because they are a concrete upstream producer into the affected command path. No larger file quota was justified.
- Prior packet dossier SHA-256: `9ec765b5c6dbf22868987ec95a797525b905c8e3e97e4d7152bbfc48d56f1432`; deterministic dossier archive SHA-256: `f05a398aeca729476c6ff4c7b1120f2672ab1c520982ab250ca4b4cd4d50f17f`. The prior native tool and harness source hashes were `7d5825ef42caa5bb0cec86fb82db394c4cb1486054f018af9c3e1e08ef614d15` and `8d6e4e0febed139ec50d9bd2e807552c71a292385f24d2d3bf029914d9f7890e`; the prior tool's overlap scanner was narrowly taught to ignore only this downstream dossier/tool.

## New complete pinned files

| File | Git blob SHA-1 | Full-byte SHA-256 | Bytes / lines | Whole-file semantic focus |
|---|---|---|---:|---|
| `src/ui/newmapconnectiondialog.cpp` | `b9938f3e8af71b10935e27ab7be1687f17283b91` | `51c96d5717ca5ca4ef1d9f92fd149977342257543d5a6cb81f47a9582f3f237b` | 4024 / 105 | Map/direction defaults, validation, Dive/Emerge replacement, and add-signal producer |
| `include/ui/newmapconnectiondialog.h` | `db9eee49ff3fb976be7dc4454cdaac5b3cd7bd8f` | `f7bdeca282eaf9956fc5cc43df819fffb3f08dc293537d9dda47c9e35b9c6d46` | 836 / 35 | Dialog ownership fields, acceptance interface, and add/replace signal declarations |

Both source rows are `NEEDS_EVIDENCE`; no earlier per-file dossier row or archive receipt exists for either path. Exact row digests and evidence dispositions are emitted by `tools/phase1_porymap_editor_map_switch.py`. The adjacent generated UI form is not included as a reviewed source file; its behavior remains an explicit untraced dependency.

Reused, pinned source anchors (not new file inventory): `src/editor.cpp` blob `34112f6355b13d9381de7188624c36e5efeba151`, SHA-256 `a505ba77243efdcaa2da8cce448e97ce80aa355145fb567290cb6d549bead270`; `src/core/map.cpp` blob `47b279919bd4afcc76b88f9eeecd459b3452989f`, SHA-256 `c2406bb2dd5950ee226a4e7fc8e1d198c70915cb638fd706a814b87de22ab332`; and prior packet's command/header identities are retained there. All were previously inventoried as reused context.

## Caller and ownership closure

1. `MainWindow::on_pushButton_AddConnection_clicked` constructs this dialog and connects `newConnectionedAdded` to `Editor::addNewConnection`. The dialog validates the chosen map against its list, permits custom direction text, and emits the map/direction request; Dive/Emerge may instead use the replacement signal.
2. `Editor::addNewConnection` constructs a `MapConnectionAdd` command and commits it to the current map. That command's direction-masked ID is part of the already pinned cross-map command source closure.
3. `Map::commit` pushes into the map's owned `QUndoStack`. On map change, `Editor::unsetMap` invokes `Map::pruneEditHistory`; `Editor::setMap` adds and activates the newly loaded map's stack in its `QUndoGroup`.
4. The prune set contains the bare connection command IDs, while `MapConnectionMove::id()` ORs the direction mask into the base ID. Exact `QSet::contains(command->id())` comparison therefore misses the masked command. A masked command survives the old stack when its map is unset. `QUndoGroup` stops routing commands to that stack while another stack is active, but the original stack remains registered and becomes active again when that map is selected.

## Native Qt evidence and controls

The new test compiles unchanged pinned bodies for `getConnectionDirectionMask`, `MapConnectionMove::id`, `Map::pruneEditHistory`, `Editor::unsetMap`, and `Editor::setMap`, with real Qt 6 `QUndoStack`/`QUndoGroup`. Test-only Map/Project/Editor shells retain map-owned stacks; the command's undo/redo state mutation is a small test double, not the upstream command implementation.

Observed controls:

- The original move-ID body produces the pinned base ID OR the `up` direction mask.
- An unmasked base-ID control is marked obsolete by the original prune body; the masked move remains non-obsolete after the actual extracted `Editor::setMap`/`unsetMap` transition.
- While map B is active, the actual Qt group does not route undo to A. Switching back to A reactivates the retained command; undo then overwrites a later B-side test mutation, and redo reapplies the earlier A value.

This is method-level native Qt evidence, not an actual Porymap GUI session. It does not execute the upstream command constructor or its original undo/redo bodies, generated UI interaction, actual `Project::loadMap`, JSON writing/readback, save prompts, cold reopen, game assets, or gameplay. Dialog caller edges are source-checked only. The test demonstrates a concrete QUndoGroup routing consequence for the observed ID/pruning mismatch, not durable cross-project data loss.

## Evidence and licensing limits

- All new file rows and the exact source/evidence identities remain `NEEDS_EVIDENCE`; CI success is not semantic approval. Preserve `FAIL_INCOMPLETE`, zero independent approvals.
- Porymap root `LICENSE.md` blob `65c5ca88a67c30becee01c5a8816d964b03862f9`, SHA-256 `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`, contains LGPL-3.0 text. No selected file-specific license notice was found; this is not a legal redistribution determination.
- The witness uses the host's Qt6 Widgets libraries. Qt translations, SQLite, GUI behavior, and hardware durability are not exercised.
- Untraced edges: generated form behavior, actual QDialog signal timing/destruction across map switches, Project object/cache lifetime in a full session, original connection-command destructor/undo/redo behavior under stack teardown, map JSON save/reload, and game consumption.

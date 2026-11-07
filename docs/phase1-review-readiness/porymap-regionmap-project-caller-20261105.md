# Phase 1 — RegionMap entry gesture to Project caller boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package extends the earlier RegionMap save/dirty-state witness upstream to the entry-drag producer and shared entry hash. It does not repeat the prior save failure, watcher, or full Porymap build experiments.

## Pinned source inventory

All sources are pinned to Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. The four new complete source files were not present in the earlier readiness tool/dossier inventories. Their original per-file dossier-row and archive digests are unavailable, so those fields and each source disposition remain `NEEDS_EVIDENCE`.

| New complete file | Git blob SHA-1 | Full-byte SHA-256 | New dossier-row SHA-256 | Bytes / lines | Boundary |
|---|---|---|---|---:|---|
| `src/ui/selectablepixmapitem.cpp` | `267fbd1fc63f08efef4b2ddb3f1ad4845816fc78` | `2fc424561b9958d71d8e097fb691756c67c1871e8402651c69ed79d0a0816cba` | `7a1072e1fb67288217d00b53559d058ea52b8dd601ee4ae385d79010a6f3be54` | 5547 / 141 | Pixel coordinate clamping and conversion to a tile cell |
| `include/ui/selectablepixmapitem.h` | `a267291efbc6c3a4811e757b64a9def9f67b8d3d` | `51dc65ebd2669dc42f5201f3f6ff089dfc6b7401f77f10f208db9bba36c5b07b` | `50edfc7f0b96fe5907c642f3ed2569968db5e79127b9bc248a562f5e2473661b` | 2880 / 66 | Base item interface and event inheritance |
| `src/ui/regionmapentriespixmapitem.cpp` | `5bf9a08f6f5588577e57e729ee54f535b324ea81` | `54cf0eaced29720b0c5e030f9003f6830dcfa59e8c769b778078f7a83f24adaf` | `18e1c060add7d9b9f096e38ad9d76fe6360b9a94cda70732a0b2340eab170259` | 4965 / 137 | Entry display, selection, and bounded drag signal |
| `include/ui/regionmapentriespixmapitem.h` | `12808c330b7ee6a778d6b8eaf9bccba72b2f7a0e` | `48f009492b826709cc0c8ba02db61f8b315fbf63746f9d0f9b311370fc866c3a` | `d57838c0c208603ac7585f2da032d1ca3b09de6e5cf9faadf9e2f69d7e7304f2` | 1288 / 44 | Entry item state, signal, and event-handler interface |

Reused caller/context files are hash-checked separately by the machine record: `src/ui/regionmapeditor.cpp`, `src/core/regionmap.cpp`, `src/core/regionmapeditcommands.cpp`, `include/core/regionmap.h`, `include/core/regionmapeditcommands.h`, and `src/project.cpp`. These are not counted as new inventory rows. Their use here is limited to verifying the item-signal connection, the edit slots, the shared entry-hash relationship, the original undo command, and the downstream Project writer call.

The earlier RegionMap package's overlap scan excludes only this later packet's tool and dossier because they identify those files as reused context. This packet separately asserts that its four new complete-file identities are disjoint from all six files in the earlier RegionMap inventory.

The pinned Porymap root `LICENSE.md` blob is `65c5ca88a67c30becee01c5a8816d964b03862f9`, SHA-256 `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`; it contains LGPL-3.0 text. This is not a redistribution determination. No SQLite or Qt translation files are included. FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and Poryscript `c32481161c767b25a3425fa9f1f8729927ff3d55` pins are unchanged and not exercised in this package.

## Caller and state path

1. `SelectablePixmapItem::getCellPos` clamps the item coordinate to the current pixmap and divides by the configured cell size.
2. `RegionMapEntriesPixmapItem::mousePressEvent` captures the selected entry-relative offset. Its `mouseMoveEvent` rejects movement when not dragging, when the requested rectangle exceeds the tilemap/padding bounds, or when the position did not change; otherwise it emits `entryPositionChanged(x, y)`.
3. `RegionMapEditor::displayRegionMapEntriesImage` connects that signal to `onRegionMapEntryDragged`. The slot invokes the original x and y value-change handlers; each updates `region_map_entries` and pushes an `EditEntry` onto the active `QUndoStack`.
4. `RegionMapEditor::setup` passes `&region_map_entries` into each `RegionMap`. `RegionMap::getEntry`/`setEntry` read and update that same hash. `EditEntry::undo` writes its saved old entry back through `RegionMap::setEntry`, so the shared editor/Project-facing hash returns to the prior coordinates on undo. `EditEntry` also merges consecutive edits for the same map and section.
5. The existing `saveRegionMapEntries` path copies this hash into `Project` and calls `saveRegionMapSections`; its writer/error behavior was covered as source context in earlier packages and was not executed here.

This closes a source-level concern about whether undo restores a detached entry copy: the pinned setup passes a shared hash pointer, and the extracted native methods exercise that shared-state transition. It does not establish that a failed Project write rolls back edits or that the actual editor reopens a Project from disk.

## Bounded native Qt witness

The test compiles unchanged pinned method bodies for pixel-to-cell conversion, entry press/move/release, the RegionMap entry getters/setters, the RegionMapEditor drag/coordinate slots, and `EditEntry` construction/redo/undo/merge. It uses real Qt6 `QGraphicsSceneMouseEvent`, `QPixmap`, `QObject::connect`, and `QUndoStack`, with test-only object-model shells.

- A real Qt signal/slot connection carries an in-bounds drag to the original editor slot; the two coordinate updates merge to one undo command, update the shared entry hash, and mark history dirty.
- Undo restores the original x/y values through `RegionMap::setEntry` to the same hash used by the editor; the stack returns to its clean index. Redo restores the moved values.
- Out-of-bounds movement and movement after mouse release emit no additional signal.
- Four pinned-source mutations and fifteen evidence mutations are rejected by the deterministic checker.

This is native Qt execution of extracted original methods with test-only model objects. The test invokes the event methods directly; it does not dispatch real GUI input through a running Porymap window. It does not invoke `Project::saveRegionMapSections`, write or compare disk bytes, test the actual Project loader, or exercise a cold Project reopen. “Undo restores shared entry state” is not application rollback after a failed write.

## Machine record and unresolved boundaries

The workflow emits per-file Git blob and full-byte hashes, new dossier-row hashes, `NEEDS_EVIDENCE` values for unavailable original row/archive hashes, prior-dossier hashes, a deterministic dossier-only archive hash, source/evidence mutation counts, and the native test record. The archive excludes upstream source copies. The current dossier SHA-256 and archive SHA-256 are emitted in the workflow JSON artifact; the archive digest is intentionally not embedded in its own archived dossier.

Still unresolved: actual MainWindow/RegionMapEditor GUI delivery; Project save failure after an entry drag; whether dirty/close UI prompts retain the edit after a failed write; actual Project load of saved RegionMap sections; full cold Project reopen; storage durability; and FireRed gameplay behavior. No writer rollback, full application run, independent review, approval, or Phase 1 gate transition is claimed.

# Phase 1 P0 — mirrored map edits are dirty on both maps, but Save Current persists one

**27 October 2026 · EXACT-PINNED SOURCE CALL-CHAIN REVIEW · NOT APPROVED.** Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. This closes the previously unresolved **dirty-state propagation** portion of the connection-ownership dossier; it does not demonstrate a Qt GUI failure or claim loss of data. **Phase 1 FAIL_INCOMPLETE; independent whole-file approvals 0/14,834.**

## Pinned source files and relevant anchors

| Exact file | Git blob SHA-1 | Source lines |
| --- | --- | --- |
| `src/core/mapconnection.cpp` | `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` | 19–42 mirror resolution; 50–60 lazy map load; 97–169 propagated setters |
| `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | 328–381 connection ownership; 393–409 dirty-state test |
| `src/core/editcommands.cpp` | `684d98c7ea8b2c600a5fb8888831b95723e741f3` | 571–695 mirrored edit commands; 703–783 add/remove |
| `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 290–325 map load signal; 1315–1326 save all; 1329–1451 save map |
| `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | 83–110 Save Current/Save All |
| `src/mainwindow.cpp` | `08ce1a7a599ef825967717b69626984cdc6d772b` | 663–671 mark edited; 819–825 connect project signal; 2713–2715 connect map signal |
| `src/config.cpp` | `9264f99bb18e0a725ef023f514c00df529d1d28d` | 324–336 mirror preference default true |

## MIR-001 — reciprocal edit marks the target map dirty in the normal MainWindow path

For a source map A with a reciprocal matching connection in map B, `MapConnection::findMirror` resolves B by calling `project->loadMap` (mapconnection.cpp:29–41, 55–60). The project emits `mapLoaded(map)` on the first successful load (project.cpp:310–325); the MainWindow has already connected that signal to `onMapLoaded` (mainwindow.cpp:819–825), which connects B's `Map::modified` to `markMapEdited(B)` (2713–2715).

A mirrored offset edit calls `B_connection->setOffset(-offset, false)` before setting A's offset (mapconnection.cpp:155–169). That target setter calls `markMapEdited`, which emits `Map::modified` (mapconnection.cpp:50–53; map.cpp:397–399). The MainWindow slot sets **B.m_hasUnsavedDataChanges = true** (mainwindow.cpp:663–671). `Map::hasUnsavedChanges` explicitly includes that flag (map.cpp:407–409). Mirrored direction and target changes follow related paths (mapconnection.cpp:123–152). The edit commands capture the mirror preference when constructed (editcommands.cpp:571–695), so changing the UI preference later does not retroactively alter that command's propagation policy.

**Resolved source-level question:** the matching target's modified signal is not simply lost because B is not the displayed map. In the normal MainWindow wiring, B becomes dirty. This is a *conditional source call-chain result*, not an executed Qt signal/slot assertion.

## MIR-002 — Save Current is not a two-map persistence transaction

`Editor::saveCurrent` delegates to `save(true)`; that branch saves only `this->map` (or the current layout) and then global data (editor.cpp:83–109). `Project::saveMap` serializes the passed map's active connection list and marks **that map** clean after writing (project.cpp:1329–1451). It does not iterate other dirty maps. `Project::saveGlobalData` writes global project resources, not B's `map.json`.

Therefore, in the conditional A→B mirror-edit path above, **Save Current while A is displayed can persist A's new connection but leave B's mirrored change dirty and not yet written to B's map.json**. This is an explicit persistence-scope distinction, not proof that Porymap silently loses B's edit: the dirty flag remains available for UI warnings and a later Save All. `Project::saveAll` iterates all maps, calling `saveMap` for each loaded one (project.cpp:1315–1326); this is broader scope but not an atomic multi-file transaction.

## MIR-003 — source identities and editor/ROM round-trip requirements

The source connection identity is a pointer owned by a Map, while mirror pairing is **inferred** from reciprocal names, directions and offsets. `findMirror` explicitly returns the first match and warns about duplicates (mapconnection.cpp:29–41). Changing the target/direction can reassign a mirror's parent map; the new parent may be lazily loaded and dirtied. Undo/redo uses captured mirror preferences and may re-resolve a different matching object (editcommands.cpp:703–783).

For an authoritative editor/ROM refresh, use an explicit **two-map change set** with source identities, both before/after connection arrays, dirty state, persistence status and ambiguity flags. Never equate `saveCurrent()` success with every affected map being durably saved, and never use pointer identity or inferred reciprocal pairing as a stable cross-import ID.

## Outstanding evidence and acceptance

1. Run a pinned Qt integration fixture with maps A and B, a matching mirror, and both mirror toggle settings. Assert B's dirty flag, JSON before/after Save Current and Save All, plus UI unsaved warning behaviour.
2. Exercise duplicate reciprocal links, edited target names, direction changes, undo/redo and map switches; ensure no unexpected reassociation or lost edits.
3. Test save failures and partial multi-file writes; document a recovery protocol rather than assuming atomicity.
4. Compare the resulting authored JSON to generated FireRed 12-byte connection records and native direction-selection semantics. Preserve `connections_no_include`, unknown fields and per-map order.
5. Independently review the **complete** pinned source files and external runtime/Qt evidence. No approval credit follows from this dossier.

**Disposition: normal GUI dirty-state propagation source-closed; Save Current two-map persistence gap source-established; actual Qt round-trip, failure recovery, native bytes and independent reviews remain OPEN.**

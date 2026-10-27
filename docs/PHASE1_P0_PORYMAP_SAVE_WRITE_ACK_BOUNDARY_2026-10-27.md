# Phase 1 P0 — Porymap save success and clean-state are not durable-write acknowledgements

**27 October 2026 · pinned source-level dependency trace · NOT a Qt fault-injection result or independent approval.** Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Phase 1 remains **FAIL_INCOMPLETE**. This extends the earlier mirrored Save Current and map-groups metadata dossiers with a separate *write-error propagation* boundary.

## Pinned source owners and consumers

| Owner | Exact pinned blob SHA-1 | Relevant lines |
| --- | --- | --- |
| Porymap `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 876–912 map-group writer; 1315–1451 save-all/map; 1474–1488 global save; 1714–1733 text writers |
| Porymap `include/lib/orderedjson.h` | `cb5139d37d955f2469ebd2eaaf089668b82884fe` | 224–239 `JsonDoc::dump` |
| Porymap `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | 401–409 clean-state/unsaved predicates |
| Porymap `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | 83–110 Save Current/All caller |
| Porymap `src/core/mapconnection.cpp` | `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` | 29–60 mirror resolution and parent-map dirty marking |
| FireRed `data/event_scripts.s` | `88d75946a7300ccf952f4a36c283966c6aebf5c0` | 90 onward compiled script `.include` consumers |
| FireRed `map_data_rules.mk` | `b32b85a91d9460642345ca983c37d165e820741f` | 30 onward map JSON generator dependencies |

The cited file blobs were inspected at immutable upstream commits. These are **call-chain excerpts, not whole-file semantic dispositions**. A reproducible source checker is tracked separately; the document itself is not an executed Qt test.

## PWS-001 — successful open is the only map JSON I/O error boundary

`Project::saveMap` opens `map.json` with `QIODevice::WriteOnly` and returns false if **open** fails (project.cpp:1359–1365). Once open succeeds, it builds the JSON, calls `OrderedJsonDoc::dump(&mapFile)`, closes the file, then calls `map->setClean()` (1440–1447). No `QFile::error()`, `QTextStream::status()`, write count, flush result, read-back comparison or atomic rename is checked between dump and clean-state transition.

`JsonDoc::dump(QFile*)` is declared **void** (orderedjson.h:231–235). It constructs a `QTextStream` and streams JSON plus newline without returning a status. The caller therefore cannot infer write success from its return. `Map::setClean` clears the edit history's dirty marker, `m_hasUnsavedDataChanges`, and sets `m_isPersistedToFile=true` (map.cpp:401–405). Thus **if an underlying stream/close write fails after successful open**, the save path can report success and mark the map clean without verifying that the new JSON was durably written. This is a **conditional source-path risk**, not an observed disk failure or an assertion that ordinary saves fail.

## PWS-002 — new-map collateral script errors are discarded

For a not-yet-persisted map, `saveMap` creates a scripts file, optionally a text file, and appends their `.include` directives to the global event-script assembly (project.cpp:1333–1356). All three calls to `saveTextFile`/`appendTextFile` have their **boolean return values ignored**. Both helper methods return false if `QFile::open` fails, but after opening they call `file.write(text.toUtf8())` without checking the returned byte count and return true (project.cpp:1714–1733).

Consequently, a **script file open failure** can be logged yet the map JSON may still be written, the map marked persisted, and `saveMap` return true. A deterministic Qt fixture can create a *directory* at the intended `scripts.inc` file path before saving a new map, so that opening that path as a file fails while `map.json` remains writable. The fixture is proposed, **not yet executed**. FireRed's pinned `data/event_scripts.s` includes per-map `scripts.inc` files, so an uncreated script is a build dependency, not merely cosmetic metadata. When Poryscript mode is enabled, generated `.inc` and its `.pory` producer must also be traced; no compiler outcome is asserted here.

## PWS-003 — global JSON and Save Current share the unchecked dump path

`Project::saveMapGroups` opens `map_groups.json`, invokes the same void `JsonDoc::dump`, closes the file and returns true without inspecting stream status (project.cpp:876–912). `Project::saveGlobalData` regards each subordinate writer's boolean result as authoritative, and clears `hasUnsavedDataChanges` when they all return true (1474–1488). `Editor::save(true)` calls `saveMap` (or `saveLayout`) and **still calls** `saveGlobalData` regardless of the first result (editor.cpp:91–109).

This means neither a successful Save Current return nor a clean global flag is a verified multi-file durability barrier. A write error in one stream can be masked by its writer's success return, and independent global files can be updated even if another save failed. This is separate from the previously documented normal behaviour that mirrored map B remains dirty after saving only map A. The map-group `connections_include_order` metadata-loss path remains a distinct issue even if every write succeeds.

## Required evidence before closing the boundary

1. Add a **Qt execution fixture** for the new-map `scripts.inc` directory collision; assert script-open failure, map.json outcome, `saveMap` return, map clean/persisted flags, and FireRed build failure or nonfailure separately.
2. Use an injected `QIODevice`/filesystem failure after successful open to test short writes, flush/close errors and JSON truncation. Record Qt version, platform and exact test result. Do not substitute the source checker for this.
3. Test `saveMapGroups` and `saveGlobalData` under controlled write failures; compare on-disk JSON with in-memory state, mirrored-map dirty state and user-facing save status.
4. Trace `saveTextFile`/`appendTextFile` and Poryscript-generated includes through actual FireRed build rules, compiled objects and runtime script pointers.
5. Require stable map/event IDs and a transactional sidecar/merge policy for PokéBacon; independently review complete pinned files. **No prepared-file or approval count is incremented.**

**Disposition:** conditional save-success/clean-state divergence is source-established; actual Qt fault-injection, generated-script compilation, emulator execution and independent approval remain **OPEN**. Phase 1 **FAIL_INCOMPLETE**.

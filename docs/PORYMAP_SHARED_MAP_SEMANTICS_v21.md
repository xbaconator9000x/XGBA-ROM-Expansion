# Phase 1 v2.1 — Porymap shared-map semantic contract

Pinned Porymap commit: `26b919d7ff4b54152de010abd5bf344af2ebe116`.

## Distinct inheritance relationships

The current Porymap data model has **two independent references**, rather than a single inherited map pointer.

- `Map::isInheritingEvents()` in [include/core/map.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/map.h) (Git blob `47d52b08e4a403e88c80c0d436f563460721e65d`) is true only if `m_sharedEventsMap` is non-empty **and the map has no local events**. Adding a local event changes this predicate.
- `Map::isInheritingScripts()` checks only `m_sharedScriptsMap`, independent of event sharing. [src/core/map.cpp:194–204](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/map.cpp#L194-L204) (blob `47b279919bd4afcc76b88f9eeecd459b3452989f`) chooses the scripts filename from the shared scripts map if configured, otherwise the map's own name, and falls back from Poryscript to normal script format if required.
- [Project::loadMapData, src/project.cpp:458–480](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L458-L480) (blob `d43b0949303433111d4478ad76117c2b3445dd13`) extracts `shared_events_map` and `shared_scripts_map` separately before reading typed events.
- [Project::saveMap, src/project.cpp:1404–1423](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L1404-L1423) emits a `shared_events_map` reference **only** when event inheritance is active; it writes the map's own four event arrays only when it is not. Script-source sharing has its own independent branch.
- [src/mainwindow.cpp:2598–2605](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/mainwindow.cpp#L2598-L2605), blob `08ce1a7a599ef825967717b69626984cdc6d772b`, explicitly warns that adding events separates the map from its inherited event source.
- Unknown top-level map attributes are appended back into the saved map JSON by `OrderedJson::append(&mapObj,map->customAttributes())` at project.cpp:1436. This is a meaningful preservation requirement for custom ROM engines.

## Compatibility requirement

**XS21-EDITOR-KEEP-SHARED-SOURCES**: A project-aware XGBA editor and its map importer/exporter must preserve *event inheritance* and *script-source inheritance* independently, including symbolic source references, typed event identities and unknown custom attributes. Editing a local event must be treated as an explicit divergence from event inheritance, not a silent copy-on-write that appears to retain the relationship. Do not flatten a map merely because there are no event arrays in its authoring JSON.

For compiled-ROM-only imports, do not invent an original authoring `shared_events_map` field from visual similarity or presumed duplicate pointer identity; mark reconstructed relationships as inferred until backed by ROM pointer evidence.

## Verification scope

The source-hash-pinned checker `tools/porymap_shared_semantics.py` verifies 12 independent source-level predicates and source-line anchors, including both inheritance reads/writes and the script-label lifecycle. Successful Qt compiler evidence confirms that these source files belong to the pinned executable; it does **not** prove full UI editing, arbitrary ROM reverse engineering or round-trip output correctness.

Phase 1 independent per-file completion gate remains **FAIL_INCOMPLETE**.

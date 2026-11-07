# Phase 1 — RegionMap multi-map save to Project JSON failure boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This is a bounded follow-up to the RegionMap gesture/caller package. It does not duplicate its source inventory or claim a full Porymap GUI session, full Project reload, application-level rollback, or storage durability.

## Reconciled source scope

The source closure is already represented by prior pinned inventories. No original upstream source files are added or recounted here. The native witness reuses these pinned Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116` files:

| Reused original source | Git blob SHA-1 | Full-byte SHA-256 | Prior source role |
|---|---|---|---|
| `src/core/regionmap.cpp` | `94f686426e5ea8a84294dd1ac35617700c54e73f` | `a6b6717820ae1fbd04424283cf1cb4c057ec34eaff6935c5a3dc8f36f90ad44c` | RegionMap tilemap/layout writes and per-map clean state |
| `src/core/regionmapeditcommands.cpp` | `f21f1d720ae22d4911ef71b984435ff66c0566f9` | `28950c048b96df25fb7525d84298e50c3d302105edf7cc6aff285572e6c92f13` | Shared-entry undo/redo |
| `src/ui/regionmapeditor.cpp` | `a96de606cc18469b558b1acfc7c787432b8dcfb4` | `43f433c1754cd25d4691491567e7be9ff48e47e89c485eb917a5b26e2e1eb4e2` | RegionMap stack ownership, Save All, entry and config wrappers |
| `include/ui/regionmapeditor.h` | `432eaab62cd897146d8f64fe9f9555ae3ce4c265` | `8ebab02239b042894fe0dcc7a644be8611316f2c505788544708271b0344753c` | Shared entry hash and `QUndoGroup` owner |
| `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | `225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b` | Project entry setter and RegionMap section JSON writer |

These are reused source identities from the existing RegionMap persistence, RegionMap caller, and cross-file transaction packets; the machine record retains their source identities and the previous caller dossier digest. FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and Poryscript `c32481161c767b25a3425fa9f1f8729927ff3d55` are unchanged and not exercised. Porymap's pinned root `LICENSE.md` has LGPL-3.0 text; this is not a redistribution determination. No FireRed/Poryscript or Qt translation/SQLite sources are included.

## Source-grounded caller and ownership path

`RegionMapEditor::setup` points each RegionMap at the same `region_map_entries` hash and adds each map's own `QUndoStack` to the editor's `QUndoGroup`. `EditEntry::undo` writes its saved entry back through `RegionMap::setEntry`, which mutates that shared hash. The Save All slot iterates every RegionMap first, then invokes `saveRegionMapEntries`, then `saveConfig`, without checking a per-map or entry-save result. The entry wrapper copies the shared hash into Project, invokes `Project::saveRegionMapSections`, and returns `true` without checking the Project result. Each `RegionMap::save` writes tilemap and layout in sequence, then marks its undo stack clean; its helpers do not propagate write errors. The Project JSON writer returns `false` when opening fails, but after a successful open it ignores serialization/write/close errors and returns `true`.

The extracted-method Qt witness observes a cross-map undo fingerprint: two per-map stacks receive edits to the same entry hash; undoing them in a different order leaves both stacks clean while the shared entry retains the intermediate coordinates. It then invokes the original Save All body with two maps. A positive control writes both tilemap/layout pairs, the global section JSON, and the editor config. A native missing-root control confirms that the original Project writer returns false on open failure while the entry wrapper returns true. In the injected `/dev/full` failure case, the two map assets and config are written while the section JSON writer encounters `ENOSPC`; the wrapper still reports success and the in-memory entry differs from the restored prior JSON bytes. This is a partial cross-file commit, not application rollback.

## Native Qt evidence and limits

The harness compiles unchanged pinned method bodies for entry movement, `EditEntry`, RegionMap `save`/tilemap/layout writers, the RegionMapEditor Save All and entry/config wrappers, and `Project::setRegionMapEntries` / `Project::saveRegionMapSections`. It uses real Qt6 `QUndoGroup`, `QUndoStack`, `QFile`, JSON document parsing, and child-process byte readback. The Project object model and `OrderedJsonDoc` serializer are test-only shells; the writer's QFile path and extracted original Project method body are exercised, but the upstream OrderedJson implementation is not.

The `/dev/full` failure test has a matched Qt `QFile` control; the test-only serializer explicitly flushes the actual `QFile` and records its flush failure/errno. `QFile::write` may buffer successfully before the failure appears at flush. This does not execute the upstream OrderedJson serializer. The fixture temporarily renames the old section file and restores that same file after the test; this cleanup is **not** application rollback. Fresh-process checks compare the persisted section/map/config bytes and reject a deliberately wrong byte expectation. They do not construct the original Project loader in the child process or re-open the project through Porymap.

Unresolved: actual RegionMapEditor GUI interaction and project-open lifecycle; original OrderedJson serialization on the failure path; short-write behavior for this integrated sequence; full Project cold reopen; physical durability; and FireRed gameplay. All source rows remain `NEEDS_EVIDENCE`. Green CI, source extraction, and this bounded Qt witness are not independent semantic approval.

# Phase 1 — actual original Porymap Qt Project new-map failure and retry (2026-10-29)

**Test candidate pending exact-head CI. No result asserted before native execution. FAIL_INCOMPLETE; 0/14,834 approvals.**

This investigation extends the source-only persisted-flag dossier with **original Project::createNewMap, Project::loadMap, Project::saveMap, Map::setClean and original Qt QFile** in a full pinned Porymap application build using a test-only entrypoint and a copied pinned FireRed project. No upstream code is patched.

Two distinct filesystem failure classes are tested and must not be conflated:

- **Case A, script failed write:** `scripts.inc` (or `scripts.pory` in Poryscript mode) is a symlink to `/dev/full`; a matched direct Qt QFile write/flush control must observe a real error. The original new-map save is expected to proceed to JSON and `setClean`, changing the persisted flag. After removing the injected link, a second save of the same Map object tests whether the missing script is regenerated or skipped.
- **Case B, map.json open failure:** `map.json` is replaced with a directory, so the original QFile open fails after collateral script creation and global `event_scripts.s` append. A second save of the still-unpersisted Map object tests whether the same include is appended again. The test asserts original project file bytes, not merely inferred source paths.

The transcript verifier rejects sixteen evidence mutations. A separate immutable-source checker rejects fifteen targeted source mutations. This is **native Qt Project execution, not GUI new-map QAction execution, complete multi-file atomicity, file-watcher correctness, fsync/power-cut durability, or whole-file semantic approval**.

Pinned Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`, `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`, `src/core/map.cpp` blob `47b279919bd4afcc76b88f9eeecd459b3452989f`. FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Preserve Porymap LGPL-3.0 and embedded permissive notices; no claim that FireRed source/assets are freely relicensable.

**Partial per-file reviewer records:** `project.cpp`: createNewMap and saveMap new-map lifecycle only; `map.cpp`: persisted flag/dirty state only; `project.h`: NewMapSettings and function interfaces only. Missing: real MainWindow workflow, file watchers, nonempty/alternate map settings, cross-file rollback, generated Poryscript include and full independent review. Do not promote any gate.

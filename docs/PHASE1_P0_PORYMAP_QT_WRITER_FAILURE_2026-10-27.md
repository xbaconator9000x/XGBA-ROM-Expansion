# Phase 1 P0 — Porymap Qt JSON writer failure-propagation boundary

**27 October 2026 · PINNED SOURCE TRACE + ISOLATED QT DEVICE TEST · NOT APPROVED.**
Upstream pin: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.
This packet is an isolated Phase 1 research branch based on draft PR #8. It does not implement XGBA expansion or modify Porymap. **All Phase 1 gates remain `FAIL_INCOMPLETE`; independent approvals: 0.**

## Source identity and dependency closure

| Pinned file | Git blob SHA-1 | Role |
| --- | --- | --- |
| `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | `saveMap`, `saveMapGroups`, `saveGlobalData` |
| `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | Save Current and Save All dispatch |
| `src/mainwindow.cpp` | `08ce1a7a599ef825967717b69626984cdc6d772b` | GUI save action and conditional failure notification |
| `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | `Map::setClean` dirty-state transition |
| `include/lib/orderedjson.h` | `cb5139d37d955f2469ebd2eaaf089668b82884fe` | `OrderedJsonDoc::dump(QFile*)` implementation |
| `src/lib/orderedjson.cpp` | `4d3a460c652541371a01132116e508db8c4c872c` | Actual pinned JSON serialization implementation |

These six files were already in the original 14,834-file inventory. **New unique machine-indexed files: 0. New registered complete-file analyst reviews: 0.** Selected function tracing and isolated serializer compilation do not establish complete-file review.

## PWRITE-001 — source-level save success can outlive unchecked JSON writes

`Project::saveMap` opens `map.json` for writing, serializes through `OrderedJsonDoc::dump(&mapFile)`, closes the file, calls `map->setClean()`, then returns success (unless a later layout save fails). There is no check of the stream status, a flush result, or a close error between dump and the clean transition. `Map::setClean` clears `m_hasUnsavedDataChanges`.

`Project::saveMapGroups` likewise checks only whether `map_groups.json` opens; it dumps, closes and returns `true` without checking the stream/close outcome. `Project::saveGlobalData` checks the *boolean return* from `saveMapGroups`, but that boolean cannot communicate a write failure that the map-groups writer never checked. `Editor::save(true)` propagates the `saveMap` and `saveGlobalData` results, so the same error-propagation gap reaches Save Current.

The pinned `MainWindow::save(bool currentOnly)` invokes the appropriate editor save and displays `RecentErrorMessage` only when its boolean `success` is false (mainwindow.cpp:1999–2019). Therefore an unchecked write error that is not reflected in the editor return value cannot trigger that specific GUI failure notification. This is a **conditional source-call-chain result**, not an observed GUI message in a failed real save.

The underlying `OrderedJsonDoc::dump(QFile*)` returns **`void`**. It creates a `QTextStream` and writes JSON plus a newline, without exposing `QTextStream::status()` to the caller. This is a **source-level detection gap**, not proof that a user lost data or that the editor GUI displayed a false success message.

The same writer uses `QFile::WriteOnly`, not an atomic replace/commit protocol. In the presence of a failed or interrupted write, preservation of the original JSON and a recoverable multi-file transaction must be established separately. This dossier does not claim an observed partial-write incident.

## PWRITE-002 — independent compiled Qt serializer witness

`tests/porymap_qt_writer_device.cpp` compiles the **actual pinned** `src/lib/orderedjson.cpp` against Qt6Core, verifies a real `QTemporaryFile` JSON round trip, then executes the same `OrderedJsonDoc` against Linux `/dev/full`, an intentionally write-failing device. It independently probes that the device really rejects writes, checks the resulting `QFile` flush/error in the harness, and statically verifies that `dump` returns `void`.

**Evidence boundary:** This test executes the pinned Qt serializer, not `Project::saveMap`, `Project::saveMapGroups`, the GUI, or a real project save/reopen. The project-level propagation claim remains source-grounded. A passing CI result would establish only the isolated device test and source guards.

`tools/phase1_porymap_qt_writer_failure.py` checks all six exact Git blobs, the call-chain anchors and nine fail-closed in-memory negative mutations. The dedicated workflow checks out the immutable Porymap commit, installs Qt6Core, compiles the serializer witness and archives machine-readable evidence. **Treat CI as unverified until it passes against the exact latest branch head.**

## Unresolved producer/consumer and failure boundaries

1. Run a pinned full-editor Qt fixture with a writable project copied into a disposable directory. Inject a short write or ENOSPC on `map.json` and `map_groups.json`, then assert actual `saveCurrent` / `saveAll` return values, dirty flags, UI messages and on-disk JSON.
2. Verify QFile/stream error observability after `close()` and actual GUI response to fault-injected saves. The pinned GUI source only shows a failure notification when the editor reports false; it does not prove any particular user-visible outcome during a real failed write.
3. Exercise mirrored A→B connections, Save Current vs Save All, unknown JSON fields, map-group metadata, reload and partial multi-file writes. Preserve source provenance independently from generated FireRed connection records.
4. Validate a crash-safe and lossless editor/ROM refresh protocol before accepting any generated native map or ROM output as authoritative.
5. Obtain independent **whole-file** review of all relevant pinned source owners, Qt persistence behaviour and compiler/runtime evidence. No self-authored packet, test or green workflow grants approval.

## Accounting

- Inventory: **14,834** distinct pinned upstream files, unchanged.
- Established machine-triage pool: **14,721 / 14,721**, previously exhausted; no new identities credited here.
- Newly processed in this packet: **0**; **1,000 short** of the requested per-run target because the established untriaged queue is exhausted.
- Authoritative registered complete-file analyst baseline: **113** on the inherited review-readiness branch. Other proposed/unregistered packets are not silently added.
- Independently approved: **0**.
- Phase 1: **`FAIL_INCOMPLETE`**. Phase 2: **not started**.

# Phase 1 P0 — FireRed map runtime-consumer closure

**9 November 2026 · SOURCE-ONLY WHOLE-FILE READ · NON-APPROVING HANDOFF.** Prepared on PR #7 at `bdd93fd1c6a87ebdeefdd3f5d087ae1adde43d77`, following the PR #8 batch-review protocol. Machine-readable per-file records are in [`phase1-review-readiness/firered-map-runtime-consumer-handoff-20261109.json`](phase1-review-readiness/firered-map-runtime-consumer-handoff-20261109.json).

Phase 1 remains `FAIL_INCOMPLETE`; independent whole-file approvals remain `0/14,834`. The four FireRed source files below were read in full and bound to the packet and original machine-dossier identities. This is not a qualifying independent receipt: dependency and licensing closure are incomplete, no verdict is submitted, and no existing approval/register/gate was changed.

## Packet and assignment reconciliation

- The PR #8 third packet, `packet-0200-0299.json`, pins FireRed at `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This handoff selects P0 source indices **297–298** for the map/connection readers and **295–296** for camera and field-input consumers.
- The requested second-packet indices **112–127/129 are not FireRed**: the pinned packet identifies mGBA Qt translation files and `src/third-party/sqlite3/sqlite3.c` at mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`. They are explicitly excluded rather than relabeled.
- Authored `scripts.inc` entries 260–292 are excluded from this packet because they overlap the Poryscript/map-script ABI work on PRs #16, #20 and #36. `src/agb_flash.c` (293) is excluded from PR #10’s flash-sector scope, and `src/load_save.c` (299) is excluded from the already-documented save-reload work.
- PR #6 owns the authored map-header/layout join; PR #7’s prior compiled mapjson connection-object analysis is delivered. This packet does not repeat either: it follows runtime consumers and marks remaining layout-table/linkage questions open. Porymap PRs #14/#27 and the Poryscript PRs are not modified or duplicated.

## Two bounded source packages

1. **Border/connection readers — `src/fieldmap.c` (297) and `src/itemfinder.c` (298).** The pinned producer/build chain is `layouts.json` / map JSON → `mapjson` → generated layout and map assembly → `map_data_rules.mk` → `maps.o`; `include/global.fieldmap.h` defines the native layout, connection and header fields. `fieldmap.c` initializes the virtual map and connected borders, looks up incoming connections during camera transitions, and exposes positional connection lookup. Itemfinder uses that lookup while scanning neighboring connected maps. The existing archived modern/classic `maps.o` artifacts remain prior evidence for connection bytes only; they do not prove these runtime paths or the layout-table link.
2. **Field-frame consumers — `src/field_camera.c` (295) and `src/field_control_avatar.c` (296).** The pinned `overworld.c` call sites drive camera updates and field-input processing. These consumers read map-grid state, move the viewport, select map events and initiate warps. This is FireRed C runtime-consumer coverage only—not a Poryscript emitter, Porymap save/reopen, or emulator experiment.

The full-file read found a camera source anomaly: both `CameraUpdate` and `CameraUpdateNoObjectRefresh` assign `deltaX` in the vertical movement-completion branch (lines 397–403 and 474–480). This is recorded as an unresolved source objection, not as a reproduced gameplay defect or a proposed source change.

Other open source obligations include zero border-dimension modulo in `GetBorderBlockAt`; conditional pointer checks and nullable `GetIncomingConnection` results; Itemfinder’s signed/unsigned coordinate transforms and connected-map event assumptions; and the camera/input consumers’ external state, array and call-order preconditions. These are source-level obligations only. Authored reachability, compiled link placement and native behavior were not established here.

## Evidence boundary

The source packet and original compressed machine-dossier archive identities, per-row SHA-256 values, source blob IDs, complete line counts, caller/build edges, licensing caveat and local source-mutation controls are recorded per file in the JSON handoff. The pinned upstream FireRed root listing observed during preparation had no `LICENSE` file (the listing response was not archived); the pinned README identity is recorded, but it does not establish a license for these files. Every record therefore leaves licensing pending. No license clearance is inferred.

No ARM GCC/binutils, agbcc, QEMU, or mGBA executable is available in this runner. No fresh native build, reader execution, linked-ROM test, emulator test, or exact-head compiled-workflow CI was performed. The prior passing mapjson build runs are at earlier commits and are cited only as archived object provenance—not as CI for this handoff. The exact-head PR check list includes Copilot’s dynamic task check, not a compiled mapjson workflow. Eight local byte-mutation controls changed their respective pinned source SHA-256 as expected; these NON-CI checks validate source identity only and do not simulate native behavior.

**Disposition:** `NON_APPROVING_HANDOFF`; no `COPILOT_REVIEWED/PASSED` or historical `APPROVED` receipt; no Phase 2 credit.

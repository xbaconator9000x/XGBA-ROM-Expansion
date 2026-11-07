# Porymap Tileset persistence boundary (non-approving)

Status: **NEEDS_EVIDENCE**. This is a new bounded source package and native Qt witness, not an independent approval, a full-GUI result, or a Phase 1 gate promotion. Current authoritative status remains `FAIL_INCOMPLETE`, with zero independent approvals.

## Backlog selection

The committed shortlist is `porymap-backlog-shortlist-20261107.json`. Its top distinct candidate is the pinned Tileset asset writer path: the existing Tileset Editor invokes `Project::saveTilesets`, while script API setters call the metatile writers directly and discard their boolean results. I excluded the map-layout blockdata path because `PHASE1_P0_PORYMAP_PACKED_BLOCK_MASK_LIFETIME_2026-10-27.md` already analyzes the same write/read behavior. FireRed mapjson, mGBA matrix/savestate, and Poryscript include packages were excluded as already covered.

The shortlist is bounded to those evidence-backed candidates; it does not assert that every one of the 14,834 inventory rows has been semantically dispositioned.

## Immutable identity and semantic scope

Pinned source: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.

| File | Original Git blob SHA-1 | Full source SHA-256 | Candidate row SHA-256 | Scope |
|---|---|---|---|---|
| `include/core/tileset.h` | `dcf55ec182200985125ee308a1ac7c8df54ab066` | `d1c8b5b37bfa14ccc528d648d9250ce23b25a668dec013e9d159095fbfe8c613` | `31030025f279eab70c34efe0941876015dee23fd74439b25206b3959f9515009` | Complete header: save/load declarations, owned metatiles, images, palettes, and image dirty state. |
| `src/core/tileset.cpp` | `0aa1f7d6726e3c8670f0758724284c792f7d9272` | `ec94552b325e26362046b5288a6c448d62ff4407c8bfa9cb5ed392407adc4b99` | `6fb6cc663f859d2783badd95b7606b497e2c7da2d322fcc1e4e04b367f9ba7e2` | Complete implementation: ownership, primary/secondary ID mapping, generated-source appends, binary/image/palette load/save, dirty state, and color queries. |
| `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | `225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b` | `b6b90abf56f02452537a9b096fa191ead9ee7360dd19d72c6f5486834bed02d7` | Caller context only: `saveTilesets` aggregates save results; `createNewTileset` ignores its initial `save` result. |
| `include/project.h` | `50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354` | `7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51` | `0a5103fa34ee62748f39cbcbd0d50c3bb9ccabc824cf9813ca53bd5118cc69eb` | Caller declaration context only. |
| `src/ui/tileseteditor.cpp` | `723a2afdeb89c1752e9811a07715462c2279c645` | `a85e7827754d3f08cec5ebe90aa7a737958524ac379d563adfd269d1b7557ced` | `940f1b1723b84449dbc3f20648e057643c96d9be19a08e9fa210746193a35ee7` | Caller context only: editor status, dirty state, and post-save updates. |
| `src/scriptapi/apimap.cpp` | `dcd4fc3300ca9dabb283ea2f803b396702d0715e` | `169dbd39e409d3fadfa09a224cd9842c78a4157802e9c7b4ba8ce3cee71e066c` | `792d485116bb9d872e8d54172a89eeb596ba6878a0160920e464ffe486bed9f0` | Caller context only: script mutation methods invoke the binary writers without propagating their results. |
| `porymap.pro` | `53d8055ecfe5d88afb6f183b82d4a3472727ad4f` | `cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996` | `93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2` | Build context only. |
| `LICENSE.md` | `65c5ca88a67c30becee01c5a8816d964b03862f9` | `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768` | `a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986` | Root notice context only. |

Archive provenance: `imports/XGBA_Phase1_v1.5_Complete_Workpack.zip` SHA-256 `5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4`; compressed `evidence/candidate_review_dossiers.jsonl.gz` SHA-256 `fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac`. The row hashes above are hashes of rows in this **automated candidate inventory**. They are not original independent semantic dossiers or receipts.

The focal files are analyzed over their complete byte ranges. Caller/build/license files are cited only for dependency closure and are not counted as new whole-file semantic reviews.

## Source findings and concrete counterexamples

Pinned source anchors in `src/core/tileset.cpp`:

- `loadMetatiles` (454–486) clears current metatiles before opening the input. It uses integer division by `bytesPerMetatile`, so partial trailing bytes are ignored; records beyond `maxMetatiles()` are discarded. `readAll()` errors are not distinguished from an empty/short file.
- `saveMetatiles` (488–506) truncates the destination, emits each 16-bit tile low byte first, calls `file.write(data)` without checking its return, and then returns `true`. A failed open does return `false`.
- `loadMetatileAttributes` (508–539) floors byte length by configured `attrSize`, truncates excess complete attributes to the in-memory metatile count, and leaves missing entries unchanged after warning. The warning says missing values default to zero, but whether that is true depends on the metatile’s prior state/initialization.
- `saveMetatileAttributes` (541–556) emits the configured number of low-to-high attribute bytes, ignores `file.write`’s result, then returns `true`.
- `Tileset::save` (687–694) attempts palette, image, metatile, and attribute persistence and aggregates reported failures, but provides no rollback across these files. Each helper can already have changed disk state before a later one fails.
- `appendToHeaders`, `appendToGraphics`, and `appendToMetatiles` (307–416) append generated build declarations, call `write`, `flush`, and `close` without checking write/flush/close results. They are not transactional as a group.
- `loadTilesImage` validates tile dimensions and palette cardinality, creates a default image when input is absent/unreadable, and marks an imported image dirty only after validation. `saveTilesImage` clears that dirty flag only after `QImage::save` reports success.
- Copy construction preserves `m_hasUnsavedTilesImage`; assignment copies the image but does not assign this dirty flag (40–67). This is a source-level state discrepancy; its effects depend on assignment callers and are unresolved here.

Caller closure:

- `TilesetEditor::save` (`src/ui/tileseteditor.cpp:738–755`) consumes the aggregate result and only clears its dirty flag on success, but applies swaps and emits `tilesetsSaved` before the success check.
- `Project::saveTilesets` (`src/project.cpp:1103–1109`) aggregates primary/secondary return values.
- `MainWindow::saveMetatilesByMetatileId` and `saveMetatileAttributesByMetatileId` (`src/scriptapi/apimap.cpp:570–586`) discard writer results. Script-side setters call these helpers after changing metatile data (e.g. lines 630–714).
- `Project::createNewTileset` (`src/project.cpp:1560 onward`) calls `tileset->save()` without checking the result before caching/emitting the created tileset.
- `porymap.pro` registers `src/core/tileset.cpp`; build/link identity is revalidated by the existing pinned-source workflow.

The native positive controls wrote exact bytes `34 12` and `ef cd ab 89`. A missing-parent output path was rejected. With unchanged original method bodies and real Qt 6 `QFile`, two writes to Linux `/dev/full` returned `-1 ENOSPC` under `strace`, while both original methods returned `true`. This demonstrates the method return/error boundary for those two paths only; it does not establish a full GUI failure or disk durability result.

## Native and deterministic controls

`tests/phase1_porymap_tileset_native.cpp` is a test harness with minimal model/config/logger stubs. `tools/phase1_porymap_tileset_closure.py` extracts the unchanged original `Tileset::saveMetatiles` and `Tileset::saveMetatileAttributes` bodies, compiles them against actual Qt 6 Core, executes the byte and failure controls, and requires `strace` attribution for each `/dev/full` ENOSPC.

The verifier checks the workpack ZIP and compressed candidate-dossier hashes, each candidate row hash/status, the exact pinned Git revision, source Git blobs/full-byte SHA-256, source/caller contracts, and shortlist exclusions. Its ten deterministic mutation controls reject archive drift, stale row identity/pin, candidate approval drift, wrong row hash, writer/caller source changes, a covered-package substitution, inflated shortlist counts, and full-byte source drift.

Evidence class: **compiled unchanged original method bodies with actual Qt 6 Core and test-only model/config/logger stubs**. It is not a full pinned Porymap application/GUI, not an actual script-engine call, not a FireRed project roundtrip, and not a generated ROM or gameplay result.

## Licensing and unresolved edges

The pinned Porymap root notice is LGPL-3.0 text. This records the upstream notice only; it is not legal advice or a distribution-compliance finding. Qt 6 Core/Gui, Qt plugins, system libraries, and the project’s other dependencies have separate licensing/redistribution conditions; this package does not resolve them. No SQLite dependency is implicated by this Tileset path.

Still `NEEDS_EVIDENCE`: full caller-owned object lifetime and assignment call sites; metatile/config invariants and all `PaletteUtil`/image-provider behavior; actual full-GUI save and script-engine failure behavior; multi-file partial-write recovery and cold reopen; tests for partial/truncated read inputs; generated build output/linker behavior; license closure; and independent per-file review receipts. The exact-head push and PR checks are pending until the workflow runs on the committed head.

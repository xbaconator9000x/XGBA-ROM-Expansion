# Phase 1 — pinned Porymap AdvanceMap 1.92 import boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This is a bounded original-parser witness and non-approving handoff, not a Porymap fix or independent whole-file approval.

## Distinct scope and provenance

The focal subsystem is the pinned `AdvanceMapParser` `.map`, `.bvd`, and palette import boundary at Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`. It is separate from the previous Tileset persistence witness: this package exercises legacy import byte decoding, version selection, dimensions, tileset-index fallback, palette stride, and importer error flags. The `TilesetEditor` and `PaletteUtil` files below are caller context only; their broader behavior is not re-reviewed.

The imported workpack ZIP SHA-256 is `5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4`; its `evidence/candidate_review_dossiers.jsonl.gz` member SHA-256 is `fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac`. These are automated candidate-inventory hashes, not original semantic dossiers or approval receipts. The machine-readable handoff preserves each candidate row hash, pinned Git blob, and full-byte source SHA-256. No independent reviewer attribution or receipt is available; both focal records remain `NEEDS_EVIDENCE`.

The pinned parser's `porymap.pro` entry enables Qt Core/GUI and compiles this source. Pinned root `LICENSE.md` is LGPL-3.0 text, but neither a source notice nor this build evidence establishes distribution compliance.

## Source-grounded import path

- `MainWindow` calls `parseLayout(filepath, &error, editor->project)` and then handles the returned `Layout`.
- `TilesetEditor` calls `parseMetatiles(filepath, &error, primary)` and takes responsibility for the returned pointers.
- `PaletteUtil` dispatches non-JASC palettes to `parsePalette`.
- `Project` supplies ordered tileset labels, allowed primary/secondary label sets, fallback labels, and primary/secondary metatile limits. `Metatile` supplies the RSE/FRLG attribute widths and conversion; `projectConfig` controls optional triple-layer padding.
- `Layout`, `Blockdata`, and `Tile` define the objects produced for downstream editor and save paths.

The full source matrix and per-file context/focal distinctions are in `porymap-advancemap-import-boundary-20261107.json`. Dependency rows cited as context are not counted as complete-file semantic reviews.

## Bounded native observation

The existing compiled-Porymap workflow compiles the **unchanged original** `src/core/advancemapparser.cpp` with Qt 6 Core and Gui, matching the pinned qmake modules and its `QRgb` interface. Test-only stubs replace `Project`, `Layout`, `Tile`, `Metatile`, and logging, so the experiment exercises parser code and Qt file I/O, not real project state or the actual Metatile attribute packers.

The controls cover:

- valid `.map` field decoding, little-endian blockdata, valid tileset indices, and cross-kind index fallback;
- rejection of short and odd `.map` files;
- RSE and FRLG `.bvd` signatures, tile order, two-/four-byte attribute reads, triple-layer padding, and unsupported signatures;
- palette channel extraction, the four-byte record stride, and malformed-length rejection; and
- an intentionally malformed 65536-by-65536 `.map` whose `width * height` expression triggers UBSan signed-overflow diagnostics in the unchanged parser.

The malformed-dimension observation is a bounded original-source defect witness; this package does not change upstream Porymap or claim the remaining malformed-input space is safe. The test does not execute the GUI callers, compile the real `Project`/`Metatile` implementations into its harness, consume a corpus of actual AdvanceMap exports, build a ROM, or test gameplay/hardware behavior.

The verifier binds all listed sources and candidate rows to the pinned revision and includes source, dependency, and evidence mutation controls. CI success validates this bounded harness and package only—not semantic approval, file completeness, or downstream compatibility. All dispositions remain non-approving.

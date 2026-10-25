# Phase 1 P0 — Porymap / Poryscript authoring-format interoperability contracts

**Date:** 2026-10-26. **Gate:** `FAIL_INCOMPLETE`. **Disposition:** SOURCE-ANCHORED CANDIDATE SEMANTICS — not a whole-file reviewer signoff and not a compiled Porymap/Poryscript runtime test.

## Immutable upstream source anchors

- Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`
  - [`src/core/block.cpp:8-75`](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp#L8-L75), Git blob `fc4fe774ccd75673c549734055907eb7c79c0fc2`
  - [`src/core/bitpacker.cpp:25-50`](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/bitpacker.cpp#L25-L50), Git blob `34f86b4e3910021613a1d090746ae53a1c6782a2`
  - [`src/core/blockdata.cpp:3-11`](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/blockdata.cpp#L3-L11), Git blob `5fcd4e32b115790f5a86b5cef5726cace8005017`
  - [`src/core/maplayout.cpp:524-628`](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp#L524-L628), Git blob `44616ab6c9c3ea9b04eff011586b7ec29183588f`
- Poryscript `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`
  - [`emitter/emitter.go:33-159`](https://github.com/huderlem/poryscript/blob/c32481161c767b25a3425fa9f1f8729927ff3d55/emitter/emitter.go#L33-L159), Git blob `d35843ef29929ead47351646d7a33dd5c692b850`
  - [`emitter/chunk.go:21-145`](https://github.com/huderlem/poryscript/blob/c32481161c767b25a3425fa9f1f8729927ff3d55/emitter/chunk.go#L21-L145), Git blob `bb3a6514988eb2699022551d3dbfe2bdce260377`
  - [`main.go:20-100`](https://github.com/huderlem/poryscript/blob/c32481161c767b25a3425fa9f1f8729927ff3d55/main.go#L20-L100), command arguments and compile configuration (pin above; blob SHA to check separately on review).

## Contract PMAP-001 — native map block is a 16-bit packed semantic record

At the pinned default, `Block` uses masks `0x03FF` for metatile ID, `0x0C00` for collision and `0xF000` for elevation. `Block::rawValue()` ORs all three independently packed fields; `Blockdata::serialize()` writes each `uint16_t` low-byte then high-byte.

**Therefore an exported map tile ID or screenshot alone cannot round-trip native collision and elevation.** The legacy map-grid record is a semantic triple encoded in **two bytes**, not an image layer.

**Configuration caveat:** `Block::setLayout()` replaces those default masks with the current project configuration. A future editor must bind the target project's masks and compiled layout ABI, not assume 10/2/4 bits for every mod.

### Lossy operations identified (not runtime-proved)

- `BitPacker::clamp` applies modulo `max + 1`, so if a user-specified field exceeds its current mask width, the value can wrap rather than remain representable. E.g. in the *default* layout, metatile 1024 resolves to 0, collision 4 resolves to 0 and elevation 16 resolves to 0.
- `Layout::readBlockdata` reads only *complete* two-byte records; an odd final byte has no corresponding block.
- `Layout::loadBlockdata` checks `width * height` and resizes the loaded block array with a warning if lengths disagree. An XGBA adapter must not silently treat that reconciliation as lossless source preservation.
- `Layout::writeBlockdata` serializes blockdata via `Blockdata::serialize`. A collision/layer-aware exporter must preserve authored block triples, configured masks and target paths, not reconstruct semantics from rendered pixels.

## Contract PMAP-002 — source project is authoritative

Porymap keeps map layout, `blockdata_path`, `border_path`, tileset labels, event groups, script references and a separate map JSON/source directory. The 16-bit blockdata stream is only one compiled/source input. For plugin integration:

1. Treat the authored project as canonical; carry stable map/layout/event/tileset IDs and project configuration into an extension sidecar.
2. Importing/recompiling a ROM must **not** silently replace editor-only layers, tile ownership, collision masks, dimensions or semantic source labels.
3. Support source-project refresh by stable identity with three-way conflict reporting; raw ROM import alone cannot prove recovery of all authoring metadata.
4. Before legacy export, validate each configured mask can represent every field, every tile word has both bytes, and block count equals `width * height`. For unsupported extension-specific fields, use a versioned companion record rather than truncation.

## Contract PSCRIPT-001 — script source and emitted assembler differ

Poryscript's compiler parses named, structured statements into an AST; `emitter/emitter.go` emits assembler text. It generates shared-logic chunks and uses branch labels, maps `map_script` tables, and emits terminator directives; `emitter/chunk.go` synthesizes labels and control-flow `goto` sequences. Command emission writes textual labels/arguments.

The compiler defaults to optimization and source-line markers (`main.go`). As a result, a ROM/assembler importer should not claim a lossless reconstruction of author-written `if`/`switch`/script naming, source formatting, compile switches or textual macros from final bytecode alone.

The extension plugin must distinguish **source Poryscript**, **emitted assembler with generated labels**, **compiled GBA bytecode**, and **external XGBA resource references**. Versioned source/provenance metadata must accompany any transformed identifiers or relocated pointers; absent provenance is an explicit incompatibility, not permission to guess.

## Pending safety checks before source/semantic acceptance

- Lossless exhaustive encode/decode across all 65,536 **valid raw 16-bit words** with unmodified masks and bytes, plus negative fixtures for out-of-mask input.
- Non-overlapping configured masks, changed project masks, odd-length block binary and block-count mismatches must be detected and rejected or explicitly reviewed; do not silently modulo or resize an extended resource.
- Recompile a pinned Porymap/Poryscript fixture, compare semantic triples/map IDs/events/text labels across export/import/refresh, and preserve original project exact bytes when the import is a no-op.
- Verify compiled Game Freak/FireRed ABI for map grid masks, metatile attributes, collision, elevation, warp scripts and Poryscript opcode/operand layouts for every build variant.
- Source-hash review and independent whole-file dispositions remain necessary for Phase 1; no approval rows were written.

**Status of this packet:** SOURCE-PINNED REVIEW CANDIDATES. It adds concrete format-loss hazards and traceable contracts without claiming Phase 1 or third-party editor compatibility complete.

# Phase 1 P0 — Porymap packed-block producer/consumer and mask-lifetime contract (27 October 2026)

**SOURCE-GROUNDED ANALYST EVIDENCE; FAIL_INCOMPLETE.** This is a new complete-file candidate batch and a source-level losslessness/compatibility investigation, not an independent review, compiled C++ run, or editor round trip.

## Immutable source evidence

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. The six small complete files were fetched at this ref and their Git blobs verified:

| Pinned file | Git blob SHA-1 | Source role |
| --- | --- | --- |
| [src/core/bitpacker.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/bitpacker.cpp) | `34f86b4e3910021613a1d090746ae53a1c6782a2` | Bit mask packing and public ABI |
| [include/core/bitpacker.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/bitpacker.h) | `4e3767e48449a974bfe1d9c63c5bf63dd2826fe9` | Bit mask packing and public ABI |
| [src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp) | `fc4fe774ccd75673c549734055907eb7c79c0fc2` | Semantic metatile/collision/elevation and public ABI |
| [include/core/block.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/block.h) | `94c674c30ed5c20231d4501cd193c0cb25365d2c` | Semantic metatile/collision/elevation and public ABI |
| [src/core/blockdata.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/blockdata.cpp) | `5fcd4e32b115790f5a86b5cef5726cace8005017` | Native word serializer and container ABI |
| [include/core/blockdata.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/core/blockdata.h) | `a1e45b63783fa2aecceee6fadbb33f1e1935b6b8` | Native word serializer and container ABI |
| [src/core/maplayout.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp) | `44616ab6c9c3ea9b04eff011586b7ec29183588f` | Adjacent read/write, dimensions, border handling (selected functions only; **not** a whole-file candidate) |

## End-to-end source-grounded dependency

`projectConfig.blockMetatileIdMask / blockCollisionMask / blockElevationMask` → `Block::setLayout` → three static `BitPacker` instances → `Block(uint16_t raw)` or field setters/three-field constructor → `Block::rawValue` → `Blockdata::serialize` (two bytes, low first) → `Layout::writeBlockdata` → `QFile::write`. Inbound: `Layout::readBlockdata` reads complete two-byte pairs, constructs Blocks with the then-active masks, and `Layout::loadBlockdata` resizes to width×height if necessary. Border load separately substitutes default dimensions for zero/negative authored values.

### PBLOCK-001 — Two distinct representability paths

The three-field Block constructor stores supplied uint16_t values without clamping; setters call `BitPacker::clamp` (modulo 2^popcount except UINT_MAX), and `rawValue` uses `pack` without calling clamp. With default 10-bit metatile mask, `Block(1024,0,0)` retains 1024 but emits packed zero, while setter `setMetatileId(1024)` stores zero. Consequently **distinct semantic triples can have identical serialized bytes**, and equality is not equivalent to byte equality. This is a source-derived witness, not compiled execution.

### PBLOCK-002 — Mask identity is part of the serialized interpretation

Default masks `0x03FF/0x0C00/0xF000` partition 16 bits. `Block::setLayout` mutates static mask packers shared by all Block instances; the per-Block fields carry no mask provenance. The same bytes can be decoded differently after a configuration change; existing triples can reserialize differently. `BitPacker` permits sparse masks; no mask-disjointness or complete-16-bit coverage check is present in these three implementation files. A lossless adapter must check field representability, mask overlap, union/coverage where raw-word identity is required, and project-config identity **before** treating a round trip as lossless.

### PBLOCK-003 — File I/O is not an atomic lossless transaction

`Blockdata::serialize` produces exactly two bytes per Block in source logic, but `Layout::writeBlockdata` does not inspect the `QFile::write` byte count before returning true. `Layout::readBlockdata` ignores an odd final byte. `Layout::loadBlockdata` warns and resizes block arrays that disagree with width×height; border load can normalize zero dimensions and resize. These are distinct source-level information-loss/error-detection boundaries, **not proven short writes or user-visible corruption**. An authoritative source-project refresh must not silently normalize these cases.

### PBLOCK-004 — 32-bit packer API does not expand the native word

`BitPacker` takes uint32_t masks and values, but `Block::rawValue` is uint16_t and `Blockdata::serialize` writes 16-bit words. The 31-set-bit expression `(1 << 31) - 1` also merits compiler-specific signed-overflow review if such a mask is supplied; no evidence here shows that project masks use it. Do not infer >16-bit native map-cell support from the packer's public type.

## Producer and UI call-site closure — four additional pinned source blobs

These four files are **selected-function evidence only**, not additional whole-file review candidates. Their exact pinned Git blobs were fetched and checked against the same Porymap commit:

| Source file | Git blob SHA-1 | Source path |
| --- | --- | --- |
| [src/project.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L2437-L2481) | `d43b0949303433111d4478ad76117c2b3445dd13` | `Project::readFieldmapMasks`, define reader and `Block::setLayout` caller |
| [src/config.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/config.cpp#L292-L300) | `9264f99bb18e0a725ef023f514c00df529d1d28d` | `getConfigUint32`, mask parse and serialization |
| [include/config.h](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/include/config.h#L323-L330) | `539c5f3d416d22d847020cd324726b33725e5437` | project defaults and 16-bit mask declarations |
| [src/ui/projectsettingseditor.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/ui/projectsettingseditor.cpp#L253-L278) | `0df96149b86694d5c95e1489493b91d646b99b98` | overlap warning and settings-save path |

**PBLOCK-005 — Two mask-input paths have different coercion.** In `Project::readFieldmapMasks`, parsed fieldmap C defines are cast to uint16_t, and truncation emits a warning but does **not** reject the mask. The function copies available defines into projectConfig and then calls `Block::setLayout`. Independently, project config-file keys `block_metatile_id_mask`, `block_collision_mask` and `block_elevation_mask` are parsed by `getConfigUint32(..., 0, Block::maxValue)`: nonnumeric input gets the configured default, and numeric input is bounded with `qBound` to the 16-bit maximum. These are distinct source-level provenance/coercion behaviours; a future adapter must record whether masks originated in defines or config rather than assuming every input was accepted verbatim.

**PBLOCK-006 — Overlap warning is not a fail-closed editor constraint.** `ProjectSettingsEditor::updateMaskOverlapWarning` detects pairwise overlap and updates a warning label/style; its own comment says overlapping masks are technically allowed and Porymap will not properly reflect linked values. `ProjectSettingsEditor::save` assigns the three spinbox masks into projectConfig, saves the config and sets `projectNeedsReload = true`; no overlap rejection appears in that save path. The code does **not** immediately call `Block::setLayout` from save; the confirmed application is `Project::readFieldmapMasks`. Whether every reload invokes that reader in the required order still needs a caller/lifecycle trace. This narrows the earlier source-level mask-identity risk: **UI warning exists, but no demonstrated hard rejection or atomic conversion.**

These findings refine the previously mapped mask dependency; they do not establish a user-visible corruption incident, a full-file review of the four large files, or an editor round-trip test.

## Fail-closed Phase 1 obligations

A compatible editor/ROM adapter must (1) bind the exact source-project masks and layout identity; (2) reject unrepresentable semantic fields and overlapping/omitted bits unless explicitly modeled; (3) detect odd bytes, unexpected block counts, dimensions and partial writes rather than silently declaring success; (4) distinguish source-preserving no-op refresh from raw ROM reconstruction; and (5) verify compiler-specific and real editor read/write round trips. Existing Porymap and FireRed ABI evidence is in [the authoring-format dossier](PHASE1_P0_PORYMAP_PORYSCRIPT_AUTHORING_ABI_2026-10-26.md); it does not prove these runtime obligations.

**Eleven exact-pinned upstream source files examined (six complete-file candidates, five selected-function dependencies); no compiled test.**

**New analyst whole-file candidates:** 0015–0020 in [the register](phase1-disposition-candidates/README.md), six unique pinned paths. No independent signoffs. **Gate: FAIL_INCOMPLETE; 0/14,834 approved. No Phase 2.**

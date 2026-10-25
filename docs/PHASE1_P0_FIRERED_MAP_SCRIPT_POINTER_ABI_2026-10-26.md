# Phase 1 P0 — FireRed map/script compiled ABI and editor provenance

**2026-10-26 · `SOURCE_GROUNDED_CROSS_FILE_SEMANTIC_MAPPING` · Signoff: PENDING.** This is a manual source interpretation and candidate dependency contract, not independently approved whole-file dispositions, an implemented XGBA runtime, or a proof that every build variant shares this ABI.

## Pinned source identity

FireRed revision: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
Porymap revision: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.
Poryscript revision: `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`.

| Native/source file | Pinned Git blob SHA-1 | Relevant exact lines |
| --- | --- | --- |
| FireRed `include/global.fieldmap.h` | `e2828ec0cb1439718e830fbef4366770b3b77b1c` | 4–14 masks; 82–110 Tileset and MapLayout; 115–207 event/map header struct pointers |
| FireRed `include/global.h` | `77155b09014aa854fcf87260e6ad2969e222da53` | 352 save block `mapView` backing |
| FireRed `include/fieldmap.h` | `639e329a9a0f721abd7e40001228859cb9466005` | 6–22 tile-count and backup-grid extent |
| FireRed `src/fieldmap.c` | `41567772299000ba5855419e5c39ad9373a34c20` | 46–81 block/attribute decode; 92–125 map materialization; 350–450 grid access/tileset resolution; 452–498 saved view bug |
| FireRed `include/script.h` | `ce10c87266a8019eeefaaf787f43b291e7a58624` | 8–23 20-pointer script call stack and four local words |
| FireRed `src/script.c` | `d0433bdda062b138e53d1a1d3184b4566ad7d9dc` | 82–144 bytecode interpreter; 165–200 call/jump/32-bit operand reader |
| FireRed `src/scrcmd.c` | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` | 118–187 native function-pointer invocation and direct branch target; 286–335 direct word/byte pointers; 2103–2118 map editing |
| FireRed `data/maps.s` | `fc88d8fc2521e92db22264bf6cf33966fda977ba` | 1–22 inclusion of original map layouts/headers/groups/events/scripts |
| FireRed `ld_script.ld` | `9a4b45031e93c1e1da8186d8c697332710526048` | 4–8 256KiB EWRAM, 32KiB IWRAM, 32MiB ROM region |
| Porymap `src/core/block.cpp` | `fc4fe774ccd75673c549734055907eb7c79c0fc2` | 8–11 default masks, 43–54 block packing and project-defined mask override |
| Porymap `src/core/blockdata.cpp` | `5fcd4e32b115790f5a86b5cef5726cace8005017` | 3–11 little-endian 16-bit block stream |
| Porymap `src/core/maplayout.cpp` | `44616ab6c9c3ea9b04eff011586b7ec29183588f` | 524–628 block save/load, warn+resize on mismatched count |
| Poryscript `emitter/emitter.go` | `d35843ef29929ead47351646d7a33dd5c692b850` | 33–158 assembler emission from AST with generated script labels |
| Poryscript `emitter/chunk.go` | `bb3a6514988eb2699022551d3dbfe2bdce260377` | 21–42 and 67–144 script chunk labels, control-flow branching, textual operands |

The exact revision+blob combination, not a floating branch, is the review key.

## Semantically traced producer → compiled data → consumer chains

### XGBA-MAP-001: authored collision/elevation survives native serialization

1. Porymap's `Block::rawValue` combines three masks. Its default layout encodes **10-bit metatile ID (`0x03FF`), 2-bit collision (`0x0C00`), 4-bit elevation (`0xF000`)**. `Block::setLayout()` *replaces* defaults using project configuration. `Blockdata::serialize` emits 16-bit little-endian values.
2. FireRed `global.fieldmap.h:4–14` declares **exactly these three default masks** for `data/layouts/*/map.bin`. This is a verified default format match, *not* a proof every nonstandard Porymap project config matches every custom ROM.
3. `MapLayout.map` is `const u16 *` (`global.fieldmap.h:92–107`). `InitMapLayoutData` copies the `width × height` u16 stream into `gBackupMapData` with the camera border offsets; `MapGridGetCollisionAt` and `MapGridGetMetatileIdAt` interpret its packed bits. Changing exporter masks without changing target engine masks silently changes game physics.
4. Rendering layers are **not the same as collision bits**: `fieldmap.c:63–81` stores metatile attribute layer type in **bits 29–30 of a separate u32 attribute entry** (`0x60000000`). Porymap image-layer render state is also separate from the `u16` map cell. Preserving collision `map.bin` by itself does **not** preserve source layers or metatile attributes.

**Contract:** export `(metatile,collision,elevation)` using the verified target map-grid masks; export or bind tileset metatile attributes and configured layer semantics separately. Fail rather than modulo-wrap out-of-range authored values. Preserve authored project objects outside `map.bin`; a rendered image is not a semantic export.

### XGBA-MAP-002: finite native virtual map and saved view

- `include/fieldmap.h:6–22` sets a native virtual map max `VIRTUAL_MAP_SIZE = 0x2800` **u16 cells** and horizontal/vertical border offsets. `fieldmap.c:92–124` verifies `(width + MAP_OFFSET_W) * (height + MAP_OFFSET_H) <= VIRTUAL_MAP_SIZE` with a Game Freak assertion, then copies the raw tiles into finite EWRAM. The native native cap is **10,240 cells**, *not* 10,240 raw file bytes; the border means supported authored area is smaller than the cell budget.
- `include/global.h:352` makes `gSaveBlock2Ptr->mapView` a `u16[0x100]` (**256 entries**). `fieldmap.c:452–468` persists a 15×14 (**210 entry**) local viewport.
- **Pinned conditional original bug:** `fieldmap.c:468–488` has `#ifndef UBFIX` checking **0x200 (=512)** u16 elements to see whether the saved view is empty, exceeding the declared **0x100 (=256)** array. The `#else` `UBFIX` path uses `NELEMS` and is bounds-correct for this loop. Which branch executes in a given compiled ROM depends on its actual preprocessor configuration and must be established from that build's compiler evidence; do not assert every ROM exhibits this bug.

**Contract:** expansion map data must not bypass the runtime's allocated backup grid; use validated streaming/sub-area buffers or an explicitly updated runtime, and version save-view data independently. Keep `UBFIX` preprocessor selection and original save-block binary layout in compatibility regression checks.

### XGBA-SCRIPT-001: bytecode operands can be live native pointers

1. Poryscript lowers structured source to generated assembler/labels (`emitter.go` and `chunk.go`). FireRed `data/script_cmd_table.inc` and script-related linker inputs associate opcodes with native command handlers. The source text, generated ASM and linked bytecode are distinct representations.
2. FireRed `ScriptContext` stores `const u8 *scriptPtr`, a 20-address return stack and a four-word data array (`include/script.h`). `RunScriptCommand` directly dereferences and advances `scriptPtr`, reads a command opcode, dispatches through a native table (`script.c:82–144`). `ScriptReadWord` consumes four little-endian bytes as a 32-bit `u32` (`script.c:188–195`).
3. Commands `ScrCmd_goto`, `ScrCmd_call`, `ScrCmd_goto_if` cast operand words to `const u8 *` and jump/call. `ScrCmd_callnative` casts a word to a C function pointer and calls it. `ScrCmd_loadbytefromptr`, `ScrCmd_setptr` and `ScrCmd_copybyte` dereference encoded absolute pointers (`scrcmd.c:118–175, 286–335`). Thus not every 32-bit operand is a relocatable external resource ID; some must remain actual CPU-addressable native function or data pointers.
4. `MapHeader`, object events, coordinate events and background events contain additional `const u8 *script` / `mapScripts` and other direct pointer fields (`global.fieldmap.h:116–206`). A live script can span frames (wait commands), branch into other scripts, or be entered via map headers.

**Contract:** classify every operand, relocation, script-header and C callback pointer by address role and lifetime before any banked or external resource rewrite. Never silently reinterpret native `u32` script pointers as a larger integer space. Remapping a bank containing a pending script/return address or native callback is unsafe without pinning the bank or providing an explicit versioned indirection layer.

### XGBA-LINK-001: linker cannot imply extra ARM address bits

The original linker file `ld_script.ld:4–8` places `ROM` at `0x08000000` and caps its memory region to **32 MiB**; `EWRAM` and `IWRAM` are separate finite regions. Growing the host ROM file does not automatically extend absolute game pointers, the compiled `MapLayout` pointer ABI, execution fetch or DMA/EEPROM arbitration. The external resource system is a *logical provider* mapped via an opt-in ABI, never native unlimited contiguous CPU address space.

## Cross-file semantic review disposition candidates (NOT APPROVED)

| Review subject | Candidate contracts | Evidence status |
| --- | --- | --- |
| Native FireRed `include/global.fieldmap.h`, `src/fieldmap.c`, `include/fieldmap.h`, `include/global.h` | XGBA-MAP-001/002 | Source interpreted and blob-pinned; requires independent whole-file review and compiled macro/build variation verification |
| Native FireRed `include/script.h`, `src/script.c`, `src/scrcmd.c`, `data/script_cmd_table.inc` | XGBA-SCRIPT-001 | Source interpreted and blob-pinned; opcode/operand-by-opcode mapping and callback lifetime coverage still incomplete |
| Native FireRed `ld_script.ld`, `data/maps.s` | XGBA-LINK-001 | Source interpreted and blob-pinned; requires full linker map and image-layout proof |
| Porymap `block.cpp`, `blockdata.cpp`, `maplayout.cpp` | XGBA-MAP-001 | Matching default serialization verified in source; actual compiled editor round trip and extension-specific masks pending |
| Poryscript `emitter.go`, `chunk.go` | XGBA-SCRIPT-001 | Structured-language → assembler lowering interpreted; type provenance of all emitted operands pending |

## Required follow-up review and regression gates

1. Verify the exact `UBFIX` C preprocessor state in each pinned original/modern FireRed build; compile-source and binary evidence must establish behavior, not a comment.
2. Trace `gScriptCmdTable` opcode macros to handler input sizes, argument pointer roles and all lifetime/stack failure paths. Independently verify relocation provenance of ASM-expanded pointers.
3. Test map border, secondary tileset, collision, elevation, layer attributes, warp/object scripts and saved-view behavior on a **compiled pinned ROM**, not only an editor reference model.
4. Prove byte-identical no-op export/import with a pinned Porymap/Poryscript source project, then negative cases for odd/truncated binary, changed masks, unrepresentable fields and unknown compiled-only metadata.
5. Do not move a candidate to the `semantic_dispositions.csv.gz` approved gate until independently reviewed rationale, exact source and evidence digests, and contract IDs are supplied.

**Phase 1 gate remains `FAIL_INCOMPLETE` (14,834 tracked / 4,685 verified text-config / 0 independently approved dispositions).** This document advances actual semantic interpretation and preserves blockers, without claiming Phase 2 architecture solved.

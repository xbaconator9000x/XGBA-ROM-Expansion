# Phase 1 reuse-first dependency and licensing decision record — 2026-11-01

**Status: source-grounded planning / NOT an integration, compatibility or semantic approval.** This is an additive Phase 1 evidence handoff on existing draft PR #8. It does not modify upstream pins, source code, the 14,834-file inventory, 338 P0 candidates, or the authoritative `FAIL_INCOMPLETE` gate. The user prioritises finishing XGBA by adapting mature implementations rather than duplicating them. No Phase 2 implementation is authorised here.

## Immutable source anchors inspected

The following **actual upstream files** were fetched at the original pinned revisions, rather than inferred from project names. Git blob IDs are SHA-1, not machine-dossier SHA-256.

| Source / revision | Inspected file and Git blob | Observed capability / limitation |
| --- | --- | --- |
| [mGBA](https://github.com/mgba-emu/mgba/tree/fd9dc5c2cbf234365068855851107e762fc6211b) `fd9dc5c2cbf234365068855851107e762fc6211b` | `CMakeLists.txt` `834e9fd9ceb94a972941fb7b12494270702601e8`; `src/arm/CMakeLists.txt` `a86f0bea1f38aeb88222fb5b532b4ea9e256767f` | Existing C11/CMake library/core build and enumerated ARM interpreter/decoder/debugger sources; do **not** rewrite a second ARM emulator. |
| same mGBA pin | `src/gba/CMakeLists.txt` `71ab7bbb199ad95422e35ded5774c06a1b2e7c5c`; `src/gba/core.c` `6bfc518bb8899205c07d1d0fc091a287cb42f874` | Existing GBA board, BIOS, DMA, timing, I/O, video, cartridge and core integration surfaces. |
| same mGBA pin | `src/gba/memory.c` `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc`; `src/gba/savedata.c` `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | Existing memory, EEPROM/Flash save implementation; the latter explicitly labels erase/program timing as estimates. |
| [Porymap](https://github.com/huderlem/porymap/tree/26b919d7ff4b54152de010abd5bf344af2ebe116) `26b919d7ff4b54152de010abd5bf344af2ebe116` | `porymap.pro` `53d8055ecfe5d88afb6f183b82d4a3472727ad4f`; `src/project.cpp` `d43b0949303433111d4478ad76117c2b3445dd13` | Existing Qt editor and project read/write path. The project source is 160,129 bytes; reusing it is lower-risk than replacing project serialization without a complete round-trip oracle. |
| [Poryscript](https://github.com/huderlem/poryscript/tree/c32481161c767b25a3425fa9f1f8729927ff3d55) `c32481161c767b25a3425fa9f1f8729927ff3d55` | `go.mod` `edec42698b10015283f4cda9b11d658efc2872c7`; `emitter/emitter.go` `d35843ef29929ead47351646d7a33dd5c692b850` | Existing Go module, parser/emitter pipeline and assembler-script output. Prefer invoking the pinned emitter over authoring a competing language/compiler. |
| [FireRed decomp](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982) `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` | `Makefile` `8b454dbd18eb0069fa5851d788697190890a5b37`; `tools/mapjson/mapjson.cpp` **not yet individually hash-verified here** | Existing build/toolchain and map generator integration. Reuse original rules and map ABI as a reference; no claim of expanded ROM build success. |

## Reuse-versus-build decisions

| Dependency-connected subsystem | Reuse first | XGBA-specific gap and smallest justified work | Risk / acceptance boundary |
| --- | --- | --- | --- |
| ARM CPU instruction decode and execution | mGBA ARM source group and its core APIs, unchanged at pin | Thin, explicitly bounded mapping/trace adapters **only if** the current memory contract cannot express the desired banked resource | Never claim unlimited addressability from mGBA: existing physical mapping limits and cache/prefetch, DMA and savestate interactions require separate evidence. Original ARM macro aliasing is still `NEEDS_REVIEW`. |
| GBA memory, cartridge, save and Flash | mGBA `src/gba/{memory,savedata,core}.c`, existing tests and prior PR #10/#13/#18/#22/#24/#26/#28 observations | Define precise bank identity, bounds, short-write, reset and save persistence contracts; write only adapter/glue with fail-closed error propagation | mGBA native synthetic tests ≠ FireRed stock gameplay ≠ `.sav` restart ≠ physical Flash. The Flash timing constants are source-commented estimates, not hardware certification. |
| Debugger and disassembly | mGBA ARM debugger rather than new debugger | Correctly scope an adapter to debugger APIs; investigate source-level unaligned disassembly PC and unbounded print-count findings from fifth Copilot review | `src/arm/debugger/cli-debugger.c` remains `NEEDS_REVIEW`; **do not import its behaviour as validated** or treat a passing build as semantic signoff. |
| Map and project editing | Porymap Qt project, connection and writer logic | Preserve original project JSON, tile bitfields, connection direction and collision semantics; test save/reopen with real Qt process, then generated native maps | Existing source/static tests do not establish a real editor round trip or fresh-process persistence. Qt dependency and bundled third-party notices need inventory. |
| Script authoring | Poryscript Go emitter, FireRed reader and original assembler | Versioned compatibility shim only where original output/reader ABI differs; compare emitted bytes, relocation/linker tables and interpreter expectations | A successful parser unit test is not linker closure or runtime proof. No silent widening of pointers or table indices. |
| FireRed compilation and layout | Pinned original FireRed Makefile/mapjson plus original agbcc and GNU ARM/preprocessor pins | Reproducible compiler/linker/map-table proof and targeted modifications only after identifying actual placement limits | Do not replace original toolchain, assert binary-equivalence from source inspection, or infer expanded ROM support from an emulator's file loading. |

## Licence and provenance decision boundary

* **mGBA:** pinned root `LICENSE` blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e` is MPL-2.0; `src/gba/savedata.c` and `src/gba/memory.c` carry MPL-2.0 notices. Modified covered files and source availability/notice obligations need review for the **actual** distribution; bundled third-party components require their own inventory.
* **Porymap:** pinned `LICENSE.md` blob `65c5ca88a67c30becee01c5a8816d964b03862f9` is LGPL-3.0; Qt, linked dependencies, bundled vendor code, relinking and redistribution obligations need a separate package-specific review.
* **Poryscript:** pinned `LICENSE.md` blob `bc574ff56a7df993996053c7b2afec43e80bdd64` is MIT; retain the copyright and permission notice when distributing copies/substantial portions.
* **FireRed / agbcc / GNU ARM:** **no combined-distribution clearance is established by this record**. The pinned FireRed README identifies a decompilation, not a blanket licence to redistribute copyrighted game assets or ROM images. Resolve original-toolchain licences and game-content rights separately before any packaging claim.
* A compatible licence is **necessary but not sufficient** for semantic, technical or commercial compatibility. Do not substitute project-level licence labels for per-file/vendor notices.

## Evidence-backed execution order (Phase 1 only)

1. Build a **reuse contract inventory** from the pinned source/API files above, linking each to the original machine dossier SHA-256 and exact source hash. Check dependency closure for mGBA `GBA_CORE`/ARM and memory/savedata before opening more arbitrary partial dossiers.
2. Close high-fanout producer→consumer gaps using existing PR evidence: FireRed mapjson→assembler→linker→map tables; Poryscript emitter→FireRed reader; Porymap save→fresh Qt reopen; mGBA memory→save/savestate and bank bounds. Distinguish source, synthetic, host, compiled, native, stock gameplay, `.sav` and physical Flash results.
3. Only then propose narrowly scoped missing glue and the exact tests it requires; do not start a second emulator, editor, script compiler or ROM build system.
4. Route full-source, hash-verified dossiers to the user-authorised Copilot review lane. Preserve separate historical legacy external-review metrics until a **versioned, tested policy migration** is accepted. The user's newer decision removes a *human* reviewer as a future completion requirement, **not** substantive review requirements.

**Unresolved / non-claims:** No whole-file semantic approval, complete dependency or third-party licence inventory, emulator modification, ROM expansion, native runtime, stock gameplay, fresh-process editor persistence, or hardware Flash evidence is created by this document. Current authoritative gate remains `FAIL_INCOMPLETE`.

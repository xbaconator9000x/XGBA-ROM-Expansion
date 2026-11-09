# Phase 1 P0 whole-file analyst handoff — pinned mGBA ARM CMake source export

**Status: NEEDS_INDEPENDENT_REVIEW, NOT APPROVED.** New independent analyst evidence prepared with connected GitHub pinned-source reads and a bounded host CMake manifest probe. This is a new whole-file semantic-review candidate, not another partial packet, runtime clearance, external approval, or change to the authoritative gate. The previous third candidate `include/mgba/internal/arm/macros.h` remains **NEEDS_REVIEW** following Copilot's substantive strict-aliasing/effective-type objection; this handoff does not override it.

## Original identity and complete file

- Target: `mgba-emu/mgba:src/arm/CMakeLists.txt` at **`fd9dc5c2cbf234365068855851107e762fc6211b`**, packet `docs/phase1-review-readiness/packet-0000-0099.json` **index 63**, priority P0.
- Pinned Git blob **`a86f0bea1f38aeb88222fb5b532b4ea9e256767f`**; 19 source lines, **394 bytes without terminal newline**. Source SHA-256 **`37d9b15aa461a72eba64465856d9377085d6dde56b8ba888e3a4e30f6859390e`**. I read all lines from the pinned GitHub source and independently reproduced both the SHA-256 and Git blob SHA-1 from the exact 394-byte text; adding a terminal newline changes both digests.
- Original machine dossier SHA-256 **`821659a5c9436e3472b409a43e08f66e703a8daff07e0b6cf70d46eaed1d491a`**, as recorded by the immutable original packet; machine state `MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION`, no reviewer or approval. **This analyst did not re-extract and hash the original compressed machine dossier bytes**; the independent reviewer MUST do that, including negative controls, before any receipt.
- Source: https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/CMakeLists.txt . The original file has no per-file license notice; the pinned root `LICENSE` is MPL-2.0, blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`. This is upstream license identification, **not** combined-distribution or legal clearance.

## Complete source semantics, lines 1–19

1. Line 1 `include(ExportDirectory)` imports the pinned module `src/platform/cmake/ExportDirectory.cmake`, Git blob `49e5ff9290c5705ceeb4a771115a8efb68a6eca9`. Pinned root `CMakeLists.txt` line 2 adds `src/platform/cmake/` to `CMAKE_MODULE_PATH`. The macro loops over named lists, prefixes `CMAKE_CURRENT_SOURCE_DIR`, and publishes `<PREFIX>_SRC` using `PARENT_SCOPE`. The `PARENT_SCOPE` boundary is essential; this is **not** a source-file compiler invocation.
2. Lines 2–8 define exactly six ARM core translation-unit paths: `arm.c`, `decoder-arm.c`, `decoder.c`, `decoder-thumb.c`, `isa-arm.c`, `isa-thumb.c`. Lines 10–13 define exactly three debugger paths: `debugger/cli-debugger.c`, `debugger/debugger.c`, `debugger/memory-debugger.c`. All nine were separately fetched at the exact pinned commit, and their Git blob IDs are recorded below.
3. Lines 15–16 place these two lists in IDE `source_group` categories. These lines alone do not prove compilation, linking, runtime invocation, or installed binary membership.
4. Lines 18–19 contain the two final `export_directory(ARM SOURCE_FILES)` and `export_directory(ARM_DEBUGGER DEBUGGER_FILES)` commands; the original machine inventory counts 19 lines because the file has no trailing newline. **Use the actual original text and line numbering from GitHub** rather than relying on this prose's numbering.
5. The pinned root `CMakeLists.txt` (blob `834e9fd9ceb94a972941fb7b12494270702601e8`) unconditionally invokes `add_subdirectory(src/arm)` at line 846. At lines 865–868, `M_CORE_GBA` gates adding `ARM_SRC` and `GBA_SRC` to `CORE_SRC`, and `ARM_DEBUGGER_SRC` and `GBA_DEBUGGER_SRC` to `DEBUGGER_SRC`. At lines 872–876, `ENABLE_DEBUGGERS` gates appending `DEBUGGER_SRC` to `FEATURE_SRC`. Root lines 916–960 assemble `SRC` and create the shared/static library when `SKIP_LIBRARY` is false. Default feature choices are set under `NOT LIBMGBA_ONLY` (lines 47–80), with a separate embedded/library-only branch (lines 94–105). These are source-configured conditional paths, **not evidence of a particular configured build**.
6. The pinned root sets C11 (line 25) and, on non-MSVC, appends warnings and `-fwrapv` (lines 25–40). Neither this manifest nor these settings establishes compiled ARM object, link-map, platform-specific flags, native execution, or strict-aliasing safety.

## Nine pinned source existence checks

| ARM source path relative to `src/arm/` | Git blob SHA-1 |
| --- | --- |
| `arm.c` | `0b92d7f55f1fb853d4b1b9c9163ee086126066e2` |
| `decoder-arm.c` | `074c04314a2a6d4c1c0133d38f128ab0e90d7b1d` |
| `decoder.c` | `21ea0e872c32689b46f7ab746d871a7a1070c97c` |
| `decoder-thumb.c` | `e96ae839613f846fbb477a6ddefc284a745c8e0d` |
| `isa-arm.c` | `af697fa0866fd7511cc430d4a2261704918e15bf` |
| `isa-thumb.c` | `30fcfde9d614dc631c7fd9945bbda3ba99d4f55c` |
| `debugger/cli-debugger.c` | `7e23640470a16d4dc09dc0479cedacdf7c91f4cf` |
| `debugger/debugger.c` | `d5e443ddc3d1af686cfb276a7f89dd489bfa9bac` |
| `debugger/memory-debugger.c` | `f1a76224e1942ddfe56f7314b46616239205d6fe` |

## Executed bounded host probe and limitations

On the analyst host, **CMake 3.31.6** configured a deliberately minimal temporary project containing the original 394-byte ARM manifest (with the final newline difference removed when hashing), the pinned `ExportDirectory.cmake` macro, and a synthetic root that adds the module search path and invokes `add_subdirectory(src/arm)`. The probe asserted absolute exported paths and counts; output: **`XGBA_ARM_MANIFEST_HOST_PROBE_PASS arm=6 debugger=3`**. This is a **synthetic host CMake list-expansion probe only**, not a pinned mGBA whole-build, compiler, linker, emulator, native, gameplay, save, or physical Flash test. The synthetic root is not original mGBA evidence.

## Independent reviewer closure requirements and fail-closed boundaries

Independently read the original complete manifest, root conditional call sites, `ExportDirectory` macro, debugger root and the nine exact original source files. Re-extract and hash **original** compressed machine dossier bytes; check packet 63 identity and negative controls, source hashes, original pinned license notice/coverage and author/reviewer separation. Confirm the root source-list dependency closure and assess any other consumers or alternate build frontends, without extrapolating from a single CMake configuration. Resolve source-list membership for `M_CORE_GBA` and `ENABLE_DEBUGGERS` combinations; do not imply actual compiler/linker output without executing it. Report any unresolved objection as `NEEDS_REVIEW`, not a receipt. If all *applicable source-mapping* requirements are independently satisfied, add a **single receipt-only direct-child commit** to the existing draft PR #8 with exact parent SHA and attributable reviewer provenance; require exact-new-head push/PR CI and a separate durable `COPILOT_REVIEWED/PASSED` attestation. This is **not** a human/external independent approval and must not alter the legacy main gate.

No Phase 2, main/audit write, source pin change, CI weakening, or claims of runtime/compiled/native compatibility are authorized.

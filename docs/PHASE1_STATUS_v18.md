# Phase 1 v1.8 — verified semantic mapping checkpoint

**Recorded:** 2026-10-25. **Decision:** `FAIL_INCOMPLETE`. **Source pinned:** five unchanged upstream commits; no emulation engine patch has been implemented.

## Authoritative reproducible evidence

- [Passing Phase 1 run #40166434213](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40166434213) contains the full downloadable 20 MB compressed audit output.
- Uploaded, import-verified [v1.5 workpack](../imports/XGBA_Phase1_v1.5_Complete_Workpack.zip) retains the **29,068-entry mapping register**, including all earlier 500-record checkpoints.
- The canonical Git blobs for **14,834 tracked files** were verified. **2,612 palette files** undergo checkout CRLF normalization; their original Git bytes were checked separately.
- **4,685** source/config files were read and SHA-verified.
- **2,832** C/C++/Go/Python files were syntax-tree parsed, yielding **39,530** function definitions (AST candidates), **91,399** single-candidate direct calls; **1,514** of these files have parser errors and are not accepted as understood. Unsupported formats and dynamic calls also remain.
- **1,235** assembler/build/linker files indexed, including **13,824** source-label candidates, **9,417** directives, **857** Make targets, and **9** linker memory declarations.
- **25/25** exact pinned-source compatibility assertions passed; Poryscript `go test ./...` and `go build ./...` passed.
- **22,916** distinct *candidate* typed dependency edges and **65,589** observed sites. Edges break down into 8,755 preprocessor includes; 5,775 AST unique-name call candidates; 1,760 explicit asset paths; 869 assembly/build includes; 5,692 generated PNG/PAL source chains; 62 composite graphics constituent links; and 3 opcode-table edges.
- **6,172 generated resource literal references**: 6,155 correspond to tracked source files via general Make rules, and the remaining **17** are accounted for by **62 ordered, source-hash-anchored constituents** of explicit composite Make rules. This is build-rule analysis, not execution of the graphics converter.
- **213 field-script and 248 battle-script opcode slots** validated against their pinned command tables, dispatch consumers and all **461 handler definitions**. The per-opcode argument semantics have not been fully verified.

## Directly inspected subsystem semantics

1. [v1.5 critical CPU/save/script contracts](CRITICAL_SOURCE_CONTRACTS_v15.md).
2. [v1.6 CPU instruction fetch, DMA, Matrix, typed maps and ARM/linker memory constraints](SEMANTIC_DEPENDENCIES_v16.md).
3. [v1.7 sprite decompression/VRAM, audio headers and separate battle-script bytecode consumers](RESOURCE_AND_BATTLE_SEMANTICS_v17.md).
4. [v1.8 generated graphics conversion and field/battle opcode dispatch](BUILD_ASSET_AND_OPCODE_SEMANTICS_v18.md).

## Required mapping-completion work

**0 / 14,834 independent file semantic dispositions are currently approved.** This is the explicit, fail-closed gate outcome; automated source-index records and opcode mapping are not equivalent to complete file-level semantic understanding.

Remaining: correct grammar/parser limitations; preprocess conditional C/C++ configurations and verify compile/link symbol resolution; interpret unresolved generated and third-party dependencies; map side effects, ownership and lifetimes through indirect function pointers and all opcode operands; establish semantics for uninspected assets and source files; test critical map/script/audio/sprite/save transitions and document exclusions; assign each file a substantive evidence-backed signoff or exclusion under the Phase 1 gate. All source/change hashes must remain pinned and reproducible.

This checkpoint does **not** claim an unlimited-size ROM is executable, nor that any emulator, patcher or external-memory sidecar was implemented or tested. Phase 2 implementation and runtime testing are separate.

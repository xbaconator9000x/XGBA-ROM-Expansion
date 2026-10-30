# Independent Poryscript → FireRed map-script ABI review

**Date:** 2026-10-30
**Scope:** Phase 1 only. Source-backed review of pinned Poryscript map-script parsing/emission and FireRed table assembly, preprocessing, dispatch, and build ownership.
**Disposition:** Review candidate only; no approval registered. The authoritative gate remains `FAIL_INCOMPLETE`, with existing independent approvals unchanged at 0.

## Reviewer and evidence identity

- **Reviewer:** `@copilot` (GitHub Copilot Coding Agent, issue #33 review).
- **Prior source interpreter:** `xbaconator9000x` (the source packets in PRs #16, #20, and #21). The reviewer identity is distinct, and the pinned upstream sources were inspected directly rather than accepting the packets' conclusions. This record is not a separate human attestation and does not count as a whole-file approval.
- **Immutable sources:** `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`; `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- **Original evidence packets:** PR #16 head `dd6fb2c8e6ec15818ccb841760b540a04dc8212d` (synthetic emitter-shaped Clang/LLD test); PR #20 actual-CLI packet, witness head `587132181ef728b635968dd091b1cf171e78f753`; PR #21 root Makefile packet head `a324b99b486d56d57eab94049a2a25ad091a862b`.
- `review.json` contains the exact Git blob SHA-1 and whole-file SHA-256 for each source, plus SHA-256 hashes for every cited line range.

## Source-backed trace

### Producer and label ownership

Poryscript's `parser/parser.go:1162–1315` stores direct map scripts separately from table-based scripts. It synthesizes inline script names from the mapscript name/type (and table entry index), and table labels from mapscript name/type. `ParseProgram` (`parser/parser.go:338–400`) checks duplicate text and movement names, but adds no equivalent map-script type, duplicate tag, or sentinel-value validation. `emitter/emitter.go:112–157` emits the mapscript label, `map_script` records, a one-byte zero sentinel, table labels/records and a two-byte zero sentinel. For a table type, `map_script_2` receives the first operand, comparison operand, and script label in that order. `emitter/chunk.go:21–37, 67–85` adds generated `_N` labels for control-flow chunks and emits the entry point with the source scope; explicit Poryscript script labels remain source-owned.

The top-level `mapscripts` label defaults to global scope. FireRed's preprocessor recognizes `::` and emits `label: ; .global label` (`asm_file.cpp:163–185`, `preproc.cpp:96–108`); direct GAS assembly of the CLI output is therefore not the native source path.

### FireRed table layout and consumers

At the pinned FireRed source:

| Record | Producer macro | Consumer | Size and termination |
|---|---|---|---|
| Outer map-script record | `asm/macros/map.inc:9–13` — one type byte and `.4byte` script pointer | `src/script.c:382–400` | 5-byte stride; one-byte zero type terminator |
| Conditional record | `asm/macros/map.inc:15–20` — two `.2byte` operands and `.4byte` script pointer | `src/script.c:409–436` | 8-byte stride; zero first halfword terminator |

`include/constants/map_scripts.h:4–10` assigns table tags 2 (`ON_FRAME_TABLE`) and 4 (`ON_WARP_INTO_MAP_TABLE`). `TryRunOnFrameMapScript` and `TryRunOnWarpIntoMapScript` call `MapHeaderCheckScriptTable`; the other listed map events go through `MapHeaderRunScriptType` and execute the pointer as script bytecode (`src/script.c:438–479`). `MapHeader` stores the map-script pointer at offset `0x08` (`include/global.fieldmap.h:191–210`).

The outer `.4byte` relocations are unaligned because each record is five bytes. FireRed's `T2_READ_PTR` reconstructs a pointer from four individual little-endian byte reads (`include/global.h:106–115`), not a naturally aligned 32-bit load. The actual-CLI witness observed relocations at offsets 1, 6, 15, and 23; its successful byte/link checks support that fixture-level interpretation.

The conditional operands are not both necessarily variable IDs. `VarGet` returns a variable's stored value when `GetVarPointer` finds a variable, and returns the input unchanged for non-variable values (`src/event_data.c:186–214, 235–241`; `VARS_START` is `0x4000`). This matches Poryscript's documented comparison-value syntax. The witness verifies serialized bytes; it does not execute the conditional test.

### Build integration and ownership boundary

The FireRed root Makefile collects `data/*.s`, assembles data sources through preproc → CPP → enum-enabled preproc → ARM assembler, then links the object set and emits a ROM (`Makefile:181–184, 342–344, 386–395`). `map_data_rules.mk:22–34` invokes mapjson for generated map headers; `mapjson.cpp:142–154` writes each header's `<MapName>_MapScripts` pointer (or an explicit `shared_scripts_map` target). `data/maps.s:11–17` includes the generated map headers, and `data/event_scripts.s:90–105` includes the map `scripts.inc` assembler files.

This closes the pointer and assembler ownership path for FireRed's existing assembly inputs, but not Poryscript's integration into that source build: the CLI witness compiles a synthetic `.pory` fixture through the pinned FireRed preprocessor and macros, then GNU ARM as/ld. It does not inject output into the complete root Makefile/ROM build. The root Makefile's stages must not be conflated with the bounded witness.

## Objections and resolutions

1. **Parser accepts table/direct type mismatches and duplicate tags.** The mapscript parser branches on the following punctuation (`:`, `{`, or `[`) and appends the chosen AST record without checking that the type is a table type, and without rejecting duplicate type tags. FireRed's type-2/type-4 callers expect conditional-table bytes; direct types expect script bytecode. The outer consumer returns the first matching tag, so duplicates shadow later entries.
   **Resolution:** Confirmed source-level contract objection. Keep the Poryscript parser/emitter per-file verdict at `NEEDS_EVIDENCE`; require actual-CLI negative fixtures and a parser rejection or documented semantics before approval.

2. **Zero conditional first operand collides with the terminator.** Poryscript forwards the operand into `map_script_2` and appends `.2byte 0`; FireRed checks the first halfword for zero before reading the rest of a conditional record. Thus a table entry whose first operand is zero is consumed as end-of-table, hiding it and subsequent entries. The source parser has no zero guard.
   **Resolution:** Confirmed source-level objection, but no actual-CLI run for this malformed input was performed. Require a zero-operand negative fixture and explicit rejection or a different pinned ABI proof.

3. **Malformed native input is not bounds checked.** Both FireRed reader loops are open-ended and receive no byte length. Missing sentinels, truncated records, and out-of-range script pointers have no source-level bound check here.
   **Resolution:** Unresolved. Existing host bounded decoding and compiler mutation controls validate the witness/validator, not native malformed-table safety.

4. **Earlier synthetic fixture could be mistaken for actual CLI evidence.** PR #16 manually formed emitter-shaped assembly; direct GAS also rejects Poryscript's `::` label form.
   **Resolution:** PR #20's exact-head witness is used instead. It executes the pinned CLI, confirms optimized/unoptimized output equality for its fixture, applies the pinned FireRed preprocessor and macros, and uses GNU ARM tools. The direct-GAS failure is retained as negative evidence about a missing stage, not as a product defect.

5. **The witness does not prove complete root-build integration.** The root Makefile has additional CPP/preprocessor/assembler/linker stages and generated map-header ownership.
   **Resolution:** The source path is traced, but the boundary remains explicit: no full ROM build or Poryscript CLI insertion into that build is claimed.

## Validation and reproducibility

The exact successful existing run was workflow **#40506170513**, job **122195911391**, at head `587132181ef728b635968dd091b1cf171e78f753`. It ran:

```text
python3 -m py_compile tools/verify_poryscript_actual_cli_arm_table.py
python3 tools/verify_poryscript_actual_cli_arm_table.py --poryscript upstream-poryscript --firered upstream-firered --output phase1-evidence/poryscript-real-cli-gnu-arm-table.json
```

Result: actual pinned CLI and FireRed preprocessor/macro use; `R_ARM_ABS32` at 1/6/15/23; optimized/unoptimized fixture output equal; **7/7 assembly mutation controls passed**. Artifact `12735216391` (`phase1-poryscript-real-cli-gnu-arm`) has ZIP SHA-256 `37cc5d0e03fd481c61721816533b8869709b1a23b7b9bc6f76df701252f988e5`. The emitted-output, unlinked-rodata, and linked-rodata SHA-256 values are in `review.json`.

The local rerun was blocked: `go` is installed, but `arm-none-eabi-as` and `arm-none-eabi-ld` are absent, and the workspace has no exact-pinned Git checkouts required by the reusable checker. The source blobs and line-range hashes were independently checked from raw immutable upstream references with:

```text
python3 tools/copilot_poryscript_abi_review.py --poryscript-root /tmp/copilot-poryscript-review/sources/poryscript --firered-root /tmp/copilot-poryscript-review/sources/pokefirered --source-files-only
```

That command checks file and excerpt hashes only; it explicitly does not claim local Git HEAD verification or rerun the actual CLI witness. The new tool also validates the review manifest without mutating the shared queue/register/gate.

## Proposed per-file verdicts

Every listed verdict is `NEEDS_EVIDENCE`, not an approval. The parser's source-level contract objections are confirmed, but the complete files were not dispositioned, actual-CLI negative inputs were not run, and the native reader's malformed-input behavior remains unresolved. Supporting integration files are source-pinned in `review.json` and are not represented as whole-file approvals.

**Accounting:** new approvals 0; existing approval total remains 0; no shared queue/register/gate edits; Phase 2 untouched.

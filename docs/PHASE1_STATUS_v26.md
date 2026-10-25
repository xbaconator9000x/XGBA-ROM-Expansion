# Phase 1 v2.6 — complete compiled FireRed symbols and source-object dependencies

**Reproducible proof:** [Successful original and modern compiler build, run 40189025048](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40189025048). [Permanently archived v2.6 evidence and checksum](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.6).

**Gate: FAIL_INCOMPLETE.** This is compiler/binary-semantic evidence, **not** completed whole-file semantic dispositions, a stable public ABI declaration, or proof of an implemented XGBA runtime. Reproducibility is limited to the two pinned FireRed build variants.

## Full executable symbol provenance

Both ELFs were built using the same pinned `pret/pokefirered` commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` in original agbcc and modern GCC modes.

| Measured category | Classic agbcc | Modern GCC |
| --- | ---: | ---: |
| All defined GNU-nm ELF symbol entries | **201,263** | **201,024** |
| Distinct global symbol names | **28,251** | **28,273** |
| Local defined symbol entries (including assembler-generated/absolute entries) | **173,012** | **172,751** |
| Compiled object files | **649** | **649** |
| Objects source-linked to exact pinned Git blobs | **649** | **649** |
| Cross-object undefined-symbol reference sites | **25,632** | **25,544** |
| Unique compiled provider candidates for those references | **25,119** | **25,111** |
| Linker/archive/external references not directly resolved among build objects | **513** | **433** |

The **347 MIDI-generated objects in each variant** are now mapped to exact tracked `.mid` input files and Git blob hashes, in addition to the 302 C/assembly-source objects. No compiled object remains unaccounted for by the source-path inventory in these two builds.

There are **28,172 symbol names shared** between the compiled variants. Their comparison yielded:

- **24,615:** address changed, size unchanged.
- **3,262:** address *and* size changed.
- **8:** region changed; mostly linked allocator/runtime state such as `__malloc_av_` and `_impure_ptr` (further semantic interpretation required).
- **1:** size changed at unchanged address (`AgbMain`).
- **286:** unchanged reported address and size; this **does not** prove byte-identical code/data.
- **79:** present only in classic.
- **101:** present only in modern.

Examples of differing GBA addresses in the *pinned compiled binaries*:

| Symbol | Classic | Modern | Role |
| --- | --- | --- | --- |
| `gScriptCmdTable` | `0x0815F9B4` | `0x08186010` | Field script dispatch |
| `gBattleScriptingCommandsTable` | `0x0825011C` | `0x082047A4` | Battle script dispatch |
| `gMapGroups` | `0x083526A8` | `0x08646230` | Map group table |
| `gSaveBlock1Ptr` | `0x03005008` | `0x03006F94` | Active legacy save-block pointer location |

### Meaning for XGBA

1. The user-facing *game and source code* can match while compiled symbol addresses differ materially. Future plugins cannot safely choose hardcoded offsets by ROM title.
2. The full symbol census is **not** a stable public API: local and compiler-generated entries may change or disappear, and a matching global symbol name does not prove identical bytes or function behavior.
3. The 649-per-variant source-to-object inventory can be used to trace symbols to pinned C, assembly and MIDI sources. Cross-object name matching supplies compiler-generated **provider candidates**, not guaranteed linker selection in the presence of weak symbols and archives.
4. Only exact binary hashes, manifest IDs, versioned adapter contracts and resource ownership checks can qualify a particular future patch as compatible. A SHA match alone does not grant a new address space.

## Evidence artifacts and remaining acceptance work

The [v2.6 release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.6) includes:

- `compiled_all_defined_symbols.csv.gz` (all classic and modern defined symbols).
- `compiled_global_symbol_semantic_delta.csv.gz` (classified shared and variant-only global symbol differences).
- `compiled_object_source_provenance.csv.gz` (all 1,298 build objects linked to pinned source blobs).
- `compiled_object_symbol_dependencies.csv.gz` (compiler-produced undefined-to-defined source-object candidates).
- Two ELF cryptographic hashes, original 11 critical-source ABI checks, binary-identity fingerprints, and a checksum.

The original **14,834-source file** and **29,068 historical/candidate mapping record** inventory remains preserved in the [v2.5 six-pipeline release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.5) and imported workpack.

**Still open:** 0/14,834 independent source-level dispositions; complete path-dependent opcode semantics; library/linker script symbol resolution for 513/433 references; asset consumption and runtime resource lifetime; compiled ROM-to-authoring round-trip; supported external memory/streaming protocol; and future ROM/emulator adapter validation. None is silently approved by the symbol census.

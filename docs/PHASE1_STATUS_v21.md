# Phase 1 checkpoint v2.1 — expanded semantic evidence

**Decision: FAIL_INCOMPLETE.** Pinned source census and machine-derived dependency inventory are complete; comprehensive, independent per-file semantic approval is not.

## Reproducible, source-hash-pinned coverage

| Area | Completed evidence | Important remaining limitation |
| --- | --- | --- |
| Five immutable repositories | 14,834 tracked files; 4,685 source/config files scanned; every original Git blob SHA verified | Does not prove code behavior for all files |
| Mapping register | 29,068 source-linked original/candidate records, 500-record checkpoints, source anchor validation | Candidate rows are not approved semantics |
| Module review map | 163 modules covering all 14,834 files; priorities and cross-module dependencies; 0 approved modules | 53 modules have AST grammar errors; 47 have unresolved includes |
| Script dispatch | 213 field + 248 battle function-pointer table entries, all linked to original handler definitions | Complete bytecode C side-effects and pointer lifetimes unverified |
| Assembler ABI | 461/461 script opcodes have source-backed macro emission evidence, including conditional macro variants; 426 fixed-width literal macro variants and 33 nontrivial variants among 459 direct macro variants | Assembly-emission source is not a complete runtime operand-role proof |
| Conditional field opcodes | 8 variants 0x4F–0x56 have proven source emitter width **and matching C handler read order** | Movement script resource ownership and scheduling still require targeted review |
| Map compiler | 425/425 maps; 850 compiled event/script pointer directives checked; four native compiler fixtures independently exercise local/shared events and scripts | Binary ROM reverse-import semantics and runtime event editing not tested |
| Cross-map object clones | All nine intentional off-layout clones resolved to original target maps/local IDs | Arbitrary third-party map extensions may behave differently |
| mGBA compiled dependency baseline | 173 source compilation units, 3,126 compiler-selected header relations, 1,403 linked object-symbol dependency edges | Current verification is a selected headless build configuration |
| FireRed ARM ABI baseline | Original FireRed/agbcc toolchain built pinned source; source-linked ELF address and script/sprite table-size constraints verified | No XGBA runtime, external sidecar, or emulator compatibility build implemented |
| Source-change drift | 14,834 unchanged files in all five pinned baselines, zero changed/added/deleted source files; version-aware reverse-impact checker included | Changed external versions require new compile evidence, ABI signoff and review |

## New source contracts

- [All opcode assembler emission and C consumer width checks](SCRIPT_ASSEMBLER_ABI_v21.md), including conditional map argument encoding and explicit movement-object bytecode widths.
- [Porymap independent event/script sharing](PORYMAP_SHARED_MAP_SEMANTICS_v21.md).
- [Native map clone behaviors](CLONE_CROSSMAP_SEMANTICS_v20.md).
- [CPU fetch, DMA, Matrix, save and editor semantics](SEMANTIC_DEPENDENCIES_v16.md).

## Source of truth

- [Verified main Phase 1 audit with all opcode macro branches](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40183416216).
- [Successful 425-map native pointer alias compiler test](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40182501905).
- [Preserved Phase 1 v1.9 full GitHub Release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v1.9).
- Source-compiled Porymap Qt meta-object ABI verification is **under active revalidation**, not passed in this checkpoint.

**Outstanding acceptance criteria:** approve source-backed dispositions or narrow justified exclusions for all 14,834 tracked files; reconcile unresolved preprocessor/config and runtime indirect edges; verify resource table, memory mapping, pointer role, editor and save-state contracts. No file gets semantic clearance from a regex hit or a zero-diff source hash. No unlimited-sized ROM or sidecar implementation has been delivered.

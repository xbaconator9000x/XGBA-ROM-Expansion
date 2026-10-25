# XGBA Phase 1 status — verified v2.2 checkpoint

**Source inventory and provenance: PASS. Focused compiled semantic contracts: PASS. Whole-file semantic signoff: FAIL_INCOMPLETE.**

## Permanent reproducible evidence

[**Phase 1 v2.2 release archive**](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.2): includes all five pinned-repository evidence pipelines, source/asset semantic candidate graph, compiled mGBA, FireRed ARM ABI and maps, compiled Porymap Qt, code-source review obligations, source-hash checkpointed mapping records, release-level integrity checksum and provenance. [Release workflow result](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40185298009).

Previous verified intermediate source mapping remains in [v1.5 imported workpack](../imports/XGBA_Phase1_v1.5_Complete_Workpack.zip).

| Dimension | Verified result |
| --- | --- |
| Immutable upstream tracked files | **14,834 / 14,834** exact source blobs verified |
| Indexed source/config files | **4,685** |
| Original plus candidate mapping register | **29,068** source-anchored rows and 500-record checkpoints |
| Structural review dossiers | All **14,834** files assigned across **163** module review dossiers |
| Candidate dependency graph | **22,916 typed edges** from AST, includes, assembler, generated assets and indirect dispatch |
| Built and indexed mGBA source | **173** compiler units in pinned headless configuration |
| Built original FireRed compiler, mapjson and ABI proofs | **425** native-compiled maps; **850** correct map event/script pointer fields; **four positive sharing fixtures** |
| Cross-map object clones | **9/9** intentionally out-of-layout clone target IDs verified |
| Built Porymap Qt source | **213** compiled translation units (including **89** qmake-generated moc/rcc), **21** source-backed ELF/MOC signals |
| Porymap map sharing contracts | **12** source-anchored independent event/script inheritance checks |
| Field and battle script opcode handlers | **461/461** source and assembler accounted for: **213 field, 248 battle** |
| Eight conditional field opcode variants | **8/8** assembler operand read widths matched with pinned C handlers |
| Field assembler ↔ C read width assessment | **213** distinct command slots, including **106** straightforward source read matches, **8** conditional matches, **46** branch-flagged matches, **19** native/raw-pointer-role flagged matches, **28** macro grammar review items and **6** genuine legacy no-consume variants |
| Battle opcode cursor survey | **248**, with **20** literal command-length cursor advances matched, **8** terminal/helper-delegated cursor cases, **219** branched/reassigned cursor cases and one multiple-macro case |
| Legacy NOP compatibility | **six** original dummy handlers, **19** direct `hidemoneybox` script invocations and verified two-byte literal-zero padding. **Opcode 0x00 must remain a vanilla NOP** |
| 32-bit script-word role contracts | **19** verified handler types with **21** source-verified 32-bit reads: byte-memory read/write, native callbacks, script targets, virtual-script rebasing |
| Source revision compatibility/drift | Five exact pinned Git revisions unchanged, source drift checker validates and flags ABI-sensitive changes |

## Critical new technical contracts

- [The original game genuinely executes NOP padding](LEGACY_NOP_SCRIPT_ABI_v22.md). Do not use unnegotiated opcode zero as XGBA escape or automatically skip dummy operands.
- [19 distinct pointer-role contracts](FIELD_POINTER_ROLES_v22.md). The same 32-bit field-script operand ABI can mean writable/readable RAM, native C callback, script PC or rebased script address.
- [Assembler opcode dispatch and width contracts](SCRIPT_ASSEMBLER_ABI_v21.md). The original 461 script opcode entries have source-backed macro provenance, with an explicit separate set of conditional command variants.
- [Cross-map clone preservation](CLONE_CROSSMAP_SEMANTICS_v20.md). Do not clamp or discard nine original off-layout object templates.
- [Porymap independent script and event sharing](PORYMAP_SHARED_MAP_SEMANTICS_v21.md). Preserve each map's distinct pointer/inheritance relationship and custom authoring fields.
- [mGBA instruction fetch, peripheral priority and FireRed toolchain limits](SEMANTIC_DEPENDENCIES_v16.md), [sprite/audio/battle consumers](RESOURCE_AND_BATTLE_SEMANTICS_v17.md).

## Outstanding acceptance work

**Phase 1 mapping gate: 0/14,834 independently approved whole-file semantic dispositions, not a pass.** The large source and dependency inventory is correct, but automatically collected lexical/AST/source evidence must not be mislabeled as complete understanding. Outstanding obligations:

1. Every source/asset file requires a documented semantic disposition or justified exclusion with provenance and approved review; especially **338 heuristic P0 file candidates** and subsequent P1 reviews.
2. **219** battle handlers with branched cursor movement, and the field bytecode handlers with branch/macro/native pointer roles, require path-dependent control/data flow and side-effect analysis. Source/assembler emission matches alone do not prove runtime execution.
3. Reconcile conditional compilation, unresolved helper and function-pointer relationships and source assets with the actual target build variants. The current compiled evidence spans selected pinned configurations, not all future decomp forks and emulators.
4. Verify runtime ownership and lifetime for expanded ROM bank switching, save states, graphics staging, audio headers, script contexts and editor object layering/round-tripping.
5. Distinguish Phase 1 semantic mapping signoff from **Phase 2** actual extension patches, emulator support, compatibility plugin ABI and end-to-end execution. None of those implementation claims has been made.

### Completion rule

No Phase 1 PASS without source-backed dispositions and independent verification of declared dependencies/exclusions. No claim that an arbitrary multi-gigabyte GBA ROM can execute on native hardware or an unchanged emulator.

**Current phase: Phase 1 — semantic verification ongoing.**

# Phase 1 P0 — Poryscript emitter to FireRed map-script ABI (27 October 2026)

**Status: PINNED_SOURCE_CANDIDATE / FAIL_INCOMPLETE.** This maps a previously under-reviewed Poryscript/FireRed authoring boundary. It is not compiled equivalence, runtime/editor interoperability, an independent whole-file disposition or Phase 2 work.

## Immutable upstream evidence

Poryscript: [huderlem/poryscript at c32481161](https://github.com/huderlem/poryscript/tree/c32481161c767b25a3425fa9f1f8729927ff3d55). Exact Git blobs:

| File | Git blob SHA-1 | Role |
| --- | --- | --- |
| emitter/emitter.go | d35843ef29929ead47351646d7a33dd5c692b850 | Map-script table emission, control-flow chunking and optimized label ordering |
| emitter/chunk.go | bb3a6514988eb2699022551d3dbfe2bdce260377 | Script labels, implicit terminators, fallthrough and post-branch chunks |
| emitter/branch.go | 9413b4699597e453c4ca8df4e1d6be9c68d250a2 | Conditional and switch rendering |
| emitter/emitter_test.go | 4c3209166937384a0dc26fc83a0341a5dac48ca5 | Expected optimized and unoptimized assembler text |
| main.go | 10db05ef1518460da78b0bd41f22bb091917a385 | CLI defaults and parse/emit configuration |

FireRed: [pret/pokefirered at ce6406d8](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). Exact Git blobs:

| File | Git blob SHA-1 | Role |
| --- | --- | --- |
| asm/macros/map.inc | 83ef472c926ce767c9133ab9bd6922280b38bb2d | Native map_script and map_script_2 record widths |
| asm/macros/event.inc | 142ad979d7d3093244087a247fa2b4883424f77f | Comparison dispatch, switch scratch variable and branch macros |

## Source-grounded contracts

**PSFR-001 — Map-script tables are typed binary records, not just labels.** Poryscript's emitMapScriptStatement writes map_script entries followed by a one-byte zero terminator; its conditional table emits map_script_2 entries followed by a two-byte zero terminator. FireRed's map.inc defines each map_script as a one-byte type plus four-byte script pointer, and each map_script_2 as a two-byte variable, two-byte comparison and four-byte pointer. An extension cannot repurpose the terminators, widen pointers or serialize the table as a generic list without a compatible loader. This is an exact source-format match, not an assembled-byte comparison.

**PSFR-002 — The native switch macro has a script-visible scratch dependency.** Poryscript's switchBranch emits switch followed by case directives. FireRed's switch macro executes copyvar into VAR_0x8000, and each case compares VAR_0x8000 against its condition. Consequently, generated switch control flow has a hidden write to VAR_0x8000 and a dependency on its contents across case comparisons. Any alternate script assembler, rewriter or virtual machine must preserve this side effect or prove a compatible replacement. This does not establish that an authored script currently corrupts that variable.

**PSFR-003 — Comparison mode affects operand meaning.** Poryscript renderVarComparison normally emits compare but selects compare_var_to_value for an AST StrictValueComparison. FireRed's generic compare macro classifies its second argument as a variable identifier when it lies in its variable/special-variable ranges, otherwise as an immediate. Reconstructing a Poryscript expression from emitted assembler or bytecode must retain whether the comparison was strict value or range-sensitive. Flag comparisons and goto_if macros use separate native paths.

**PSFR-004 — Source control-flow identity is not preserved by emitted bytecode.** chunk.go assigns a base entry label to chunk 0 and numbered labels to generated chunks, rejects authored labels that collide with generated chunk/text labels, emits return when returnID is -1 unless explicitly configured for end, and emits goto when the return chunk is not physically next. emitter.go optionally reorders chunks to exploit fallthrough and suppresses unused generated labels. Both optimized and unoptimized expected outputs are represented in the pinned emitter test. The CLI defaults to optimization and line markers enabled, but line markers require an input filepath. These are provenance and source-reconstruction constraints, not proof of a reversible compiler.


## Native consumer closure — script.c and event_data.c

The producer-side map record interpretation above now has an exact-pinned FireRed reader join:

- [src/script.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c), blob d0433bdda062b138e53d1a1d3184b4566ad7d9dc: MapHeaderGetScriptTable scans tag+pointer entries in **five-byte strides** until the **one-byte zero tag**, then returns the pointer for the matching tag. MapHeaderCheckScriptTable reads a **two-byte first variable**, stops if zero, reads a **two-byte second operand**, compares both via VarGet and otherwise advances four bytes over the pointer, giving an eight-byte entry. This directly confirms both Poryscript-emitted terminator widths and FireRed macro record widths.
- [src/event_data.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/event_data.c), blob da9391cf0ef74c1addf550def8616c81f16e89e3: VarGet returns its input unchanged if GetVarPointer returns NULL, otherwise dereferences the variable pointer. GetVarPointer returns NULL below VARS_START, indexes saved variables below SPECIAL_VARS_START, and otherwise indexes gSpecialVars. Thus the table's second operand can act as an immediate or a variable ID under the pinned variable ABI; the first operand value **zero is reserved as a sentinel**. No local table-length guard appears in these reader loops, so malformed/truncated data remains an unverified safety boundary, not a proven gameplay exploit.

The source checker now pins **nine** upstream blobs and rejects **24** semantic mutations, including incorrect reader strides, sentinels and VarGet behaviour. Exact-head [GitHub Actions #40380232920](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380232920) passed at 38c197926a93508bea36d249fecf0dc23a984668; archived [artifact #12677781784](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380232920/artifacts/12677781784), digest SHA-256 ea8b18cbd9ecf95af4594d4088ca4af5b2a6476762f5a1a10dc013aea40ee6b3. A subsequent documentation-only head must be rechecked. This closes the **source-level producer/consumer width join**, but does not close compiled output, invalid-table runtime behaviour, editor round trips or independent review.

## Reproducibility and review boundary

Run the [nine-blob fail-closed source checker](../tools/phase1_poryscript_firered_map_script_abi.py) against the two pinned upstream checkouts. It validates bounded producer/consumer anchors, verifies exact upstream commits and Git blob hashes, and requires **24 in-memory semantic mutations to be rejected**. The dedicated workflow archives JSON evidence, including negative-control count, without incrementing the authoritative gate.

The [whole-file chunk.go candidate](phase1-disposition-candidates/0009-poryscript-chunk.md) inventories all functions, including the nonbranching label/command paths. It is pending an actual independent reviewer.

**Unresolved:** compiled assembler bytes for map-script tables; malformed/truncated table runtime behaviour; conditional switch scratch-variable reachability; parse/emit round trips across compile flags; label uniqueness across top-level scripts; ROM-bytecode-to-source information loss; Porymap/FireRed editor integration; independent whole-file review.

**Gate: FAIL_INCOMPLETE. Independent whole-file approvals: 0/14,834. No Phase 2 implementation.**

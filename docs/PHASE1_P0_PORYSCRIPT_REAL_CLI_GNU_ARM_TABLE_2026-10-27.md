# Phase 1 P0 — actual pinned Poryscript CLI output to GNU ARM map-table object

**27 October 2026.** Status: **TEST SUBMITTED / CI NOT YET VERIFIED / FAIL_INCOMPLETE**. This is a narrowly scoped producer/assembler/linker test using a synthetic input, not a FireRed stock ROM, mGBA execution, independent approval, or Phase 2 implementation.

## Why this packet is distinct

Draft PR #16 proved that a manually constructed Poryscript-emitter-shaped table assembled with Clang and linked with LLD. It explicitly did **not** run the actual Poryscript executable to generate that table. This packet closes that particular producer gap by building the **actual pinned Go CLI** and passing its original emitted assembler text to **GNU ARM binutils**. No source transformation of emitted labels, record widths, directives, or sentinels is allowed.

## Immutable source owners and dependency closure

- Poryscript `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`: `main.go` (blob `10db05ef1518460da78b0bd41f22bb091917a385`), `emitter/emitter.go` (blob `d35843ef29929ead47351646d7a33dd5c692b850`), and `emitter/emitter_test.go` (blob `4c3209166937384a0dc26fc83a0341a5dac48ca5`).
- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`: `asm/macros/map.inc` (blob `83ef472c926ce767c9133ab9bd6922280b38bb2d`) and `src/script.c` (blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`).
- Producer: Go CLI parses a synthetic `mapscripts` definition containing one direct transition script and two on-frame conditional entries. Three raw one-byte script placeholders provide relocation targets without requiring the full FireRed script opcode macro closure.
- Consumer: FireRed's five-byte tag/pointer reader and eight-byte conditional table reader remain pinned source anchors.
- Build: exact FireRed `map_script` and `map_script_2` macro bodies are prepended to the **unmodified CLI output**. The assembler receives only a synthetic section directive and two symbolic map-script constants in addition to the real output.

## Expected fail-closed controls (not yet verified by CI)

The checker requires the optimized and unoptimized CLI outputs to match for this deliberately simple fixture, verifies table record order and both terminators, and checks the GNU ARM object and linked `.rodata` bytes against explicit expected arrays.

Expected outer records: 2 × 5 bytes, followed by one-byte zero; conditional records: 2 × 8 bytes, followed by two-byte zero; three one-byte script placeholders. Expected four `R_ARM_ABS32` relocations at byte offsets **1, 6, 15, 23**. The linked target offsets should be **29, 11, 30, 31** relative to a synthetic `0x08000000` section base.

Seven in-memory assembly mutations (tag, outer sentinel, conditional variable, comparison value, pointer target, native macro pointer width and script payload) must be rejected by compilation or byte/relocation validation. These are regression controls, not independently observed gameplay defects.

The actual output and object hashes are deliberately recorded by the CI runner rather than guessed in this document.

## Explicit unresolved boundaries and negative evidence

1. This does **not** compile all script commands with the stock FireRed build system, original agbcc, its full linker script, or its exact ROM layout. GNU binutils are a distinct build toolchain.
2. This does **not** execute the emitted script table in mGBA, test malformed tables in native gameplay, or validate save recovery.
3. This does **not** prove all Poryscript scripts, optimize modes, line-marker modes or authoring features preserve the native ABI. It tests one bounded fixture.
4. This does **not** test Porymap project persistence or editor round trips.
5. The source file identities were already counted in the original inventory and machine triage. Partial tracing is **not** complete-file review.
6. A green workflow on a previous SHA does not establish this commit's correctness. Exact-head CI must be checked independently.

## Accounting

Inventory **14,834**. Historical machine triage **14,721/14,721** (no newly available untriaged identities); newly machine-processed this run **0**, shortfall against nominal 1,000 target **1,000**. Authoritative inherited registered complete-file analyst candidates **113**; new complete-file records **0**; independently approved **0**. Every Phase 1 gate remains **FAIL_INCOMPLETE**; Phase 2 untouched.

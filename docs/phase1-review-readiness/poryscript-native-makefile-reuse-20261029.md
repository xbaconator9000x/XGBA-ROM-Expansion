# Phase 1 — reuse pinned FireRed's native Poryscript assembly path (2026-10-29)

**Status: prior exact-head CI failed on an overstrong bypass assumption; corrective CI pending; FAIL_INCOMPLETE; independently approved 0/14,834. Partial-file evidence only.**

## Decision: reuse, not rebuild

**Reuse the existing pinned Poryscript CLI, FireRed's two-pass preprocessor and Makefile recipes, GNU ARM assembler/linker, original agbcc for C, and the existing mGBA and Porymap implementations.** The source-to-object path already exists; replacing it with a custom compiler, assembler, linker or script compiler would introduce avoidable ABI drift. For future expanded-ROM support, locate the specific ROM address/section/pointer-width/geometry assumptions and use the smallest compatible patch, adapter, plugin or configuration change. This is an architectural constraint, **not Phase 2 authorization**.

The existing green actual CLI → FireRed preprocessor → GNU ARM table witness was a deliberately narrow *one-pass* preprocessor fixture. It did not prove that the normal FireRed Makefile assembly recipe's **preproc → C preprocessor → preproc -ie → ARM assembler** stages preserve the same bytes. This packet tests that distinct native-build integration using the existing pinned executables and emitted CLI assembly. It does not replace any upstream implementation.

## Immutable source owners

- FireRed: \`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982\`, \`Makefile\` Git blob \`8b454dbd18eb0069fa5851d788697190890a5b37\`, \`tools/preproc/preproc.cpp\` blob \`20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1\`, \`asm/macros/map.inc\` blob \`83ef472c926ce767c9133ab9bd6922280b38bb2d\`, \`src/script.c\` blob \`d0433bdda062b138e53d1a1d3184b4566ad7d9dc\`. The source checker verifies these and all existing fixture pins.
- Poryscript: \`huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55\`, \`emitter/emitter.go\` blob \`d35843ef29929ead47351646d7a33dd5c692b850\`. The existing CLI test also pins \`main.go\` and \`emitter_test.go\`.
- Existing Makefile rules for both \`src/*.s\` and \`data/*.s\` are checked against their exact recipe. The test builds the pinned \`tools/preproc\` and the pinned Poryscript CLI, invokes the same ordered pipeline on the synthetic emitted map-script fixture, then uses the existing GNU ARM linker and existing expected bytes/relocation verifier.
- The source checker refuses eight mutations: first/second preprocessor bypass, missing \`-ie\`, assembler flags loss, C preprocessor include loss, missing data-assembly rule, replacement preprocessor path and replacement assembler prefix. An executable negative bypasses the pinned preprocessor and requires the CLI's \`::\` label to be rejected by the assembler. Six output-evidence mutations must fail closed.

The test **does not invoke the full root \`make\` target** or claim an exact final FireRed ROM link. It executes the recipe's stage order using existing tools, with a synthetic \`.rodata\` base of \`0x08000000\`. It checks the already established 32-byte table, four \`R_ARM_ABS32\` relocations at offsets 1/6/15/23, and expected raw/linked section hashes. Do not confuse this integration witness with a new runtime mGBA reader execution, editor save/reopen, or malformed native memory safety.

## Licensing and interoperability

The pinned \`tools/preproc/preproc.cpp\` contains a permissive notice requiring preservation of its copyright and permission notice in copies/substantial portions. No root \`LICENSE\` file was found at the inspected pinned FireRed, Poryscript or agbcc paths; **that absence does not establish unrestricted reuse or any particular license**. Any distribution or incorporation of upstream code/assets requires separate component-by-component licensing review and rights verification. Do not bundle or distribute ROM assets as part of this evidence.

The interoperability decision is to **retain Poryscript's source language and FireRed's assembler ABI**, rather than defining an incompatible XGBA-specific script format. Editor integration should preserve native project identifiers and script references and route through the existing exporter/compiler. Cross-toolchain changes must preserve symbol naming, pointer relocation, macro widths, sentinel termination and original build configurations.

## Remaining dependency closure and reviewer questions

1. The compiled original-agbcc reader exists, but no actual mGBA instruction execution of a Poryscript-linked table or bounded malformed native record is established by this packet.
2. The full FireRed Makefile may apply additional flags/asset-generation/section/linker dependencies outside this synthetic fixture; verify exact full-ROM linkage separately.
3. The map editor's script authoring and project save/reload path is not covered by this source-to-object test.
4. What minimal address-mapping/linker/emulator changes are required for an expanded ROM, and what existing upstream APIs accept them without incompatible replacements?
5. Verify licensing of each upstream component before any distributed integration. Independently review complete source files before incrementing approvals.

**Per-file scope:** FireRed \`Makefile\`, \`tools/preproc/preproc.cpp\`, \`asm/macros/map.inc\`, \`src/script.c\`; Poryscript \`main.go\`, \`emitter/emitter.go\`, \`emitter/emitter_test.go\` — **partial contract-level investigation only**, not whole-file semantic dispositions. New complete-file approvals: 0. All Phase 1 gates remain \`FAIL_INCOMPLETE\`.

## Actual first CI failure and correction

Exact-head [Actions #40705312692](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40705312692) failed after compiling the positive full native recipe: the additional *negative* assumption that omitting both native preprocessor passes must make the CPP-mediated fixture fail was false. The earlier direct-GAS negative did not include the C preprocessor, so it could not justify that stronger assertion. This is a **test assumption error**, not evidence that upstream tools are defective or that bypassed bytes are ABI-equivalent. The correction records whether the CPP-mediated bypass assembles and its object hash, without calling it safe, and instead tests a source-grounded `.4byte` to `.2byte` macro mutation through the complete pinned pipeline. No previous failed run is green-certified.

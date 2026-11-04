# Phase 1 P0 whole-file candidate — pinned FireRed root Makefile

**State:** Proposed analyst-prepared candidate, **not added to the authoritative 113-entry register** and **not independently approved**. The authoritative Phase 1 gate remains `FAIL_INCOMPLETE`. No expanded ROM, emulator, modified upstream or Phase 2 implementation is claimed.

## Exact source identity and whole-file scope

- Repository: `pret/pokefirered`
- Immutable revision: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- Primary source: `Makefile`, Git blob `8b454dbd18eb0069fa5851d788697190890a5b37`, 400 lines including final newline (399 non-terminator lines).
- This packet accounts for the **entire root Makefile** by build phase; it is not a substring-only lexical finding. Independent review must still inspect all recipe paths and indirect generated dependencies.
- Exact pinned direct dependencies: `config.mk` (`c07d31fc083fa341cca29c340e560ed107d5364a`), `make_tools.mk` (`d7b9315ad7beb37116793d8f805160679d3b4001`), `ld_script.ld` (`9a4b45031e93c1e1da8186d8c697332710526048`), `ld_script_rev10.ld` (`4eb3bc2eec749437be5797202442188972ac0693`), `ld_script_modern.ld` (`e930243522bd21da40cc1a05de9a42b8ad409b46`).

## Whole-file semantic accounting and dependency closure

| Root Makefile lines | Source-defined responsibility | Obligations and consumers |
|---|---|---|
| 1–60 | Includes configuration; selects devkitARM/binutils, preprocessing, output ROM/ELF/MAP/SYM names and source directories | `config.mk`, external binutils, environment `DEVKITARM`, host OS, header-fix tool |
| 61–126 | Assembler, preprocessor, classic agbcc versus modern GCC flags/libraries, local tools, Make setup and default rules | `tools/agbcc`, `make_tools.mk`, `charmap.txt`, modern toolchain, `scaninc` |
| 127–212 | Pre-build generation, dependency scanning, C/ASM/data/song inventory, object naming and intermediate directories | Recursive tool builder, `generated`, mapjson output, dependency graph and all source assets |
| 213–300 | Friendly build/clean targets; includes graphics, tileset, map, spritesheet, JSON and audio rules; per-object compiler exceptions | Included `*_rules.mk`, asset encoders, old compiler variants, special Flash and RFU objects |
| 301–368 | C preprocessing and assembler pipelines, scaninc dependency files, script/data assembly, RAM-symbol generation | `preproc`, `scaninc`, `ramscrgen`, `sym_*.txt`, `charmap.txt`, linker generated fragments |
| 369–400 | Selects legacy/rev10/modern linker scripts, links ELF, fixes ROM header, objcopies binary, emits symbol file | Linker script memory regions, objcopy `--gap-fill` and `--pad-to`, `gbafix`, external emulator/flash loaders |

**Source-backed invariants (not runtime claims):**

1. The root build selects classic `tools/agbcc/bin/agbcc` when `MODERN=0`, but selects `arm-none-eabi-gcc`'s `cc1` with distinct flags and libraries when `MODERN=1`. Selected C objects also override compiler/flags, so a single global compiler-mode assumption is unsafe.
2. `config.mk` defaults to `GAME_VERSION=FIRERED`, `GAME_REVISION=0`, `MODERN=0`; game code is `BPR` or `BPG` with English suffix `E`. `gbafix` applies title, code, maker and revision to the linked ELF. Game identity therefore depends on configuration and a post-link producer, not only source `rom_header.s`.
3. Legacy revision 10 selects `ld_script_rev10.ld`; other legacy builds select `ld_script.ld`; modern builds select `ld_script_modern.ld`. All three pinned scripts declare a **32-MiB ROM linker region starting at `0x08000000`**.
4. The final `.gba` rule uses `objcopy -O binary --gap-fill 0xFF --pad-to 0x9000000`. `0x09000000 - 0x08000000 = 16 MiB`: the pad argument is an **absolute load-memory address**, not a 144-MiB output-size request. This yields a **16-MiB padding floor under the expected section LMA**, not a proof that the output is always exactly 16 MiB or that 32-MiB content is supported at runtime. It must not be interpreted as an unbounded resource scheme.
5. `rom` depends on the ELF; ELF depends on selected linker script, generated symbol fragments and objects; objects depend on preprocessing, source generation and scaninc. Any expansion architecture that changes source producers, object placement, runtime addressing or output identity must preserve/re-evaluate these edges.

**Evidence boundaries and unresolved obligations:** Verify the actual ELF program headers, section LMAs, binary length and linker overflow under each classic/modern/revision path; verify `gbafix` header changes and mGBA cartridge-size/autodetection behavior against the exact compiled output; trace the six included asset-rule Makefiles and all generated linker fragments; compare host toolchain version behavior and incremental rebuild invalidation; test relocation overflow, pointer encoding, ROM mirror windows and unsupported sizes with independent compiler/emulator evidence. No such test is asserted as passing here.

## Reproducibility and negative controls

`tools/phase1_firered_root_build_contract.py --firered <pinned checkout>` re-verifies the immutable upstream HEAD and **all six Git tree/blob identities**; scans the complete file and its pinned direct dependency texts for source contract anchors; calculates the address-span relationship; and rejects six negative controls (changed padding, changed linker selector, missing map-rule include, changed modern default, changed linker region, and changed Git blob identity). This is source-contract testing only, not a compiled-ROM or semantic approval test.

## Review handoff

- Primary candidate: `pret/pokefirered:Makefile` (one unique complete-file candidate **proposed**, not registered).
- Five dependency files are pinned and examined for the listed cross-file contracts, but **not separately claimed as new whole-file candidates**.
- Reviewer must independently validate source identity, complete recipe semantics, all indirect include rules, and compiler/linker/emulator/asset compatibility; must record actual failures and counterexamples, not infer runtime safety from textual matches.
- Counts unchanged: independent approvals **0/14,834 (0.0000%)**, registered substantive candidates **113/14,834 (0.7618%)**, historical distinct machine triage **14,721/14,834 (99.2382%)**, inventory **14,834/14,834 (100%)**. No gate edits or worker-branch modifications.

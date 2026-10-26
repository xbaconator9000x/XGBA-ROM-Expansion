# Phase 1 P0 — FireRed linker variants and native ROM output boundary (26 October 2026)

**State: pinned source-level contract, NOT a compiled ELF/ROM test, runtime certification, independent semantic signoff, or XGBA implementation.** Phase 1 remains `FAIL_INCOMPLETE`; independently approved whole-file dispositions remain **0/14,834**.

## Immutable source anchors

All five files below are from `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

| Source | Git blob | Contract |
| --- | --- | --- |
| [Makefile](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/Makefile#L370-L395) | `8b454dbd18eb0069fa5851d788697190890a5b37` | Variant-dependent linker script, ELF linking, header fixing, binary conversion |
| [config.mk](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/config.mk#L1-L18) | `c07d31fc083fa341cca29c340e560ed107d5364a` | Original default revision and compiler mode |
| [ld_script.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script.ld#L1-L10) | `9a4b45031e93c1e1da8186d8c697332710526048` | Default original ROM region and fixed graphics section |
| [ld_script_rev10.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script_rev10.ld#L1-L10) | `4eb3bc2eec749437be5797202442188972ac0693` | Revision 10 original ROM region and fixed graphics section |
| [ld_script_modern.ld](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script_modern.ld#L1-L67) | `e930243522bd21da40cc1a05de9a42b8ad409b46` | Modern linker layout without the original fixed graphics section |

## Resolved source-level dependency

1. **All three build variants declare the same finite ROM linker region:** origin `0x08000000`, length `32M` (32 MiB). This is a **linker allocation contract**, not evidence that an emulator can access external data or that the physical ROM can be unlimited.
2. **Build selection is semantically significant:** original non-modern revision 10 uses `ld_script_rev10.ld`; other non-modern builds use `ld_script.ld`; modern builds use `ld_script_modern.ld`. The default configuration selects original revision 0 and `MODERN=0`. The original and modern C compiler branches also differ (agbcc versus ARM GCC).
3. **Original linker variants place `gfx_data` at the fixed address `0x08D00000`**, exactly 13 MiB from the ROM origin. The modern linker script does not declare that fixed section and instead collects modern `.text`, `.data`, and `.rodata` into ROM sections. A plugin cannot assume that a resource retains its original fixed address across compiler modes.
4. **The ROM image rule uses `objcopy -O binary --gap-fill 0xFF --pad-to 0x9000000`.** Relative to `0x08000000`, this is a **minimum 16 MiB output extent** if the linked sections end earlier. It is **not a 16 MiB upper bound**, nor a mechanism for addressing resources beyond the 32 MiB native linker region.
5. The ELF is linked using the selected script, then processed by `gbafix` before `objcopy`. Source authoring, object placement, linker map/symbol identity and final ROM bytes are therefore distinct compatibility surfaces.

**Interoperability implication:** a future XGBA-aware linker/patcher/editor contract must bind to the **actual compiled build variant, linker map, ROM digest and resource identities**. A source symbol or offset from the original fixed-layout build cannot safely be transplanted into a modern binary by name alone. This extends the existing [map/script pointer ABI](PHASE1_P0_FIRERED_MAP_SCRIPT_POINTER_ABI_2026-10-26.md) and [external resource banking contract](PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md), without altering either.

## Reproducible source verification

The [pinned variant checker](../tools/phase1_firered_linker_variant_contract.py) rejects upstream revision/blob drift and asserts the build-mode dispatch, all three ROM memory regions, fixed legacy graphics placement, modern output sections and ELF-to-ROM rule. **Ten synthetic mutations** must be rejected, including altered ROM extents, changed fixed graphics addresses, a newly added modern fixed section, switched linker variant, changed image padding, altered compiler and changed default mode.

It emits `phase1-evidence/firered-linker-variant.json` in the existing source-check workflow. **Do not call this a CI PASS until the exact-head run has succeeded and its evidence has been inspected.**

## Open proof obligations

Obtain actual ELF section addresses and symbol/map files for each selected build variant, including the effects of link-time padding and `gfx_data` placement. Correlate the compiled binary with emulator ROM aperture/mirroring, executable pointer encoding and bank-switch behaviour. Complete editor round trips, external-resource identity tests and independent whole-file semantic reviews. No Phase 2 work is authorized by this packet.

**Gate: `FAIL_INCOMPLETE`.**

# Phase 1 P0 — compiled FireRed IRQ copy boundary (26 October 2026)

**Decision: `FAIL_INCOMPLETE`.** This checkpoint adds a compiled ELF/object verification obligation, not an XGBA implementation, emulator execution test, independent review or compatibility signoff.

## Exact source and compiler dependency

The checker [`tools/phase1_compiled_irq_relocation.py`](../tools/phase1_compiled_irq_relocation.py) requires immutable `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and the exact Git blob identities:

| Pinned file | Blob | Semantics |
| --- | --- | --- |
| [`src/crt0.s`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s) | `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14` | ROM entry, `intr_main`, callback-table and `gSTWIStatus` literal-pool references |
| [`src/main.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/main.c) | `542b0f5d16dd93107523d11163bfcb70a42b707a` | `DmaCopy32(3, intr_main, IntrMain_Buffer, sizeof(IntrMain_Buffer))`, buffer of 0x200 words and vector repointing |
| [`include/gba/defines.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/defines.h) | `5521e942c00cc2c263b842ae7608dfb7ac881a76` | IRQ vector slot `0x03007FFC` |

The [compiled FireRed variants workflow](../.github/workflows/compiled-firered-variants.yml) builds **both** original agbcc and modern GCC ELFs from that same pinned source revision. The new step reads actual `arm-none-eabi-nm` linked symbols, `arm-none-eabi-readelf` object section sizes and relocations, and SHA-256 digests of each ELF and `crt0.o`. It does not infer linked addresses from source constants.

## Verification contract

For each variant, fail unless the compiled `intr_main` source is ARM text within the native 32 MiB ROM region; `IntrMain_Buffer` is a uniquely defined 2048-byte IWRAM allocation whose copy window ends before the reserved upper 512 bytes; `gIntrTable` resolves into IWRAM; and the `crt0.o` `.text` extent from `intr_main` through its trailing literal pool fits within the 2048-byte DMA copy. The object must retain relocations to `AgbMain`, `gIntrTable` and `gSTWIStatus`. The checker includes six targeted fail-closed mutations for ROM source, IWRAM destination, callback table, handler extent, compiled buffer size and empty handler.

The emitted `firered-variant-evidence/compiled_irq_relocation.json` contains exact addresses and hashes **only if the compiled workflow succeeds**. No specific address or success is presumed in this document.

## Boundaries still open

A static object `.text` span is an intentionally conservative coverage bound, not a proof of all possible instruction paths or runtime DMA completion. The ELF test does not execute the handler, validate interrupt timing, emulate a real BIOS, establish ROM remap/prefetch coherence, certify the editor, or review all 14,834 tracked files. If a compiler/linker changes the input section layout or strips symbols, the checker fails rather than treating missing evidence as success.

**No independent whole-file dispositions have been approved (0/14,834); Phase 1 remains `FAIL_INCOMPLETE`.** The PR must remain draft and unmerged until the broader gates are satisfied.

# Phase 1 P0 — FireRed ↔ mGBA IRQ vector and RAM reset bridge (26 October 2026)

**Status: exact-pinned cross-repository source interpretation, not runtime or hardware certification.** The Phase 1 gate remains `FAIL_INCOMPLETE`; independent whole-file approvals remain **0/14,834**.

## Immutable upstream dependencies

FireRed is pinned to `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and mGBA to `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`. The [cross-repository verifier](../tools/phase1_firered_mgba_irq_bridge.py) rejects a changed Git commit or blob identity before examining source semantics.

| Source file | Exact Git blob | Role |
| --- | --- | --- |
| [FireRed crt0.s](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s) | `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14` | Early `intr_main` vector assignment |
| [FireRed main.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/main.c) | `542b0f5d16dd93107523d11163bfcb70a42b707a` | Later DMA3 copy to IWRAM handler |
| [FireRed defines.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/defines.h) | `5521e942c00cc2c263b842ae7608dfb7ac881a76` | IRQ vector slot `0x03007FFC` |
| [mGBA bios.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/bios.c#L35-L44) | `edb21e2d4b02d90907f1a9b3f8f08e1bafdd3a5b` | HLE SWI RAM-reset flags and reserved IWRAM tail |
| [mGBA hle-bios.s](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/hle-bios.s#L116-L132) | `eccbaa1433ee8316269a669109689f7fa44b941c` | IRQ trampoline word load and SWI stub |
| [mGBA memory.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L119-L126) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` | Full emulator machine reset versus SWI reset; IWRAM word mirror |
| [mGBA memory.h](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/memory.h) | `0aad912613e726560d06bbdbf6061986e69e5842` | 32 KiB IWRAM aperture |

## Cross-source semantic conclusions

**IRQ vector alias:** FireRed writes its IRQ vector at `0x03007FFC`. The pinned mGBA HLE BIOS IRQ trampoline executes `mov r0, #0x04000000` then `ldr pc, [r0, #-4]`, reading `0x03FFFFFC`. mGBA's 32-bit IWRAM read masks the address with `GBA_SIZE_IWRAM - 4` (32 KiB minus four bytes), yielding **offset `0x7FFC` for both addresses**. This is an explicit source-level explanation for the mirrored IRQ vector address, not an assumption that the addresses differ.

**Two reset scopes:** In mGBA's HLE SWI `RegisterRamReset` implementation, the IWRAM bit clears **`GBA_SIZE_IWRAM - 0x200`**, i.e. 32 KiB minus 512 bytes. This matches the reserved top-512-byte boundary observed in FireRed's modern manual clear loop. In contrast, `GBAMemoryReset` clears **all 32 KiB** of IWRAM during the emulator's separate machine-reset lifecycle. These paths must not be conflated.

**BIOS selection is a material dependency:** `GBASwi16` raises the ARM SWI and returns when `memory.fullBios` is true. Otherwise, the `GBA_SWI_REGISTER_RAM_RESET` case invokes the C `_RegisterRamReset` implementation. The HLE BIOS assembly lists `RegisterRamReset` among unimplemented stubs, so that label is not proof of the reset semantics; the C SWI dispatch supplies the inspected HLE behaviour. A loaded real BIOS follows a different path and is **not** covered by this source-only proof.

**Expansion consequence:** A future ROM bank mapper must not treat a ROM-resident IRQ handler, an IWRAM handler copied by DMA, a BIOS IRQ trampoline and a full machine reset as one interchangeable resource. Any boot-time bank switching, save restoration or remapping during interrupts needs explicit, runtime-verified coherence of code, vector slot, DMA and prefetch. No such mechanism is implemented here.

## Reproduction and open gates

Run `python3 tools/phase1_firered_mgba_irq_bridge.py --firered <pinned FireRed checkout> --mgba <pinned mGBA checkout> --output phase1-evidence/firered-mgba-irq-bridge.json`. The checker validates **seven exact upstream Git blobs**, asserts the mirrored IRQ-vector arithmetic, distinct SWI/machine reset extents and real-BIOS dispatch branch, and applies **nine fail-closed source mutations**. The pinned CI workflow archives the JSON manifest.

**CI evidence is not considered verified until the exact-head run passes.** Remaining obligations: real BIOS and HLE execution, compiled IRQ addresses, ROM remap and prefetch behaviour during IRQ/DMA, editor interoperability and independent per-file semantic review. **No Phase 2 implementation; `FAIL_INCOMPLETE`.**

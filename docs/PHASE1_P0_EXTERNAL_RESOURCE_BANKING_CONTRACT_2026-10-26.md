# Phase 1 P0: external resource identity and bank-switch safety contract

**Checkpoint:** 26 October 2026. **State:** SOURCE-ANCHORED REQUIREMENTS, native baseline verified; **NOT independent semantic disposition** and **NOT an XGBA implementation**.

## Verified original engine constraints

The authoritative pinned mGBA revision is `fd9dc5c2cbf234365068855851107e762fc6211b`. Native in-memory synthetic-ROM characterization was compiled and run in [34/34 green CI run 40204719637](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637). The [independent archived ZIP](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637) records:

- ZIP SHA-256: `1384cc86a3abda6c1b1079a8ffaaad41083c650dcea16b3e4148ec497d47a82f`.
- Executed native test source SHA-256: `88760d928e51104d58bdf30b8f42a37217908e4b66cca6cb629dba55c4c3be29`.
- Summary JSON SHA-256: `6a75b5a468f0692d5257960943e02acd3b69529e4a8b3185b66a4070eba5014f`.
- Native runtime log SHA-256: `3172b1ecfc2f0f824826527c18591910813b323497335445883de7c23f5c949e`.
- Exactly **34 named PASS, 0 FAIL and 4 true hazardous-behaviour observations**. No emulator source was modified. This is baseline behaviour, not proof of extension correctness.

### Native boundaries mapped with exact source anchors

| Boundary | Pinned source | Interpretation |
| --- | --- | --- |
| ROM loader | [`src/gba/gba.c:425-489`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L425-L489) | ROM files larger than 32 MiB select a Matrix implementation only when byte 0xAC is `M`; non-M oversized files use a standard 32 MiB visible mapping |
| Matrix physical addressing | [`src/gba/cart/matrix.c:16-79`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L16-L79) | The physical start address is `value & 0x03FFFFFF` (26-bit, **64 MiB address range**) and the virtual bank window is tightly constrained. This native cartridge mode cannot itself address an arbitrarily sized sidecar |
| Mapping validation | `src/gba/cart/matrix.c:16-37` | Virtual boundaries are checked; physical backing `paddr + length` and `VFile` seek/read results are not verified. Native run confirms out-of-range physical mapping metadata can be accepted |
| CPU fetch | [`src/arm/arm.c:198-225`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/arm.c#L198-L225) plus `include/mgba/internal/arm/isa-inlines.h` | ARM/Thumb prefetch uses active memory region/mask. Native bank remapping does not synchronously refresh already-prefetched instructions |
| Peripheral arbitration | `src/gba/memory.c:586-625`, `src/gba/dma.c:259-330` | ROM2_EX 16-bit accesses and DMA3 have EEPROM and e-Reader paths; extension-only interception of every ROM read is unsafe |
| Native save-state identity | [`src/gba/serialize.c:95-165`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c#L95-L165) | Title and game code mismatches reject a load, but ROM CRC mismatch only warns. Native external bank data drift can go unrecognized |
| Native Matrix restoration | `src/gba/cart/matrix.c:100-133` | Sixteen native bank-slot locations and control fields serialized, 512-byte chunks replayed. No arbitrary external resource identity is encoded |

## Candidate XGBA interoperability contracts — fail closed until implementation and tests

1. **XGBA-ACTIVATION:** Never treat a single existing header byte, ROM length, or native Matrix command as an XGBA handshake. Require an explicit, authenticated/version-bound extension manifest recognized by the emulator and the ROM. No extension = exact ordinary GBA/Matrix behaviour.
2. **XGBA-ADDRESS-SPACE:** Distinguish the CPU's finite native ROM aperture from external, variable-size resource storage. Larger data must be addressed through an opt-in logical paging/streaming protocol. Do not claim a literal infinite file or contiguous ARM bus mapping.
3. **XGBA-PHYSICAL-EXTENT:** Validate logical bank ID, nonnegative logical offset, length, checked offset+length, exact provider identity, configured quotas and short reads **before mutating any address map**. Reject partially available or truncated banks without exposing stale previously mapped bytes.
4. **XGBA-PREFETCH-ATOMICITY:** Establish a defined instruction-boundary remap point, with instruction prefetch and any relevant translated access caches made coherent. On an active DMA/peripheral operation, queue or reject a remap rather than exposing partially switched views.
5. **XGBA-PERIPHERAL-PRESERVATION:** Preserve memory access width and ordering for EEPROM, Flash, SRAM, e-Reader, GPIO, DMA and unlicensed native cartridges. Never shadow `ROM2_EX` EEPROM arbitration.
6. **XGBA-SAVESTATE-ID:** Carry a versioned mapping state and an exact digest manifest for the *whole* selected external backing resource set; reject restore if any required resource is missing, truncated or has unexpected hash. Do not rely on mGBA's warning-only ROM CRC compatibility check.
7. **XGBA-TOOLS:** Expose a documented, machine-readable manifest/ABI to editors, script compilers, emulator frontends and patchers. Use stable resource identities and fail-closed version adaptation so updated source mappings cannot silently redirect old offsets.
8. **XGBA-REPRODUCIBILITY:** Bind patcher/plugin compatibility to compiled ROM and sidecar byte identities or source-justified drift ranges; shared compiled symbol names alone are insufficient (see `docs/PHASE1_STATUS_v28.md`).
9. **XGBA-RETURN-TO-VANILLA:** Disabling the extension must restore baseline GBA memory semantics; unsupported host or missing sidecar must not silently load arbitrary alternate resources.

## Required evidence to close the design obligations

For each proposed contract, create a source-hash-pinned owner and cross-file dependency docket, deterministic negative fixtures (including missing/truncated resources, ROM identity swap, CPU prefetch, simultaneous DMA, savestate corruption), actual target emulator runtime coverage, and interoperability checks for editor/patcher producers. Record real independent review and link exact dossiers before changing any `semantic_dispositions.csv.gz` rows.

**Current Phase 1 semantic gate: `FAIL_INCOMPLETE`; verified source files 4,685; tracked 14,834; independent whole-file approvals 0.** This document reconciles cross-source semantics but is not a signed-off file review and does not begin Phase 2.

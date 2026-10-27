# Phase 1 semantic disposition candidate 0002 — FireRed GBA syscall declarations

**Review state: PENDING_INDEPENDENT_REVIEW; no semantic approval claimed.** This is a whole-file analyst candidate, not a gate input or an independent signoff.

## Exact source identity
- Repository: `pret/pokefirered`
- Pinned commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- File: `include/gba/syscall.h`
- Git blob SHA: `22fdf09facfaa812bf11b13d1f3ff86271598511`, checked against the exact upstream GitHub file response.
- [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/syscall.h); [related boot/IRQ dossier](../PHASE1_P0_FIRERED_BOOT_IRQ_RAM_LIFETIME_2026-10-26.md); [related emulator reset dossier](../PHASE1_P0_FIRERED_MGBA_IRQ_BRIDGE_2026-10-26.md).

## Complete source declaration inventory
- Guard: `GUARD_GBA_SYSCALL_H`.
- Eight single-bit reset constants: `RESET_EWRAM=0x01`, `RESET_IWRAM=0x02`, `RESET_PALETTE=0x04`, `RESET_VRAM=0x08`, `RESET_OAM=0x10`, `RESET_SIO_REGS=0x20`, `RESET_SOUND_REGS=0x40`, `RESET_REGS=0x80`; `RESET_ALL=0xFF` combines those bits.
- Three `CpuSet` control constants: `CPU_SET_SRC_FIXED=0x01000000`, `CPU_SET_16BIT=0x00000000`, `CPU_SET_32BIT=0x04000000`. One `CpuFastSet` control constant: `CPU_FAST_SET_SRC_FIXED=0x01000000`.
- Exactly fifteen function declarations, in source order:
  1. `void SoftReset(u32 resetFlags)`
  2. `void RegisterRamReset(u32 resetFlags)`
  3. `void VBlankIntrWait(void)`
  4. `u16 Sqrt(u32 num)`
  5. `u16 ArcTan2(s16 x, s16 y)`
  6. `void CpuSet(const void *src, void *dest, u32 control)`
  7. `void CpuFastSet(const void *src, void *dest, u32 control)`
  8. `void BgAffineSet(struct BgAffineSrcData *src, struct BgAffineDstData *dest, s32 count)`
  9. `void ObjAffineSet(struct ObjAffineSrcData *src, void *dest, s32 count, s32 offset)`
  10. `void LZ77UnCompWram(const void *src, void *dest)`
  11. `void LZ77UnCompVram(const void *src, void *dest)`
  12. `void RLUnCompWram(const void *src, void *dest)`
  13. `void RLUnCompVram(const void *src, void *dest)`
  14. `int MultiBoot(struct MultiBootParam *mp)`
  15. `s32 Div(s32 num, s32 denom)`.
- No definitions, inline assembly, storage declarations, or executable implementations appear in this file. The header assumes integer aliases (`u32`, `u16`, `s16`, `s32`) and named structure types are available in its include context; it does not include their definitions.

## Semantics and expansion dependencies
- `RESET_ALL & ~RESET_IWRAM` evaluates to `0xFD` given these constants. The boot dossier establishes that FireRed's modern startup uses this mask, followed by its own manual IWRAM clear. **The header alone cannot prove what a real BIOS or emulator resets.**
- The CPU copy and decompression declarations are possible ROM-to-RAM and ROM-to-VRAM data movement boundaries. Any future external resource architecture must inspect call sites, alignment, transfer lengths, and the concrete SWI implementation before claiming compatibility.
- `MultiBoot`, affine transform and arithmetic functions likewise describe an interface, not runtime semantics or cartridge address capacity. No pointer width, memory bank extension, or save-format guarantee can be inferred from these prototypes.
- mGBA HLE and loaded-BIOS behaviour can differ; the related pinned bridge dossier is necessary context, but does not turn this header into hardware certification.

## Outstanding whole-file reviewer obligations
1. Enumerate actual declarations' call sites and wrapper/implementation mappings at the pinned source commit, including conditional compiler variants; independently verify all fifteen prototypes and constants.
2. Compare the compiled calling conventions and SWI dispatch against linked objects; verify how reset masks are consumed under HLE versus full BIOS.
3. Verify copy/decompression alignment, size, source/destination address assumptions and edge/error behaviour before any XGBA relocation contract is approved.
4. Resolve include-order/type-declaration dependencies and whether the declarations are consumed by any external tool/editor.

## Review state and gate
Independent reviewer identity, date, rationale, and signed verdict: **none**. Whole-file reviewer checks above remain open. **PENDING_INDEPENDENT_REVIEW; gate contribution 0.** No manual gate count changes, no invented semantic signoffs.

At this checkpoint, **Phase 1 remains FAIL_INCOMPLETE: 0/14,834 independent approvals.**

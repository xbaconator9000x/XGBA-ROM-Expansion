# Analyst whole-file candidate 0106 — HBlank DMA scanline effect ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/scanline_effect.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/scanline_effect.h); exact pinned Git blob SHA-1 `5bd8b554686ebd85eaf21ea551ff722a5d8c8984`. Inspected the **entire 48-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

Two DMA-control macros build 16- and 32-bit one-unit HBlank repeat transfers. Eight register-offset macros derive BG0..BG3 scroll offsets relative to BG0HOFS. ScanlineEffectParams/ScanlineEffect carry DMA pointers, callback, state and task ID; exported double buffer is u16[2][0x3C0].

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SCANLINE_EFFECT_H`
- L2: `#define GUARD_SCANLINE_EFFECT_H`
- L5: `#define SCANLINE_EFFECT_DMACNT_16BIT (((DMA_ENABLE | DMA_START_HBLANK | DMA_REPEAT | DMA_SRC_INC | DMA_DEST_INC | DMA_16BIT | DMA_DEST_RELOAD) << 16) | 1)`
- L6: `#define SCANLINE_EFFECT_DMACNT_32BIT (((DMA_ENABLE | DMA_START_HBLANK | DMA_REPEAT | DMA_SRC_INC | DMA_DEST_INC | DMA_32BIT | DMA_DEST_RELOAD) << 16) | 1)`
- L8: `#define SCANLINE_EFFECT_REG_BG0HOFS (REG_ADDR_BG0HOFS - REG_ADDR_BG0HOFS)`
- L9: `#define SCANLINE_EFFECT_REG_BG0VOFS (REG_ADDR_BG0VOFS - REG_ADDR_BG0HOFS)`
- L10: `#define SCANLINE_EFFECT_REG_BG1HOFS (REG_ADDR_BG1HOFS - REG_ADDR_BG0HOFS)`
- L11: `#define SCANLINE_EFFECT_REG_BG1VOFS (REG_ADDR_BG1VOFS - REG_ADDR_BG0HOFS)`
- L12: `#define SCANLINE_EFFECT_REG_BG2HOFS (REG_ADDR_BG2HOFS - REG_ADDR_BG0HOFS)`
- L13: `#define SCANLINE_EFFECT_REG_BG2VOFS (REG_ADDR_BG2VOFS - REG_ADDR_BG0HOFS)`
- L14: `#define SCANLINE_EFFECT_REG_BG3HOFS (REG_ADDR_BG3HOFS - REG_ADDR_BG0HOFS)`
- L15: `#define SCANLINE_EFFECT_REG_BG3VOFS (REG_ADDR_BG3VOFS - REG_ADDR_BG0HOFS)`
- L17: `struct ScanlineEffectParams`
- L18: `{`
- L19: `volatile void *dmaDest;`
- L20: `u32 dmaControl;`
- L21: `u8 initState;`
- L22: `u8 unused9;`
- L23: `};`
- L25: `struct ScanlineEffect`
- L26: `{`
- L27: `void *dmaSrcBuffers[2];`
- L28: `volatile void *dmaDest;`
- L29: `u32 dmaControl;`
- L30: `void (*setFirstScanlineReg)(void);`
- L31: `u8 srcBuffer;`
- L32: `u8 state;`
- L33: `u8 unused16;`
- L34: `u8 unused17;`
- L35: `u8 waveTaskId;`
- L36: `};`
- L38: `extern struct ScanlineEffect gScanlineEffect;`
- L40: `extern u16 gScanlineEffectRegBuffers[2][0x3C0];`
- L42: `void ScanlineEffect_Stop(void);`
- L43: `void ScanlineEffect_Clear(void);`
- L44: `void ScanlineEffect_SetParams(struct ScanlineEffectParams);`
- L45: `void ScanlineEffect_InitHBlankDmaTransfer(void);`
- L46: `u8 ScanlineEffect_InitWave(u8 startLine, u8 endLine, u8 frequency, u8 amplitude, u8 delayInterval, u8 regOffset, bool8 a7);`
- L48: `#endif // GUARD_SCANLINE_EFFECT_H`

## Dependencies, expansion relevance and independent review

High-risk MMIO and DMA contract: verify volatile destination alignment, HBlank timing, 16/32-bit register widths, source double-buffer lifetime, wave start/end bounds and interaction with palette/VRAM transfers. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

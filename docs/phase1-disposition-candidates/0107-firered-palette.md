# Analyst whole-file candidate 0107 — Palette fade control and inline backdrop writers

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/palette.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/palette.h); exact pinned Git blob SHA-1 `3bde46cad02e187c0ca41471d531547a7a14e744`. Inspected the **entire 99-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros, inline definitions and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header defines 32-palette masks, 16-color bank indexing, fade states and PaletteFadeControl with packed bitfields. It exports faded/unfaded palette buffers and a broad palette transfer/blend/tint API. Two static inline backdrop setters call FillPalette or LoadPalette at offset zero for one palette entry.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_PALETTE_H`
- L2: `#define GUARD_PALETTE_H`
- L4: `#include "global.h"`
- L6: `#define gPaletteFade_selectedPalettes (gPaletteFade.multipurpose1) // normal and fast fade`
- L7: `#define gPaletteFade_blendCnt         (gPaletteFade.multipurpose1) // hardware fade`
- L8: `#define gPaletteFade_delay            (gPaletteFade.multipurpose2) // normal and hardware fade`
- L9: `#define gPaletteFade_submode          (gPaletteFade.multipurpose2) // fast fade`
- L11: `#define PLTT_BUFFER_SIZE (PLTT_SIZE / sizeof(u16))`
- L13: `#define PALETTE_FADE_STATUS_DELAY 2`
- L14: `#define PALETTE_FADE_STATUS_ACTIVE 1`
- L15: `#define PALETTE_FADE_STATUS_DONE 0`
- L16: `#define PALETTE_FADE_STATUS_LOADING 0xFF`
- L18: `#define PALETTES_BG      0x0000FFFF`
- L19: `#define PALETTES_OBJECTS 0xFFFF0000`
- L20: `#define PALETTES_ALL     (PALETTES_BG | PALETTES_OBJECTS)`
- L22: `#define PLTT_ID(n) ((n) * 16)`
- L23: `#define BG_PLTT_OFFSET 0x000`
- L24: `#define OBJ_PLTT_OFFSET 0x100`
- L25: `#define BG_PLTT_ID(n) (BG_PLTT_OFFSET + PLTT_ID(n))`
- L26: `#define OBJ_PLTT_ID(n) (OBJ_PLTT_OFFSET + PLTT_ID(n))`
- L27: `#define OBJ_PLTT_ID2(n) (PLTT_ID((n) + 16))`
- L29: `enum`
- L30: `{`
- L31: `FAST_FADE_IN_FROM_WHITE,`
- L32: `FAST_FADE_OUT_TO_WHITE,`
- L33: `FAST_FADE_IN_FROM_BLACK,`
- L34: `FAST_FADE_OUT_TO_BLACK,`
- L35: `};`
- L37: `struct PaletteFadeControl`
- L38: `{`
- L39: `u32 multipurpose1;`
- L40: `u8 delayCounter:6;`
- L41: `u16 y:5; // blend coefficient`
- L42: `u16 targetY:5; // target blend coefficient`
- L43: `u16 blendColor:15;`
- L44: `u16 active:1;`
- L45: `u16 multipurpose2:6;`
- L46: `u16 yDec:1; // whether blend coefficient is decreasing`
- L47: `u16 bufferTransferDisabled:1;`
- L48: `u16 mode:2;`
- L49: `u16 shouldResetBlendRegisters:1;`
- L50: `u16 hardwareFadeFinishing:1;`
- L51: `u16 softwareFadeFinishingCounter:5;`
- L52: `u16 softwareFadeFinishing:1;`
- L53: `u16 objPaletteToggle:1;`
- L54: `u8 deltaY:4; // rate of change of blend coefficient`
- L55: `u32 unused;`
- L56: `};`
- L58: `extern struct PaletteFadeControl gPaletteFade;`
- L59: `extern u32 gPlttBufferTransferPending;`
- L60: `extern u16 gPlttBufferUnfaded[PLTT_BUFFER_SIZE];`
- L61: `extern u16 gPlttBufferFaded[PLTT_BUFFER_SIZE];`
- L63: `void LoadCompressedPalette(const u32 *src, u16 offset, u16 size);`
- L64: `void LoadPalette(const void *src, u16 offset, u16 size);`
- L65: `void FillPalette(u16 value, u16 offset, u16 size);`
- L66: `void TransferPlttBuffer(void);`
- L67: `u8 UpdatePaletteFade(void);`
- L68: `void ResetPaletteFade(void);`
- L69: `void ReadPlttIntoBuffers(void);`
- L70: `bool8 BeginNormalPaletteFade(u32 selectedPalettes, s8 delay, u8 startY, u8 targetY, u16 blendColor);`
- L71: `void ResetPaletteFadeControl(void);`
- L72: `void InvertPlttBuffer(u32 selectedPalettes);`
- L73: `void TintPlttBuffer(u32 selectedPalettes, s8 r, s8 g, s8 b);`
- L74: `void UnfadePlttBuffer(u32 selectedPalettes);`
- L75: `void BeginFastPaletteFade(u8 submode);`
- L76: `void BeginHardwarePaletteFade(u8 blendCnt, u8 delay, u8 y, u8 targetY, u8 shouldResetBlendRegisters);`
- L77: `void BlendPalettes(u32 selectedPalettes, u8 coeff, u16 color);`
- L78: `void BlendPalettesUnfaded(u32 selectedPalettes, u8 coeff, u16 color);`
- L79: `void TintPalette_GrayScale(u16 *palette, u16 count);`
- L80: `void TintPalette_GrayScale2(u16 *palette, u16 count);`
- L81: `void TintPalette_SepiaTone(u16 *palette, u16 count);`
- L82: `void TintPalette_CustomTone(u16 *palette, u16 count, u16 rTone, u16 gTone, u16 bTone);`
- L83: `void PaletteStruct_ResetById(u16 id);`
- L84: `void CopyPaletteInvertedTint(const u16 *src, u16 *dst, u16 count, u8 tone);`
- L85: `void BlendPalettesGradually(u32 selectedPalettes, s8 delay, u8 coeff, u8 coeffTarget, u16 color, u8 priority, u8 id);`
- L86: `bool32 IsBlendPalettesGraduallyTaskActive(u8 var);`
- L87: `void DestroyBlendPalettesGraduallyTask(void);`
- L89: `static inline void SetBackdropFromColor(u16 color)`
- L90: `{`
- L91: `FillPalette(color, 0, PLTT_SIZEOF(1));`
- L92: `}`
- L94: `static inline void SetBackdropFromPalette(const u16 *palette)`
- L95: `{`
- L96: `LoadPalette(palette, 0, PLTT_SIZEOF(1));`
- L97: `}`
- L99: `#endif // GUARD_PALETTE_H`

## Dependencies, expansion relevance and independent review

Verify compiler bitfield layout, palette buffer bounds, 32-bit selected-palette masks, source lengths and transfer synchronization with DMA/HBlank; inline functions are executable source in this header and must be included in compiled ABI review. This file does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

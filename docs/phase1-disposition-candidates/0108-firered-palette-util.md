# Analyst whole-file candidate 0108 — Palette pulse/roulette bitfield and tilemap utilities

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/palette_util.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/palette_util.h); exact pinned Git blob SHA-1 `b33d60f790b28f3baae744cc20183b90a297cab5`. Inspected the **entire 83-line header**; every nonblank, non-comment source line is enumerated below. No independent approval is implied.

## Whole-file semantic disposition (source-level)

The header declares PulseBlendSettings and PulseBlendPalette with signed/unsigned bitfields, a PulseBlend containing 16 palette entries, RouletteFlashSettings/Palette and RouletteFlashUtil with another 16 palette entries, and a flash color sentinel at bit 15. APIs manage initialization, selection, pulse updates, roulette flashing, palette ownership and tilemap rectangle writes. A `static void ClearPulseBlendPalettesSettings(...)` prototype is declared without an inline body; independent linkage inspection must determine whether it is intentionally translation-unit local or dead. The two rectangle helpers accept u8 geometry and raw u16 pointers, with no capacity metadata in their signatures.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_PALETTE_UTIL_H`
- L2: `#define GUARD_PALETTE_UTIL_H`
- L4: `struct PulseBlendSettings`
- L5: `{`
- L6: `u16 blendColor;`
- L7: `u16 paletteOffset;`
- L8: `u8 numColors;`
- L9: `u8 delay;`
- L10: `u8 numFadeCycles;`
- L11: `s8 maxBlendCoeff:4;`
- L12: `s8 fadeType:2;`
- L13: `s8 restorePaletteOnUnload:1;`
- L14: `s8 unk7_7:1;`
- L15: `};`
- L17: `struct PulseBlendPalette`
- L18: `{`
- L19: `u8 paletteSelector;`
- L20: `u8 blendCoeff:4;`
- L21: `u8 fadeDirection:1;`
- L22: `s8 unk1_5:1;`
- L23: `s8 available:1;`
- L24: `u32 inUse:1;`
- L25: `u8 delayCounter;`
- L26: `u8 fadeCycleCounter;`
- L27: `struct PulseBlendSettings pulseBlendSettings;`
- L28: `};`
- L30: `struct PulseBlend`
- L31: `{`
- L32: `u16 usedPulseBlendPalettes;`
- L33: `struct PulseBlendPalette pulseBlendPalettes[16];`
- L34: `};`
- L36: `#define FLASHUTIL_USE_EXISTING_COLOR (1 << 15)`
- L38: `struct RouletteFlashSettings`
- L39: `{`
- L40: `u16 color;`
- L41: `u16 paletteOffset;`
- L42: `u8 numColors;`
- L43: `u8 delay;`
- L44: `u8 unk6;      // Set but never used`
- L45: `s8 numFadeCycles:5;`
- L46: `s8 unk7_5:2;  // Set but never used`
- L47: `s8 colorDeltaDir:1;`
- L48: `};`
- L50: `struct RouletteFlashPalette`
- L51: `{`
- L52: `u8 state:7;`
- L53: `u8 available:1;`
- L54: `u8 delayCounter;`
- L55: `s8 fadeCycleCounter;`
- L56: `s8 colorDelta;`
- L57: `struct RouletteFlashSettings settings;`
- L58: `};`
- L60: `struct RouletteFlashUtil`
- L61: `{`
- L62: `u8 enabled;`
- L63: `u8 unused;`
- L64: `u16 flags;`
- L65: `struct RouletteFlashPalette palettes[16];`
- L66: `};`
- L68: `void RouletteFlash_Reset(struct RouletteFlashUtil *);`
- L69: `u8 RouletteFlash_Add(struct RouletteFlashUtil *, u8, const struct RouletteFlashSettings *);`
- L70: `void RouletteFlash_Run(struct RouletteFlashUtil *);`
- L71: `void RouletteFlash_Enable(struct RouletteFlashUtil *, u16);`
- L72: `void RouletteFlash_Stop(struct RouletteFlashUtil *, u16);`
- L73: `void InitPulseBlend(struct PulseBlend *);`
- L74: `int InitPulseBlendPaletteSettings(struct PulseBlend *, const struct PulseBlendSettings *);`
- L75: `static void ClearPulseBlendPalettesSettings(struct PulseBlendPalette *);`
- L76: `void UnloadUsedPulseBlendPalettes(struct PulseBlend *, u16, u8);`
- L77: `void MarkUsedPulseBlendPalettes(struct PulseBlend *, u16, u8);`
- L78: `void UnmarkUsedPulseBlendPalettes(struct PulseBlend *, u16, u8);`
- L79: `void UpdatePulseBlend(struct PulseBlend *);`
- L80: `void FillTilemapRect(u16 *dest, u16 src, u8 left, u8 top, u8 width, u8 height);`
- L81: `void SetTilemapRect(u16 *dest, u16 *src, u8 left, u8 top, u8 width, u8 height);`
- L83: `#endif // GUARD_PALETTE_UTIL_H`

## Dependencies, expansion relevance and independent review

Verify original/modern compiler bitfield packing and signedness, palette selection and color index bounds, 16-slot ownership flags, u8 rectangle geometry and pointer capacity, and task lifetime. The header lacks global.h despite fixed-width types; include-order assumptions need validation. Trace each function's definition, call sites and resource cleanup before certifying compiled, emulator or editor behavior. No runtime/compiled proof or independent signoff is claimed.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

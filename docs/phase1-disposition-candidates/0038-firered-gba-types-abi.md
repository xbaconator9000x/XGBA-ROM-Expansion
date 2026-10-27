# Phase 1 whole-file candidate 0038 — FireRed GBA types and packed hardware-facing structs

**PENDING INDEPENDENT REVIEW — NOT APPROVED.** Pinned source `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Complete-file analyst preparation only; no independent whole-file approval or compiled/runtime certification.

**Identity:** `include/gba/types.h`, exact Git blob `35d02e26391d872b486ca051d51f8485f3a7a0e5`. [Pinned full source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/types.h). All **172 lines** inspected.

## Whole-file semantic inventory
- Guard and `stdint.h`; fixed-width aliases `u8/u16/u32/u64`, `s8/s16/s32/s64`; corresponding `volatile` integer aliases; `f32/f64`; 8/16/32-bit boolean storage aliases and volatile forms. These are typedefs, not dynamic pointer-width extension mechanisms.
- `BgCnt` declares sixteen bits of background control (priority, character/screen base blocks, mosaic, palette mode, overflow mode and size); `vBgCnt` is a volatile structure typedef. `PlttData` declares 5-bit red/green/blue components plus one unused bit.
- `OamData` declares sprite attributes using `u32` bitfields for position, affine mode, object mode, mosaic, color depth, shape, matrix/flip bits and size; `u16` fields for tile number, priority, palette and affine parameter. The inline source comments identify native offsets `0x00`, `0x02`, `0x04`, `0x06`, but compiler layout and binary offsets require actual ABI verification.
- The `ST_OAM_*` macros define flip masks, blend/window modes, affine modes, 4/8bpp, shapes and size indices. Twelve `SPRITE_SIZE_WxH` macros encode the four square, four horizontal and four vertical dimensions. `SPRITE_SIZE(dim)` and `SPRITE_SHAPE(dim)` extract size and shape from the combined macro constant.
- `BgAffineSrcData` stores fixed-point texture/screen coordinates, scales and angle; `BgAffineDstData` stores affine coefficients and displacement; `ObjAffineSrcData` stores scale/rotation. `SioMultiCnt` declares link-cable baud, status, ID, mode, interrupt and data fields, with `ST_SIO_*` mode and baud constants.

## Expansion relevance and reviewer requirements
The source explicitly constrains graphics attributes, palette channels, tile index and serial-control fields to small fixed bit widths; no ROM-expansion scheme can infer extra sprite or palette capacity from wider host integers. Structure bitfields are compiler/ABI-sensitive; check `sizeof`, alignments and binary packing under pinned legacy and modern compilers and compare GBA register/OAM consumers. Review all include consumers, all 12 sprite dimensions and all struct fields, not just the ROM-relevant aliases. No compiled layout or hardware test has been run. **Verdict PENDING; reviewer none; 0 approval credit.**

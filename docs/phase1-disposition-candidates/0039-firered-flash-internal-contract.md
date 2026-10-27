# Phase 1 whole-file candidate 0039 — FireRed save-flash internal ABI

**PENDING INDEPENDENT REVIEW — NOT APPROVED.** Pinned source `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Complete-file analyst preparation only; no independent whole-file approval or compiled/runtime certification.

**Identity:** `include/gba/flash_internal.h`, exact Git blob `39e14ef73ce3d020427baada43ab165d34d04e8b`. [Pinned full source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/flash_internal.h). All **83 lines** inspected.

## Whole-file semantic inventory
- Include guard; `FLASH_BASE ((u8 *)0xE000000)` and volatile byte write macro `FLASH_WRITE(addr,data)` address the **save-flash bus window**, not the cartridge ROM expansion window. `FLASH_ROM_SIZE_1M 131072` is a 1-megabit flash **device capacity** constant, not a 128-KiB game ROM size. `SECTORS_PER_BANK 16`.
- `FlashSector` holds size, shift, count and top; `FlashType` holds flash device size, sector descriptor, two wait-state values and maker/device ID union (separate bytes or joined halfword). These are device metadata structs; field layout/endianness and runtime device selection require compiled proof.
- `FlashSetupInfo` holds five operation/timer callback pointers (`programFlashByte`, `programFlashSector`, `eraseFlashChip`, `eraseFlashSector`, `WaitForFlashWrite`), `maxTime` and a `FlashType` copy. Global externs expose remaining byte count, selected operation callbacks, max time, selected flash type, polling callback and timeout flag.
- Three setup descriptors are declared: `MX29L010`, `LE26FV10N1TS`, `DefaultFlash`. Public declarations cover `SwitchFlashBank`, `ReadFlashId`, timer start/stop/configuration, `SetReadFlash1`, full/partial sector program-and-verify, `ReadFlash`, common wait, MX-specific erase/program routines and `IdentifyFlash`. All declarations are source interfaces; this header contains no implementation of wear leveling, persistence or actual flash programming.

## Expansion relevance and reviewer requirements
Do not confuse flash save banking, flash sector indices and callbacks with expanded ROM code/resource banks. IRQ timer callbacks, save reload and flash read/write semantics require consumer traces, linker/compiled addresses and emulator save-state tests. Confirm `u8/u16/u32` provenance via `include/gba/types.h` and all flash drivers and save consumers. Do not infer binary ABI from uncompiled C structs. **Verdict PENDING; reviewer none; 0 approval credit.**

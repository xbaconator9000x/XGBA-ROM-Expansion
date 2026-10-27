# Phase 1 whole-file analyst candidate 0012 — FireRed GBA address and section macros

**State: PENDING_INDEPENDENT_REVIEW; no independent signoff.**

## Immutable upstream source
`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, path `include/gba/defines.h`, Git blob `5521e942c00cc2c263b842ae7608dfb7ac881a76` (directly verified from exact pinned source). [Entire source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/defines.h); [boot IRQ cross-file evidence](../PHASE1_P0_FIRERED_BOOT_IRQ_RAM_LIFETIME_2026-10-26.md).

## Complete-file semantic coverage
1. **Header and booleans:** include guard `GUARD_GBA_DEFINES`, `<stddef.h>`, `TRUE=1`, `FALSE=0`. These are macros, not stored values.
2. **Section attributes:** under `__APPLE__`, `IWRAM_DATA` and `EWRAM_DATA` use Mach-O-style `__DATA,iwram_data` and `__DATA,ewram_data` section strings; otherwise they use `iwram_data` and `ewram_data`. `COMMON_DATA` always selects `common_data`. The pinned modern linker explicitly consumes `ewram_data` and `common_data`, but **does not explicitly name `iwram_data`**: do not assume automatic RAM placement of that section without object/linker inspection.
3. **Compiler branch:** `NOINLINE` is `__attribute__((noinline))` only when `MODERN` is truthy; otherwise expands to nothing. `ALIGNED(n)` is a GCC-style alignment attribute.
4. **Upper IWRAM aliases:** `SOUND_INFO_PTR` is a dereferenced `struct SoundInfo **` at `0x03007FF0`; `INTR_CHECK` is `u16` at `0x03007FF8`; `INTR_VECTOR` is `void **` at `0x03007FFC`. These are **dereferencing macros**, not variable declarations. Their live ownership/aliasing must be checked with startup, IRQ, sound, BIOS and emulator.
5. **RAM limits:** EWRAM start `0x02000000`, end `0x02040000` (exclusive under conventional range use); IWRAM start `0x03000000`, end `0x03008000`. The macros do not allocate memory or validate accesses.
6. **Palette and VRAM:** palette base `0x05000000`, BG palette 0x200 bytes and OBJ palette at BG+0x200 for another 0x200 bytes; VRAM base `0x06000000`, size `0x18000`. BG VRAM size `0x10000`, BG character block `0x4000`, BG screen block `0x800`; BG char/screen/tile address macros add block-size multiples (`BG_TILE_ADDR` uses 0x80). H/V/HV flip helpers add `0x400`, `0x800`, `0xC00` respectively to supplied values; they do not mask or validate input tile indices.
7. **OBJ VRAM variants:** text-mode `OBJ_VRAM0=VRAM+0x10000`, size `0x8000`; bitmap-mode `OBJ_VRAM1=VRAM+0x14000`, size `0x4000`. The file itself does not select display mode or verify overlapping allocation.
8. **OAM/header/display:** OAM `0x07000000`, size `0x400`; `ROM_HEADER_SIZE=0xC0`; display width 240 and height 160.
9. **Tile/palette arithmetic:** 4bpp tile 32 bytes, 8bpp tile 64 bytes; `BG_TILE_ADDR_4BPP(n)` and both `TILE_OFFSET_*` compute BG VRAM offsets; `TOTAL_OBJ_TILE_COUNT=1024`; `PLTT_SIZEOF(n)=n*sizeof(u16)`, 4bpp palette 16 entries, 8bpp 256, `PLTT_OFFSET_4BPP(n)` multiples of a 16-entry palette. These are arithmetic macros with no range checks.
10. **Attributes and close:** `NAKED` and `UNUSED` wrap corresponding compiler attributes; include guard closes. No executable functions or global definitions appear in this header.

## Expansion/interoperability risks and review needs
A future XGBA tool cannot treat header macros as proof of physical bus mapping, safe VRAM/OAM writes, section placement, reserved IRQ RAM lifetime or 32-bit pointer portability. Reconcile the actual linker output, Apple vs non-Apple toolchain sections, ROM header bytes, IRQ alias behaviour and emulator memory implementation. Search consumers of each macro, especially `IWRAM_DATA`, `COMMON_DATA`, `INTR_VECTOR`, `BG_TILE_ADDR` and `OBJ_VRAM*`; test actual compiled addresses/ELF map and relevant runtime reset/interrupt paths.

**Verified:** exact full source and blob, branch predicates, macros and arithmetic. **Not verified:** exhaustive external consumers, compiled placement, emulator/hardware behaviour, independent reviewer identity/date/verdict. Reviewer status: **pending**.

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; 0/14,834 approvals.**

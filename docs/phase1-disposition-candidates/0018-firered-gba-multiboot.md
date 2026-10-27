# Candidate 0018 — FireRed GBA multiboot interface header

**State: PENDING_INDEPENDENT_REVIEW; no independent approval.** Directly read the entire pinned 56-line header.

## Source identity
- `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `include/gba/multiboot.h`, exact Git blob `a8bc8fddfd820eda38ba8fba4fd1db917bccc1ae` verified by pinned upstream file fetch.
- [Immutable source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/multiboot.h).

## Whole-file authored contract
- Guard: `GUARD_GBA_MULTIBOOT_H`. Header includes no other headers; it relies on previously available `u8`, `u16`, `u32` types (for example via `gba/gba.h`), a compilation-order dependency.
- Transfer bounds: `MULTIBOOT_NCHILD = 3`, `MULTIBOOT_HEADER_SIZE = 0xC0`, `MULTIBOOT_SEND_SIZE_MIN = 0x100`, `MULTIBOOT_SEND_SIZE_MAX = 0x40000`. The last value is a multiboot *transmission limit constant*, **not** the game's cartridge ROM size or XGBA bank limit.
- The sole struct, `MultiBootParam`, declares `system_work[5]` (u32); `handshake_data` and `padding` (u8); `handshake_timeout` (u16); `probe_count` and `client_data[3]`, `palette_data`, `response_bit`, `client_bit`, `reserved1` (u8); three `const u8 *` pointers `boot_srcp`, `boot_endp`, `masterp`; three `u8 *reserved2[3]` pointers; `system_work2[4]` (u32); and four u8 flags `sendflag`, `probe_target_bit`, `check_wait`, `server_type`. The field ordering and pointer representation are ABI-sensitive. **No compiled struct-size or packing proof** is asserted from source alone.
- Error codes: `MULTIBOOT_ERROR_04/08/0c/40/44/48/4c/80/84/88/8c` map to corresponding hex values; `NO_PROBE_TARGET = 0x50`, `NO_DLREADY = 0x60`, `BOOT_FAILURE = 0x70`, `HANDSHAKE_FAILURE = 0x71`.
- Other constants: `CONNECTION_CHECK_WAIT = 15`, `SERVER_TYPE_NORMAL = 0`, `SERVER_TYPE_QUICK = 1`, `HANDSHAKE_TIMEOUT = 400`. Header contains no function definitions or implementation of transmission, validation or retries.

## Dependencies, risk, and reviewer obligations
Review `gba/types.h` and all uses of `MultiBootParam` in pinned multiboot/BIOS callers; compile representative legacy/modern variants and compare `sizeof`, `offsetof`, pointer widths, alignment and generated transfer calls. Validate actual multiboot transmission boundaries and error handling against emulator/BIOS evidence before claiming runtime compatibility. External-ROM resource pointers must not be inserted into this fixed ABI by assumption. Independent reviewer identity, verdict and date **not supplied**; source-only analyst candidate contributes **zero** approved dispositions. **FAIL_INCOMPLETE.**

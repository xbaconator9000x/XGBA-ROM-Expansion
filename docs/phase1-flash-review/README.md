# Phase 1 — FireRed 1-Mbit Flash banking, timers and write verification

**Status:** Four proposed, source-pinned, complete-file semantic review packets; independent reviewer **not yet assigned**. These are not added to the 113-entry authoritative analyst register and are not approved dispositions. Gate remains `FAIL_INCOMPLETE`.

## Source and scope

Pinned upstream: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. The accompanying manifest records exact Git blob SHA-1, every function's start/end line, all file-scope data symbols, line counts, and include identities. It covers **611 physical source lines**, **22 function definitions** and **21 file-scope data symbols** across:

| File | Git blob | Lines | Functions | Complete-file interpretation |
| --- | --- | ---: | ---: | --- |
| `src/agb_flash.c` | `08aeed1638e214a3cad8b28d103964ab24342fba` | 297 | 15 | Flash bank switching, chip ID reads, timer IRQ ownership, RAM-executed read/verify routines, bounded retry wrappers |
| `src/agb_flash_1m.c` | `e249fab9a350f3263e7df5f20ff301a6d008e3db` | 86 | 2 | Chip identification, fallback dispatch and timeout polling |
| `src/agb_flash_mx.c` | `b4f710f36449c46946294d0df3d61d493d5c0d1f` | 197 | 5 | Macronix chip/sector erase, byte programming and full-sector programming |
| `src/agb_flash_le.c` | `39d956e2778af564cf187ea732a019e46479ac12` | 31 | 0 | LE chip timing, geometry, ID and dispatch descriptor |

Source dependency identities, **not newly counted complete-file reviews**: `include/gba/flash_internal.h` (`39e14ef73ce3d020427baada43ab165d34d04e8b`, 83 lines) and `src/save.c` (`36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`, 963 lines). The manifest's source-contract checker validates these exact hashes too.

## Full-file semantics and dependency closure

### `agb_flash.c` — 15 of 15 functions

- **Banking and identification (22–63):** `SwitchFlashBank` issues the chip's unlock/bank commands at `0x5555`, `0x2AAA` and `0x0000`; `ReadFlashId` installs a copied Thumb byte-reader in a 0x20-halfword stack buffer, enters ID mode, reads maker/device bytes and exits ID mode. This is Flash memory, **not cartridge ROM bank selection**.
- **Timer lifetime (65–104):** `FlashTimerIntr` decrements a shared countdown; `SetFlashTimerIntr` accepts only timer indices 0–3 and installs an IRQ callback; `StartFlashTimer` indexes `gFlashMaxTime[phase*3]`, programs timer/interrupt registers and sets `REG_IME=1`; `StopFlashTimer` disables the selected timer and restores saved IME. The timer register pointer must be initialized by the caller before a timed write.
- **RAM execution and read (106–174):** `ReadFlash1` is the byte primitive; `SetReadFlash1` copies Thumb instructions using the address difference between two functions; `ReadFlash_Core` performs volatile byte reads; `ReadFlash` copies that routine into a 0x40-halfword stack buffer, selects the bank for 1-Mbit Flash, and calculates the sector+offset address.
- **Verification (176–259):** `VerifyFlashSector_Core` returns zero for equality or the first mismatching target address. `VerifyFlashSector` and `VerifyFlashSectorNBytes` copy it into a 0x80-halfword stack buffer, select the bank and compare a whole sector or caller-specified `n` bytes.
- **Retry wrappers (261–297):** `ProgramFlashSectorAndVerify` and `ProgramFlashSectorAndVerifyNBytes` make up to three programming/verification attempts, returning the last result. The NBytes version still calls the full-sector program callback, but checks only the requested prefix.

### `agb_flash_1m.c` — 2 of 2 functions

- `IdentifyFlash` (13–49) changes SRAM wait states, reads the chip ID, walks `sSetupInfos` until matching ID or zero-maker fallback, then installs **all** Flash function pointers, timing array and geometry. It returns 0 on recognized chip, 1 on fallback, but the fallback still installs the default chip implementation.
- `WaitForFlashWrite_Common` (51–86) starts a phase-indexed timer, polls the RAM byte-reader, checks chip status bit 0x20 and timer timeout, issues reset command on failure and always stops the timer before returning.

### `agb_flash_mx.c` — 5 of 5 functions

- `mxMaxTime`, `MX29L010`, and `DefaultFlash` specify 131,072-byte Flash, 4,096-byte sectors, 32 sectors, and a four-phase timer table. The chip ID is conditional on the `GERMAN && SAPPHIRE` build configuration (lines 22–27).
- `EraseFlashChip_MX` (58–79) emits full-chip erase commands, waits for completion, then resets SRAM wait states.
- `EraseFlashSector_MX` (81–123) rejects sectors outside `gFlash->sector.count`, selects bank, emits sector erase, and retries on selected error bits before restoring wait states.
- `ProgramFlashByte_MX` (125–148) validates byte offset but **does not validate sector number**, selects bank, issues program command and returns polling status.
- `ProgramByte` (150–158) emits a single-byte write command; `ProgramFlashSector_MX` (160–197) validates sector, erases it, then programs every byte while decrementing shared `gFlashNumRemainingBytes`. It uses `void *` arithmetic (`src++`), requiring compiler-specific behavior to be established.

### `agb_flash_le.c` — all data, no functions

- `leMaxTime` (4–10) provides the four timer triples.
- `LE26FV10N1TS` (12–31) supplies the alternative chip ID `0x62/0x13`, same 131,072-byte / 32-sector geometry and the shared MX programming/erase routines.

## Typed producer → consumer edges

1. `IdentifyFlash` → `ReadFlashId` → `SetReadFlash1` / `PollFlashStatus` → `sSetupInfos` → `gFlash` and all installed operation callbacks.
2. `src/save.c` → `ProgramFlashSectorAndVerify` (source consumer line 221, also 876) → installed `ProgramFlashSector_MX` → `EraseFlashSector_MX` → `ProgramByte` → `WaitForFlashWrite_Common` → `StartFlashTimer` / `FlashTimerIntr` / `StopFlashTimer`.
3. `src/save.c` → `ProgramFlashByte` (335, 355, 384, 408) and `ReadFlash` (610, 842); these require correct chip identification, sector bounds and bank state.
4. `src/save.c` → `EraseFlashSector` (102, 328, 662, 689), whose callback is chosen by `IdentifyFlash`. `include/gba/flash_internal.h` declares the shared callback ABI and `SECTORS_PER_BANK=16`.

## High-risk hypotheses, not confirmed runtime failures

1. **Compiler/linker/Thumb placement dependency:** `SetReadFlash1`, `ReadFlash`, `VerifyFlashSector` and `VerifyFlashSectorNBytes` infer copied function length from *adjacent function addresses*, then copy into fixed-size stack buffers (0x20/0x40/0x80 halfwords). Function reordering, Thumb interworking, compiler codegen, LTO, or changed linkage may break the assumptions. Need compiled object/disassembly size and alignment witnesses for every build variant.
2. **Unbounded read and partial-verify inputs:** `ReadFlash` does not locally validate `sectorNum`, `offset` or `size`; `VerifyFlashSectorNBytes` does not locally cap `n`. Call-site preconditions and boundary tests are required; this is **not** proof that normal callers violate them.
3. **Asymmetric byte-write bounds:** `ProgramFlashByte_MX` checks `offset` but not `sectorNum`, unlike sector erase and full-sector program. An invalid sector can select/wrap a bank. Determine whether all production callers enforce the sector range.
4. **IRQ ownership and phase bounds:** `StartFlashTimer` assumes `SetFlashTimerIntr` has initialized `sTimerReg`, assumes phase indexes fit the timing table, and temporarily sets `REG_IME=1`. Trace timer assignment, other interrupt users and disabled-interrupt callers before claiming safety.
5. **Chip identification fallback:** an unknown ID installs `DefaultFlash` callbacks despite returning 1. Trace whether callers gate writes on the return value; an unexpected chip must not silently be assumed compatible.
6. **Partial prefix acceptance:** the NBytes retry wrapper programs a whole sector but checks only `n` bytes. Determine the intended save-sector contract and whether trailing bytes matter to recovery.
7. **Build-variant ABI:** MX chip ID differs under `GERMAN && SAPPHIRE`; `src++` on `void *` and RAM-executed function copying require pinned compiler behavior. No generic C or modern compiler portability is inferred.

## Review and gate handoff

An independent reviewer must inspect all 611 source lines and the dependency endpoints, verify symbol/stack-buffer sizes from compiled objects, examine Flash IRQ registration and caller reachability, establish save-sector bounds and chip-ID fallback behavior, and supply signed, source-revision-bound dispositions. Existing static tests can prove only source contracts, not real Flash timing or compiled/runtime safety. The original 14,834 inventory, 113 registered substantive candidates and 0 independent approvals remain unchanged. **FAIL_INCOMPLETE.**

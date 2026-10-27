# Phase 1 independent-review handoff — mGBA GBA savedata implementation

**State:** source-grounded analyst review preparation, **not** an independent approval. This is an isolated proposed packet and is **not registered** in the authoritative 113-file candidate register; do not increase its count without identity reconciliation and reviewer acceptance. Phase 1 gate remains `FAIL_INCOMPLETE`.

## Exact pinned identity and evidence

- Repository: `mgba-emu/mgba`, pinned commit `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Complete source: `src/gba/savedata.c`, Git blob SHA-1 `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`, **800 physical lines**, 28 function definitions. All line references below are to this pinned blob.
- Direct contract header: `include/mgba/internal/gba/savedata.h`, blob `6227be25e8c9d2c1cc14c06ded34389b96138577`, 129 physical lines. Exposes `GBASavedata` state, flash/EEPROM commands, RTC buffer, 22 public declarations and backing `VFile`.
- Consumer evidence: `src/gba/memory.c` blob `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc`; `src/gba/serialize.c` blob `a307a51e751f412c64a7378323c56758304ebe85`; `src/gba/gba.c` blob `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e`; `include/mgba-util/vfs.h` blob `6c9bd299153af4c3c9cd5487f2425a2481331ee5`.
- Direct includes (source lines 6–21): savedata, ARM macros, defines, GBA, serialized-state, memory, VFS, conditional PSP2 RTC, errno and fcntl. Conditional compilation: `PSP2` at 16–18 and 670–708.
- No GBA runtime, compiler, emulator regression, binary-format interoperability, or independent reviewer signoff is claimed.

## Exhaustive function-definition inventory (28)

| Source lines | Functions | Source-grounded responsibility |
|---|---|---|
| 39–45 | `_ashesToAshes` | Timing callback currently does nothing |
| 46–65, 66–70, 71–106 | `GBASavedataInit`, `GBASavedataReset`, `GBASavedataDeinit` | Initialize type, file mapping, timing and state; reset protocol; release backing memory |
| 107–119, 120–136 | `GBASavedataMask`, `GBASavedataUnmask` | Redirect and restore mapped save backing; optional writeback |
| 137–168, 169–193, 194–227 | `GBASavedataClone`, `GBASavedataSize`, `GBASavedataLoad` | Copy/load/save-size selection across mapped or VFile paths |
| 228–266 | `GBASavedataForceType` | Reinitialize/dispatch save type and memory-block callback |
| 267–298, 299–326 | `GBASavedataInitFlash`, `GBASavedataInitEEPROM` | Allocate/map, grow and erase-initialize flash/EEPROM |
| 327–351, 352–376 | `GBASavedataInitSRAM`, `GBASavedataInitSRAM512` | Allocate/map SRAM variants and initialize new bytes to 0xFF |
| 377–397, 398–484 | `GBASavedataReadFlash`, `GBASavedataWriteFlash` | Flash ID, busy-read behaviour, unlock/program/erase/bank state machine |
| 485–506, 507–559, 560–585 | `_ensureEeprom`, `GBASavedataWriteEEPROM`, `GBASavedataReadEEPROM` | Promote 512-byte to 8-KiB EEPROM and implement serial bit protocol |
| 586–605 | `GBASavedataClean` | Dirty-age-based file sync and RTC write |
| 606–639, 640–643, 644–714 | `GBASavedataRTCWrite`, `_unBCD`, `GBASavedataRTCRead` | RTC trailer persistence, BCD decode, local-time offset |
| 715–734, 735–758 | `GBASavedataSerialize`, `GBASavedataDeserialize` | Save-type/protocol state and pending timing state |
| 759–778, 779–788, 789–800 | `_flashSwitchBank`, `_flashErase`, `_flashEraseSector` | 1-Mbit promotion/bank pointer and chip/sector erase |

The three forward declarations at 35–37 are **not** extra definitions. There are 28 function definitions in 800 physical lines; all are assigned a responsibility above.

## Cross-file consumer and state obligations

1. `memory.c:613–614, 720–736, 990–995, 1064–1088` routes SRAM/flash/EEPROM bus reads/writes, including autodetection. The write path is not interchangeable with a ROM-size/memory-bank extension.
2. `serialize.c:89,234` invokes savedata serialization/deserialization. Serialized save *protocol state* is distinct from the save-file bytes; independent reviewer must trace both.
3. `gba.c:84–87, 168–176, 497–501, 968–1005` owns initialization, unload, save VFile replacement, frame-based cleaning and notification. Mapping lifetime and callback ordering must be checked.
4. `vfs.h:43` defines `VFile.read` as returning signed `ssize_t`, making negative error returns relevant to the following boundary cases.

## Specific source-level risks requiring independent disposition

**R1 — flash growth initialization gap (lines 275–294).** When an existing flash file is at least `GBA_SIZE_FLASH512` but smaller than requested `GBA_SIZE_FLASH1M`, the code truncates/grows to `flashSize` at 285–288, but the 0xFF initialization at 292–294 runs only if `end < GBA_SIZE_FLASH512`. Thus the newly grown second bank is not explicitly erased to 0xFF on this path. A normal sparse-file extension may supply zeros, but backend-dependent behavior and reachability require tests. Distinguish from `_flashSwitchBank:759–778`, which explicitly fills the new bank on 512→1M promotion.

**R2 — EEPROM growth initialization gap (lines 306–323).** An existing 512-byte file opened directly as 8-KiB EEPROM is grown at 315–319, but initialization at 321–323 runs only if `end < GBA_SIZE_EEPROM512`. The newly extended region is not explicitly filled with erased EEPROM bytes. The separate `_ensureEeprom:485–505` promotion path does initialize it; review each entry path separately.

**R3 — signed read and unchecked write in VFile copying (lines 137–168, 194–225).** `GBASavedataClone` passes signed `read` to `out->write(..., size_t)` without first rejecting negative values, and ignores short writes. `GBASavedataLoad` similarly passes a signed read result as a write length and overwrites `read` with the write result. The VFile interface has signed read returns. Error-path reproductions and callers are required before classifying impact.

**R4 — signed-to-unsigned RTC read conversion (lines 649–655).** `GBASavedataRTCRead` assigns signed `VFile.read` to `size_t size`. If the backend returns -1, the unsigned value can bypass `size < sizeof(buffer)` and code can consume uninitialized `buffer` fields at 658–666. Verify backend error behavior and whether a short/failed RTC read is reachable.

**R5 — conditional pointer arithmetic in serialization (line 720).** `&savedata->data[0x10000]` is evaluated in the flash-bank flag comparison even for other save types. If `data` is null or a smaller allocation, forming that pointer may be outside defined C pointer arithmetic. The condition is not proof of a runtime fault; review compiler treatment, actual save-type states and sanitizer tests.

**R6 — timing, RTC and writeback contracts.** Flash busy-sector reads use the `dust` event (389–395), writes reschedule it (403–407, 535–539, 796–799), deserialization schedules pending timing (752–756), and dirty cleanup syncs mapped bytes (586–605). RTC trailers cause unmap/remap (620–637); verify bank-pointer restoration and error returns. No successful runtime regression has been shown.

## Reviewer handoff / bounded negative tests

- Build exact pinned mGBA with supported configurations and check R1/R2 using pre-existing 64-KiB flash / 512-byte EEPROM files, 1-Mbit/8-KiB forced types, and byte-for-byte erased-value assertions.
- Fault-inject `VFile.read` returning -1 and `VFile.write` returning a short count, under sanitizers, for clone/load/RTC paths.
- Test save-state restore during pending flash/EEPROM settling, non-flash save serialization, and RTC trailer remapping, including map/unmap failures.
- Resolve direct and indirect callers, save-format compatibility, editor/tool expectations, and all negative counterexamples before independent reviewer approval.

**Accounting:** no change to inventory 14,834/14,834; independently approved 0/14,834; registered substantively prepared baseline 113/14,834. This packet is **proposed/unregistered**, not an approved disposition.

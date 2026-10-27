# Analyst whole-file candidate 0057 — FireRed GPU register buffering and IRQ synchronization

**ANALYST-PREPARED ONLY; no independent review.** Exact pinned [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/gpu_regs.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/gpu_regs.c), Git blob SHA-1 **`2f52c5be334f90ce41eb52f8d4828e50e6da8e6d`**. The entire **158-line implementation** (159 split elements including trailing newline) was inspected. All **11 function bodies** and file-scope state/macro definitions are accounted for below.

## Complete-file semantic disposition

| Source lines | Symbols and source behavior |
| --- | --- |
| 1–18 | Includes `global.h`; defines `GPU_REG_BUF_SIZE=0x60`, `GPU_REG_BUF(offset)` as a casted `u16` view of a byte buffer, `GPU_REG(offset)` as a volatile 16-bit MMIO lvalue, `EMPTY_SLOT=0xFF`; declares two 96-byte arrays, three flags/state variables, and three private helpers. |
| 20–33 | `InitGpuRegManager`: zeros all 96 bytes of the register buffer, initializes all 96 queue slots to `EMPTY_SLOT`, clears lock/sync flags and cached IE. |
| 35–46 | `CopyBufferedValueToGpuReg`: DISPSTAT uses read-modify-write preserving non-HBlank/VBlank IRQ bits; other offsets write buffered 16-bit values to `REG_BASE+offset`. |
| 48–63 | `CopyBufferedValuesToGpuRegs`: when unlocked, iterates queued offsets in order until first empty slot, copies and clears each. Packed queue order is a precondition. |
| 65–93 | `SetGpuReg`: accepts any byte offset below 96, writes a 16-bit buffer value, then copies immediately during scanlines 161–225 or forced blank, otherwise queues a unique offset. The queue loop tests duplicates; if all 96 valid distinct offsets are queued, any next offset must duplicate one, conditional on the queue's uniqueness invariant. |
| 95–104 | `GetGpuReg`: live DISPSTAT/VCOUNT reads; other offsets return the buffered 16-bit view with **no local bounds/alignment guard**. |
| 106–116 | `SetGpuRegBits` / `ClearGpuRegBits`: read buffered 16-bit value, then delegate to `SetGpuReg`; their initial read precedes its bounds check. |
| 118–127 | `SyncRegIE`: if dirty, saves IME, disables interrupts, writes cached IE, restores IME and clears dirty state. |
| 129–143 | `EnableInterrupts` / `DisableInterrupts`: update cached IE mask, synchronize and update DISPSTAT VBlank/HBlank IRQ enable bits. |
| 145–158 | `UpdateRegDispstatIntrBits`: derives the two DISPSTAT IRQ bits from cached IE and queues/sets a new value only if those two bits differ from the live register. |

## Dependencies, source-level hazards and reviewer questions

- The companion pinned [`include/gpu_regs.h`](0058-firered-gpu-regs-public-api.md) declares the nine public entry points including `SetGpuReg_ForcedBlank`; **no definition for that name was found in this implementation**, and a pinned repository code search returned only the header. Do not infer a linker failure without exhaustive variant and assembly symbol review.
- The complete pinned [GBA I/O macro contract](0055-firered-gba-io-register-contract.md) provides `REG_BASE`, DISPSTAT, VCOUNT, IE, IME and interrupt bit definitions. `global.h` supplies the types and other macros; no emulator behavior is proven.
- **Conditional 16-bit buffer boundary:** `SetGpuReg` accepts offset 95 because `95 < 96`, yet `GPU_REG_BUF(95)` spans bytes 95–96 of a 96-byte array. `GetGpuReg` and bit-set/clear helpers also lack local range checks; odd offsets are not aligned for 16-bit accesses. This is a **source-level API precondition/conditional out-of-bounds hazard**, not evidence that any stock caller supplies such an offset or that a crash occurred.
- The 96-slot waiting list uses `sGpuRegWaitingList[i]` after its scan. The uniqueness/valid-offset invariant is necessary to establish that `i < 96`; test it under valid and malformed queue states before calling this a runtime overflow.
- The immediate-write path and DISPSTAT read-modify-write depend on scanline timing and MMIO side effects. Confirm all callers pass valid even offsets, generated agbcc/modern instruction widths, VBlank timing, IRQ ordering, and mGBA behavior. Source search finds callers in `src/bg.c`, `src/field_screen_effect.c`, `src/main.c` and other UI modules; the list is **not exhaustive**.
- Expansion must preserve the hardware I/O window and the 96-byte buffer/queue layout unless both consumers and compiled/runtime behavior are revised and verified. The code has no direct ROM banking logic.

**Disposition:** complete-file source preparation only; caller preconditions, compiler and emulator tests unresolved. **Independent approval pending; FAIL_INCOMPLETE.**

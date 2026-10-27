# Candidate 0019 — FireRed debug printing and assertion interface

**State: PENDING_INDEPENDENT_REVIEW; no independent approval.** The entire pinned 70-line header, including both conditional paths, was inspected.

## Source identity
- `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `include/gba/isagbprint.h`, exact Git blob `9c79e03e8e95c02b17361073eff841bd59a8311c` verified by direct upstream fetch.
- [Immutable source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/isagbprint.h).

## Whole-file authored contract
- Guard `GUARD_GBA_ISAGBPRINT_H` and `#include "gba/types.h"`.
- Five mGBA log levels: `MGBA_LOG_FATAL = 0`, `ERROR = 1`, `WARN = 2`, `INFO = 3`, `DEBUG = 4`.
- For `defined(NDEBUG) && !(REVISION >= 0xA)`, `DebugPrintf`, `DebugPrintfLevel`, `MgbaOpen`, `MgbaClose`, `AGBPrintInit`, and `DebugAssert` expand to empty macros. This is a compile-time elimination of call sites in that branch, **not** evidence that all logging/side effects are absent in every build.
- Otherwise the header declares `MgbaOpen`, `MgbaClose`, `MgbaPrintf`, `MgbaAssert`, `NoCashGBAPrintf`, `NoCashGBAAssert`, `AGBPrintf`, `AGBAssert`, `AGBPrintInit`. `LOG_HANDLER_MGBA_PRINT` routes `DebugPrintf` and assertions to mGBA (info-level default); `LOG_HANDLER_NOCASH_PRINT` routes to no$gba; fallback routes to AGBPrint. `DebugPrintfLevel` in the no$gba and AGBPrint paths does **not** forward its level argument; only the mGBA path forwards the level.
- A separate `#ifdef NDEBUG` removes `AGB_ASSERT`, `AGB_WARNING`, `AGB_ASSERT_EX`, `AGB_WARNING_EX` regardless of the `REVISION >= 0xA` exception above. In non-`NDEBUG` builds, the macros evaluate expressions and call `DebugAssert` for false values, with `TRUE` stop for assertions and `FALSE` for warnings; EX variants use caller-supplied file and line.
- No source-defined logging transport, memory-mapped emulator detection, or implementation of the declared functions occurs in this header.

## Dependencies, expansion relevance and unresolved proof
The build's `REVISION`, `NDEBUG`, `LOG_HANDLER`, `TRUE/FALSE` and handler constants must be resolved from the pinned configuration/preprocessor environment. Debug output can be an optional emulator-specific compatibility surface, not an XGBA runtime bank protocol. A reviewer must test preprocessing across all branches (including `REVISION >= 0xA` with `NDEBUG`), link each selected backend, inspect call-site side effects, and verify the exact emulator debug port/handler independently. **No reviewer identity/date/verdict; zero gate approvals. FAIL_INCOMPLETE.**

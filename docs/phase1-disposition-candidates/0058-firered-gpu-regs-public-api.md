# Analyst whole-file candidate 0058 — FireRed GPU register manager public API

**ANALYST-PREPARED ONLY; independent reviewer verdict pending.** Exact pinned [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gpu_regs.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gpu_regs.h), Git blob SHA-1 **`3930f680987b09cb087834ccf370be9e0b156e59`**. Complete **21-line header** (22 split elements including terminal newline) inspected.

## Whole-file semantic disposition

- Lines 1–4: `GUARD_GPU_REGS_H` guard and `#include "global.h"`. The API's `u8` and `u16` widths depend on this include; no standalone implementation is present.
- Lines 6–9: exported type/RAM/ROM declaration comment sections are empty, not evidence of hidden state.
- Lines 10–18: nine public declarations: `InitGpuRegManager(void)`, `CopyBufferedValuesToGpuRegs(void)`, `SetGpuReg(u8,u16)`, `SetGpuReg_ForcedBlank(u8,u16)`, `GetGpuReg(u8)`, `SetGpuRegBits(u8,u16)`, `ClearGpuRegBits(u8,u16)`, `EnableInterrupts(u16)`, `DisableInterrupts(u16)`.
- Lines 20–21: include guard closes. No build-condition branch, inline code, struct layout or direct hardware address appears in this file.

## Dependency and review boundary

The pinned implementation [`src/gpu_regs.c`](0057-firered-gpu-register-buffer-runtime.md) defines eight of the nine declared public names, plus three static helpers. `SetGpuReg_ForcedBlank` is **declared here but absent from that implementation**; a pinned repository code search returned only this header. A complete independent review must inspect all linked objects, alternate build variants and assembly definitions before classifying this as a real unresolved linker symbol. Header-only absence of a definition does not prove a build failure.

The `u8` offset and `u16` value ABI is significant: the implementation uses 16-bit accesses to a 96-byte buffer and hardware MMIO. Confirm all consumers respect even-offset and range preconditions, including dynamic arguments; test original agbcc and modern builds and mGBA before changing the ABI. This document does not assert caller safety, binary compatibility or actual hardware behavior.

**Disposition:** full-file source preparation; consumer census and missing-definition provenance pending. **0 independent approvals; Phase 1 FAIL_INCOMPLETE.**

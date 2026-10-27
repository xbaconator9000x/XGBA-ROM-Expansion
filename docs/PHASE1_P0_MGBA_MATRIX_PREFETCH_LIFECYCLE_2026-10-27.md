# Phase 1 P0 — mGBA Matrix remap, ARM/Thumb prefetch and savestate ordering (27 October 2026)

**Verdict: PINNED_SOURCE_CANDIDATE / FAIL_INCOMPLETE.** This is a cross-file source dependency proof, not an executed remap, a runtime defect finding, a hardware claim, an independent semantic review or Phase 2 implementation.

## Exact upstream evidence

Pinned upstream: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`. The [fail-closed verifier](../tools/phase1_mgba_matrix_prefetch_lifecycle.py) checks the commit and each source Git blob before asserting semantics.

| Source | Git blob SHA-1 | Responsibility |
| --- | --- | --- |
| [ARM execution](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/arm.c#L201-L247) | `0b92d7f55f1fb853d4b1b9c9163ee086126066e2` | ARM/Thumb step consumes and shifts the two-slot instruction prefetch |
| [PC-write helpers](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/arm/isa-inlines.h#L73-L94) | `ebda28e411f627c6cd1570aff6f29a3b79a60840` | ARMWritePC/ThumbWritePC refill both slots after active-region selection |
| [Matrix](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L16-L79) | `9ccbe883235b98bcf56cd609015e7b4003aa832c` | Command remap copies backing VFile bytes into the ROM buffer |
| [Savestate restore](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c#L187-L243) | `a307a51e751f412c64a7378323c56758304ebe85` | Pipeline restore before optional Matrix mapping replay |
| [Active ROM region](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L247-L374) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` | Instruction fetch region points to the ROM buffer and its ROM mask |

## Producer → consumer lifecycle

1. **Instruction consumption.** `ARMStep` and `ThumbStep` execute `prefetch[0]`, shift `prefetch[1]` into slot 0, and fetch the next instruction into slot 1. A remapped ROM buffer alone does not rewrite instructions already stored in the CPU prefetch array.
2. **Explicit refill path.** `ARMWritePC` and `ThumbWritePC` select the active memory region and load *both* instruction slots. `GBASetActiveRegion` binds the ROM regions to the ROM buffer pointer and ROM mask; it is not itself a general Matrix-remap invalidation operation.
3. **Native Matrix remap.** Commands `0x01` and `0x11` invoke `_remapMatrix`, which seeks/reads backing VFile bytes into `gba->memory.rom`. The inspected remap/command functions do not call the PC-write helpers, invalidate `cpu->prefetch`, or reselect the active region. Thus a **source-level stale-prefetch window is possible** when mapped executable bytes change without a subsequent pipeline refill. This is not a proof that every mapping change executes stale code.
4. **Savestate replay ordering.** `GBADeserialize` first restores unlicensed-cartridge mapping and reselects the active region. Its ARM and Thumb paths then either restore both saved prefetch words (when both are nonzero) or read fallback words from the current active region for backwards compatibility. RAM and device restoration follow; *only then*, when Matrix is active, are 16 Matrix mappings replayed into the ROM buffer. There is no local prefetch refresh between that replay and `mTimingInterrupt`. Both the saved-word and fallback paths therefore need runtime coherence checks, particularly when backing content differs.
5. **Important boundary.** This analysis is confined to the inspected functions and pinned version. It does not prove that all runtime callers leave the pipeline unchanged; an interrupt, branch or later PC write may refill it. It also does not establish actual backing-file identity or read completeness, covered separately in the [VFile/identity dossier](PHASE1_P0_MGBA_MATRIX_ROM_IDENTITY_VFS_2026-10-27.md).

## Gate and reproducibility

Run:

```sh
python3 tools/phase1_mgba_matrix_prefetch_lifecycle.py \
  --mgba upstream-mgba \
  --output phase1-evidence/mgba-matrix-prefetch-lifecycle.json
```

The checker pins **five Git blobs**, asserts bounded producer/consumer ordering and runs **14 scoped negative mutation controls**. A passing run proves these exact source assertions survived its mutation suite, **not** emulator execution or independent whole-file approval.

**Unresolved:** live ARM/Thumb execution during remap; prefetch contents before/after Matrix savestate replay; fallback behaviour with old states; altered/truncated backing VFiles; instruction-fetch timing and translated execution modes; compiled/runtime/editor interoperability; independent dispositions across the five pinned repositories.

**Phase 1: FAIL_INCOMPLETE. Independent whole-file approvals: 0/14,834. PR #7 remains draft. No Phase 2 work.**

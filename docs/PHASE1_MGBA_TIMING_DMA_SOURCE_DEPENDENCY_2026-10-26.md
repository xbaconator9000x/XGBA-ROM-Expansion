# Phase 1 P0 — pinned mGBA scheduler/DMA semantic dependency packet (26 October 2026)

**State: SOURCE-INTERPRETED ADDITIVE REVIEW CANDIDATES. Independent whole-file signoffs: 0. Phase 1: FAIL_INCOMPLETE.** No Phase 2 implementation, emulator patch or fresh native test is claimed.

## Exact pinned source identities

All source paths below are from the same immutable mGBA commit `fd9dc5c2cbf234365068855851107e762fc6211b`. Source was inspected directly through connected GitHub at that revision.

| Source | Git blob SHA-1 | Relevant lines | Role |
| --- | --- | --- | --- |
| [`src/core/timing.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/core/timing.c) | `cebd619957b0845deedfc03b1e9c89d168861ea1` | 28–63, 69–124, 135–140 | Scheduler queue, interrupt reroot, event priority, callback dispatch |
| [`include/mgba/core/timing.h`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/core/timing.h) | `6e938970e9ffdaa2c8c6f20d71319c0df9eccb5e` | 14–51 | Callback ABI, root/reroot state, cycle pointer ownership |
| [`src/gba/dma.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/dma.c) | `da2a800ba48cb32d6e10e42c3b3527ef406bad22` | 35–39, 96–144, 199–254, 259–315 | DMA event producer/consumer and EEPROM arbitration (already in the original 29-file curated registry) |

The two timing sources are **additional** candidates. Their machine-readable identities, roles, dependency edges and unresolved obligations are in [the additive registry](../semantic-snapshots/curated/mgba_timing_dma_additive_candidates_2026-10-26.json). The original 29-file curated register and 14,834-file source queue are unchanged.

## Producer → scheduler → callback → peripheral chain

1. `GBADMAInit` assigns `_dmaEvent` to the native `mTimingEvent.callback` slot, with a `GBA*` context and priority `0x40` (`dma.c:35–39`). This is an explicit typed callback dependency; a lexical direct-call graph alone misses it.
2. `GBADMAWriteCNT_HI` configures immediate DMA to start at `mTimingCurrentTime + 3` cycles, then invokes `GBADMAUpdate` (`dma.c:137–140`). `GBADMAUpdate` chooses the earliest active channel, deschedules the prior event and schedules the selected DMA event (`dma.c:233–254`).
3. `mTimingSchedule` stores an absolute `when` based on relative and master cycles, and inserts into `reroot` when that list is present, otherwise `root` (`timing.c:36–63`). For equal times it uses event priority as a secondary order; the exact comparator is `next->priority > priority`.
4. `mTimingInterrupt` moves `root` to `reroot` and clears `root` (`timing.c:28–34`). `mTimingTick` processes callbacks on the current `root`, then promotes `reroot` to `root` **after** the processing loop (`timing.c:104–124`). A newly promoted callback may require another scheduler tick before execution.
5. `_dmaEvent` calls `GBADMAService` while count remains, then handles completion/IRQ/repeat logic (`dma.c:199–231`). `GBADMAService` sets DMA access source, blocks CPU execution during service, and has a dedicated **16-bit ROM2_EX EEPROM** read/write branch (`dma.c:259–315`).

### Why this matters to XGBA

An external ROM-bank protocol cannot be specified as a blanket intercept of ROM-region data loads or as an arbitrary callback inserted into the DMA event queue. CPU prefetch, DMA timing, ROM2_EX EEPROM arbitration and bank-state restoration have separate producer/consumer paths. A source-level callback edge is not evidence of safe remap atomicity, and a single scheduler tick is not proof that a scheduled DMA has executed.

The earlier [DMA fixture diagnosis](PHASE1_DMA3_SCHEDULER_REROOT_CHECKPOINT_2026-10-26.md) attributed two failing synthetic checks to not advancing the scheduler through the reroot promotion. [CI run 40203666311](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203666311) subsequently passed the bounded 25-check fixture; the later [34/34 native baseline](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637) and [evidence verifier](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40205086061) also passed. These are **prior CI observations**, not tests newly executed for this packet.

## Required before independent file disposition

- Review both timing files **in full**, not just cited ranges, including `mTimingDeschedule`, `mTimingIsScheduled`, `mTimingNextEvent`, callback reentrancy and all call sites.
- Verify `root`/`reroot` exclusivity and event ordering across interrupt, deschedule and callback interleavings, under actual compiled configuration; do not infer a race or safety proof from a small excerpt.
- Reconcile DMA event timing with CPU instruction prefetch, instruction-boundary remap and active peripheral accesses.
- Verify all source Git blob identities and the dependency record against the 14,834-file authoritative manifest; any changed pin or missing dependency must fail closed.
- Obtain an actual independent review attestation, compiled/variant evidence and runtime negative controls. Do not count the two new candidates as approved or silently alter the 29-file historical registry.

**Decision remains `FAIL_INCOMPLETE`.**

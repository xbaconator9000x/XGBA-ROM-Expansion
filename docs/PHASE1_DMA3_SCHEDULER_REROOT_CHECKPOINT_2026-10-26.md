# Phase 1 P0 DMA3 timing scheduler reroot — checkpoint (26 Oct 2026)

**Gate:** FAIL_INCOMPLETE; zero independent whole-file semantic approvals. No XGBA runtime modification or compatibility certification.

## Observed native regression failure

The pinned mGBA build succeeded, but native synthetic-cartridge test runs [40203381724](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203381724) and [40203542695](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203542695) each failed two DMA3 assertions:

- `native_DMA3_16bit_ROM2_EX_reads_EEPROM`
- `native_DMA3_immediate_one_unit_completes`

The latter run recorded a scheduled DMA event at time 3, `activeDMA=3`, `nextCount=1`, and `nextEvent=0`. After a single `mTimingTick(...,80)`, time advanced to 80 but the event remained scheduled, `nextCount=1`, destination remained sentinel `0xA5A5`, and `nextEvent=-80`. This does **not** demonstrate that native DMA ignores EEPROM: it demonstrates that this fixture had not dispatched its scheduled DMA callback.

## Pinned-source explanation

The unchanged mGBA `src/core/timing.c` at commit `fd9dc5c2cbf234365068855851107e762fc6211b` has separate `root` and `reroot` queues. `mTimingSchedule` inserts into `reroot` when nonnull. `mTimingTick` drains the current `root` callbacks first and only afterward promotes `reroot` to `root`, updating `nextEvent`. Consequently one tick need not dispatch a newly promoted event; additional scheduler turns may be required. In the same pinned mGBA `src/gba/dma.c`, `GBADMAWriteCNT_HI` schedules immediate DMA with a three-cycle delay, `_dmaEvent` services a unit and subsequently clears the enable bit on completion, and `GBADMAService` handles 16-bit ROM2_EX EEPROM explicitly.

## Bounded test-only correction

- [`e54a2702`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/e54a2702d298cb841ac76f4ba5400d332c0c2293) changes **only** `tests/mgba_bank_boundary.c`: run up to eight native timing ticks while DMA3 remains enabled, recording each scheduler turn. It does not call internal DMA callbacks or patch mGBA.
- [`76d0fe1b`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/76d0fe1b50a5023d499aa42eb9ba9253c3189989) updates the native probe suite revision in `tools/compiler_bindings_semantics.py`, triggering the pinned mGBA workflow and hash-bound artifact generation.
- [Verification run 40203666311](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203666311) was queued when this checkpoint was drafted. **Its result is not assumed.** A subsequent reviewer must check the run and preserve exact success/failure observations.

The existing native observations about stale ARM/Thumb prefetch after Matrix remap and accepted physical ranges extending beyond the backing EOF remain independent safety obligations, regardless of this fixture's result.

**Acceptance boundary:** A passing native fixture would validate only the tested scheduler/EEPROM and Matrix behaviours at this pinned mGBA revision. It would not prove external XGBA banking, general DMA/interrupt compatibility, or any independent semantic disposition.

## Verified post-fix CI result

[Run 40203666311](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203666311) **completed successfully** on commit `76d0fe1b50a5023d499aa42eb9ba9253c3189989`. The `Analyze actual compiler targets and linked symbols` and subsequent compiled-dependency steps both passed. The native boundary probe reported **25 positive checks passed, 0 failed**; the earlier DMA3 failure is therefore resolved in the bounded pinned fixture. This does **not** close the two native-gap observations or the Phase 1 independent semantic review gate.

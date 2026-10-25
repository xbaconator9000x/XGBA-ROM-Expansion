# Phase 1 — cross-packet mGBA review queue checkpoint (26 October 2026)

**Gate: `FAIL_INCOMPLETE`. Independently approved whole-file semantic dispositions: zero.** This is a deterministic scheduling/reconciliation checkpoint, not a signoff, compiled ABI proof or ROM expansion.

## Provenance

The [timing/DMA source packet](../semantic-snapshots/curated/mgba_timing_dma_additive_candidates_2026-10-26.json) was authored on draft PR #3. The [EEPROM/savestate source packet](../semantic-snapshots/curated/mgba_eeprom_savestate_additive_candidates_2026-10-26.json) and its [exact-pinned verifier](../tools/verify_mgba_eeprom_savestate_additive.py) were carried byte-for-byte from draft PR #4 to allow a reproducible stacked integration. The upstream mGBA revision is `fd9dc5c2cbf234365068855851107e762fc6211b`. The immutable 14,834-file source census, original 338 P0 entries and 29-file curated register remain unchanged.

The [combined review scheduler](../tools/phase1_crosspacket_review_scheduler.py) first executes the existing PR #3 scheduler, checks the v2 evidence digest, revalidates both candidate registries against the immutable source queue and authoritative fail-closed mapping gate, then produces a deterministic gzip v3 queue with **29 original + 2 timing + 2 EEPROM = 33 pending candidates**. All 14,834 source rows, 338 P0 priorities, 163 original P0 gameplay-script fixtures and original machine-review statuses must be preserved. The generated JSON records SHA-256 hashes of each registry, original queue, v2 queue and v3 queue. No status is promoted to approved.

## Source-grounded cross-packet dependencies

- **EEPROM settling event → timing scheduler.** `savedata.c:524-540` schedules the EEPROM dust/settling event through `src/core/timing.c:36-63`, within the separately pinned timing candidate (`timing.c:28-140`). This is a producer/consumer line-reference intersection, not proof of callback reentrancy or exact runtime interleavings.
- **CPU and DMA ROM2_EX → EEPROM arbitration.** The CPU EEPROM dispatch `memory.c:611-625` intersects the memory consumer `memory.c:586-625` in the DMA3 ROM2_EX packet. Both paths must be reviewed before claiming that an expanded cartridge-bank abstraction preserves 16-bit EEPROM access.
- **Savestate → restored timing event.** `savedata.c:715-756` restores a pending settling event; `serialize.c:229-240` orders savedata restoration before Matrix deserialization and timing interrupt. An expansion must not silently invalidate event identity or save-file mapping on load.

The cross-packet validator adds 12 deliberate false-approval, source-identity, queue-status and dependency mutations to the two original verifiers' existing controls. Passing these guards only demonstrates that the **specified** invalid records are rejected. It cannot substitute for independent whole-file semantic review, compiled struct layout verification, all CPU/DMA/save-type interleavings, emulator runtime equivalence, editor import/export round trips or ROM expansion compatibility.

## Reproducible workflow

The [cross-packet GitHub Actions workflow](../.github/workflows/phase1-mgba-crosspacket-source.yml) fetches the exact pinned upstream commit, runs both original source-contract verifiers, executes the combined scheduler and archives the machine-readable v2/v3 queues, SHA evidence and source assertions. Run locally from repository root with a checkout of pinned mGBA at `upstream/mgba`:

```sh
python3 tools/verify_mgba_timing_dma_additive.py upstream/mgba
python3 tools/verify_mgba_eeprom_savestate_additive.py upstream/mgba
python3 tools/phase1_crosspacket_review_scheduler.py
```

**Review policy:** Keep this branch/PR in draft. Do not merge it as an independent semantic approval. PR #2's cryptographic reviewer trust gate remains a separate draft; no trust roots or independent reviewer attestations were created here. A green source-contract CI job is not evidence that Phase 1's independent semantic/compatibility gates have passed.

## Outstanding Phase 1 work

Whole-file and callgraph semantic dispositions across the five pinned repositories; typed dependencies, alias/lifetime and interrupt ordering; compiler/linker and ABI variants; emulator CPU/DMA/savestate behaviour; save and asset compatibility; editor/tool interoperability; and independent, authenticated review. The authoritative mapping gate must remain `FAIL_INCOMPLETE` until its real requirements are satisfied.

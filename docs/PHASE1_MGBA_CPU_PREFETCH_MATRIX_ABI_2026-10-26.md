# Phase 1 — mGBA CPU prefetch / Matrix ABI dependency checkpoint (26 October 2026)

**Gate: FAIL_INCOMPLETE. Zero independently approved whole-file semantic dispositions.** This is pinned-source interpretation, not an emulator extension or a compatibility certificate.

## Exact source provenance

mGBA revision: fd9dc5c2cbf234365068855851107e762fc6211b. Four new header candidates are recorded with full-file ranges and exact Git blob SHA-1 values in [the additive registry](../semantic-snapshots/curated/mgba_cpu_matrix_abi_additive_candidates_2026-10-26.json): ARM core/memory callbacks, ARM/Thumb branch refill inlines, GBA memory regions/ownership and native Matrix command/mapping ABI. Five previously mapped producer/consumer C sources are independently pinned by the [source verifier](../tools/verify_mgba_cpu_matrix_abi_additive.py).

Eight typed source dependencies connect CPU prefetch, branch-refill callbacks, the GBA ROM execution region, Matrix VFile-to-ROM remapping, sixteen fixed Matrix savestate slots, savedata-before-Matrix restore ordering, native oversized-ROM Matrix selection and ROM2_EX EEPROM/e-Reader dispatch.

## Semantic boundary requiring review

- [ARM and Thumb stepping](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/arm.c#L198-L225) shifts a two-entry prefetch buffer and directly reads the next opcode from the active region and mask, independently of generic data load callbacks.
- [Branch refill inlines](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/arm/isa-inlines.h#L73-L91) call setActiveRegion before filling both prefetch slots. [GBA initialization](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L42-L80) binds that callback, and [ROM execution mapping](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L338-L349) selects memory->rom and memory->romMask.
- [Native Matrix remapping](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L16-L38) copies VFile bytes into the same ROM backing buffer without refreshing the already-prefetched opcodes. Its fixed [sixteen mapping slots](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/cart/matrix.h#L13-L31) are replayed during savestate restoration. Native Matrix is not an XGBA protocol.
- [ROM2_EX 16-bit stores](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L986-L1001) arbitrate e-Reader and EEPROM paths; ROM bank interception cannot ignore access width or peripheral priority.

These are source-backed interpretations and concrete safety requirements. They do **not** prove that every callback path, interrupt interleaving, compiled ABI variant, physical bank extent or external-resource identity is safe.

## Deterministic review queue

The [v4 scheduler](../tools/phase1_cpu_matrix_review_scheduler.py) first regenerates the v3 source queue and checks its SHA-256 provenance, then reconciles all 14,834 original source rows and preserves all original priorities and machine-review statuses. The new pending review total is 29 original + 2 timing + 2 EEPROM + 4 CPU/Matrix = **37**, with 338 original P0 and 163 original P0 gameplay-script fixtures unchanged. It emits a deterministic gzip queue and SHA-256 summary. No disposition is approved.

The focused [CI workflow](../.github/workflows/phase1-mgba-cpu-matrix-source.yml) checks nine exact upstream blobs, 19 line-bounded source expressions, eight typed dependencies, 11 candidate-registry and two source-expression negative controls, plus ten v4 queue negative controls. Reproduction from repository root requires an exact-pinned mGBA checkout at upstream/mgba, then runs the timing, EEPROM and CPU/Matrix verifiers followed by the v4 scheduler. Green source CI cannot substitute for independent review.

## Outstanding Phase 1 obligations

Authenticated independent whole-file semantic dispositions across all five pinned repositories; complete callback/alias/lifetime analysis; compiled CPU/GBA/Matrix struct offsets; instruction-boundary prefetch and DMA/EEPROM ordering; Matrix extent and short-read handling; savestate backing identity; compiler/linker, save/asset and editor/tool round-trip gates. No trusted reviewer identity or signoff was created, and no Phase 2 implementation was attempted.

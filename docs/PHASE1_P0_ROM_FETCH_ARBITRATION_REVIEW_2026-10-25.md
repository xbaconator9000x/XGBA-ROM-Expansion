# P0 review packet: mGBA ROM fetch, data access and cartridge arbitration

**Status:** SOURCE-ANCHORED CONTRACT RECONCILIATION; NOT AN INDEPENDENT WHOLE-FILE APPROVAL. Phase 1 remains FAIL_INCOMPLETE.

## Immutable inputs

- mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b`.
- `src/arm/arm.c` blob `0b92d7f55f1fb853d4b1b9c9163ee086126066e2`, lines 198–225.
- `src/gba/memory.c` blob `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc`, lines 285–377, 586–625, 701–716.
- `src/gba/dma.c` blob `da2a800ba48cb32d6e10e42c3b3527ef406bad22`, lines 259–330.
- `src/gba/cart/matrix.c` blob `9ccbe883235b98bcf56cd609015e7b4003aa832c`, lines 16–79 and 100–128.

These anchors and the semantic interpretation were already preserved in `docs/SEMANTIC_DEPENDENCIES_v16.md`. This packet reconciles their scope and outstanding obligations; it does not claim fresh upstream runtime tests.

## Verified source-linked claims and boundaries

1. ARM/Thumb instruction prefetch uses the CPU active region/mask, not simply the generic GBA data-read callbacks. Consequently changing data-load mapping alone is insufficient to redirect instruction fetch. **Not proven:** safe remap timing at every CPU instruction boundary.
2. The GBA memory decoder has independent ROM size, mirror, EEPROM/e-Reader and other peripheral cases. `tools/gba_memory_region_contracts.py` inventories cases lexically and expressly labels conditional flow unverified. **Not proven:** exhaustive preprocessor-resolved fallthrough or all runtime predicate outcomes.
3. The 16-bit DMA ROM2_EX path can interact with EEPROM; treating this address window as exclusively banked ROM would be unsafe. **Not proven:** arbitration across all DMA widths, transfers and native cartridge modes.
4. Matrix cartridge code mutates backing ROM and serializes its bank state. **Not proven:** composability with an opt-in XGBA bank manager.

## Negative-control obligations before semantic acceptance

| Test | Required positive control | Required negative/fail-closed control |
| --- | --- | --- |
| ARM and Thumb remap | fetch and data reads agree after authorized remap | reject absent/invalid backing bank; no stale prefetch |
| Native compatibility | original ROM fetch/mirror semantics preserved | no implicit XGBA activation for vanilla images |
| EEPROM and e-Reader | original 16-bit access and DMA behavior retained | extension command must not shadow peripheral reads |
| Matrix bank state | native bank state round-trips through savestate | conflicting extension remap rejected, not silently combined |
| Decoder exhaustiveness | compile-time branches classified per actual configuration | unknown conditional/fallthrough cannot be marked verified |
| Debugger and rewind | instruction/data views and rewind reflect same selected bank | stale cache or mismatched backing identity rejected |

## Review decision

**No file disposition is approved.** The existing evidence demonstrates substantive semantic mapping, but it does not close the dynamic fetch, DMA, peripheral arbitration, or savestate regression obligations. Reviewers must separately validate each exact source blob and dossier hash and record independent identity/rationale before the authoritative gate can count acceptance.

**Next bounded step:** implement and execute a pinned mGBA test harness for the instruction-fetch/data-read remap boundary and an invalid-bank negative control, or document the precise build/test blocker. Do not expand the ROM architecture based on the lexical branch inventory alone.

# Phase 1 P0 — FireRed save reload ↔ mGBA savestate/Matrix ROM identity (27 October 2026)

**Verdict: PINNED_SOURCE_CANDIDATE / FAIL_INCOMPLETE.** This is a dependency analysis, not a demonstration of a runtime defect, a certified external-bank implementation, or an independently approved whole-file disposition.

## Immutable upstream scope

FireRed: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. mGBA: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`. The [reproducible checker](../tools/phase1_firered_mgba_savestate_mapping.py) validates **six exact Git blobs** before source assertions:

| Repository | File | Git blob SHA-1 |
| --- | --- | --- |
| FireRed | [src/reset_save_heap.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/reset_save_heap.c) | `745270dc7415b869c302daaa7b9c2b2e5b2865f1` |
| mGBA | [src/gba/serialize.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c) | `a307a51e751f412c64a7378323c56758304ebe85` |
| mGBA | [include/mgba/internal/gba/serialize.h](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/serialize.h) | `0192cd90ffeeb1d435cd51915325783bf18fb85c` |
| mGBA | [src/gba/cart/matrix.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c) | `9ccbe883235b98bcf56cd609015e7b4003aa832c` |
| mGBA | [include/mgba/internal/gba/cart/matrix.h](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/cart/matrix.h) | `27e32a75c0f521dac9ded53821591485089d7b76` |
| mGBA | [src/gba/memory.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` |

## Source-grounded dependency graph

1. **These are two distinct operations.** FireRed's `ReloadSave` masks IME, requests `RegisterRamReset(RESET_EWRAM)`, restores IME, rebinds save-block pointers, reads a cartridge save and installs `CB2_ContinueSavedGame`. mGBA's `GBADeserialize` restores a full emulator snapshot, including CPU, IWRAM, EWRAM, video/audio, save-device protocol state and optional Matrix mapping. A compatibility layer must not treat a game-internal reload as a savestate restore.
2. **Savestate identity checks are not uniform.** mGBA's format is `0x0100000B` and the source declares a `0x61000`-byte state structure. A game ID/title mismatch sets `error=true`; a **ROM CRC32 mismatch only logs a warning**. The ROM-size/PC check may reject a current PC beyond the loaded ROM, but does not verify every referenced resource. Too-new/invalid versions reject; older versions log that they continue. A BIOS checksum mismatch is conditionally fatal depending on BIOS involvement and the saved PC. These source branches are not equivalent to a full content-identity gate.
3. **Restoration is ordered.** After early validation and CPU register restore, `GBAUnlCartDeserialize` runs *before* active-region reselection and prefetch restoration because it can remap the ROM. Then video, RAM, I/O, audio and save-device protocol state are deserialized. Only **after** these does `GBAMatrixDeserialize` run, conditional on `gba->memory.matrix.size`. Finally `mTimingInterrupt` runs. The source does not establish that arbitrary external bank content is coherent with restored instruction prefetch.
4. **Matrix replay has separate resource-provenance obligations.** The pinned Matrix implementation has **16 mapping slots**. Deserialization sets a temporary 512-byte mapping size and replays all 16 serialized physical mappings into the ROM window by seeking and reading `gba->romVf`, then restores the serialized Matrix command/address/size fields. `_remapMatrix` checks virtual-address and size alignment/range, but **does not locally check the return values** of the VFile seek/read operations. The physical address accepted by `GBAMatrixWrite` is masked with `0x03FFFFFF` (26 bits); this is not a limitless physical store or a guarantee that the backing VFile contains those bytes.
5. **The base RAM snapshot is explicit.** `GBAMemoryDeserialize` copies all `GBA_SIZE_EWRAM` and all `GBA_SIZE_IWRAM` bytes, unlike FireRed's EWRAM-only reload. Neither the fixed-format state header nor a warning-only ROM CRC check certifies the identity of externally banked assets.

## Fail-closed boundary and next evidence

Run `python3 tools/phase1_firered_mgba_savestate_mapping.py --firered upstream-firered --mgba upstream-mgba --output phase1-evidence/firered-mgba-savestate-mapping.json`. The checker validates the pinned files, source-local ordering and **14 scoped negative mutations**. Its result is explicitly source-only; a PASS is not runtime, editor, hardware or independent-review approval.

**Open proofs:** inspect compiled savestate layout and variant ABI; determine Matrix VFile length and read-error behaviour; reproduce restores with same game ID/title but altered ROM/bank contents; trace pipeline and prefetch after Matrix remapping, including old-format savestates; verify save-device state under reset and restore; test editor round trips and obtain independent whole-file reviews. The earlier native mGBA regression observations are relevant but do not close these additional proofs.

**Phase 1: FAIL_INCOMPLETE. Independent whole-file approvals: 0/14,834. No Phase 2 implementation.**

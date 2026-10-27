# Phase 1 — FireRed ↔ mGBA Flash1M identification contract (review handoff)

**Status:** source-grounded, cross-repository P0 dependency witness; **not** a complete-file independent disposition, a new registered prepared candidate, or runtime certification. No upstream code is modified. This packet is isolated from the separate Phase 1 worker.

## Immutable sources and evidence

FireRed is pinned to `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; mGBA is pinned to `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`. The verifier checks **11 exact Git blob hashes**, anchored source statements, chip-ID byte ordering, and seven negative controls. The complete blob identity table is in `tools/phase1_firered_mgba_flash_contract.py`. These are *dependency endpoints* of previously prepared Flash/savedata packets, **not eleven newly prepared or approved files**.

| Producer / consumer | Pinned source evidence | Contract |
|---|---|---|
| FireRed Flash identification | `src/agb_flash_1m.c:6–49`; `src/agb_flash_le.c:12–31` | `IdentifyFlash` accepts the Sanyo LE ID bytes `62 13` (little-endian `0x1362`) and otherwise uses the fallback descriptor with a nonzero return |
| FireRed save availability | `src/load_save.c:46–57` | `CheckForFlashMemory` sets `gFlashMemoryPresent=FALSE` on nonzero `IdentifyFlash` result |
| mGBA 1-Mbit identification | `src/gba/savedata.c:377–396`; `include/mgba/internal/gba/savedata.h:49–54` | In Flash1M mode, ID reads return `FLASH_SANYO_LE26FV10N1TS=0x1362`, matching the pinned FireRed LE descriptor |
| mGBA initial 512-Kbit identification | Same files, plus `src/gba/savedata.c:267–278` | If first initialized from `GBA_SAVEDATA_AUTODETECT`, `GBASavedataInitFlash` selects `FLASH512`, whose ID read is Panasonic `0x1B32`, **not** one of FireRed's 1-Mbit setup descriptors |
| mGBA save-type override | `src/gba/overrides.c:132–148,385–445`; `src/gba/core.c:787–790` | Known FireRed IDs (e.g. `BPRE`) map to Flash1M. The modified-Pokémon-ROM heuristic recognizes a lowercase ROM text marker at offset `0x108` and an unknown CRC, then forces Flash1M and RTC; user config and explicit overrides can change this |
| mGBA first Flash write | `src/gba/memory.c:1064–1076` | An autodetected first Flash unlock write selects `GBASavedataInitFlash`, which initially chooses Flash512; later bank switching can promote to Flash1M, **but that is not necessarily soon enough for FireRed's earlier chip-ID check** |
| Physical save geometry | FireRed `include/save.h:6–30`, `src/agb_flash_le.c:20–29`; mGBA `include/mgba/internal/gba/memory.h:72–73`, `src/gba/savedata.c:759–776` | 128 KiB Flash, 32 × 4-KiB sectors; 14 sectors per slot × 2 slots plus sectors 28–31; 64-KiB bank switch. This is *save Flash*, not cartridge ROM address space |

## P0 interoperability boundary

Three **conditional paths** follow from the pinned source, not from a run of either game or emulator:

1. **Known FireRed game code retained** (e.g. `BPRE`): the built-in mGBA override can force Flash1M before FireRed identifies the chip; Sanyo `0x1362` matches the FireRed LE descriptor.
2. **Game code changed, but the expected lowercase Pokémon ROM marker remains at offset `0x108`, and CRC is not in the known table**: the mGBA hack heuristic can force Flash1M, but also enables RTC and `vbaBugCompat`. This is not a guarantee for every emulator, override configuration, or ROM header.
3. **Both game code and heuristic marker changed/removed, with no explicit save-type override**: mGBA can remain in AUTODETECT, initialize Flash512 on the first Flash command, and expose Panasonic `0x1B32` on FireRed's initial ID read. FireRed's 1-Mbit setup list does not include that ID; `IdentifyFlash` can return failure and `CheckForFlashMemory` can mark Flash unavailable. Later 512→1M bank promotion does not retroactively prove successful initial identification.

This is a **concrete source-level compatibility risk** for ROM expansion, header rewriting, and romhacking tool exports. It is not evidence that an existing build fails: actual ROM headers, emulator versions, explicit configuration, first-write ordering and supported hardware must be tested. **Do not “fix” by blindly preserving a fake game code or rewriting mGBA.** A ROM/editor export should explicitly declare its save-chip contract, preserve compatible identification where appropriate, and test each supported emulator.

## Distinct additional obligations

- Check **actual** exported ROM header bytes (game code, text marker and CRC), whether mGBA's `GBAOverrideApplyDefaults` runs before `CheckForFlashMemory`, and explicit/manual override precedence.
- Trace FireRed `ReadFlashId`, Flash timer registration, the `IdentifyFlash` fallback and ROM revision/compiler conditions. Confirm no alternate FireRed save initialization changes the observed decision tree.
- Test baseline FireRed and a deliberately changed-header ROM under pinned mGBA, with and without manual Flash1M override; compare mGBA, other emulators and hardware/flashcart save-chip handling. Those runtime and release regressions are **future evidence**, not claimed by this Phase 1 packet.
- Verify 32-sector save-file preservation, 64-KiB bank selection, 4-KiB sector erase and the mGBA direct-Flash1M initialization gap already documented in PR #12/#13; no savedata growth or save-state approval follows from an ID match.
- Obtain an **independent reviewer**, with source-revision-bound signoff and counterexample analysis. Do not self-approve or change gate counts.

## Evidence boundaries

The verifier is deliberately source-contract-only. Exact SHA-1 verifies Git blob bytes, not compiler behavior, runtime initialization order, save-file integrity or emulator interoperability. The conditional model is not an emulation harness. Existing packets: [FireRed Flash PR #17](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/17), [mGBA savedata PR #12](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/12), [mGBA initialization witness PR #13](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/13).

**Accounting remains unchanged:** inventory 14,834/14,834 (100%); registered substantive candidates **113/14,834 (0.7618%)**; independently approved **0/14,834 (0.0000%)**; historical machine triage **14,721/14,834 (99.2382%)**. Authoritative gate **`FAIL_INCOMPLETE`**. Historical binary-aware migration and independent review remain outstanding.

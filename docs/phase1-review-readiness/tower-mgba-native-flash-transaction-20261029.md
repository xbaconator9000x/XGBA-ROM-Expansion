# Phase 1 — native mGBA Trainer Tower special-sector bus witness (partial)

**Review state: FAIL_INCOMPLETE.** This is not a whole-file disposition or independent approval.

## Immutable source identities

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`. Existing Trainer Tower source audits establish physical sector IDs 30/31, and original host C wrappers have separately been executed.
- mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`; `src/gba/savedata.c` blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`, MPL-2.0 notice. Original mGBA Flash command handling is linked into a native mGBA core, unchanged.
- Reuse strategy: existing `GBASavedataForceType`, native `mCore` GBA bus, mGBA Flash bank-switch, erase and program command handlers. No new emulator or Flash serializer. Test-only synthetic cartridge and bus command driver are not a replacement implementation.

## New runtime experiment

The C fixture `tests/phase1_tower_native/phase1_tower_mgba_flash.c` runs the actual mGBA core against an in-memory synthetic ROM. It selects Flash1M bank 1, sends genuine emulated Flash unlock/bank/erase/program bus commands, and observes byte regions corresponding to FireRed sectors 30 (`0x1E000`) and 31 (`0x1F000`). It writes two matching generations, interrupts after updating only the first sector, then retries the second sector. Negative controls check adjacent sector and bank-zero isolation, invalid bank selection and unlocked writes. The independent Python evidence checker enforces pinned source identity, 14 ordered native assertions, explicit scope limitations, 17 source and 14 transcript mutations; the parser also requires all 12 original mGBA Flash diagnostic lines.

This is **native mGBA emulator Flash command execution with host-driven synthetic transactions**, not original agbcc ARM execution of `TryWriteSpecialSaveSector` or `CEReaderTool_SaveTrainerTower`. The test-only generation marker is not FireRed's original checksum or sentinel validator. The interruption is a deliberate stop between writes, not a hardware power cut. No persistent `.sav` reload or game-initiated save is claimed.

## Dependency / reuse decision and reviewer questions

- **Reuse** original mGBA Flash bank mapping, rather than building a new Flash device. Its bank 1 local sectors 14/15 correspond to the FireRed special sector IDs. Preserve existing ROM and save behavior.
- **Reuse** original FireRed special-sector and CEReader functions in subsequent ARM-linked tests, rather than transcribing their semantics into a new reader.
- **Unresolved**: can the actual original-agbcc functions execute in mGBA at their source-built ROM locations, with stock caller reachability? Does a restarted mGBA core observe the same persisted `.sav` bytes? What does genuine power interruption do to the second sector? No hardware durability claim is supported.
- **Licensing/interoperability**: mGBA MPL-2.0 source remains unmodified and is built as its own library; FireRed source is checked by pin, not copied into this fixture. Review upstream licenses before redistribution or incorporating patches.

This dossier is **partial scope only** for `src/gba/savedata.c`, `src/save.c` and the test harness. All Phase 1 gates remain `FAIL_INCOMPLETE`; 0/14,834 independent approvals.

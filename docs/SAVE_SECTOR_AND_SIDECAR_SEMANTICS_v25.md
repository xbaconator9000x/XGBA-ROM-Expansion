# Phase 1 v2.5 — native flash save layout and sidecar state obligations

**Source pinned:** `pret/pokefirered` `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `mgba-emu/mgba` `fd9dc5c2cbf234365068855851107e762fc6211b`.

## Actual FireRed flash layout

[FireRed include/save.h:6–30](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save.h#L6-L30) (Git blob `87fb9b615b434b58823d15688056695acda9feab`) declares:

- **4,096 bytes per sector**: 3,968 data bytes + 128 footer bytes (12 footer bytes used).
- **14 sectors per main save slot**, with **two rotating slots** (sector offsets 0–13 and 14–27).
- **Four special sectors** (28–31) for Hall of Fame and Trainer Tower.
- **All 32 sectors are assigned**: exactly 131,072 bytes (128 KiB); there are no extra unallocated native flash sectors.
- [SaveSector structure:63–74](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save.h#L63-L74) stores a sector ID, 16-bit checksum, 32-bit signature `0x08012025`, and save counter.

[FireRed src/save.c:133–195](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/save.c#L133-L195) (Git blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`) rotates sectors using both `gLastWrittenSector` and `gSaveCounter % NUM_SAVE_SLOTS`, writes the signature and counter and calculates the native checksum.

[FireRed src/save.c:439–565](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/save.c#L439-L565) checks native checksums/signatures in **both slots**, evaluates valid-sector bitsets and chooses the latest acceptable counter. A partially damaged save may therefore recover from an older slot.

[FireRed src/load_save.c:69–130](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/load_save.c#L69-L130) (Git blob `8b723dd044c6024b3671bb890b25b56a53f99ec5`) deliberately offsets active save-block pointers, relocates native structures, and rotates the encryption key used for legacy game data.

## Emulator savedata is type-specific, not an unbounded file

[mGBA include/mgba/internal/gba/memory.h](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/memory.h) (Git blob `0aad912613e726560d06bbdbf6061986e69e5842`) defines 64 KiB `FLASH512` and 128 KiB `FLASH1M`. [`src/gba/savedata.c:169–201`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/savedata.c#L169-L201) (Git blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`) selects the native file size from the emulated savedata type and expects exactly that many bytes when importing into mapped savedata.

## Required XGBA compatibility contract: SAVE-SIDECAR-v0

1. **Preserve all original 32 flash sectors**, slot ordering, sector ID sizes, native checksum and signature rules. A sidecar must not overwrite sector 28–31 or append unsupported bytes to a `.sav`.
2. Use separately versioned *logical* extension save records, not raw FireRed RAM pointers, physical sector numbers or mGBA host VFile addresses.
3. Tie extension state to a stable game + extension manifest identity **and the successfully selected native save commit**. Handle power-loss recovery, corrupted auxiliary records and slot rollback deliberately.
4. When the native save falls back from one slot to another, extension data must follow the validated slot or fail closed, not mix a newer sidecar with older save-sector contents.
5. Respect mGBA native save-type selection, ROM unload/reload and flash bank switching. Emulator **savestates** and game **flash saves** need separate extension identity/serialization paths.
6. Testing must include two slots, counter rollover, partial writes, invalid signatures, invalid checksum, out-of-range sector IDs, sidecar missing, sidecar stale, and legacy save round-trip.

## Evidence and limits

[`tools/save_sector_source_semantics.py`](../tools/save_sector_source_semantics.py) successfully verified **17 pinned-source contracts** and native sector arithmetic. It does *not* prove end-to-end save power-loss atomicity or any XGBA implementation. The mapping gate remains **FAIL_INCOMPLETE** pending independently reviewed file dispositions.

Do not infer limitless in-game save storage from an emulator being able to open an arbitrarily large host file.

# Phase 1 semantic disposition candidate 0001 — FireRed ROM header

**Review state: PENDING_INDEPENDENT_REVIEW (not approved).** This is a source-grounded, whole-file *analyst candidate* prepared for an independent reviewer. It does not count toward the Phase 1 approval gate.

## Immutable identity
- Upstream: `pret/pokefirered`
- Commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- Path: `src/rom_header.s`
- Git blob SHA: `c98c89992a128b82ef3bc8f75c791cd1c6cbdcb9`, verified directly by GitHub's file response for the exact commit.
- [Exact source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/rom_header.s); [pinned cross-file boot trace](PHASE1_P0_FIRERED_BOOT_IRQ_RAM_LIFETIME_2026-10-26.md).

## Whole-file inventory and semantics
The complete assembly source was read, not only the entry branch:
1. Exported `Start` emits `b start_vector`. This is the cartridge entry's source-level dependency on the reset stub in `src/crt0.s`; the linker variant controls actual ROM placement.
2. `RomHeaderNintendoLogo` reserves 156 bytes; `RomHeaderGameTitle` 12; exported `RomHeaderGameCode` 4; `RomHeaderMakerCode` 2; `RomHeaderMagic`, `RomHeaderMainUnitCode` and `RomHeaderDeviceType` each emit one zero byte.
3. `RomHeaderReserved1` reserves 7 bytes; exported `RomHeaderSoftwareVersion` emits one zero; `RomHeaderChecksum` emits one zero; `RomHeaderReserved2` reserves 2 bytes; one zero word follows.
4. Exported `GPIOPortData`, `GPIOPortDirection`, `GPIOPortReadEnable` each emit one zero halfword; a 6-byte gap follows.
5. Twelve consecutive `.4byte 0xFFFFFFFF` entries close the file. These are authored values, not proven runtime-accessed memory, padding or a general-purpose expansion area.
6. The source explicitly states that `gbafix` fills header fields using Makefile-supplied data. The source therefore does **not** establish final cartridge header bytes by itself.

## Dependencies and XGBA relevance
- Producer: assembler and linker place the source in the ROM image; post-link `gbafix` populates header fields. The precise Makefile invocation, tool version and final header bytes must be checked independently.
- Consumer: CPU reset path reaches `start_vector`; header/logo/checksum fields are subject to GBA cartridge boot conventions, but this file alone does not prove hardware validation, emulator behaviour or final linked addresses.
- The header is fixed-format, not a self-describing unbounded resource table. Future XGBA metadata must not repurpose these bytes without a separately verified compatibility contract.
- The GPIO halfword labels and trailing words must not be assumed to be free space or hardware-mapped GPIO registers solely from their names. Verify linker addresses, consumers and compiled bytes before any remap design.

## Evidence quality and unresolved obligations
- **Verified:** entire pinned source content and exact Git blob hash; source-level entry branch, all declarations and authored constants.
- **Cross-file source evidence:** boot chain and linker ordering in the pinned boot dossier.
- **Not yet verified for this whole-file disposition:** every external symbol consumer, exact section VMA/LMA and final ROM offsets, `gbafix`/Makefile transformation and resulting bytes, GPIO consumers, boot-time emulator/hardware behaviour, and independent reviewer evaluation.
- **Suggested reproducible next tests:** compile both pinned FireRed variants; inspect `Start`, header/GPIO symbol addresses and final header bytes before/after `gbafix`; search all pinned source/linker references to exported symbols and compare against linker map/relocations.

## Reviewer decision
- Candidate author: automated source-grounded analysis; **not independent**.
- Independent reviewer identity/date: **not supplied**.
- Verdict: **PENDING_INDEPENDENT_REVIEW**.
- Gate contribution: **0 approvals**. Do not convert this candidate to `approved` or edit gate counts without a separate whole-file reviewer decision and verified ingestion.

**Phase 1 decision: FAIL_INCOMPLETE; 0/14,834 independent approvals.**

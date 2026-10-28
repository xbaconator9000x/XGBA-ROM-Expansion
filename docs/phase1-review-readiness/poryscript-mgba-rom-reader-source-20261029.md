# Phase 1: FireRed Poryscript reader to mGBA ROM data-read boundary (2026-10-29)

**SOURCE-ONLY / FAIL_INCOMPLETE / 0 of 14,834 independent approvals.**

Pinned identities: FireRed ce6406d8c2eaf46d543c8a2606de0c3cb1951982, src/script.c blob d0433bdda062b138e53d1a1d3184b4566ad7d9dc. mGBA fd9dc5c2cbf234365068855851107e762fc6211b, src/gba/memory.c blob aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc and memory.h blob 0aad912613e726560d06bbdbf6061986e69e5842.

**MAXIMUM REUSE:** original FireRed reader and original agbcc, existing Poryscript-generated table, original mGBA memory and core. Do not rebuild a CPU, ROM mapper or script parser. Future smallest extension: test-only mGBA core/debugger instrumentation; preserve original behaviour and immutable blobs.

**New source-proven cross-repository boundary:** FireRed outer reader scans five-byte entries until zero; conditional reader scans eight-byte entries until zero first u16. Neither has explicit length. Pinned mGBA ROM data loads GBALoad8/16/32 use address-derived fallback values on out-of-ROM reads (with cartridge/AGBPrint exceptions), and unaligned 16/32-bit reads rotate. Invalid instruction fetch in GBASetActiveRegion has separate _deadbeef/coreCrashed behaviour. Thus an unterminated table is not guaranteed to fault or safely terminate in mGBA. Prior POSIX guard-page SIGSEGV is host-only and not a native emulator fault prediction.

The new checker uses immutable Git blob checks and 12 fail-closed source mutations across reader stride/sentinels, three data widths, 32-bit macro fallback, instruction-fetch distinction and ROM aperture. **No native mGBA execution has been performed by this checker.**

Next: reuse original-agbcc linked reader and existing generated Poryscript table, verify ROM placement and map-header pointer, instrument bounded valid and malformed table execution in pinned mGBA; archive PC, memory reads, return pointer, step budget, ROM/ELF hashes and configuration. Distinguish synthetic fixture from stock reachability. mGBA MPL-2.0 source notice/root license; FireRed code/assets require separate licensing review. Partial-file dossier only; no whole-file approvals.

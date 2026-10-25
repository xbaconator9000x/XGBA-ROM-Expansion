# Phase 1 v2.8 — independent cartridge image reproducibility

**Primary evidence:** [Run A: pinned FireRed original + modern build](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40190335380), [Run B: independently repeated pinned source builds](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40190655461). [Checksummed permanent v2.8 release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.8).

Both builds use the exact `pret/pokefirered` revision `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Executable ROM bytes have **not** been distributed: artifacts retain SHA-256 whole-ROM, ELF, symbol-table and per-64-KiB page digests.

## Measured cross-run identity

| Artifact | Original agbcc two-run result | Modern GCC two-run result |
| --- | --- | --- |
| ELF SHA-256 | **Identical** | **Different** |
| Native 16 MiB `.gba` SHA-256 | **Identical** | **Different** |
| All compiled defined symbol names, sizes, addresses and regions | **Identical** | **Identical** |
| First 192 cartridge-header bytes | **Identical** | **Identical** |
| 64 KiB ROM pages differing | **0 / 256** | **1 / 256** |

The modern changed page is **page index 30**, native ROM offset `0x001E0000–0x001EFFFF`, GBA CPU addresses **`0x081E0000–0x081EFFFF`**. Both runs produce exactly 16,777,216 bytes and retain the standard GBA header `0x96` fixed byte. The modern symbol-table hash is identical across the compared builds; exact ROM bytes are not.

### Native image hashes (SHA-256)

- Original agbcc, both runs: `3d0c79f1627022e18765766f6cb5ea067f6b5bf7dca115552189ad65a5c3a8ac`.
- Modern GCC, Run A: `d1170c8d66766c4ba7b035f21d8158cd23548075e88d318af3ae4c39a9ab4c56`.
- Modern GCC, Run B: `7505ec2ffd9385f6d94cb5ddf4545d6f8dba6eb4dea1a3d125a7b39431f0e031`.

**Interpretation:** changing the modern ELF hash is **not purely a harmless debug/ELF-metadata change**; at least one 64 KiB region of its *actual GBA ROM* differs. Whether that one-page change affects live instructions, static data, padding or generator metadata is still unresolved and must not be guessed from matching symbol addresses. The source-host linker build is not necessarily reproducible byte-for-byte.

## Compatibility requirement

A future XGBA plugin cannot assume two ROMs are compatible simply because they derive from the same pinned Git commit and yield the same exported C symbol table. A conservative exact-binary adapter must also bind to the **actual cartridge image hash**. An alternative version-tolerant adapter requires byte-level semantic/provenance proof for every changed range and must fail closed until established.

This finding does **not** justify loosening the existing elf-hash preflight without more work. The new proposed `tools/runtime_rom_symbol_preflight.py` is intentionally a separate candidate contract, awaiting verified compile and negative tests.

## Next verified analysis

The reproducible `tools/firered_runtime_rom_hashes.py` source scanner will sample the specific changing page in 32-byte digest chunks for additional independent runs, preserving content hashes rather than publishing game data. A source-address review will then determine whether the differences fall inside a named resource, initialization table, or unaccounted build section.

**Completion remains FAIL_INCOMPLETE**, with 0 independent whole-file semantic signoffs and no XGBA memory expansion implemented.

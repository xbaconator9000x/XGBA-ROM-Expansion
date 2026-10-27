# Phase 1 P0 — compiled Poryscript-to-FireRed map-table relocation boundary (27 October 2026)

**Status:** `PINNED_COMPILED_SYNTHETIC_WITNESS / FAIL_INCOMPLETE`. This is a reproducible LLVM ARMv4T object/link test, **not** original agbcc/linker equivalence, a compiled stock FireRed ROM, an mGBA/GBA execution, a whole-file semantic approval or Phase 2.

## Dependency-connected source closure

| Owner / pinned source | Git blob SHA-1 | Scope |
| --- | --- | --- |
| `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55:emitter/emitter.go` | `d35843ef29929ead47351646d7a33dd5c692b850` | Producer writes `map_script`, `map_script_2` and their distinct terminators |
| `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982:asm/macros/map.inc` | `83ef472c926ce767c9133ab9bd6922280b38bb2d` | Actual unmodified assembler macros extracted by the checker |
| Same FireRed commit, `src/script.c` | `d0433bdda062b138e53d1a1d3184b4566ad7d9dc` | Native five-byte tag/pointer reader and eight-byte conditional-table reader |
| Same FireRed commit, `include/constants/map_scripts.h` | `1353de360cf1e00b6efbb26ec59c4822c99b59bf` | Type 2 on-frame table and type 3 transition tags |

These four files are **source anchors, not new machine-triage identities or completed whole-file reviews**. The existing nine-blob [source-level producer/consumer dossier](PHASE1_P0_PORYSCRIPT_FIRERED_MAP_SCRIPT_ABI_2026-10-27.md) remains separate.

## Reproducible compiled result

The [checker](../tools/verify_poryscript_compiled_map_table.py) verifies both exact upstream commits and all four Git blobs before extracting the **original FireRed map macros**. It then assembles a deliberately synthetic, Poryscript-emitter-shaped table using `clang --target=armv4t-none-eabi`, links with `ld.lld` at synthetic ROM address `0x08000000`, and reads ELF32 sections/REL relocations with Python standard-library code. The fixture has two outer tags (2 and 3), a one-byte outer zero sentinel, two type-2 conditional entries, and a two-byte conditional zero sentinel.

| Verified contract | Synthetic object/link result |
| --- | --- |
| Outer records | 5 bytes each; pointer fields begin at byte offsets 1 and 6 |
| Outer terminator | One byte at offset 10 |
| Conditional records | 8 bytes each; first begins at offset 11 |
| Conditional terminator | Two bytes at offsets 27–28 |
| ARM object relocations | Four `R_ARM_ABS32` relocations at offsets **1, 6, 15, 23** |
| Linked pointer values | `0x0800000B`, `0x0800001D`, `0x0800001F`, `0x08000020` |
| Object `.rodata` SHA-256 | `49e9e75bb51e69925bb8c7470d47242cd584c88ebdabe2298e4f799ca8d17bfa` |
| Linked `.rodata` SHA-256 | `0f7c77fec5bec5b40f0405cd64c381e9c3b00c39288fdc8306f6c82abb2d8a27` |

The compiled witness shows that these macro pointer relocations are **unaligned**, as expected from the packed five-byte outer records. FireRed's native consumer uses the `T2_READ_PTR` access path rather than an ordinary naturally aligned pointer-field struct. A future source editor or extended pointer format must preserve the reader's ABI or explicitly replace both producer and consumer. The ELF object/link proof does not demonstrate that arbitrary relocated ROM pointers are safe in the real engine.

Nine deliberately mutated synthetic fixtures (tag, terminator widths, first-variable sentinel, variable, comparison, pointer target, script byte, pointer width) must all be rejected by the exact byte/relocation checker or the assembler/linker. These are **negative controls**, not nine independent runtime tests.

## Open edges and negative evidence

- No actual Poryscript binary was executed to emit this fixture; the producer template was source-pinned, and the assembly was constructed independently to match its directives.
- No original `agbcc` or legacy FireRed linker was used. The LLVM link base is a **synthetic test address**, not a stock ROM layout.
- No mGBA execution, malformed/truncated table test, flash/save interaction, or live script dispatch was performed.
- No source-to-assembler round-trip or preservation of authored script names/control-flow was established.
- No Porymap editor save/reload or native editor interoperability was tested.
- No whole-file review record is added; no external reviewer independently approved these source identities.
- The authoritative machine-triage pool is already exhausted: **0 newly processed files this run, shortfall 1,000 against the nominal target**. Previously reported **14,721/14,721** machine-triaged coverage is not recounted as new work.

## Reproduction

```bash
python3 tools/verify_poryscript_compiled_map_table.py --self-test
python3 tools/verify_poryscript_compiled_map_table.py \
  --poryscript /path/to/exact-pinned-poryscript \
  --firered /path/to/exact-pinned-pokefirered \
  --output phase1-evidence/poryscript-compiled-map-table.json
```

The dedicated [workflow](../.github/workflows/phase1-poryscript-compiled-map-table.yml) checks out both pinned upstream repositories, runs the compiled fixture, and archives the machine-readable evidence. A green run must be matched to its **exact commit SHA** before citing it.

**All Phase 1 gates remain `FAIL_INCOMPLETE`; independent approvals remain 0; Phase 2 untouched.**

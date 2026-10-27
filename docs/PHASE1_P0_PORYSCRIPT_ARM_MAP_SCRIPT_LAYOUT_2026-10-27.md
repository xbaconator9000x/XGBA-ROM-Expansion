# Phase 1 P0 — ARMv4T map-script macro serialization witness

**27 October 2026 — isolated ARMv4T Clang object, not a full FireRed build or independent review.** Phase 1 remains **FAIL_INCOMPLETE**.

## Pinned source and producer/consumer boundary

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `asm/macros/map.inc`, Git blob `83ef472c926ce767c9133ab9bd6922280b38bb2d`: `map_script` emits a one-byte tag followed immediately by a four-byte pointer; `map_script_2` emits two 16-bit fields and one 32-bit pointer.
- Poryscript `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`, `emitter/emitter.go`, Git blob `d35843ef29929ead47351646d7a33dd5c692b850`: map-script statements emit the two native macro forms and their distinct one-byte/two-byte zero sentinels.
- FireRed `src/script.c`, Git blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`: native readers advance five bytes per tagged map-script entry and eight bytes per table entry, with separate terminator tests. Existing source contract: `tools/phase1_poryscript_firered_map_script_abi.py`.

## Isolated ARM object evidence

The exact macro bodies inspected in the pinned `map.inc` were assembled in a standalone `armv4t-none-eabi` Clang 17 object. Two `map_script` records plus `.byte 0` occupied **11 bytes**; two `map_script_2` records plus `.2byte 0` occupied **18 bytes**, contiguous in a **29-byte** read-only section without implicit 4-byte alignment between records.

Observed section bytes:

```text
01 34 12 00 08  02 78 56 00 08  00
01 40 34 12 bc 9a 00 08  00 80 01 00 f0 de 00 08  00 00
```

SHA-256 of these 29 bytes: `c1435980e94a73a3df4c6c580ff5d93550cdadbf3d28f5818c149ff35278a854`. Replacing the first `.4byte \script` with `.2byte \script` failed compilation because the synthetic 32-bit address did not fit in 16 bits; the negative control did **not** silently produce the expected object.

Reproducer: `tools/phase1_poryscript_arm_map_script_layout.py --source /path/to/pinned/pokefirered/asm/macros/map.inc --output audit-output/poryscript_arm_map_script_layout.json`. The reproducer checks the exact source Git blob before extracting macros. The isolated snippet/object and negative control were executed locally; the complete pinned-file command is **not yet recorded as executed** because the pinned checkout and GitHub Actions runner were unavailable in this environment.

## Remaining gates and editor consequences

This proves the **isolated macro expansion** under the stated compiler, not original GNU as/agbcc output, actual Poryscript-generated script bytes, final FireRed linker relocation, emulator execution, malformed-table handling, or PokéBacon's reconstruction of script/event graphs. A future script editor must distinguish the five-byte tag/pointer table from the eight-byte variable-comparison table and preserve both sentinel widths. Full pinned build and emulator counterexamples remain required. No whole-file review candidate or independent approval is added; **0 approvals**, **FAIL_INCOMPLETE**.

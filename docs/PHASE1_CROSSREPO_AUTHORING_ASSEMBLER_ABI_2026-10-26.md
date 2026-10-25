# Phase 1 — pinned cross-repository map authoring → assembler ABI review (26 October 2026)

**FAIL_INCOMPLETE; 0 independent whole-file approvals; no Phase 2 changes.**

This additive packet follows the v4 mGBA dependency checkpoint. It maps **one previously uncurated FireRed source file**, `asm/macros/map.inc`, and **seven typed producer/consumer relationships** across the pinned Porymap, Poryscript and FireRed repositories. The other seven sources were already in the original curated 29-file register; this does **not** count them twice.

## Source-grounded semantic findings

1. Porymap `src/core/block.cpp:8-10,43-52` defaults to masks 0x03FF/0x0C00/0xF000 but allows project-configured masks. FireRed `include/global.fieldmap.h:4-11` fixes those masks in the compiled runtime. A project whose editor masks differ is not automatically binary-compatible with FireRed.
2. Porymap `src/core/blockdata.cpp:3-10` emits **little-endian 16-bit packed blocks**. FireRed `src/fieldmap.c:103-127` copies map layout rows as `u16` and checks finite virtual-grid capacity. A rendered tile image or metatile ID alone is not a complete native block record.
3. Porymap `src/core/maplayout.cpp:576-626` can resize mismatched block arrays and discards an odd trailing byte during pairwise reads. Those behaviours must be treated as potentially **lossy** by an XGBA import/refresh adapter; they are not proof of a lossless round trip.
4. Poryscript `emitter/emitter.go:112-145` emits `map_script`, `map_script_2` and distinct table terminators. FireRed `asm/macros/map.inc:9-20` expands these into byte/halfword fields and **32-bit symbol pointers**. Compiler output and source-authored Poryscript are not interchangeable provenance.
5. FireRed `asm/macros/map.inc:22-38` packs native object-event fields including a script pointer, with corresponding `ObjectEventTemplate` layout in `include/global.fieldmap.h:110-134`. The linker `ld_script.ld:4-9` declares a **32 MiB ROM region**. These are native ABI constraints, not an expansion mechanism.

## Reproduction and gate

`semantic-snapshots/curated/crossrepo_authoring_abi_additive_2026-10-26.json` records all exact Git blob identities and bounded dependency endpoints. `tools/phase1_crossrepo_authoring_abi_review.py` checks **eight pinned blobs**, **12 bounded source expressions**, **seven typed edges**, **ten fail-closed negative controls** and preserves the original **14,834 rows, 338 P0 priorities, 29 curated files and 37 prior candidates**. It emits a deterministic v5 review queue and SHA-256 evidence.

Pending review total: **29 original + 8 earlier additive + 1 authoring ABI = 38**, with **zero approvals**. Exact source pins: Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`; Poryscript `c32481161c767b25a3425fa9f1f8729927ff3d55`; FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. mGBA v4 checks remain pinned separately.

**Outstanding:** independent whole-file review and authentication, compiled assembler/linker relocations and offsets, map event/script ABI across build variants, real Porymap/Poryscript export-import-refresh comparisons, masks/collision/elevation preservation, and cross-emulator compatibility. No compatibility signoff is implied by green source CI.

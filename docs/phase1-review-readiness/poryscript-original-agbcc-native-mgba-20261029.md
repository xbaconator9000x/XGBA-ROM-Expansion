# Phase 1 — original-agbcc FireRed Poryscript map reader in pinned native mGBA

**Native test candidate; no runtime success claimed until exact-head CI passes. FAIL_INCOMPLETE; 0 independent approvals.**

## Maximum reuse

Build original `pret/pokefirered@ce6406d8` with original `pret/agbcc@da598c1d`, original GNU ARM/preproc; generate a **real** 32-byte table using pinned `huderlem/poryscript@c3248116` CLI, original map macros and preproc; load a test-only relocated copy of that table into a source-built FireRed ROM in unchanged `mgba-emu/mgba@fd9dc5c2`. No replacement parser, compiler, emulator, ROM mapper or runtime engine.

Use the original linked `MapHeaderGetScriptTable` and `gMapHeader` symbols from the actual ELF. A test-only host controller writes the table pointer into the original EWRAM map header, starts the original-agbcc Thumb function directly, and single-steps with a 500-instruction limit. Valid tags 3 and 2 and unknown tag 99 are compared to the Poryscript-generated table's exact relocated pointer/sentinel representation. A separate malformed synthetic fixture overwrites the outer sentinel and following ROM padding with nonzero bytes; it records return/budget behaviour without asserting universal bounds safety.

**Not stock gameplay reachability, not an unmodified stock ROM table placement, not an original game event dispatch, not physical hardware or Flash.** The table's relocation into spare ROM is test-only. ROM/ELF are not uploaded; only source identity, hashes and text evidence.

## Reviewer obligations

Confirm the test-only direct CPU entry and Thumb pipeline setup against original mGBA, inspect linked original-agbcc disassembly and source blob `src/script.c` `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`, verify `gMapHeader.mapScripts` offset 8 from pinned `include/global.fieldmap.h`, compare generated table bytes with the previously green GNU ARM witness, and independently reproduce native return PCs/values. A bounded malformed run is **not** proof of safe termination. Check stock map-header and gameplay callsite reachability separately. FireRed code/assets, Poryscript and mGBA license notices remain distinct; no upstream changes.

Partial-file review only. All Phase 1 gates FAIL_INCOMPLETE.

# Phase 1 — original-agbcc FireRed Poryscript map reader in pinned native mGBA

**Native test candidate; no runtime success claimed until exact-head CI passes. FAIL_INCOMPLETE; 0 independent approvals.**

## Maximum reuse

Build original `pret/pokefirered@ce6406d8` with original `pret/agbcc@da598c1d`, original GNU ARM/preproc; generate a **real** 32-byte table using pinned `huderlem/poryscript@c3248116` CLI, original map macros and preproc; load a test-only relocated copy of that table into a source-built FireRed ROM in unchanged `mgba-emu/mgba@fd9dc5c2`. No replacement parser, compiler, emulator, ROM mapper or runtime engine.

Use the original linked `MapHeaderGetScriptTable` and `gMapHeader` symbols from the actual ELF. A test-only host controller writes the table pointer into the original EWRAM map header, starts the original-agbcc Thumb function directly, and single-steps with a 500-instruction limit. Valid tags 3 and 2 and unknown tag 99 are compared to the Poryscript-generated table's exact relocated pointer/sentinel representation. A separate malformed synthetic fixture overwrites the outer sentinel and following ROM padding with nonzero bytes; it records return/budget behaviour without asserting universal bounds safety.

**Not stock gameplay reachability, not an unmodified stock ROM table placement, not an original game event dispatch, not physical hardware or Flash.** The table's relocation into spare ROM is test-only. ROM/ELF are not uploaded; only source identity, hashes and text evidence.

## Reviewer obligations

Confirm the test-only direct CPU entry and Thumb pipeline setup against original mGBA, inspect linked original-agbcc disassembly and source blob `src/script.c` `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`, verify `gMapHeader.mapScripts` offset 8 from pinned `include/global.fieldmap.h`, compare generated table bytes with the previously green GNU ARM witness, and independently reproduce native return PCs/values. A bounded malformed run is **not** proof of safe termination. Check stock map-header and gameplay callsite reachability separately. FireRed code/assets, Poryscript and mGBA license notices remain distinct; no upstream changes.

Partial-file review only. All Phase 1 gates FAIL_INCOMPLETE.

## Extended malformed-table native experiment (pending exact-head CI)

The previous four-case native reader workflow passed on head `76a2eb4406b4dc9c7bc2ff995beaa47af3834e35` (push #40790130213, PR #40790136494). That execution was **original-agbcc ARM in pinned mGBA with synthetic direct entry**, not stock gameplay. This extension deliberately keeps the original Poryscript-generated first two five-byte records but overwrites its byte-10 outer terminator and remaining test-only ROM padding with `0x7f`. The unchanged original reader is asked for absent tag 99:

- Case 1: no terminator within the bounded 500-step window; require exhaustion without a return, **not** an assertion about infinite loops or memory safety.
- Case 2: insert a synthetic zero terminator at offset 35, **beyond the original 32-byte generated table**; require a native NULL return.
- Case 3: insert a synthetic zero terminator at offset 105, likewise outside the generated table; require a native NULL return after more steps than offset 35.
- Retain the original three valid cases (tags 3, 2, 99). The verifier now requires six cases and rejects additional malformed-case and result mutations.

This directly tests whether the original reader traverses beyond the generated table's extent, rather than extrapolating from host guard pages or from a 500-step bounded non-return alone. The sentinel placements are **synthetic padding**, not natural FireRed map data, and this is not proof of an exploitable fault or physical hardware outcome. Reuse the original agbcc ROM, original Poryscript CLI, GNU ARM/preproc and original mGBA core without upstream changes. Source files `src/script.c` and the mGBA memory reader remain partial-review records; independent complete-file approval is zero.

**Status: new exact-head CI pending.** Do not treat this extension as executed until its push and PR workflows succeed and their evidence is reconciled. Gate `FAIL_INCOMPLETE`.

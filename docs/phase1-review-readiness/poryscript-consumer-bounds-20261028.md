# Phase 1 — Poryscript emitted map table / FireRed consumer bounds (2026-10-28)

**Status: pending exact-head CI / FAIL_INCOMPLETE. Independent approvals: 0.**

## Distinct semantic boundary

The previously verified actual pinned Poryscript CLI → FireRed native preprocessor → GNU ARM assembler/linker witness established two five-byte outer map-script entries, a one-byte outer sentinel, two eight-byte conditional entries, a two-byte conditional sentinel, and four `R_ARM_ABS32` relocations. It did **not** establish what FireRed does when linked map-script bytes are malformed.

Pinned FireRed `src/script.c` blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc` implements `MapHeaderGetScriptTable`: it reads one tag, returns on a zero sentinel, otherwise advances **5 bytes** per record and resolves the matching pointer using `T2_READ_PTR`. `MapHeaderCheckScriptTable` reads a **16-bit** variable index, returns at zero, then reads another 16-bit index and a **32-bit** pointer, advancing **8 bytes** for each unmatched conditional entry. Neither function accepts a table length. Consequently the source does not establish bounds-safe handling of missing terminators or invalid pointers.

The new host-only `phase1_poryscript_consumer_bounds.py` independently decodes the *actual linked* section bytes with these source-pinned widths, requires all expected records and both terminators, checks pointer destinations against the fixture section and rejects nine deliberate malformed-data variants: missing/altered sentinels, early conditional termination, out-of-range and incorrect pointers, and truncated outer/conditional/script bytes. It is called after the existing exact-CLI compiled witness and its seven assembly mutations. **This host validator must never be described as native FireRed malformed-table rejection.** It only prevents malformed or mislinked fixture evidence from being marked as a successful producer/consumer ABI witness.

## Source and build identities

Poryscript `c32481161c767b25a3425fa9f1f8729927ff3d55`; FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Source blob checks remain enforced by `verify_poryscript_actual_cli_arm_table.py`. This extension does not alter the pinned upstream producer, emitted assembly, macro bodies, assembler or linker.

## Open reviewer questions

- What native FireRed runtime behavior follows a missing outer or conditional terminator, and can a controlled emulator test bound the fault without claiming universal memory safety?
- Are pointer relocation targets valid for a full stock ROM link, not merely this synthetic `.rodata` section?
- Does any map editor or Poryscript input mode emit alternative table widths, tags or sentinel forms?
- Which full-file dependencies require complete independent semantic dispositions?

No complete-file approvals, XGBA-expanded-ROM compatibility or Phase 2 implementation is claimed.


## Pinned FireRed C reader function execution on host (2026-10-28; pending CI)

A distinct test extracts the **exact complete C function bodies** `MapHeaderGetScriptTable` and `MapHeaderCheckScriptTable` from pinned `pret/pokefirered@ce6406d8.../src/script.c` (Git blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`), without rewriting their instructions. A test-only host C harness supplies `gMapHeader`, `VarGet`, `T1_READ_16` and a 32-bit ROM-address-to-host-pointer translator for the previously linked 32-byte Poryscript map-table fixture. The two actual source-extracted FireRed reader bodies are compiled by host `cc` and exercised in nine cases: null map-script header; transition and frame-table pointer lookup; unknown tag reaching the outer sentinel; unmatched conditional values reaching the inner sentinel; first and second conditional matches returning distinct script targets; early outer sentinel; and early conditional sentinel. Six source-extraction mutations and four output-evidence mutations are fail-closed.

**Scope:** this is executable pinned FireRed C reader semantics with host shims, **not** original-agbcc compiled ROM or mGBA execution. The host pointer translator validates fixture pointer ranges for test safety; the original FireRed reader does **not** implement that bound. Deliberately unterminated/out-of-bounds tables are not executed in this test, and native malformed-table memory safety remains unproven. The prior GNU ARM table/relocation witness and nine host bounded-decoder negatives remain separate evidence. No new semantic approval or Phase 2 implementation is claimed. Reviewer follow-up: instrument compiled ARM reader against valid linked ROM map table, then bounded emulator malformed-data experiments with explicit memory guard and no universal safety inference.

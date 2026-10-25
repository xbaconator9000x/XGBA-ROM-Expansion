# Phase 1 — script opcode and compiled linker-variant semantic checkpoint (26 October 2026)

**Decision: FAIL_INCOMPLETE.** This source-grounded packet adds two previously uncurated files to the v5 queue: `pret/pokefirered/asm/macros/event.inc` and `pret/pokefirered/ld_script_modern.ld`. The original 29 curated records and 14,834 source records remain authoritative. There are **40 candidates awaiting review** and **zero independent approvals**.

## Findings and limits

1. The pinned FireRed Makefile chooses `tools/agbcc/bin/agbcc` when `MODERN=0` and the system ARM GCC `cc1` when `MODERN=1` (Makefile:80–93). It selects `ld_script.ld` for ordinary non-modern builds, `ld_script_rev10.ld` for revision 10, and `ld_script_modern.ld` for modern builds (Makefile:370–382). The revision-10 script is **not** covered by this packet.
2. Both examined original and modern linker scripts reserve a 32 MiB ROM region at 0x08000000 (both scripts:4–9), but the modern script uses wildcard section aggregation for text, script data and rodata (ld_script_modern.ld:40–66). A common memory limit is **not proof of identical symbol/section/relocation placement** across compiler variants.
3. The pinned Makefile's objcopy rule pads to 0x09000000 (Makefile:393–395), producing a 16 MiB native image under the normal 0x08000000 ROM base. This is a build-output boundary, not an XGBA storage or executable address expansion.
4. Poryscript chunk output emits `goto`, `end`, and `return` (emitter/chunk.go:67–92). FireRed's event assembler encodes `goto` as opcode 0x05 plus a four-byte destination, `call` as 0x04 plus a four-byte destination, and distinguishes end (0x02) from return (0x03) (asm/macros/event.inc:11–45). FireRed's ScrCmd_goto/call and conditional variants consume direct 32-bit addresses (src/scrcmd.c:133–168).
5. `loadword` writes a four-byte operand and `setvar` two halfwords (event.inc:103–108,152–157), matching the native bytewise little-endian `ScriptReadWord` and `ScrCmd_setvar` consumption (src/script.c:188–195; src/scrcmd.c:336–340). The runtime indexes `cmdTable[cmdCode]` before comparing the resulting pointer with `cmdTableEnd` (src/script.c:124–134); validation of arbitrary script bytes and pointer targets remains unresolved.

## Reproduction

`semantic-snapshots/curated/script_variant_abi_additive_2026-10-26.json` pins **seven exact Git blobs, 20 bounded source checks and 12 typed dependencies**. `tools/phase1_script_variant_review.py` rechecks exact pinned revisions and Git blob SHA-1, executes v5 source verification and queue reconciliation, enforces ten negative controls, and writes deterministic SHA-256-tracked v6 evidence/queue artifacts. The existing cross-repository CI workflow invokes this verification on pinned upstream checkouts.

**Still required:** independent whole-file semantic dispositions; compiled original/modern/revision-10 relocation, section and symbol comparison; actual Poryscript→assembler→ROM round-trip checks; runtime opcode/pointer validity; and emulator/editor compatibility certification. This checkpoint neither approves a file nor implements Phase 2.

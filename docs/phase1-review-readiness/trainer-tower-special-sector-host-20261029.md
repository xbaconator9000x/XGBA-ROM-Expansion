# Phase 1 — actual pinned FireRed special-sector wrapper C execution (2026-10-29)

**Status: new experiment, awaiting exact-head CI. Phase 1 FAIL_INCOMPLETE; 0/14,834 independent approvals.**

## Reuse decision and immutable source owners

Reuse the original FireRed save/Flash wrappers and original agbcc/GNU ARM/mGBA for subsequent native work. Do not create an XGBA-specific Flash driver. This new *host-only* experiment extracts the **unchanged complete bodies** of the two pinned \`src/save.c\` functions \`TryReadSpecialSaveSector\` and \`TryWriteSpecialSaveSector\`, then compiles them with a **test-only in-memory fake Flash backend**. It does not replace either original function or patch upstream.

- \`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982\`
- \`src/save.c\` Git blob \`36b960f375c92711aa49b99bdfe9c6b3a99d6b1c\`
- \`include/save.h\` Git blob \`87fb9b615b434b58823d15688056695acda9feab\`

The \`include/save.h\` ABI defines 4,096-byte sectors, 3,968-byte data, 128-byte footer, and counter at byte 4,092. The special-sector wrappers copy **4,092 bytes** between physical offsets 4–4,095 and the caller, including the last four bytes nominally occupied by the ordinary-save counter. The first four bytes are the special-sector sentinel. This source layout was previously modeled; **this experiment newly executes the original pinned wrapper functions**, not the earlier synthetic model or the separate \`cereader_tool.c\` host test.

## Required executed controls

1. Positive physical sector 30 write/read, sentinel, exact 4,092-byte payload and final four bytes.
2. Invalid sentinel read rejects without touching destination.
3. Changing the final physical byte with a valid sentinel is accepted by this wrapper (no wrapper-level checksum).
4. Out-of-range sector 29 rejects both read and write without backend I/O.
5. Simulated \`ProgramFlashSectorAndVerify\` failure for sector 31 propagates \`SAVE_STATUS_ERROR\`.
6. Two sequential writes with a simulated failed second update leave new sector 30 and old sector 31, showing the **lack of a wrapper-level two-sector transaction** in the host fixture.

The checker rejects nine source mutations and eight output mutations, pins exact Git source identities, and emits text-only evidence. No ROM, source assets, ELF or Flash dump is uploaded. A CI failure must remain a failure until corrected and rerun at the exact head.

## Limits, interop and reviewer questions

The backend is simulated; this is **not mGBA, original-agbcc ARM execution, native physical Flash timing, an interrupted real write, or proof of normal stock gameplay reachability**. Stock FireRed's separately verified \`ReadTrainerTowerAndValidate\` stub returns FALSE, so do not portray a torn sector as an observed player-facing vulnerability. The \`src/cereader_tool.c\` paired loader/writer host evidence and linked stub evidence remain separate and are not rerun here.

Follow-up: run the original agbcc-compiled save.c special-sector functions in pinned mGBA with physical sector 30/31 backing, verify Flash error/retry semantics and actual reachability, and preserve the original two-sector representation. Verify upstream component licensing separately; an absent root license is not permission to redistribute code or copyrighted ROM assets. This packet is partial-function evidence, not a complete-file disposition, independent approval or Phase 2 implementation.

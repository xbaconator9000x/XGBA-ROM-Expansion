# Phase 1 — source-backed savedata boundary witness (proposed, no approval)

**Scope:** Follow-on to the complete 800-line mGBA savedata review packet. This is a source-level conditional witness, not native mGBA execution, an actual GBA save-corruption report, an independent semantic approval, or Phase 2 work.

Pinned identities: **mgba-emu/mgba at fd9dc5c2cbf234365068855851107e762fc6211b**; source **src/gba/savedata.c**, Git blob **fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb**; and constants **include/mgba/internal/gba/memory.h**, Git blob **0aad912613e726560d06bbdbf6061986e69e5842**. The constants header defines 64-KiB/128-KiB flash and 512-byte/8-KiB EEPROM boundaries (lines 72–75).

The verifier imports the existing pinned whole-file checker, independently checks the memory-header Git blob and tree identity, extracts **the actual two complete pinned C function bodies** (GBASavedataInitFlash at 267–297 and GBASavedataInitEEPROM at 299–325), and compiles them into a standalone C harness with a deliberately specified mock VFile backend. Three source mutations must be rejected. The mock extends files with zero bytes; it does not claim all real VFile implementations behave identically.

## Six observed boundary cases under the explicit mock

| Initial state | Requested type | Observed initialized bytes | Conditional risk |
|---|---|---|---|
| 64-KiB existing flash filled with 0xA5 | 128-KiB Flash1M | First 64 KiB remains 0xA5; grown 64 KiB remains mock zero | Flash growth branch at 285–294 does not explicitly fill new bank with 0xFF |
| Empty file | 128-KiB Flash1M | All 128 KiB 0xFF | Positive control; full erase initialization |
| 512-byte existing EEPROM filled with 0xA5 | 8-KiB EEPROM | First 512 bytes 0xA5; grown 7,680 bytes remain mock zero | EEPROM growth branch at 316–323 does not explicitly fill upper range |
| Empty file | 8-KiB EEPROM | First 512 bytes 0xFF; remaining 7,680 mock zero | **Additional source finding:** even empty 8-KiB EEPROM is only explicitly initialized for 512 bytes |
| No VFile; zero-initialized anonymous mock | 8-KiB EEPROM | First 512 bytes 0xFF; remaining 7,680 zero | Anonymous allocation follows same 512-byte fill limit |
| Empty file | 512-byte EEPROM | All 512 bytes 0xFF | Positive control; small EEPROM correctly initialized |

The **new empty/anonymous 8-KiB EEPROM observation** strengthens the prior R2 finding beyond existing-file growth. It remains conditional on actual allocator/backend semantics and reachability. The separate _ensureEeprom promotion path (485–505) fills the upper EEPROM range, so reviewers must distinguish promotion from direct 8-KiB initialization. The flash _flashSwitchBank path (759–778) likewise explicitly fills the new bank on one promotion route.

## Outstanding independent-review obligations

1. Test real pinned VFile backends and anonymous-memory mapping, including mapping/truncation failure and negative VFile.size results. The mock intentionally does not exercise these error paths.
2. Establish real caller reachability of direct 8-KiB initialization versus _ensureEeprom promotion; trace type forcing, savestate restore, reset, file replacement and allocation lifetime.
3. Compare persisted bytes, hardware erase semantics, editor/tool interoperability and regressions across 512-byte/8-KiB EEPROM and 64-/128-KiB flash save files.
4. Obtain genuine independent review before accepting any disposition. No source files in mGBA were changed.

**Accounting unchanged:** inventory 14,834/14,834 (100%); registered substantively prepared 113/14,834 (0.7618%); independently approved 0/14,834 (0.0000%); historical v1 machine triage 14,721/14,834 (99.2382%). This is additional evidence for an **unregistered** packet, not another prepared or approved file. Authoritative gate **FAIL_INCOMPLETE**.

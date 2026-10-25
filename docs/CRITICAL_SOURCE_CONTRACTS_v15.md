# New Phase 1 source-anchored contracts — v1.5

**Status:** targeted semantic findings with pinned blob anchors. No XGBA patch, ROM build, emulator build, or runtime proof. These are design constraints, not a declaration that their owning files are fully reviewed.

## XC15-SAVESTATE-ROMCRC-MISMATCH-WARNING — P0
**Upstream:** `mgba-emu/mgba` at `fd9dc5c2cbf234365068855851107e762fc6211b`; `src/gba/serialize.c` blob `a307a51e751f412c64a7378323c56758304ebe85`, lines 118–145.

**Observed:** the GBA deserializer validates game ID and title and treats a mismatch as an error; a ROM CRC mismatch logs a warning without setting the same fatal error. An XGBA extension package therefore **cannot use the legacy CRC warning alone as a security/identity guarantee**.

**Compatibility requirement:** implement a separately versioned extension identity (base-ROM identity + external resource manifest hash), validate it **before** restoring external memory state, while preserving native mGBA legacy save-state behavior for unextended ROMs.

**Unrun tests:** legacy CRC-warning fixture; mismatched external package rejected for extended states; unchanged original game savestate compatibility.

## XC15-SAVESTATE-ROM-REMAP-BEFORE-CPU-PIPELINE — P0
**Upstream:** same file, lines 178–197.

**Observed:** `GBAUnlCartDeserialize(gba,state)` precedes `activeRegion=-1` and `setActiveRegion(..., PC)`. Source comment explicitly requires ROM remapping before pipeline reset.

**Compatibility requirement:** restore any opt-in XGBA memory-window identifiers and validated backing bytes before the CPU's active region/prefetch state is reconstructed. External-file loss should cause a controlled incompatibility error, not execute bytes from a wrong bank.

**Unrun tests:** restore while executing a banked ROM window; rewind after remap; missing backing-file rejection; preservation of native e-Reader/Matrix/multicart state.

## XC15-FR-SCRIPT-BYTECODE-RAW-POINTER — P0
**Upstream:** `pret/pokefirered` at `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `src/script.c` blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`, lines 115–129 and 165–195.

**Observed:** `RunScriptCommand` dereferences and increments `ctx->scriptPtr`; `ScriptJump` and `ScriptCall` assign raw pointers; `ScriptReadWord` reads four bytes via that advancing pointer. Source-to-assembler edits alone cannot virtualize these active bytecode reads.

**Compatibility requirement:** define tagged external handles plus a runtime resolution/banked-copy strategy that preserves legacy 32-bit script arguments, call stack, and bytecode execution. Never interpret arbitrary vanilla script addresses as extension handles.

**Unrun tests:** normal vanilla jump/call/return and four-byte argument decoding; tag negotiation; cross-bank script call/return; script context persistence and pointer invalidation.

## XC15-FR-SAVEBLOCK-ASLR-AND-ENCRYPTION — P1
**Upstream:** `pret/pokefirered` same commit; `src/load_save.c` blob `8b723dd044c6024b3671bb890b25b56a53f99ec5`, lines 66–84 and 87–131.

**Observed:** `SetSaveBlocksPointers` randomly offsets save-block pointers, updates bag pointers and adjusts quest-log offsets. `MoveSaveBlocks_ResetHeap` relocates structures and reapplies encryption with a new key. This entire file received no lexical hits in the first census; its initial automated P3 rating was therefore a **false negative**.

**Compatibility requirement:** never persist host pointers or offset-dependent XGBA handles inside legacy saves. External extension state needs a versioned, portable keyed representation and lifecycle hooks that tolerate save-block pointer movement and encryption changes.

**Unrun tests:** save-block randomization; save/load cycle; encryption-key rotation; original save compatibility; corrupted external-state rejection.

## Mapping gate

Four new source-anchored contract findings, not four approved whole-file dispositions. Phase 1 semantic mapping remains open. The source-hash-verified review queue gives this file group P0/P1 priority after the v1.5 priority-floor correction.

All source locations: [mGBA serialize.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c) · [FireRed script.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c) · [FireRed load_save.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/load_save.c).

# Phase 1 — FireRed save-block relocation and encryption: complete-file analyst review packet

**Review status: proposed whole-file analyst preparation; NOT registered or independently approved.** Source identity: pret/pokefirered at immutable commit ce6406d8c2eaf46d543c8a2606de0c3cb1951982, src/load_save.c, Git blob 8b723dd044c6024b3671bb890b25b56a53f99ec5. Source link: https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/load_save.c

## Whole-file coverage and inventory

Read all 298 physical source lines (with a trailing newline), 13 direct includes, 21 function definitions, all EWRAM/IWRAM declarations, one REVISION conditional and all save data fields in this translation unit. The accompanying fail-closed verifier pins the source and eight dependency blobs, enumerates all 21 definitions, and rejects source/anchor mutations. This is source-level semantic preparation, not compiled ABI equivalence or runtime certification.

| Source line | Function | Full-file semantic responsibility |
| --- | --- | --- |
| 46 | CheckForFlashMemory | IdentifyFlash status and flash timer activation |
| 59 | ClearSav2 | Zero SaveBlock2 plus 128-byte relocation padding by one CpuFill16 span |
| 64 | ClearSav1 | Zero SaveBlock1 plus 128-byte relocation padding by one CpuFill16 span |
| 69 | SetSaveBlocksPointers | Random 4-byte-aligned offset 0..124; relocate three block pointers; refresh bag pockets and quest-log pointers |
| 85 | MoveSaveBlocks_ResetHeap | Suspend callbacks, copy three blocks through heap, relocate, restore, reset heap and rekey |
| 134 | UseContinueGameWarp | Read continue-warp bit from SaveBlock2 |
| 139 | ClearContinueGameWarpStatus | Clear continue-warp bit |
| 144 | SetContinueGameWarpStatus | Set continue-warp bit |
| 149 | SetContinueGameWarpStatusToDynamicWarp | Set dynamic warp 0 and continue-warp bit |
| 155 | ClearContinueGameWarpStatus2 | Second clear entry point, same bit |
| 160 | SavePlayerParty | Copy party count and all PARTY_SIZE members into SaveBlock1 |
| 170 | LoadPlayerParty | Copy count and all PARTY_SIZE members from SaveBlock1 |
| 180 | SaveObjectEvents | Copy all OBJECT_EVENTS_COUNT object events into SaveBlock1 |
| 188 | LoadObjectEvents | Restore all OBJECT_EVENTS_COUNT object events from SaveBlock1 |
| 196 | SaveSerializedGame | Dispatch party and object-event save copies |
| 202 | LoadSerializedGame | Dispatch party and object-event restore copies |
| 208 | LoadPlayerBag | Stage five bag pockets plus mail; remember SaveBlock2 encryption key |
| 239 | SavePlayerBag | Restore five pockets and mail; convert item quantities from staged key to current key |
| 274 | ApplyNewEncryptionKeyToHword | XOR old and new key into 16-bit encrypted value |
| 280 | ApplyNewEncryptionKeyToWord | XOR old and new key into 32-bit encrypted value |
| 286 | ApplyNewEncryptionKeyToAllEncryptedData | Rekey Trainer Tower times, game stats, bag, berry powder, money and coins |

Data declarations L16–41: LoadedSaveData contains five bag pocket arrays and mail; each of the three EWRAM save structures is followed in source by 128 bytes of relocation padding; loaded bag staging and last key are global; flash-present flag and three movable pointers are COMMON_DATA. REVISION >= 0xA alone invokes svc_SetSaveBlock2 at L129–131. No other conditional compilation occurs in this file.

## Verified producer/consumer relationships (source-level)

- src/item.c (blob 0587adf7db9feea06275fbe33dc1756adf23759a), L41–70: ApplyNewEncryptionKeyToBagItems traverses each configured bag pocket and uses the halfword XOR helper; SetBagPocketsPointers rebinds all five pockets to gSaveBlock1Ptr after relocation. Thus bag pointer refresh is a required part of the relocation contract.
- src/quest_log.c (blob 0a2f76f2c4019fa0938d5044da73fcea1b2b069c), L176–195: QL_AddASLROffset derives pointer delta from old and new SaveBlock1 addresses, adjusts defeated-wild-mon record and conditionally recording/playback pointers. This creates an indirect relocation dependency beyond the three save-block pointers.
- src/reset_save_heap.c (blob 745270dc7415b869c302daaa7b9c2b2e5b2865f1), L9–27: ReloadSave resets EWRAM, calls SetSaveBlocksPointers before loading saved data and later initializes heap. Relocation must therefore tolerate startup/reset states as well as live migration.
- src/overworld.c (blob 339014da46ae8543143edc99ab72bf7496203a0d), L394 onward: rekeys game stats; src/berry_powder.c (blob d5090e0ddcd47f11afb018e047b23c97b5a89bd8), L27 onward: rekeys berry powder. Both are reached by ApplyNewEncryptionKeyToAllEncryptedData.
- include/malloc.h (blob bf89badc53a4cad8ba5615900d5014cc34f76fea) fixes HEAP_SIZE = 0x1C000. ld_script_modern.ld (blob e930243522bd21da40cc1a05de9a42b8ad409b46) places gHeap at the start of the EWRAM region and reserves 0x1C000. The heap backup must fit all three structures, with no overlapping live consumers.
- include/load_save.h (blob 95de991a82204927d209a39e426f78633af0c04c) exposes relocation, bag and encryption interfaces. It contains a duplicate MoveSaveBlocks_ResetHeap prototype, which the checker explicitly recognizes; its declarations alone do not prove callers, variant compatibility or execution reachability.

## Source-grounded risks and proof obligations

1. **Padding/contiguity (P0 ABI):** ClearSav1 and ClearSav2 each clear sizeof(struct) + 128 bytes from the struct address, crossing C object boundaries. Source declaration order suggests adjacent padding, but does not prove compiled EWRAM order/alignment for every compiler/linker variant. Validate symbol addresses, sizes, 4-byte alignment, adjacent buffers and 128-byte headroom in both original and modern link outputs.
2. **Heap alias and interrupt lifetime (P0):** MoveSaveBlocks_ResetHeap uses gHeap as temporary storage for three entire structs, invalidating pre-existing heap contents. It nulls vblankCallback, hblankCallback and vblankCounter1, but restores only the two callbacks. Establish caller quiescence, heap capacity, live pointer invalidation, vblankCounter1 intended lifetime and failure/reentry paths before changing save layout.
3. **Quest-log pointer delta (P0):** QL_AddASLROffset subtracts void pointers, including possible oldSave == NULL after reset. This is a compiler-extension and portability-sensitive expression, not portable ISO C pointer arithmetic. Test pinned compiler behaviour and pointer consumers; no runtime corruption is established by this source alone.
4. **Encryption consistency (P0):** The live migration generates a new key and calls all listed rekey consumers before assigning gSaveBlock2Ptr->encryptionKey. The bag staging path temporarily reinstates gLastEncryptionKey before converting quantities. Audit all encrypted fields, key initialization, staged bag lifetime, save/load order and variant-specific added fields; a new save field would not be automatically rekeyed.
5. **Persisted counts (P1):** LoadPlayerParty copies a stored count without a local bound check, while copying exactly PARTY_SIZE slots. Prove upstream save validation and downstream count assumptions before claiming malformed-save safety.
6. **Revision-specific hook (P1):** svc_SetSaveBlock2 executes only for REVISION >= 0xA. Verify ABI and hook availability for both revision families.
7. **No overclaim:** No compiled layout offsets, ARM/agbcc equivalence, GBA/mGBA execution, corrupted-save exploit, or independent review are demonstrated here.

## Reviewer acceptance and gate

Run pinned-source verifier and its negative controls. Obtain compiled EWRAM symbol/struct-size witness for original and modern linkers, exercise 0/4/124 offset and heap/rekey failure paths, trace callers and indirect consumers, then obtain an independent reviewer decision bound to immutable blobs and evidence. Do not register this as a substantive whole-file candidate until reviewer-readiness evidence and register deduplication are reconciled. Independently approved 0/14,834; baseline registered prepared 113/14,834; authoritative gate FAIL_INCOMPLETE. No Phase 2 work.

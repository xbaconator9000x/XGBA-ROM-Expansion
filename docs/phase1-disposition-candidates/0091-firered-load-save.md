# Analyst whole-file candidate 0091 — Save-block memory relocation and encryption API

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/load_save.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/load_save.h); exact pinned Git blob SHA-1 `95de991a82204927d209a39e426f78633af0c04c`. Inspected the **entire 38-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The header exports flash-present state and SaveBlock1/SaveBlock2/PokemonStorage objects, along with clear, serialize, bag/party, heap reset, encryption-key migration and continue-warp APIs. MoveSaveBlocks_ResetHeap is declared twice identically.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_LOAD_SAVE_H`
- L2: `#define GUARD_LOAD_SAVE_H`
- L4: `#include "global.h"`
- L6: `extern bool32 gFlashMemoryPresent;`
- L7: `extern struct SaveBlock1 gSaveBlock1;`
- L8: `extern struct SaveBlock2 gSaveBlock2;`
- L9: `extern struct PokemonStorage gPokemonStorage;`
- L11: `void ClearSav2(void);`
- L12: `void ClearSav1(void);`
- L13: `void CheckForFlashMemory(void);`
- L14: `void MoveSaveBlocks_ResetHeap(void);`
- L15: `bool32 GetSecretBase2Field_9(void);`
- L16: `void ClearSecretBase2Field_9(void);`
- L17: `void SetSecretBase2Field_9(void);`
- L18: `void SetSecretBase2Field_9_AndHideBG(void);`
- L19: `void ClearSecretBase2Field_9_2(void);`
- L20: `void SavePlayerParty(void);`
- L21: `void LoadPlayerParty(void);`
- L22: `void SaveSerializedGame(void);`
- L23: `void LoadSerializedGame(void);`
- L24: `void LoadPlayerBag(void);`
- L25: `void SavePlayerBag(void);`
- L26: `void SetSaveBlocksPointers(void);`
- L27: `void MoveSaveBlocks_ResetHeap(void);`
- L28: `void ApplyNewEncryptionKeyToAllEncryptedData(u32 encryptionKey);`
- L29: `void ApplyNewEncryptionKeyToBagItems(u32 encryptionKey);`
- L30: `void ApplyNewEncryptionKeyToWord(u32 * word, u32 encryptionKey);`
- L31: `void ApplyNewEncryptionKeyToHword(u16 * hword, u32 encryptionKey);`
- L32: `void ClearContinueGameWarpStatus2(void);`
- L33: `void SetContinueGameWarpStatusToDynamicWarp(void);`
- L34: `void SetContinueGameWarpStatus(void);`
- L35: `bool32 UseContinueGameWarp(void);`
- L36: `void ClearContinueGameWarpStatus();`
- L38: `#endif // GUARD_LOAD_SAVE_H`

## Dependencies, expansion relevance and independent review

Critical save pointer lifetime: trace EWRAM/IWRAM relocation, key updates and pointer invalidation, serializer sizes, party/bag storage, dynamic warp and reset timing. Repeated prototype is not itself a linker conflict. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

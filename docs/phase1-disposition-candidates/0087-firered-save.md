# Analyst whole-file candidate 0087 — Flash sector layout and save transaction ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/save.h); exact pinned Git blob SHA-1 `87fb9b615b434b58823d15688056695acda9feab`. Inspected the **entire 107-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals, macros and prototypes. This is not independent approval.

## Whole-file semantic disposition (source-level)

The file fixes each 4 KiB flash sector to 3968 data bytes plus 128 footer bytes, with a 12-byte used footer containing ID/checksum/signature/counter; it defines two 14-sector save slots plus Hall of Fame and Trainer Tower sectors (32 total). SaveSectorLocation holds a pointer and u16 length, SaveSector fixes 4096-byte layout, and APIs cover sector writes, special sectors, link saves and load status.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_SAVE_H`
- L2: `#define GUARD_SAVE_H`
- L4: `#include "global.h"`
- L8: `#define SECTOR_DATA_SIZE 3968`
- L9: `#define SECTOR_FOOTER_SIZE 128`
- L10: `#define SECTOR_SIZE (SECTOR_DATA_SIZE + SECTOR_FOOTER_SIZE)`
- L12: `#define NUM_SAVE_SLOTS 2`
- L15: `#define SECTOR_SIGNATURE 0x08012025`
- L17: `#define SPECIAL_SECTOR_SENTINEL 0xB39D`
- L19: `#define SECTOR_ID_SAVEBLOCK2          0`
- L20: `#define SECTOR_ID_SAVEBLOCK1_START    1`
- L21: `#define SECTOR_ID_SAVEBLOCK1_END      4`
- L22: `#define SECTOR_ID_PKMN_STORAGE_START  5`
- L23: `#define SECTOR_ID_PKMN_STORAGE_END   13`
- L24: `#define NUM_SECTORS_PER_SLOT         14`
- L26: `#define SECTOR_ID_HOF_1              28`
- L27: `#define SECTOR_ID_HOF_2              29`
- L28: `#define SECTOR_ID_TRAINER_TOWER_1    30`
- L29: `#define SECTOR_ID_TRAINER_TOWER_2    31`
- L30: `#define SECTORS_COUNT                32`
- L32: `#define NUM_HOF_SECTORS 2`
- L34: `#define SAVE_STATUS_EMPTY    0`
- L35: `#define SAVE_STATUS_OK       1`
- L36: `#define SAVE_STATUS_INVALID  2`
- L37: `#define SAVE_STATUS_NO_FLASH 4`
- L38: `#define SAVE_STATUS_ERROR    0xFF`
- L43: `#define FULL_SAVE_SLOT 0xFFFF`
- L45: `enum`
- L46: `{`
- L47: `SAVE_NORMAL,`
- L48: `SAVE_LINK,`
- L49: `SAVE_EREADER,`
- L50: `SAVE_HALL_OF_FAME,`
- L51: `SAVE_OVERWRITE_DIFFERENT_FILE,`
- L52: `SAVE_HALL_OF_FAME_ERASE_BEFORE, // unused`
- L53: `};`
- L57: `struct SaveSectorLocation`
- L58: `{`
- L59: `u8 *data;`
- L60: `u16 size;`
- L61: `};`
- L63: `struct SaveSector`
- L64: `{`
- L65: `u8 data[SECTOR_DATA_SIZE];`
- L66: `u8 unused[SECTOR_FOOTER_SIZE - 12]; // Unused portion of the footer`
- L67: `u16 id;`
- L68: `u16 checksum;`
- L69: `u32 signature;`
- L70: `u32 counter;`
- L71: `}; // size is SECTOR_SIZE (0x1000)`
- L73: `#define SECTOR_SIGNATURE_OFFSET offsetof(struct SaveSector, signature)`
- L74: `#define SECTOR_COUNTER_OFFSET   offsetof(struct SaveSector, counter)`
- L77: `enum`
- L78: `{`
- L79: `ENABLE,`
- L80: `DISABLE,`
- L81: `CHECK // unused`
- L82: `};`
- L84: `extern u32 gDamagedSaveSectors;`
- L85: `extern struct SaveSector *gSaveDataBufferPtr; // the pointer is in fast IWRAM but points to the slower EWRAM.`
- L86: `extern u16 gSaveFileStatus;`
- L87: `extern void (*gGameContinueCallback)(void);`
- L88: `extern u16 gSaveAttemptStatus;`
- L90: `extern struct SaveSector gSaveDataBuffer;`
- L92: `void ClearSaveData(void);`
- L93: `void Save_ResetSaveCounters(void);`
- L94: `u8 HandleSavingData(u8 saveType);`
- L95: `u8 TrySavingData(u8 saveType);`
- L96: `bool8 LinkFullSave_Init(void);`
- L97: `bool8 LinkFullSave_WriteSector(void);`
- L98: `bool8 LinkFullSave_ReplaceLastSector(void);`
- L99: `bool8 LinkFullSave_SetLastSectorSignature(void);`
- L100: `bool8 WriteSaveBlock2(void);`
- L101: `bool8 WriteSaveBlock1Sector(void);`
- L102: `u8 LoadGameSave(u8 saveType);`
- L103: `u32 TryReadSpecialSaveSector(u8 sector, u8 *dst);`
- L104: `u32 TryWriteSpecialSaveSector(u8 sector, u8 *src);`
- L105: `void Task_LinkFullSave(u8 taskId);`
- L107: `#endif // GUARD_SAVE_H`

## Dependencies, expansion relevance and independent review

Critical fixed-size persistence contract: validate sizeof/offsetof and checksum/counter/rotation behavior in compiled variants; prove sector ID and length bounds, power-loss atomicity, pointer relocation, mGBA flash emulation and editor save interoperability. This file is not an unlimited ROM/save architecture. The header alone does not establish every caller precondition, compiled/linker behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

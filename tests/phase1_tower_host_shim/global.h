#ifndef PHASE1_HOST_GLOBAL_H
#define PHASE1_HOST_GLOBAL_H
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdbool.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef u32 bool32;
#define TRUE 1
#define FALSE 0
#define MAX_TRAINER_TOWER_FLOORS 8
#define MAX_TRAINERS_PER_FLOOR 3
#define CHALLENGE_TYPE_KNOCKOUT 2
#define SECTOR_SIZE 4096
#define SECTOR_COUNTER_OFFSET 4092
#define SECTOR_ID_TRAINER_TOWER_1 30
#define SECTOR_ID_TRAINER_TOWER_2 31
#define STATIC_ASSERT(x,name) _Static_assert((x),#name)
#define ABSPATH(x) x
#define AGB_ASSERT_EX(exp,file,line) ((void)0);
struct TrainerTowerTrainer { u8 bytes[328]; };
struct TrainerTowerFloor { u8 id, floorIdx, challengeType, prize; struct TrainerTowerTrainer trainers[3]; u32 checksum; };
struct EReaderTrainerTowerSet { u8 numFloors, id; u16 dummy; u32 checksum; struct TrainerTowerFloor floors[8]; };
struct HostSaveBlock1 { struct { u8 unk9; } trainerTower[1]; };
extern struct HostSaveBlock1 *gSaveBlock1Ptr;
void *AllocZeroed(size_t);
void Free(void *);
u32 CalcByteArraySum(const u8 *, u32);
bool32 TryWriteSpecialSaveSector(u16, u8 *);
bool32 TryReadSpecialSaveSector(u16, void *);
bool32 ValidateTrainerTowerData(struct EReaderTrainerTowerSet *);
bool32 CEReaderTool_SaveTrainerTower(struct EReaderTrainerTowerSet *);
bool32 CEReaderTool_LoadTrainerTower(struct EReaderTrainerTowerSet *);
bool32 ReadTrainerTowerAndValidate(void);
_Static_assert(sizeof(struct TrainerTowerTrainer)==328,"trainer layout");
_Static_assert(sizeof(struct TrainerTowerFloor)==992,"floor layout");
_Static_assert(sizeof(struct EReaderTrainerTowerSet)==7944,"set layout");
#endif

/* R15 pinned FireRed ordinary Flash save and real cold-boot continuation.
 * Called from patched native FireRed paths, NOT host writes into game RAM.
 * Internal proof only; flash save contents must never be published.
 */
#include "save.h"

#define XGBA_R15_SAVE_MAGIC 0x52313550u
struct XgbaR15SaveProof {
    volatile u32 magic;
    volatile u32 boot_loaded;
    volatile u32 boot_continue;
    volatile u32 save_requests;
    volatile u32 save_result;
    volatile u32 saved_group;
    volatile u32 saved_num;
    volatile u32 saved_x;
    volatile u32 saved_y;
};
EWRAM_DATA volatile struct XgbaR15SaveProof gXgbaR15SaveProof = {0};

bool8 XgbaR15StartWithSavedGame(void)
{
    u8 status;
    /* This is the game's real Flash save loader, identical to the title
     * flow except that test-only boot skips the visual title menu. */
    SetSaveBlocksPointers();
    Save_ResetSaveCounters();
    status=LoadGameSave(SAVE_NORMAL);
    gXgbaR15SaveProof.magic=XGBA_R15_SAVE_MAGIC;
    gXgbaR15SaveProof.boot_loaded=status;
    gXgbaR15SaveProof.boot_continue=(status==SAVE_STATUS_OK);
    return status==SAVE_STATUS_OK;
}

static void XgbaR15TickSave(void)
{
    if(gMain.newKeys & SELECT_BUTTON) {
        u8 result;
        ++gXgbaR15SaveProof.save_requests;
        gXgbaR15SaveProof.saved_group=gSaveBlock1Ptr->location.mapGroup;
        gXgbaR15SaveProof.saved_num=gSaveBlock1Ptr->location.mapNum;
        gXgbaR15SaveProof.saved_x=gSaveBlock1Ptr->pos.x;
        gXgbaR15SaveProof.saved_y=gSaveBlock1Ptr->pos.y;
        /* The original menu's SaveDialogCB_DoSave uses this exact routine:
         * flash sector serialization, checksums and write verification are
         * performed by actual game code, not by the emulator harness. */
        result=TrySavingData(SAVE_NORMAL);
        gXgbaR15SaveProof.save_result=result;
    }
}

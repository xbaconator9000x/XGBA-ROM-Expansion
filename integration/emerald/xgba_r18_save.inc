/* R18: actual Emerald Flash saving and cold LoadGameSave/continue.
 *
 * Integrates with the R17 genuinely external map/secondary tileset. Unlike
 * FireRed, Emerald's save pointers are shifted by trainer-ID-derived offsets.
 * This test calls the original native code and preserves a real on-disk .sav,
 * never an mGBA save-state or a host-authored memory snapshot.
 */
#include "save.h"
#include "load_save.h"
#include "new_game.h"

#define XGBA_R18_MAGIC 0x52313845u
struct XgbaR18Proof {
    volatile u32 magic;
    volatile u32 boot_status;
    volatile u32 boot_continue;
    volatile u32 save_requests;
    volatile u32 save_result;
    volatile u32 saved_group;
    volatile u32 saved_num;
    volatile u32 saved_x;
    volatile u32 saved_y;
    volatile u32 base_offset;
    volatile u32 save_type;
#ifdef XGBA_R40_SCRIPT_TEST
    /* Append-only proof ABI: R18's first eleven words remain untouched. */
    volatile u32 r40_state;
    volatile u32 r40_fetches;
    volatile u32 r40_executions;
    volatile u32 r40_value;
    volatile u32 r40_flag;
    volatile u32 r40_errors;
#endif
};
EWRAM_DATA volatile struct XgbaR18Proof gXgbaR18Proof = {0};

/* Called ONLY after Emerald's real CheckForFlashMemory / InitHeap.
 * Original game-owned saved sector reading is retained unchanged. */
bool8 XgbaR18TryContinue(void)
{
    u16 offset;
    u8 result;
    Save_ResetSaveCounters();
    offset=GetSaveBlocksPointersBaseOffset();
    SetSaveBlocksPointers(offset);
    result=LoadGameSave(SAVE_NORMAL);
    gXgbaR18Proof.magic=XGBA_R18_MAGIC;
    gXgbaR18Proof.boot_status=result;
    gXgbaR18Proof.boot_continue=(result==SAVE_STATUS_OK);
    gXgbaR18Proof.base_offset=offset;
    return result==SAVE_STATUS_OK;
}

static void XgbaR18Tick(void)
{
    if(gMain.newKeys & SELECT_BUTTON) {
        u8 save_type;
        u8 result;
        ++gXgbaR18Proof.save_requests;
        gXgbaR18Proof.saved_group=gSaveBlock1Ptr->location.mapGroup;
        gXgbaR18Proof.saved_num=gSaveBlock1Ptr->location.mapNum;
        gXgbaR18Proof.saved_x=gSaveBlock1Ptr->pos.x;
        gXgbaR18Proof.saved_y=gSaveBlock1Ptr->pos.y;
        /* The normal Emerald Start→Save code uses an overwrite save when
         * the current player file differs, including first-time new games. */
        save_type=gDifferentSaveFile ? SAVE_OVERWRITE_DIFFERENT_FILE : SAVE_NORMAL;
        gXgbaR18Proof.save_type=save_type;
        result=TrySavingData(save_type);
        gXgbaR18Proof.save_result=result;
        if(result==SAVE_STATUS_OK)
            gDifferentSaveFile=FALSE;
    }
}

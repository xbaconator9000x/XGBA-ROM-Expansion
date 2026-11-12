/* R40: Execute a SHA-verified EXTERNAL nine-byte script using the original
 * Emerald script interpreter, NOT a host event-state replay.
 *
 * Single deliberately restricted fixture script: setvar (0x40FE, 0x5A39),
 * setflag (0x8F0), end. Bytecode is stored exclusively in the XGBA sidecar.
 * The emulator's provider SHA-verifies it before this GBA-side parser runs.
 * This is not a general-purpose safe interpreter for modified ROM hacks.
 */
#ifndef XGBA_R40_SCRIPT_TEST
#error R40 external event script may only be included for R40 native fixture
#endif
#ifndef XGBA_R18_SAVE_TEST
#error R40 persistence test requires genuine R18 Emerald Flash
#endif
#include "script.h"
#include "event_data.h"
#define XGBA_R40_VAR  0x40FEu
#define XGBA_R40_FLAG 0x08F0u
#define XGBA_R40_VALUE 0x5A39u
#define XGBA_R40_SCRIPT_BYTES 9u
#define XGBA_R40_SCRIPT_READY 1u
#define XGBA_R40_RESTORED 2u
#define XGBA_R40_SCRIPT_REJECTED 0xE40u
static EWRAM_DATA u8 sXgbaR40Script[XGBA_R40_SCRIPT_BYTES] = {0};
static EWRAM_DATA char sXgbaR40Id[24] = {0};

static void XgbaR40Tick(void)
{
    u32 copied;
    u32 i;
    const char name[]="emerald.r40.script";
    /* Original Emerald's EWRAM_DATA is not a guaranteed initialized ROM
     * data image. Match the working R17 path: copy the resource ID into
     * real guest EWRAM before making the MMIO request. */
    /* Native overworld is initialized, and original save blocks exist. */
    if(gXgbaR18Proof.r40_state != 0 || !gSaveBlock1Ptr ||
       !gMapHeader.mapLayout)
        return;
    if(gXgbaR18Proof.boot_continue) {
        /* Do NOT replay on Continue. This is the game's genuine Flash-loaded
         * event variable and flag, not a host-authored snapshot. */
        gXgbaR18Proof.r40_state=XGBA_R40_RESTORED;
        gXgbaR18Proof.r40_value=VarGet(XGBA_R40_VAR);
        gXgbaR18Proof.r40_flag=FlagGet(XGBA_R40_FLAG);
        return;
    }
    for(i=0;i<sizeof(name);++i)
        sXgbaR40Id[i]=name[i];
    ++gXgbaR18Proof.r40_fetches;
    copied=XgbaGuestFetch(sXgbaR40Id,sXgbaR40Script,
                          XGBA_R40_SCRIPT_BYTES);
    if(copied != XGBA_R40_SCRIPT_BYTES ||
       sXgbaR40Script[0]!=0x16u ||
       sXgbaR40Script[1]!=0xFEu ||
       sXgbaR40Script[2]!=0x40u ||
       sXgbaR40Script[3]!=0x39u ||
       sXgbaR40Script[4]!=0x5Au ||
       sXgbaR40Script[5]!=0x29u ||
       sXgbaR40Script[6]!=0xF0u ||
       sXgbaR40Script[7]!=0x08u ||
       sXgbaR40Script[8]!=0x02u) {
        gXgbaR18Proof.r40_state=XGBA_R40_SCRIPT_REJECTED;
        gXgbaR18Proof.r40_errors=1u;
        return;
    }
    /* Executes pret/pokeemerald's original gScriptCmdTable through
     * RunScriptImmediately, using real VarSet/FlagSet saveblock pointers.
     * This script contains no waiting commands and ends in `end`. */
    RunScriptImmediately(sXgbaR40Script);
    ++gXgbaR18Proof.r40_executions;
    gXgbaR18Proof.r40_value=VarGet(XGBA_R40_VAR);
    gXgbaR18Proof.r40_flag=FlagGet(XGBA_R40_FLAG);
    if(gXgbaR18Proof.r40_value != XGBA_R40_VALUE ||
       gXgbaR18Proof.r40_flag != TRUE) {
        gXgbaR18Proof.r40_state=XGBA_R40_SCRIPT_REJECTED;
        gXgbaR18Proof.r40_errors=2u;
        return;
    }
    gXgbaR18Proof.r40_state=XGBA_R40_SCRIPT_READY;
}

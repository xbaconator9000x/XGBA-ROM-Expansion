/* R42 native, interactive original Emerald source-labelled events.
 *
 * Both ORIGINAL-EMERALD-FORMAT script+text resources are independently loaded
 * from SHA-256 verified XGBA host sidecars, bounded by their own source IDs.
 * Uses the real global asynchronous Emerald script dispatcher, message UI,
 * bag operations, flags and vars. These are AUTHORED COMPATIBILITY scripts,
 * not unmodified Rocket/HnS binary scripts.
 */
#ifndef XGBA_R42_EVENT_TEST
#error R42 source event adapters are exclusively for the native fixture
#endif
#ifndef XGBA_R18_SAVE_TEST
#error R42 game event persistence uses actual original Emerald Flash
#endif
#include "script.h"
#include "event_data.h"
#include "item.h"

#define XGBA_R42_SIZE 96u
#define XGBA_R42_TEXT 22u
#define XGBA_R42_ROCKET_VAR 0x40FDu
#define XGBA_R42_JOHTO_VAR 0x40FCu
#define XGBA_R42_ROCKET_FLAG 0x08F1u
#define XGBA_R42_JOHTO_FLAG 0x08F2u
#define XGBA_R42_ROCKET_VALUE 0x524Bu
#define XGBA_R42_JOHTO_VALUE 0x484Eu
#define XGBA_R42_NUGGET 110u
#define XGBA_R42_SILK_SCARF 217u
#define XGBA_R42_READY 1u
#define XGBA_R42_RESTORED 2u
#define XGBA_R42_COMPLETE 3u
#define XGBA_R42_REJECTED 0xE42u

/* EWRAM_DATA MUST be initialized explicitly inside the guest: original
 * Emerald's NOLOAD region does not retain ROM initializer bytes.
 * Script buffers remain alive while async native text tasks are running. */
static EWRAM_DATA u8 sXgbaR42Rocket[XGBA_R42_SIZE] = {0};
static EWRAM_DATA u8 sXgbaR42Johto[XGBA_R42_SIZE] = {0};
static EWRAM_DATA char sXgbaR42RocketId[24] = {0};
static EWRAM_DATA char sXgbaR42JohtoId[24] = {0};

static void XgbaR42Inspect(void)
{
    gXgbaR18Proof.r42_rocket_flag=FlagGet(XGBA_R42_ROCKET_FLAG);
    gXgbaR18Proof.r42_johto_flag=FlagGet(XGBA_R42_JOHTO_FLAG);
    gXgbaR18Proof.r42_rocket_var=VarGet(XGBA_R42_ROCKET_VAR);
    gXgbaR18Proof.r42_johto_var=VarGet(XGBA_R42_JOHTO_VAR);
    gXgbaR18Proof.r42_nugget=CheckBagHasItem(XGBA_R42_NUGGET,1);
    gXgbaR18Proof.r42_silk_scarf=CheckBagHasItem(XGBA_R42_SILK_SCARF,1);
}

static bool8 XgbaR42Validate(const u8 *code, u16 var, u16 value,
                            u16 flag, u16 item)
{
    u32 i;
    /* No raw arbitrary script may execute. Original command format:
     * SETVAR, SETFLAG, ADDITEM, LOAD_WORD 0,<reloc>, CALL_STD 4, END,
     * followed by source-authored original-font text with FF terminator. */
    if(code[0]!=0x16u || code[1]!=(u8)var || code[2]!=(u8)(var>>8) ||
       code[3]!=(u8)value || code[4]!=(u8)(value>>8) ||
       code[5]!=0x29u || code[6]!=(u8)flag || code[7]!=(u8)(flag>>8) ||
       code[8]!=0x44u || code[9]!=(u8)item || code[10]!=(u8)(item>>8) ||
       code[11]!=1u || code[12]!=0u ||
       code[13]!=0x0Fu || code[14]!=0u ||
       code[15]!=0u || code[16]!=0u || code[17]!=0u || code[18]!=0u ||
       code[19]!=0x09u || code[20]!=4u || code[21]!=0x02u)
        return FALSE;
    for(i=XGBA_R42_TEXT;i<XGBA_R42_SIZE;++i)
        if(code[i]==0xFFu)
            return TRUE; /* payload source hash remains independently checked */
    return FALSE;
}

static void XgbaR42Relocate(u8 *code)
{
    u32 ptr=(u32)(code+XGBA_R42_TEXT);
    /* These four bytes are the sole runtime relocation and point to the
     * already-verified SAME source's message text in the guest EWRAM arena. */
    code[15]=(u8)ptr;
    code[16]=(u8)(ptr>>8);
    code[17]=(u8)(ptr>>16);
    code[18]=(u8)(ptr>>24);
}

static bool8 XgbaR42FetchBoth(void)
{
    const char rocket[]="rocket.r42.event";
    const char johto[]="heart_soul.r42.event";
    u32 i;
    if(gXgbaR18Proof.r42_fetches!=0u)
        return FALSE; /* forbid refetch/partially-invalidated scripts */
    for(i=0;i<sizeof(rocket);++i)
        sXgbaR42RocketId[i]=rocket[i];
    for(i=0;i<sizeof(johto);++i)
        sXgbaR42JohtoId[i]=johto[i];
    gXgbaR18Proof.r42_fetches=2u;
    if(XgbaGuestFetch(sXgbaR42RocketId,sXgbaR42Rocket,XGBA_R42_SIZE)!=XGBA_R42_SIZE ||
       XgbaGuestFetch(sXgbaR42JohtoId,sXgbaR42Johto,XGBA_R42_SIZE)!=XGBA_R42_SIZE)
        return FALSE;
    if(!XgbaR42Validate(sXgbaR42Rocket,XGBA_R42_ROCKET_VAR,
                        XGBA_R42_ROCKET_VALUE,XGBA_R42_ROCKET_FLAG,XGBA_R42_NUGGET) ||
       !XgbaR42Validate(sXgbaR42Johto,XGBA_R42_JOHTO_VAR,
                        XGBA_R42_JOHTO_VALUE,XGBA_R42_JOHTO_FLAG,XGBA_R42_SILK_SCARF))
        return FALSE;
    XgbaR42Relocate(sXgbaR42Rocket);
    XgbaR42Relocate(sXgbaR42Johto);
    gXgbaR18Proof.r42_state=XGBA_R42_READY;
    return TRUE;
}

static void XgbaR42Tick(void)
{
    bool8 rocket;
    if(!gSaveBlock1Ptr || !gMapHeader.mapLayout)
        return;
    if(gXgbaR18Proof.boot_continue &&
       gXgbaR18Proof.r42_state==0u) {
        gXgbaR18Proof.r42_state=XGBA_R42_RESTORED;
        XgbaR42Inspect();
        return;
    }
    if(gXgbaR18Proof.r42_state==XGBA_R42_REJECTED ||
       gXgbaR18Proof.r42_state==XGBA_R42_RESTORED)
        return;
    /* Unlike R40's immediate script, R42 uses the original ASYNCHRONOUS
     * global interpreter: refresh proof only after native frame execution. */
    if(gXgbaR18Proof.r42_state!=0u)
        XgbaR42Inspect();
    if(ScriptContext_IsEnabled())
        return;
    /* R = Team Rocket adaptation, L = Heart & Soul adaptation.
     * The original physical controller feeds gMain.newKeys in actual mGBA. */
    rocket=!!(gMain.newKeys & R_BUTTON);
    if(!rocket && !(gMain.newKeys & L_BUTTON))
        return;
    XgbaR42Inspect();
    if(rocket ? gXgbaR18Proof.r42_rocket_flag :
                gXgbaR18Proof.r42_johto_flag)
        return; /* one-time reward, no duplicate item on future keypress */
    if(!gXgbaR18Proof.r42_fetches && !XgbaR42FetchBoth()) {
        gXgbaR18Proof.r42_state=XGBA_R42_REJECTED;
        gXgbaR18Proof.r42_errors=1u;
        return;
    }
    if(gXgbaR18Proof.r42_state==XGBA_R42_REJECTED)
        return;
    ScriptContext_SetupScript(rocket ? sXgbaR42Rocket : sXgbaR42Johto);
    ++gXgbaR18Proof.r42_launches;
    XgbaR42Inspect();
    if(gXgbaR18Proof.r42_launches==2u)
        gXgbaR18Proof.r42_state=XGBA_R42_COMPLETE;
}

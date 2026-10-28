/* Phase 1: unchanged pinned FireRed dispatch bodies; host stubs only. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint8_t u8;
typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
#include "phase1_dispatch_constants.inc"
static int gQuestLogState;
static u8 fakeScript[1] = {0xEE};
static int allowGet, allowCheck, getHits, checkHits, immediateHits, setupHits;
static int getTag, checkTag;
static u8 *MapHeaderGetScriptTable(u8 tag) {
    ++getHits; getTag = tag;
    return allowGet ? fakeScript : NULL;
}
static u8 *MapHeaderCheckScriptTable(u8 tag) {
    ++checkHits; checkTag = tag;
    return allowCheck ? fakeScript : NULL;
}
static void RunScriptImmediately(const u8 *ptr) {
    if (ptr != fakeScript) {fprintf(stderr,"unexpected immediate pointer\n");exit(1);}
    ++immediateHits;
}
static void ScriptContext_SetupScript(const u8 *ptr) {
    if (ptr != fakeScript) {fprintf(stderr,"unexpected setup pointer\n");exit(1);}
    ++setupHits;
}
#include "phase1_dispatch_functions.inc"
static void check(int ok, const char *label) {
    if (!ok) {fprintf(stderr,"FAIL %s\n",label);exit(1);}
}
static void reset(void) {
    allowGet=allowCheck=0;
    getHits=checkHits=immediateHits=setupHits=0;
    getTag=checkTag=-1;
    gQuestLogState=0;
}
int main(void) {
    struct Wrapper {void (*run)(void); int tag;} wrappers[] = {
        {RunOnLoadMapScript, MAP_SCRIPT_ON_LOAD},
        {RunOnTransitionMapScript, MAP_SCRIPT_ON_TRANSITION},
        {RunOnResumeMapScript, MAP_SCRIPT_ON_RESUME},
        {RunOnReturnToFieldMapScript, MAP_SCRIPT_ON_RETURN_TO_FIELD},
        {RunOnDiveWarpMapScript, MAP_SCRIPT_ON_DIVE_WARP},
    };
    for (unsigned i=0; i<sizeof(wrappers)/sizeof(wrappers[0]); ++i) {
        reset(); allowGet=1; wrappers[i].run();
        check(getHits==1 && getTag==wrappers[i].tag &&
              immediateHits==1 && checkHits==0 && setupHits==0,
              "wrapper positive tag/immediate");
        reset(); wrappers[i].run();
        check(getHits==1 && getTag==wrappers[i].tag &&
              immediateHits==0 && checkHits==0 && setupHits==0,
              "wrapper absent-script control");
    }
    reset(); gQuestLogState=QL_STATE_PLAYBACK_LAST; allowCheck=1;
    check(TryRunOnFrameMapScript()==FALSE && checkHits==0 &&
          setupHits==0 && immediateHits==0, "last playback suppresses frame");
    reset();
    check(TryRunOnFrameMapScript()==FALSE && checkHits==1 &&
          checkTag==MAP_SCRIPT_ON_FRAME_TABLE && setupHits==0,
          "unmatched frame condition");
    reset(); allowCheck=1;
    check(TryRunOnFrameMapScript()==TRUE && checkHits==1 &&
          checkTag==MAP_SCRIPT_ON_FRAME_TABLE && setupHits==1 &&
          immediateHits==0, "matched frame schedules context");
    reset(); allowCheck=1; gQuestLogState=QL_STATE_PLAYBACK;
    check(TryRunOnFrameMapScript()==TRUE && checkHits==1 &&
          setupHits==1, "ordinary playback is not playback-last");
    reset(); TryRunOnWarpIntoMapScript();
    check(checkHits==1 && checkTag==MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE &&
          immediateHits==0, "unmatched warp condition");
    reset(); allowCheck=1; TryRunOnWarpIntoMapScript();
    check(checkHits==1 && checkTag==MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE &&
          immediateHits==1 && setupHits==0, "matched warp immediate");
    puts("HOST_EXTRACTED_FIRERED_MAP_SCRIPT_DISPATCH PASS cases=16 gate=FAIL_INCOMPLETE approvals=0");
    return 0;
}

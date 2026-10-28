/* Execute exact source-extracted FireRed MapHeader* functions on host.
 * This is NOT stock GBA/mGBA execution or a malformed-table safety claim.
 * Host pointer translation is a test shim, not a FireRed bounds check.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define BASE 0x08000000u
static u8 linked[] = {
    0x03,0x1d,0,0,8, 0x02,0x0b,0,0,8, 0,
    0,0x40,0x34,0x12,0x1e,0,0,8, 1,0x40,0x35,0x12,0x1f,0,0,8,
    0,0, 2,3,4
};
static struct {u8 *mapScripts;} gMapHeader;
static int mode;
static u16 VarGet(u16 idx) {
    if (mode==1 && (idx==0x4000 || idx==0x1234)) return 0x77;
    if (mode==2 && (idx==0x4001 || idx==0x1235)) return 0x77;
    return idx;
}
static u16 read16(const u8 *p) {return (u16)(p[0] | ((u16)p[1]<<8));}
static u8 *readptr(const u8 *p) {
    uint32_t a=(uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
    if(a<BASE || a>=BASE+sizeof(linked)) { fprintf(stderr,"HOST_POINTER_GUARD_FAIL\n"); exit(1); }
    return linked+(a-BASE);
}
#define T1_READ_16(ptr) read16(ptr)
#define T2_READ_PTR(ptr) readptr(ptr)
#include "phase1_reader_functions.inc"
static void check(int condition,const char *s) {
    if(!condition) {fprintf(stderr,"FAIL %s\n",s);exit(1);}
}
int main(void) {
    gMapHeader.mapScripts=NULL;
    check(MapHeaderGetScriptTable(2)==NULL,"null header");
    gMapHeader.mapScripts=linked;
    check(MapHeaderGetScriptTable(3)==linked+29,"transition");
    check(MapHeaderGetScriptTable(2)==linked+11,"frame table");
    check(MapHeaderGetScriptTable(99)==NULL,"outer sentinel");
    mode=0;
    check(MapHeaderCheckScriptTable(2)==NULL,"conditional sentinel");
    mode=1;
    check(MapHeaderCheckScriptTable(2)==linked+30,"first conditional");
    mode=2;
    check(MapHeaderCheckScriptTable(2)==linked+31,"second conditional");
    mode=0; linked[0]=0;
    check(MapHeaderGetScriptTable(2)==NULL,"early outer sentinel");
    linked[0]=3;
    linked[12]=0; mode=1;
    check(MapHeaderCheckScriptTable(2)==NULL,"early conditional sentinel");
    linked[12]=0x40;
    printf("HOST_EXTRACTED_FIRERED_MAP_SCRIPT_READER PASS cases=9 gate=FAIL_INCOMPLETE approvals=0\n");
    return 0;
}

/* R67 original game NPC script/text witness integrity for genuine native Fly.
 * Read-only, stack-only, 256-byte original source packet admission. The host
 * checks original owner-ROM SHA and resource SHA; the guest checks the exact
 * original source-qualified NPC coordinates, script pointer/opcode sequence,
 * bounded dialogue length and terminator. No native map state is modified.
 * This validates one source NPC's original script, not arbitrary scripts.
 */
#ifndef XGBA_R67_ORIGINAL_NPC_WITNESS_H
#define XGBA_R67_ORIGINAL_NPC_WITNESS_H
#include <stdint.h>
#define XGBA_R67_BYTES 256u
#define XGBA_R67_HEADER 32u
#define XGBA_R67_SCRIPT_LENGTH 9u
static inline uint16_t XgbaR67Le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0]|((uint16_t)p[1]<<8));
}
static inline uint32_t XgbaR67Le32(const uint8_t *p)
{
    return (uint32_t)XgbaR67Le16(p)|
           ((uint32_t)XgbaR67Le16(p+2u)<<16);
}
static inline int XgbaR67ValidateOriginalNpcWitness(
    unsigned world,const uint8_t *p,unsigned bytes)
{
    static const uint8_t groups[3]={0u,0u,0u};
    static const uint8_t maps[3]={9u,9u,4u};
    static const uint8_t npcs[3]={2u,2u,7u};
    static const int16_t x_coord[3]={12,14,39};
    static const int16_t y_coord[3]={13,13,22};
    static const uint16_t gfx[3]={17u,17u,406u};
    static const uint32_t scripts[3]={0x1e8022u,0x215543u,0x390519u};
    static const uint32_t texts[3]={0x1e8acfu,0x1dc3364u,0x3908e6u};
    unsigned i,text_len;
    const uint8_t *s;
    if(world>=3u || !p || bytes!=XGBA_R67_BYTES)return 0;
    if(p[0]!='X' || p[1]!='4' || p[2]!='8' || p[3]!='N' ||
       p[4]!=1u || p[5]!=world || p[6]!=groups[world] ||
       p[7]!=maps[world] || p[8]!=npcs[world] ||
       (int16_t)XgbaR67Le16(p+9u)!=x_coord[world] ||
       (int16_t)XgbaR67Le16(p+11u)!=y_coord[world] ||
       XgbaR67Le16(p+13u)!=gfx[world] ||
       XgbaR67Le32(p+15u)!=scripts[world] ||
       XgbaR67Le32(p+19u)!=texts[world] ||
       XgbaR67Le16(p+23u)!=XGBA_R67_SCRIPT_LENGTH)
        return 0;
    text_len=XgbaR67Le16(p+25u);
    if(!text_len || text_len>210u ||
       XGBA_R67_HEADER+XGBA_R67_SCRIPT_LENGTH+text_len>XGBA_R67_BYTES)
        return 0;
    for(i=27u;i<XGBA_R67_HEADER;i++)
        if(p[i]!=0u)return 0;
    s=p+XGBA_R67_HEADER;
    if(s[0]!=0x0fu || s[1]!=0u ||
       XgbaR67Le32(s+2u)!=UINT32_C(0x08000000)+texts[world] ||
       s[6]!=0x09u || s[7]!=0x02u || s[8]!=0x02u ||
       s[XGBA_R67_SCRIPT_LENGTH+text_len-1u]!=0xffu)
        return 0;
    return 1;
}
#endif

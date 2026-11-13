/* R66 source OAM and first-animation admission for REAL native Emerald OBJ.
 *
 * The private host SHA and R56 guest CRC authenticate exact original sprite
 * bytes before this original GBA OAM/AnimCmd adapter accepts them. Decode the
 * 8-byte non-affine 4bpp OAM (shape and size included), and enforce bounded
 * first-animation commands. Reject unsupported source layouts rather than
 * showing invented Emerald still animations or substituting another sprite.
 *
 * Source sprite dimensions and first-animation bytes are not the full
 * FRLG/HnS directional animation table. Directional paging remains pending.
 */
#ifndef XGBA_R66_ORIGINAL_OBJ_ANIMATION_H
#define XGBA_R66_ORIGINAL_OBJ_ANIMATION_H
#include <stdint.h>
#define XGBA_R66_OAM_BYTES 8u
#define XGBA_R66_ANIM_MAX_COMMANDS 32u
#define XGBA_R66_ANIM_MAX_BYTES (XGBA_R66_ANIM_MAX_COMMANDS*4u)
static inline uint16_t XgbaR66Le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1]<<8));
}
static inline int XgbaR66OriginalOamValid(
    const uint8_t *raw,unsigned bytes,unsigned width,unsigned height)
{
    static const uint8_t shape_width[3][4]={
        {8,16,32,64},{16,32,32,64},{8,8,16,32}
    };
    static const uint8_t shape_height[3][4]={
        {8,16,32,64},{8,8,16,32},{16,32,32,64}
    };
    uint16_t attr0,attr1,attr2,attr3;
    unsigned shape,size;
    if(!raw || bytes!=XGBA_R66_OAM_BYTES)return 0;
    attr0=XgbaR66Le16(raw);
    attr1=XgbaR66Le16(raw+2u);
    attr2=XgbaR66Le16(raw+4u);
    attr3=XgbaR66Le16(raw+6u);
    shape=(attr0>>14u)&3u;
    size=(attr1>>14u)&3u;
    if(shape>=3u || shape_width[shape][size]!=width ||
       shape_height[shape][size]!=height)
        return 0;
    /* Non-affine, ordinary 4bpp OAM. Don't interpret a source's OBJ-window,
     * blend, mosaic, 8bpp or affine raw bytes with Emerald's unrelated API. */
    if((attr0 & UINT16_C(0x3f00))!=0u ||
       (attr1 & UINT16_C(0x3c00))!=0u ||
       (attr2 & UINT16_C(0xf3ff))!=0u ||
       attr3!=0u)
        return 0;
    /* attr0's upper shape bits and attr1 size bits are permitted above.
     * FRLG source priority bits in attr2[11:10] are preserved. */
    return 1;
}
static inline int XgbaR66OriginalFirstAnimationValid(
    const uint8_t *raw,unsigned bytes,unsigned frame_count)
{
    unsigned i,commands;
    if(!raw || !frame_count || frame_count>8u ||
       bytes<8u || bytes>XGBA_R66_ANIM_MAX_BYTES || (bytes&3u))
        return 0;
    commands=bytes/4u;
    for(i=0u;i<commands;i++){
        const uint16_t image=XgbaR66Le16(raw+4u*i);
        const uint16_t argument=XgbaR66Le16(raw+4u*i+2u);
        if(image==UINT16_C(0xfffe)) /* native ANIMCMD_END */
            return i>0u && i+1u==commands && argument==0u;
        if(image==UINT16_C(0xfffd)){ /* native ANIMCMD_JUMP */
            return i>0u && i+1u==commands && argument<i;
        }
        if(image>=frame_count || argument==0u || argument>255u)
            return 0;
    }
    return 0; /* Unterminated original animation would read outside backing. */
}
#endif

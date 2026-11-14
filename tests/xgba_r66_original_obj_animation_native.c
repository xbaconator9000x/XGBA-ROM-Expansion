/* R66: real GBA OAM/AnimCmd-compatible source byte admission.
 * Fixtures below are authored; original Rocket private bytes never enter Git.
 */
#include "../integration/common/xgba_r66_original_obj_animation.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    /* Source OAM shape vertical, size2 = 16x32, normal 4bpp,
     * source priority2. First animation frame0 duration16 then end. */
    const uint8_t oam[8]={0x00,0x80,0x00,0x80,0x00,0x08,0x00,0x00};
    const uint8_t animate[8]={0x00,0x00,0x10,0x00,0xfe,0xff,0x00,0x00};
    uint8_t bad[8];
    assert(XgbaR66OriginalOamValid(oam,sizeof(oam),16u,32u));
    assert(!XgbaR66OriginalOamValid(oam,sizeof(oam),32u,32u));
    assert(!XgbaR66OriginalOamValid(oam,7u,16u,32u));
    memcpy(bad,oam,8);bad[0]=0x01; /* OAM y is allowed */
    assert(XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[1]=0xa0; /* 8bpp bit set: reject */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[1]=0x90; /* mosaic bit set: reject */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[1]=0xc0; /* forbidden shape3 */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[3]=0xc0; /* wrong OAM size */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[4]=0x01; /* native tileNum must be zero */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[5]=0x04; /* different native priority is allowed */
    assert(XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[5]=0xf8; /* source paletteNum must be zero */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    memcpy(bad,oam,8);bad[7]=0x01; /* affine padding forbidden */
    assert(!XgbaR66OriginalOamValid(bad,8u,16u,32u));
    assert(XgbaR66OriginalFirstAnimationValid(animate,sizeof(animate),1u));
    /* R95 HnS source NPC has nine native frames, not eight. */
    assert(XgbaR66OriginalFirstAnimationValid(animate,sizeof(animate),9u));
    assert(!XgbaR66OriginalFirstAnimationValid(animate,sizeof(animate),17u));
    assert(!XgbaR66OriginalFirstAnimationValid(animate,4u,1u));
    assert(!XgbaR66OriginalFirstAnimationValid(animate,7u,1u));
    memcpy(bad,animate,8);bad[0]=1u; /* second frame absent */
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    assert(XgbaR66OriginalFirstAnimationValid(bad,8u,2u));
    memcpy(bad,animate,8);bad[2]=0u; /* zero frame duration */
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    memcpy(bad,animate,8);bad[4]=0xffu; /* native 0xffff END */
    assert(XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    bad[6]=1u; /* nonzero terminator data rejected */
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    memcpy(bad,animate,8);bad[4]=0xfdu;bad[5]=0xffu;
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u)); /* LOOP cannot masquerade as JUMP */
    memcpy(bad,animate,8);
    assert(XgbaR66OriginalFirstAnimationValid(bad,8u,1u)); /* genuine JUMP(0) */
    bad[6]=1u; /* out-of-range jump */
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    memcpy(bad,animate,8);bad[2]=0x50; /* duration 16 and original hFlip */
    assert(XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    bad[3]=1u; /* reserved frame argument high bits */
    assert(!XgbaR66OriginalFirstAnimationValid(bad,8u,1u));
    puts("PASS_R66_ORIGINAL_OAM_FIRST_ANIMATION_NATIVE_SAFE_ADMISSION");
    return 0;
}

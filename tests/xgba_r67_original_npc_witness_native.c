/* R67: source-safe original NPC read-only preflight verifier.
 * All test speech is authored and never copied from commercial game ROMs.
 */
#include "../integration/common/xgba_r67_original_npc_witness.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void le16(uint8_t *p,uint16_t n)
{
    p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);
}
static void le32(uint8_t *p,uint32_t n)
{
    le16(p,(uint16_t)n);le16(p+2u,(uint16_t)(n>>16));
}
static void fixture(uint8_t *p,unsigned world)
{
    const unsigned npc[]={2u,2u,7u};
    const unsigned map[]={9u,9u,4u};
    const unsigned x[]={12u,14u,39u},y[]={13u,13u,22u};
    const unsigned gfx[]={17u,17u,406u};
    const uint32_t scripts[]={0x1e8022u,0x215543u,0x390519u};
    const uint32_t texts[]={0x1e8acfu,0x1dc3364u,0x3908e6u};
    memset(p,0,XGBA_R67_BYTES);
    memcpy(p,"X48N",4u);
    p[4]=1u;p[5]=(uint8_t)world;p[7]=(uint8_t)map[world];
    p[8]=(uint8_t)npc[world];
    le16(p+9u,(uint16_t)x[world]);
    le16(p+11u,(uint16_t)y[world]);
    le16(p+13u,(uint16_t)gfx[world]);
    le32(p+15u,scripts[world]);le32(p+19u,texts[world]);
    le16(p+23u,9u);le16(p+25u,3u);
    p[32]=0x0fu;p[33]=0u;le32(p+34u,UINT32_C(0x08000000)+texts[world]);
    p[38]=9u;p[39]=2u;p[40]=2u;
    p[41]=0xfcu;p[42]=1u;p[43]=0xffu;
}
int main(void)
{
    uint8_t src[XGBA_R67_BYTES];
    unsigned w;
    assert(!XgbaR67ValidateOriginalNpcWitness(3u,src,256u));
    assert(!XgbaR67ValidateOriginalNpcWitness(0u,NULL,256u));
    for(w=0u;w<3u;w++){
        fixture(src,w);
        assert(XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,255u));
        assert(!XgbaR67ValidateOriginalNpcWitness((w+1u)%3u,src,256u));
        src[8]^=1u;
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[13]^=1u; /* original gfx ID */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[34]^=1u; /* original script pointer */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[38]=1u; /* original msgbox/end opcode */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[43]=0u; /* original text terminator */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[27]=1u; /* reserved header padding */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[25]=0u; /* zero text length */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);src[25]=255u; /* excess text length */
        assert(!XgbaR67ValidateOriginalNpcWitness(w,src,256u));
        fixture(src,w);
    }
    puts("PASS_R67_ALL_THREE_AUTHORED_ORIGINAL_NPC_PACKET_VALIDATION_AND_CORRUPTION_REFUSAL");
    return 0;
}

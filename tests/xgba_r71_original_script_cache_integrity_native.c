/* R71 authored NPC fixture; no original commercial dialogue in public CI. */
#include "../integration/common/xgba_r71_original_script_cache_integrity.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static void store32(uint8_t *p,uint32_t x)
{
    p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8u);
    p[2]=(uint8_t)(x>>16u);p[3]=(uint8_t)(x>>24u);
}
int main(void)
{
    unsigned world;
    uint8_t payload[XGBA_R71_PACKET_BYTES];
    for(world=0u;world<3u;world++){
        uint32_t canonical;
        memset(payload,0,sizeof(payload));
        memcpy(payload,"X48N",4u);
        payload[5]=(uint8_t)world;
        payload[32]=0x0fu;payload[33]=0u;
        store32(payload+XGBA_R71_TEXT_PTR_OFF,XgbaR71OriginalTextPointer(world));
        payload[40]=0x02u;payload[42]=0x59u;payload[43]=0xffu;
        canonical=XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload),0);
        assert(canonical!=0u);
        assert(XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload)-1u,0)==0u);
        assert(XgbaR71CanonicalPacketCrc(3u,payload,sizeof(payload),0)==0u);
        assert(XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload),1)==canonical);
        store32(payload+XGBA_R71_TEXT_PTR_OFF,
                (uint32_t)(uintptr_t)(payload+XGBA_R71_SCRIPT_TEXT_OFF));
        assert(XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload),1)==canonical);
        assert(XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload),0)!=canonical);
        payload[50]^=1u;
        assert(XgbaR71CanonicalPacketCrc(world,payload,sizeof(payload),1)!=canonical);
        payload[50]^=1u;
        store32(payload+XGBA_R71_TEXT_PTR_OFF,
                (uint32_t)(uintptr_t)(payload+XGBA_R71_SCRIPT_TEXT_OFF+1u));
        assert(XgbaR67Le32(payload+XGBA_R71_TEXT_PTR_OFF)!=
            (uint32_t)(uintptr_t)(payload+XGBA_R71_SCRIPT_TEXT_OFF));
        store32(payload+XGBA_R71_TEXT_PTR_OFF,
                (uint32_t)(uintptr_t)(payload+XGBA_R71_SCRIPT_TEXT_OFF));
        assert(XgbaR67Le32(payload+XGBA_R71_TEXT_PTR_OFF)==
            (uint32_t)(uintptr_t)(payload+XGBA_R71_SCRIPT_TEXT_OFF));
    }
    assert(XgbaR71OriginalPacketCrc(0u)==UINT32_C(0x3ee29fb3));
    assert(XgbaR71OriginalPacketCrc(1u)==UINT32_C(0xdc79ff6b));
    assert(XgbaR71OriginalPacketCrc(2u)==UINT32_C(0xfa898797));
    puts("PASS_R71_CRC32_CANONICAL_ORIGINAL_DIALOGUE_POINTER_RELOCATION_AND_CORRUPTION_REFUSAL");
    return 0;
}

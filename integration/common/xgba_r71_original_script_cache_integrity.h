/* R71: source-authentic original 256-byte NPC packet integrity across guest
 * script relocation. The host already SHA-verifies all private R64 resources;
 * the guest pins CRC32 of each original unmodified R64 source witness.
 *
 * The original script's 4-byte ROM text pointer becomes a native EWRAM
 * pointer for the actual script engine. Reconstruct those four ORIGINAL ROM
 * bytes only while calculating CRC; NEVER mutate a live cached script or
 * add EWRAM allocations. A stale/corrupt cached packet fails closed rather
 * than authorizing Fly or executing a damaged dialogue/script pointer.
 */
#ifndef XGBA_R71_ORIGINAL_SCRIPT_CACHE_INTEGRITY_H
#define XGBA_R71_ORIGINAL_SCRIPT_CACHE_INTEGRITY_H
#include <stdint.h>
#include <stddef.h>
#include "xgba_r67_original_npc_witness.h"
#define XGBA_R71_PACKET_BYTES 256u
#define XGBA_R71_TEXT_PTR_OFF (32u+2u)
#define XGBA_R71_SCRIPT_TEXT_OFF (32u+9u)
static inline uint32_t XgbaR71OriginalTextPointer(unsigned world)
{
    static const uint32_t original_text_offsets[3]={
        UINT32_C(0x1e8acf),UINT32_C(0x1dc3364),UINT32_C(0x3908e6)
    };
    return world<3u?UINT32_C(0x08000000)+original_text_offsets[world]:0u;
}
static inline uint32_t XgbaR71OriginalPacketCrc(unsigned world)
{
    /* Original 256-byte source packet CRCs from the PRIVATE R64 provider,
     * independently checked against 377 SHA-256 resource entries. */
    static const uint32_t source_crc[3]={
        UINT32_C(0x3ee29fb3),UINT32_C(0xdc79ff6b),UINT32_C(0xfa898797)
    };
    return world<3u?source_crc[world]:0u;
}
static inline uint32_t XgbaR71CanonicalPacketCrc(
    unsigned world,const uint8_t *p,unsigned bytes,int relocated)
{
    uint32_t crc=UINT32_C(0xffffffff),original_ptr;
    unsigned i,bit;
    if(world>=3u || !p || bytes!=XGBA_R71_PACKET_BYTES)return 0u;
    original_ptr=XgbaR71OriginalTextPointer(world);
    for(i=0u;i<XGBA_R71_PACKET_BYTES;i++){
        uint8_t current=p[i];
        if(relocated && i>=XGBA_R71_TEXT_PTR_OFF &&
           i<XGBA_R71_TEXT_PTR_OFF+4u)
            current=(uint8_t)(original_ptr>>(8u*(i-XGBA_R71_TEXT_PTR_OFF)));
        crc^=current;
        for(bit=0u;bit<8u;bit++)
            crc=(crc>>1u)^((crc&1u)?UINT32_C(0xedb88320):0u);
    }
    return ~crc;
}
static inline int XgbaR71OriginalNpcPacketValid(
    unsigned world,const uint8_t *p,unsigned bytes)
{
    return world<3u && XgbaR67ValidateOriginalNpcWitness(world,p,bytes) &&
           XgbaR71CanonicalPacketCrc(world,p,bytes,0)==
               XgbaR71OriginalPacketCrc(world);
}
static inline int XgbaR71CachedOriginalNpcValid(
    unsigned world,const uint8_t *p,unsigned bytes)
{
    uint32_t expected_ewram;
    if(world>=3u || !p || bytes!=XGBA_R71_PACKET_BYTES)return 0;
    expected_ewram=(uint32_t)(uintptr_t)(p+XGBA_R71_SCRIPT_TEXT_OFF);
    /* The NPC's script pointer must still point into its original
     * independent EWRAM packet, never ROM, stack or a foreign world. */
    return XgbaR67Le32(p+XGBA_R71_TEXT_PTR_OFF)==expected_ewram &&
           XgbaR71CanonicalPacketCrc(world,p,bytes,1)==
               XgbaR71OriginalPacketCrc(world);
}
#endif

/* R50: stage original R49 map-event bytes for the ACTUAL Emerald field engine.
 * R49 preserves every original byte; this adapter intentionally quarantines
 * foreign scripts, warps and flags until safe source-aware guest support exists.
 * No source-labelled substitutes are invented. NOT a Fly acceptance pass.
 */
#ifndef XGBA_R50_ENGINE_EVENT_ADAPTER_H
#define XGBA_R50_ENGINE_EVENT_ADAPTER_H
#include "xgba_r49_full_original_map_events.h"

#define XGBA_R50_EVENT_CAPACITY 4096u
#define XGBA_R50_MAX_OBJECTS 64u

/* Source sprite index -> installed guest slot. Reject unknown sprites; never
 * truncate 16-bit expanded Heart & Soul IDs into Emerald's 8-bit slot. */
typedef int (*XgbaR50ResolveSprite)(void *ctx, uint8_t source,
                                   uint16_t original_sprite, uint8_t *slot);
struct XgbaR50EngineEvents {
    uint32_t active_source_key;
    uint32_t script_origins[XGBA_R50_MAX_OBJECTS];
    uint16_t original_flags[XGBA_R50_MAX_OBJECTS];
    uint16_t originals_bytes;
    uint16_t object_bytes,warp_bytes,coordinate_bytes,background_bytes;
    uint8_t object_count,original_warp_count,coordinate_count,background_count;
    uint8_t runtime_warp_count,graphics_verified,valid;
    uint16_t width,height;
    /* 32-bit alignment of original GBA object/coord pointer fields. */
    uint32_t bytes_aligned[XGBA_R50_EVENT_CAPACITY/4u];
};
#define XgbaR50EventBytes(events) ((uint8_t *)(events)->bytes_aligned)

static inline int XgbaR50StageEvents(
    struct XgbaR49Reader *reader, uint32_t source_key,
    uint16_t map_width,uint16_t map_height,
    XgbaR50ResolveSprite sprite,void *sprite_ctx,
    uint32_t verified_guest_safe_script,
    struct XgbaR50EngineEvents *out)
{
    struct XgbaR49OriginalEvents e;
    uint32_t total, offsets[4],seen[8]={0};
    uint8_t graphics_slots[XGBA_R50_MAX_OBJECTS];
    unsigned i,source=(source_key>>16u)&255u;
    uint8_t *bytes;
    if(!reader || !out || !sprite || !map_width || !map_height ||
       map_width>255u || map_height>255u || source>=3u ||
       (source_key>>24u)!=0u || verified_guest_safe_script==0u ||
       (verified_guest_safe_script&3u)!=0u)
        return 0;
    if(!XgbaR49LoadOriginalMapEvents(reader,source_key,&e))return 0;
    total=e.bytes_total;
    if(total>XGBA_R50_EVENT_CAPACITY || e.object_count>XGBA_R50_MAX_OBJECTS)
        return 0;
    offsets[0]=0u;
    offsets[1]=(uint32_t)e.object_count*24u;
    offsets[2]=offsets[1]+(uint32_t)e.warp_count*8u;
    offsets[3]=offsets[2]+(uint32_t)e.coordinate_count*16u;
    if(offsets[3]+(uint32_t)e.background_count*12u!=total)return 0;
    /* Validate ALL original NPC objects before any live game state changes. */
    for(i=0u;i<e.object_count;i++){
        const uint8_t *p=e.objects+24u*i;
        uint8_t id=p[0],slot=0;
        uint16_t gfx=XgbaR49Le16(p+1u);
        int16_t x=(int16_t)XgbaR49Le16(p+4u);
        int16_t y=(int16_t)XgbaR49Le16(p+6u);
        uint32_t script_addr=XgbaR49Le32(p+16u);
        if(!id || (seen[id>>5u]&(UINT32_C(1)<<(id&31u))) ||
           x<0 || y<0 || x>=map_width || y>=map_height ||
           !sprite(sprite_ctx,(uint8_t)source,gfx,&slot) ||
           (script_addr && (script_addr<UINT32_C(0x08000000) ||
              script_addr>=UINT32_C(0x0a000000))))
            return 0;
        seen[id>>5u]|=UINT32_C(1)<<(id&31u);
        graphics_slots[i]=slot;
    }
    /* Deep copy: the R49 16 KiB scratch page can be reused after return. */
    bytes=XgbaR50EventBytes(out);
    if(total)memcpy(bytes,e.objects,total);
    for(i=0u;i<e.object_count;i++){
        uint8_t *p=bytes+24u*i;
        out->script_origins[i]=XgbaR49Le32(p+16u);
        out->original_flags[i]=XgbaR49Le16(p+20u);
        p[1]=graphics_slots[i]; /* explicit source sprite translation */
        p[2]=0u; /* original Emerald OBJ_KIND_NORMAL, not gfx upper byte */
        /* Quarantine source-ROM pointers. R48 can resolve an authentic
         * original-NPC script on an actual physical A-button interaction. */
        p[16]=(uint8_t)verified_guest_safe_script;
        p[17]=(uint8_t)(verified_guest_safe_script>>8u);
        p[18]=(uint8_t)(verified_guest_safe_script>>16u);
        p[19]=(uint8_t)(verified_guest_safe_script>>24u);
        p[20]=0u;p[21]=0u; /* never use another world's flag IDs */
    }
    /* Original coordinate callbacks must not run as Emerald-ROM pointers. */
    for(i=0;i<e.coordinate_count;i++){
        uint8_t *p=bytes+offsets[2]+16u*i;
        p[12]=(uint8_t)verified_guest_safe_script;
        p[13]=(uint8_t)(verified_guest_safe_script>>8u);
        p[14]=(uint8_t)(verified_guest_safe_script>>16u);
        p[15]=(uint8_t)(verified_guest_safe_script>>24u);
    }
    /* Original warp/coord/bg content remains in the intact R49 source store.
     * Do NOT expose untranslated foreign destinations, specials or rewards. */
    out->active_source_key=source_key;
    out->originals_bytes=(uint16_t)total;
    out->object_bytes=(uint16_t)offsets[1];
    out->warp_bytes=(uint16_t)(offsets[2]-offsets[1]);
    out->coordinate_bytes=(uint16_t)(offsets[3]-offsets[2]);
    out->background_bytes=(uint16_t)(total-offsets[3]);
    out->object_count=e.object_count;
    out->original_warp_count=e.warp_count;
    out->coordinate_count=0u;
    out->background_count=0u;
    out->runtime_warp_count=0u;
    out->width=map_width;out->height=map_height;
    out->graphics_verified=1u;out->valid=1u;
    return 1;
}
#endif

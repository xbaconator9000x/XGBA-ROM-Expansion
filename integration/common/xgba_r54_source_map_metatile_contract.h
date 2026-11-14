/* R54: physical original-map source art validation for native Emerald.
 *
 * The original 512/640 primary metatile split reserves ID space; the
 * original source may have authored only 2, 8, 144, 256, ... definitions.
 * Before exposing ORIGINAL R51 cells to original Emerald's field camera,
 * validate every terrain and border metatile against R53's authenticated
 * physical source counts. Higher six bits are original behavior/elevation
 * flags, not the ten-bit metatile ID. Fail closed on unused source IDs.
 *
 * No original ROM art included. This is an engine-independent, bounded
 * pure C11 contract suitable for ASan/UBSan and the real GBA ARM build.
 */
#ifndef XGBA_R54_SOURCE_MAP_METATILE_CONTRACT_H
#define XGBA_R54_SOURCE_MAP_METATILE_CONTRACT_H
#include <stdint.h>
#include <stddef.h>

#define XGBA_R54_GRID_MAX_BYTES 5600u
#define XGBA_R54_BORDER_BYTES 8u
#define XGBA_R54_METATILE_MASK UINT16_C(0x03ff)

struct XgbaR54OriginalMapUse {
    uint32_t cells_verified, primary_cells, secondary_cells;
    uint16_t max_primary_id, max_secondary_relative_id;
};

static inline int XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
    const uint8_t *source_original_grid_plus_border,
    uint16_t map_width,uint16_t map_height,uint32_t grid_bytes,
    uint16_t source_primary_split,uint16_t source_primary_authored,
    uint16_t source_secondary_authored,
    struct XgbaR54OriginalMapUse *result)
{
    struct XgbaR54OriginalMapUse next={0};
    uint32_t count,i;
    if(!source_original_grid_plus_border || !result ||
       !map_width || !map_height ||
       !grid_bytes || grid_bytes>XGBA_R54_GRID_MAX_BYTES ||
       grid_bytes!=2u*(uint32_t)map_width*(uint32_t)map_height ||
       (source_primary_split!=512u && source_primary_split!=640u) ||
       !source_primary_authored || source_primary_authored>source_primary_split ||
       !source_secondary_authored ||
       source_secondary_authored>1024u-source_primary_split)
        return 0;
    count=(grid_bytes+XGBA_R54_BORDER_BYTES)/2u;
    for(i=0;i<count;i++){
        uint32_t off=i*2u;
        uint16_t word=(uint16_t)source_original_grid_plus_border[off] |
                      ((uint16_t)source_original_grid_plus_border[off+1u]<<8);
        uint16_t id=word&XGBA_R54_METATILE_MASK;
        if(id<source_primary_split){
            if(id>=source_primary_authored)return 0;
            ++next.primary_cells;
            if(id>next.max_primary_id)next.max_primary_id=id;
        } else {
            uint16_t relative=(uint16_t)(id-source_primary_split);
            if(relative>=source_secondary_authored)return 0;
            ++next.secondary_cells;
            if(relative>next.max_secondary_relative_id)
                next.max_secondary_relative_id=relative;
        }
    }
    next.cells_verified=count;
    *result=next; /* transactional; failures do not claim a validated map */
    return 1;
}
#endif

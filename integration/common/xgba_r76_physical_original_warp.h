/* R76 pure source-original warp tile hit recognition.
 * Call this only from the actual Emerald avatar step/warp metatile path.
 * This function never enables a foreign map or changes a warp destination.
 */
#ifndef XGBA_R76_PHYSICAL_ORIGINAL_WARP_H
#define XGBA_R76_PHYSICAL_ORIGINAL_WARP_H
#include <stdint.h>
#include "xgba_r73_source_warp_preflight.h"
static inline int XgbaR76FindOriginalWarpOnTile(
    const uint8_t *warps,unsigned count,unsigned map_width,unsigned map_height,
    unsigned x,unsigned y,unsigned elevation,uint8_t *original_warp_index)
{
    unsigned i;
    if(!warps || !original_warp_index || count==0u || count>255u ||
       map_width==0u || map_height==0u ||
       x>=map_width || y>=map_height || elevation>255u)
        return 0;
    for(i=0u;i<count;i++){
        const uint8_t *p=warps+XGBA_R73_WARP_BYTES*i;
        if(XgbaR73Le16(p)==x && XgbaR73Le16(p+2u)==y &&
           (p[4]==elevation || p[4]==0u)){
            *original_warp_index=(uint8_t)i;
            return 1;
        }
    }
    return 0;
}
#endif

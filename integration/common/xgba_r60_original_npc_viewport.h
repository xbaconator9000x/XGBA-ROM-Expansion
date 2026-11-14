/* R60: authentic per-viewport original NPC admission.
 *
 * The immutable R49 original event store retains every NPC. However real
 * Emerald's 16 hardware objects and four ordinary source NPC palette slots
 * must not allocate every offscreen character on a 40+ NPC foreign map.
 * At the original Fly *landing* only, stage the original NPC records whose
 * source tile positions are in the same 15x11 tile camera envelope.
 *
 * This is a BOUNDED FIRST-SPAWN adapter, not yet runtime scrolling/paging.
 * On moving beyond the initial view, the native source event roster must be
 * refreshed after safe DMA/palette ownership transfer. Never claim the
 * complete world is playable based on one viewport.
 */
#ifndef XGBA_R60_ORIGINAL_NPC_VIEWPORT_H
#define XGBA_R60_ORIGINAL_NPC_VIEWPORT_H
#include <stdint.h>
#define XGBA_R60_WORLD_ROCKET 1u
#define XGBA_R60_WORLD_JOHTO 2u
#define XGBA_R60_HALF_W 7
#define XGBA_R60_HALF_H 5

static inline int XgbaR60OriginalArrival(unsigned world,unsigned group,
    unsigned map,int *x,int *y)
{
    if(!x || !y || group!=0u)return 0;
    if(world==1u && map==9u){*x=14;*y=14;return 1;}
    if(world==2u && map==4u){*x=39;*y=23;return 1;}
    return 0;
}
static inline int XgbaR60OriginalNpcIsInLandingView(
    unsigned world,unsigned group,unsigned map,
    unsigned width,unsigned height,int x,int y)
{
    int origin_x,origin_y;
    if(x<0 || y<0 || (unsigned)x>=width || (unsigned)y>=height)
        return 0;
    if(world==0u)return 1; /* native Emerald original engine unchanged */
    if(!XgbaR60OriginalArrival(world,group,map,&origin_x,&origin_y))
        return 0;
    return x>=origin_x-XGBA_R60_HALF_W &&
           x<=origin_x+XGBA_R60_HALF_W &&
           y>=origin_y-XGBA_R60_HALF_H &&
           y<=origin_y+XGBA_R60_HALF_H;
}
#endif

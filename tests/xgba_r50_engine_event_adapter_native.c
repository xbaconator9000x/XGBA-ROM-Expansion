/* R50: original-layout map events -> real Emerald-shaped guest event arrays.
 * Fixtures are authored; real owner-ROM witness bytes are validated privately.
 * This does NOT claim any foreign original-engine Fly or NPC execution. */
#include "../integration/common/xgba_r50_engine_event_adapter.h"
#include <assert.h>
#include <stdio.h>
static uint8_t index_page[16384],event_page[16384],scratch[16384];
static unsigned reads;
static void w16(uint8_t *p,uint16_t n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void w32(uint8_t *p,uint32_t n){w16(p,(uint16_t)n);w16(p+2,(uint16_t)(n>>16));}
static int fetch(void *ctx,const char *id,uint8_t *out,uint16_t n)
{
    (void)ctx;
    if(n!=16384)return 0;
    if(!strcmp(id,"r49.index.000"))memcpy(out,index_page,n);
    else if(!strcmp(id,"r49.events.000"))memcpy(out,event_page,n);
    else return 0;
    reads++;return 1;
}
static int resolve(void *ctx,uint8_t source,uint16_t sprite,uint8_t *slot)
{
    (void)ctx;
    if(source==2u && sprite==406u){*slot=42u;return 1;}
    if(source<2u && sprite==17u){*slot=17u;return 1;}
    return 0;
}
static void fixture(unsigned row,uint32_t key,unsigned pos,
                    unsigned object_id,unsigned gfx,unsigned x,unsigned y)
{
    uint8_t *ind=index_page+16u*row;
    uint8_t *e=event_page+pos;
    uint8_t *p=e+32u;
    memcpy(e,"X49E",4);w32(e+4,key);
    e[8]=1u;e[9]=1u;e[10]=1u;e[11]=1u;
    w32(e+12,0x100u+row);w32(e+16,0x200u+row);
    p[0]=(uint8_t)object_id;w16(p+1,(uint16_t)gfx);
    w16(p+4,(uint16_t)x);w16(p+6,(uint16_t)y);
    w32(p+16,0x08000000u+0x3000u+row);w16(p+20,0x0800u+row);
    w32(p+24,0xFFFFFFFFu); /* unknown warp destination: quarantine */
    w32(p+24+8+12,0x09005000u+row); /* coord script */
    w32(e+20,XgbaR49Crc32(p,24u+8u+16u+12u));
    w32(e+24,60u);w32(e+28,0x300u+row);
    w32(ind,key);w16(ind+4,0);w16(ind+6,(uint16_t)pos);
    w32(ind+8,92u);w32(ind+12,0x100u+row);
}
int main(void)
{
    struct XgbaR49Reader r={.fetch=fetch,.scratch=scratch,
        .indexed_maps=3,.cached_index_page=XGBA_R49_INVALID_PAGE};
    struct XgbaR50EngineEvents out={0};
    uint8_t old[4096];unsigned before;
    fixture(0,0x000009u,0u,2u,17u,12u,13u);
    fixture(1,0x010009u,92u,2u,17u,14u,13u);
    fixture(2,0x020004u,184u,7u,406u,39u,22u);
    assert(XgbaR50StageEvents(&r,0x000009u,20,20,resolve,NULL,0x02001000u,&out));
    assert(out.active_source_key==0x000009u && out.object_count==1u);
    assert(out.script_origins[0]==0x08003000u && out.original_flags[0]==0x800u);
    assert(XgbaR49Le32(XgbaR50EventBytes(&out)+16)==0x02001000u);
    assert(XgbaR49Le16(XgbaR50EventBytes(&out)+20)==0u);
    assert(out.original_warp_count==1 && out.runtime_warp_count==0 &&
           out.coordinate_count==0 && out.background_count==0);
    assert(XgbaR50StageEvents(&r,0x010009u,24,25,resolve,NULL,0x02001000u,&out));
    assert(out.active_source_key==0x010009u && out.script_origins[0]==0x08003001u);
    memcpy(old,XgbaR50EventBytes(&out),sizeof(old));
    before=out.active_source_key;
    assert(!XgbaR50StageEvents(&r,0x020004u,58,46,NULL,NULL,0x02001000u,&out));
    assert(!XgbaR50StageEvents(&r,0x020004u,20,20,resolve,NULL,0x02001000u,&out));
    assert(out.active_source_key==before && !memcmp(XgbaR50EventBytes(&out),old,sizeof(old)));
    assert(XgbaR50StageEvents(&r,0x020004u,58,46,resolve,NULL,0x02001000u,&out));
    assert(out.active_source_key==0x020004u && XgbaR50EventBytes(&out)[1]==42u &&
           XgbaR50EventBytes(&out)[2]==0u);
    assert(out.script_origins[0]==0x08003002u && XgbaR50EventBytes(&out)[0]==7u);
    memcpy(old,XgbaR50EventBytes(&out),sizeof(old));
    before=reads;
    event_page[184u+32u+16u]^=1u;
    assert(!XgbaR50StageEvents(&r,0x020004u,58,46,resolve,NULL,0x02001000u,&out));
    event_page[184u+32u+16u]^=1u;
    assert(out.active_source_key==0x020004u && !memcmp(old,XgbaR50EventBytes(&out),sizeof(old)));
    assert(!XgbaR50StageEvents(&r,0x010004u,58,46,resolve,NULL,0x02001000u,&out));
    assert(reads>before);
    printf("PASS_R50_GUEST_ENGINE_EVENT_STAGING source_collisions=1 "
           "foreign_sprite_406_mapped=1 original_scripts_retained=1 "
           "foreign_ptrs_quarantined=1 warps_quarantined=1 corrupted_refused=1\n");
    return 0;
}

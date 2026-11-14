/* R60 bounded native viewport using authored R49-shaped source objects.
 * Genuine private Rocket original map has these 9 source coordinates/IDs.
 * No copyrighted frames, scripts or ROM pages included in GitHub.
 */
#define XGBA_R60_FOREIGN_VIEWPORT 1
#include "../integration/common/xgba_r50_engine_event_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t scratch[16384],idx[16384],events[16384];
static struct XgbaR50EngineEvents out;
static const uint16_t ids[]={6,17,9,215,94,94,607,64,0};
static const uint8_t coords[][2]={
    {18,10},{14,13},{16,17},{6,10},{3,10},{20,3},
    {24,11},{16,10},{5,10}
};
static unsigned sprite_calls,reads;
static void le16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void le32(uint8_t *p,uint32_t v){le16(p,(uint16_t)v);le16(p+2,(uint16_t)(v>>16));}
static int page_fetch(void *ctx,const char *name,uint8_t *target,uint16_t len)
{
    (void)ctx;
    if(len!=16384u)return 0;
    if(strcmp(name,"r49.index.000")==0)memcpy(target,idx,len);
    else if(strcmp(name,"r49.events.000")==0)memcpy(target,events,len);
    else return 0;
    ++reads;
    return 1;
}
static int sprite(void *ctx,uint8_t world,uint16_t source_gfx,uint8_t *slot)
{
    static const uint16_t allowed[]={6,17,9,64};
    unsigned i;
    (void)ctx;
    if(world!=1u || !slot)return 0;
    for(i=0;i<4u;i++)if(source_gfx==allowed[i]){
        *slot=(uint8_t)(180u+i);
        ++sprite_calls;
        return 1;
    }
    return 0;
}
static void fixture(void)
{
    uint32_t key=(1u<<16)|9u;
    unsigned i;
    uint8_t *raw=events+32;
    memcpy(events,"X49E",4);
    le32(events+4,key);
    events[8]=9u;
    le32(events+12,UINT32_C(0x01234560));
    le32(events+16,UINT32_C(0x01234580));
    le32(events+24,9u*24u);
    for(i=0;i<9u;i++){
        uint8_t *npc=raw+i*24u;
        npc[0]=(uint8_t)(i+1u);
        le16(npc+1,ids[i]);
        le16(npc+4,coords[i][0]);
        le16(npc+6,coords[i][1]);
        le32(npc+16,UINT32_C(0x08001200)+4u*i);
        le16(npc+20,(uint16_t)(100u+i));
    }
    le32(events+20,XgbaR49Crc32(raw,9u*24u));
    le32(idx,key);
    le16(idx+4,0u);le16(idx+6,0u);
    le32(idx+8,32u+9u*24u);
    le32(idx+12,UINT32_C(0x01234560));
}
int main(void)
{
    struct XgbaR49Reader reader={0};
    uint8_t *b;
    unsigned i;
    int x,y;
    fixture();
    reader.fetch=page_fetch;
    reader.scratch=scratch;
    reader.cached_index_page=XGBA_R49_INVALID_PAGE;
    reader.indexed_maps=1u;
    assert(XgbaR60OriginalArrival(1u,0u,9u,&x,&y));
    assert(x==14 && y==14);
    assert(XgbaR60OriginalArrival(2u,0u,4u,&x,&y));
    assert(x==39 && y==23);
    assert(!XgbaR60OriginalArrival(2u,1u,4u,&x,&y));
    for(i=0u;i<9u;i++){
        int accepted=XgbaR60OriginalNpcIsInLandingView(1u,0u,9u,
                         24u,25u,coords[i][0],coords[i][1]);
        assert(accepted==(i==0u||i==1u||i==2u||i==7u));
    }
    assert(XgbaR50StageEvents(&reader,(1u<<16)|9u,24u,25u,
                 sprite,NULL,UINT32_C(0x08000040),&out));
    assert(out.valid && out.graphics_verified);
    assert(out.active_source_key==((1u<<16)|9u));
    assert(out.object_count==4u);
    assert(out.originals_bytes==9u*24u);
    assert(out.object_bytes==4u*24u);
    assert(out.warp_bytes==0u && out.coordinate_bytes==0u);
    assert(out.background_bytes==0u); /* compacted NPCs are NOT bg events */
    assert(out.script_origins[0]==UINT32_C(0x08001200));
    assert(out.script_origins[3]==UINT32_C(0x08001200)+7u*4u);
    assert(out.original_flags[3]==107u);
    assert(sprite_calls==4u && reads>=2u);
    b=XgbaR50EventBytes(&out);
    assert(b[0]==1u && b[24]==2u && b[48]==3u && b[72]==8u);
    assert(b[1]==180u && b[25]==181u && b[49]==182u && b[73]==183u);
    assert(XgbaR49Le32(b+16)==UINT32_C(0x08000040));
    assert(XgbaR49Le32(b+24+16)==UINT32_C(0x08000040));
    assert(XgbaR49Le32(b+48+16)==UINT32_C(0x08000040));
    assert(XgbaR49Le32(b+72+16)==UINT32_C(0x08000040));
    /* R65: extra ORIGINAL source background record must survive the
     * compacted first-viewport NPC array without phantom background bytes
     * from the five original NPCs that were not staged. */
    {
        uint8_t authored_bg[12]={2u,13u,4u,4u,6u,8u,0u,0u,0u,0u,0u,0u};
        uint8_t *raw=events+32u;
        memcpy(raw+9u*24u,authored_bg,sizeof(authored_bg));
        events[11]=1u; /* original background event count */
        le32(events+24u,9u*24u+12u);
        le32(events+20u,XgbaR49Crc32(raw,9u*24u+12u));
        le32(idx+8u,32u+9u*24u+12u);
        reader.cached_index_page=XGBA_R49_INVALID_PAGE;
        assert(XgbaR50StageEvents(&reader,(1u<<16)|9u,24u,25u,
                 sprite,NULL,UINT32_C(0x08000040),&out));
        assert(out.object_count==4u && out.object_bytes==96u);
        assert(out.originals_bytes==228u);
        assert(out.background_bytes==12u);
        assert(out.warp_bytes==0u && out.coordinate_bytes==0u);
        assert(memcmp(XgbaR50EventBytes(&out)+out.object_bytes,
                      authored_bg,sizeof(authored_bg))==0);
        /* The native Emerald MapEvents intentionally quarantines original
         * background callbacks until their script IDs are translated. */
        assert(out.background_count==0u);
    }
    printf("PASS_R60_ROCKET_REAL_LANDING_COORDINATES "
           "ARCHIVED_NPCS=9 PHYSICAL_ENTRY_NPCS=4 "
           "PRESERVED_FULL_16BIT_IDS=1 OFFMAP_REJECTED=1 "
           "ORIGINAL_SOURCE_EVENTS_UNMODIFIED=1\n");
    return 0;
}

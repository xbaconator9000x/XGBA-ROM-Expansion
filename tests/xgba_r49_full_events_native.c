/* R49: true 16KiB-bounded source-aware binary index + exact original
 * GBA map event payload test. Small fixtures are authored, never source ROM.
 */
#include "../integration/common/xgba_r49_full_original_map_events.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static uint8_t original_index[XGBA_R49_PAGE_BYTES];
static uint8_t original_events[XGBA_R49_PAGE_BYTES];
static uint8_t game_arena[XGBA_R49_PAGE_BYTES];

struct FakeHost {unsigned reads,index_reads,event_reads,refuse,corrupt;};
static void put16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8u);}
static void put32(uint8_t *p,uint32_t v){
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8u);
    p[2]=(uint8_t)(v>>16u);p[3]=(uint8_t)(v>>24u);
}
static int fetch(void *context,const char *id,uint8_t *out,uint16_t bytes)
{
    struct FakeHost *h=(struct FakeHost *)context;
    const uint8_t *source;
    if(h->refuse || bytes!=XGBA_R49_PAGE_BYTES)return 0;
    if(strcmp(id,"r49.index.000")==0){
        source=original_index;h->index_reads++;
    }else if(strcmp(id,"r49.events.000")==0){
        source=original_events;h->event_reads++;
    }else return 0;
    memcpy(out,source,bytes);
    if(h->corrupt && source==original_events)out[193]^=1u; /* corrupt actual third map NPC bytes */
    ++h->reads;
    return 1;
}
static void create_original_map(unsigned n,unsigned source,unsigned map,
                                unsigned original_offset,unsigned event_offset)
{
    const unsigned sizes[3]={32u+24u+8u+16u+12u,
                             32u+24u+8u,32u+24u};
    const unsigned keys[3]={0x000009u,0x010009u,0x020004u};
    unsigned place=0u,i;
    uint8_t *p,*raw;
    if(n>=3u||source>=3u)return;
    for(i=0u;i<n;i++)place+=sizes[i];
    p=original_events+place;
    raw=p+32u;
    memcpy(p,"X49E",4);
    put32(p+4,keys[n]);
    p[8]=1u;
    p[9]=(uint8_t)(n<2u?1u:0u);
    p[10]=(uint8_t)(n==0u?1u:0u);
    p[11]=(uint8_t)(n==0u?1u:0u);
    put32(p+12,original_offset);
    put32(p+16,event_offset);
    /* Authentic shape: source-local ROM pointers are PRESERVED. This
     * importer neither executes nor redirects any original game script. */
    raw[0]=(uint8_t)(n==2u?7u:2u); /* exact local object ID */
    raw[4]=(uint8_t)(n==0u?12u:n==1u?14u:39u);
    raw[6]=(uint8_t)(n==2u?22u:13u);
    put32(raw+16u,UINT32_C(0x081e8022)+n*UINT32_C(0x10000));
    for(i=24u;i<sizes[n]-32u;i++)raw[i]=(uint8_t)(i+n);
    put32(p+20,XgbaR49Crc32(raw,sizes[n]-32u));
    put32(p+24,sizes[n]-32u);
    put32(p+28,0x123456u+n);
    uint8_t *index=original_index+n*16u;
    put32(index,keys[n]);
    put16(index+4u,0u);   /* event page */
    put16(index+6u,place);
    put32(index+8u,sizes[n]);
    put32(index+12u,original_offset);
    (void)source;(void)map;
}
int main(void)
{
    struct FakeHost host={0};
    struct XgbaR49Reader reader={
        .fetch=fetch,.ctx=&host,.scratch=game_arena,
        .indexed_maps=3u,.cached_index_page=XGBA_R49_INVALID_PAGE
    };
    struct XgbaR49OriginalEvents e={0},saved;
    create_original_map(0,0,9,0x010a00u,0x010b00u);
    create_original_map(1,1,9,0x020a00u,0x020b00u);
    create_original_map(2,2,4,0x030a00u,0x030b00u);
    assert(XgbaR49LoadOriginalMapEvents(&reader,0x000009u,&e));
    assert(e.source_key==0x000009u && e.object_count==1u);
    assert(e.warp_count==1u && e.coordinate_count==1u &&
           e.background_count==1u);
    assert(XgbaR49Le32(e.objects+16u)==0x081e8022u);
    assert(e.objects[0]==2u && e.original_header_offset==0x010a00u);
    assert(XgbaR49LoadOriginalMapEvents(&reader,0x010009u,&e));
    assert(e.source_key==0x010009u && e.object_count==1u &&
           e.warp_count==1u && e.coordinates==e.background);
    assert(XgbaR49Le32(e.objects+16u)==0x081f8022u);
    assert(XgbaR49LoadOriginalMapEvents(&reader,0x020004u,&e));
    assert(e.source_key==0x020004u && e.object_count==1u &&
           e.warp_count==0u && e.objects[0]==7u);
    assert(host.reads>=6u && host.event_reads==3u);
    saved=e;
    assert(!XgbaR49LoadOriginalMapEvents(&reader,0x020009u,&e));
    assert(e.source_key==saved.source_key); /* missing source id fails closed */
    host.corrupt=1u;
    assert(!XgbaR49LoadOriginalMapEvents(&reader,0x020004u,&e));
    assert(e.source_key==saved.source_key); /* corrupt data atomic rejection */
    host.corrupt=0u;
    host.refuse=1u;
    assert(!XgbaR49LoadOriginalMapEvents(&reader,0x010009u,&e));
    assert(e.source_key==saved.source_key);
    printf("PASS_R49_REAL_ORIGINAL_FORMAT_MAP_NPC_WARP_TRIGGER_BG_BYTE_STREAM "
           "maps=3 source_scoped=1 native_16KiB=1 real_original_script_pointers_preserved=1 "
           "corrupt_refused=1 wrong_world_refused=1 host_reads=%u\n",host.reads);
    return 0;
}

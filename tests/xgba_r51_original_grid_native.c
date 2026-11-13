/* R51: guest-sized native terrain from original indexed source bytes.
 * These public byte patterns are AUTHOR-CREATED fixtures; private original
 * ROM map cells are tested locally, never copied into GitHub artifacts.
 */
#include "../integration/common/xgba_r51_original_grid_reader.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define GRID_CAP (3u*XGBA_R51_PAGE_BYTES)
static uint8_t grid_pages[GRID_CAP],index_pages[XGBA_R51_PAGE_BYTES],scratch[XGBA_R51_PAGE_BYTES];
static unsigned reads=0u,inject_corruption=0u,refuse_page=0u;
static void put16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8u);}
static void put32(uint8_t *p,uint32_t v){put16(p,v);put16(p+2u,v>>16u);}
static int host(void *ctx,const char *id,uint8_t *target,uint16_t count)
{
    unsigned page;
    (void)ctx;
    if(refuse_page || count!=XGBA_R51_PAGE_BYTES)return 0;
    if(!strcmp(id,"r51.index.000"))memcpy(target,index_pages,count);
    else if(sscanf(id,"r51.grid.%5u",&page)==1 && page<3u)
        memcpy(target,grid_pages+page*XGBA_R51_PAGE_BYTES,count);
    else return 0;
    if(inject_corruption && strstr(id,"r51.grid.") && page==1u)
        target[1000u]^=1u;
    ++reads;return 1;
}
static void fixture(unsigned i,uint32_t key,uint16_t w,uint16_t h,
                    uint32_t off,uint32_t original_src)
{
    uint8_t *p=index_pages+32u*i;
    uint32_t size=(uint32_t)w*h*2u, j;
    for(j=0;j<size+8u;j++)
        grid_pages[off+j]=(uint8_t)((j*17u+i*11u+3u)&255u);
    put32(p,key);put16(p+4,w);put16(p+6,h);
    put32(p+8,off);put32(p+12,size);
    put32(p+16,original_src);put32(p+20,original_src+0x2000u);
    put32(p+24,XgbaR49Crc32(grid_pages+off,size+8u));
    put32(p+28,original_src+0x4000u);
}
int main(void)
{
    struct XgbaR51Reader r={.fetch=host,.scratch=scratch,
        .indexed_maps=3u,.cached_index_page=XGBA_R51_INVALID_PAGE};
    struct XgbaR51NativeGeometry out={0};
    struct XgbaR51IndexRow entry={0};
    unsigned first_reads;
    fixture(0u,0x000009u,20u,20u,0u,0x00100000u);
    /* Deliberate cross-page slice while retaining authentic map identities.
     * Holes here are public test padding, not omitted private source maps. */
    fixture(1u,0x010009u,24u,25u,16000u,0x01000000u);
    fixture(2u,0x020004u,58u,46u,17208u,0x01050000u);
    assert(XgbaR51FindSourceMap(&r,0x020004u,&entry));
    assert(entry.width==58u && entry.height==46u &&
           entry.byte_offset==17208u && entry.grid_bytes==5336u);
    assert(!XgbaR51FindSourceMap(&r,0x000004u,&entry));
    assert(!XgbaR51FindSourceMap(&r,0x030004u,&entry));
    assert(XgbaR51StageOriginalGrid(&r,0x000009u,&out));
    assert(out.valid && out.width==20u && out.height==20u &&
           out.grid_bytes==800u && out.original_grid_offset==0x00100000u);
    assert(XgbaR51NativeBytes(&out)[0]==3u);
    XgbaR51InvalidateGeometry(&out);
    assert(XgbaR51StageOriginalGrid(&r,0x010009u,&out));
    assert(out.width==24u && out.height==25u && out.grid_bytes==1200u);
    assert(XgbaR51NativeBytes(&out)[0]==14u);
    XgbaR51InvalidateGeometry(&out);
    assert(XgbaR51StageOriginalGrid(&r,0x020004u,&out));
    assert(out.width==58u && out.height==46u && out.grid_bytes==5336u);
    assert(out.original_header_offset==0x01054000u);
    assert(XgbaR51NativeBytes(&out)[0]==25u);
    assert(XgbaR51NativeBytes(&out)[5336u]==(uint8_t)((5336u*17u+25u)&255u));
    assert(!XgbaR51StageOriginalGrid(&r,0x020004u,&out));
    XgbaR51InvalidateGeometry(&out);
    first_reads=reads;
    inject_corruption=1u;
    assert(!XgbaR51StageOriginalGrid(&r,0x020004u,&out));
    assert(!out.valid);
    inject_corruption=0u;
    assert(reads>first_reads);
    refuse_page=1u;
    assert(!XgbaR51StageOriginalGrid(&r,0x020004u,&out));
    refuse_page=0u;
    /* Guest cannot fit a 70x70 source map in 5.6KiB but the R51
     * original-source index would still retain it exactly. */
    put16(index_pages+2u*32u+4u,70u);
    put16(index_pages+2u*32u+6u,70u);
    put32(index_pages+2u*32u+12u,9800u);
    assert(!XgbaR51StageOriginalGrid(&r,0x020004u,&out));
    printf("PASS_R51_NATIVE_ORIGINAL_GRID_COLLISION_GEOMETRY "
           "three_source_keys=1 page_boundary=1 16bit_source_cells=1 "
           "crc_checked=1 invalid_world_refused=1 oversized_guest_refused=1 "
           "host_reads=%u\n",reads);
    return 0;
}

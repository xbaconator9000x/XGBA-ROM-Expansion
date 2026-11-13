/* R56 authored sprite-byte fixtures, never copyrighted user ROM pixels. */
#include "../integration/common/xgba_r56_original_obj_reader.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t scratch[XGBA_R56_PAGE_BYTES],head[64];
static uint8_t parts[4][XGBA_R56_PAGE_BYTES],written[8192u+32u+512u+1024u];
static unsigned sizes[4]={1024u,32u,16u,12u},reads,bad_page,bad_padding,bad_second;
static unsigned writes[4];
static void put16(uint8_t *p,unsigned x){p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);}
static void put32(uint8_t *p,uint32_t x){put16(p,(unsigned)x);put16(p+2,(unsigned)(x>>16));}
static int getpage(void *ctx,const char *id,uint8_t *dst,uint16_t length)
{
    const char *names[]={"r56.w2.s4000.f00","r56.w2.s4000.p00",
                         "r56.w2.s4000.o00","r56.w2.s4000.a00"};
    unsigned i;
    (void)ctx;
    if(!strcmp(id,"r56.w2.s4000.meta")){
        if(length!=64u)return 0;
        memcpy(dst,head,64u);
    }else{
        if(length!=XGBA_R56_PAGE_BYTES)return 0;
        for(i=0;i<4u;i++)if(!strcmp(id,names[i]))break;
        if(i==4u || bad_page==i+1u)return 0;
        memcpy(dst,parts[i],length);
        if(bad_padding==i+1u)dst[length-1u]=0x5au;
        if(bad_second==i+1u && reads>4u)dst[0]^=0x80u;
    }
    ++reads;
    return 1;
}
static int stage(void *ctx,unsigned section,const uint8_t *data,
                 uint32_t offset,uint32_t length)
{
    (void)ctx;
    if(section>=4u || offset || length!=sizes[section] ||
       length>sizeof(written))return 0;
    memcpy(written,data,length);
    ++writes[section];
    return !memcmp(written,parts[section],length);
}
static void fixture(void)
{
    unsigned i,j;
    memset(head,0,sizeof(head));
    memcpy(head,"X56S",4);
    head[4]=1u;head[5]=2u;put16(head+6,0x4000u);
    put32(head+8,UINT32_C(0x120040));
    for(i=0;i<4u;i++){
        for(j=0;j<sizes[i];j++)parts[i][j]=(uint8_t)(i*23u+j*7u+9u);
        put32(head+12u+4u*i,sizes[i]);
        put32(head+28u+4u*i,XgbaR49Crc32(parts[i],sizes[i]));
        head[44u+i]=1u;
    }
    head[48]=1u;head[49]=1u;head[50]=32u;head[51]=32u;
    put16(head+52,2u);
    put32(head+60,XgbaR49Crc32(head,60u));
}
int main(void)
{
    struct XgbaR56Reader r={.fetch=getpage,.scratch=scratch};
    struct XgbaR56SourceObject m={0},prior;
    char name[32];
    unsigned i;
    fixture();
    XgbaR56ResourceId(name,2u,0x4000u,'a',0u);
    assert(!strcmp(name,"r56.w2.s4000.a00"));
    assert(XgbaR56ReadMeta(&r,2u,0x4000u,&m));
    assert(m.world==2u && m.original_id==0x4000u &&
           m.frame_count==2u && m.sizes[0]==1024u);
    for(i=0;i<4u;i++)assert(XgbaR56VisitSection(&r,&m,i,stage,NULL));
    for(i=0;i<4u;i++)assert(writes[i]==1u);
    prior=m;
    assert(!XgbaR56ReadMeta(&r,1u,0x4000u,&m));
    assert(m.descriptor_offset==prior.descriptor_offset);
    head[6]^=1u;
    assert(!XgbaR56ReadMeta(&r,2u,0x4000u,&m));
    head[6]^=1u;put32(head+60,XgbaR49Crc32(head,60u));
    assert(XgbaR56ReadMeta(&r,2u,0x4000u,&m));
    parts[0][0]^=0x80u;
    assert(!XgbaR56VisitSection(&r,&m,0u,stage,NULL));
    parts[0][0]^=0x80u;
    bad_page=2u;
    assert(!XgbaR56VisitSection(&r,&m,1u,stage,NULL));
    bad_page=0u;
    bad_padding=3u;
    assert(!XgbaR56VisitSection(&r,&m,2u,stage,NULL));
    bad_padding=0u;
    reads=0u;bad_second=1u;
    assert(!XgbaR56VisitSection(&r,&m,0u,stage,NULL));
    bad_second=0u;
    head[50]=7u;put32(head+60,XgbaR49Crc32(head,60u));
    assert(!XgbaR56ReadMeta(&r,2u,0x4000u,&m));
    printf("PASS_R56_ORIGINAL_OBJ_AUTHENTICATED_16BIT_SOURCE_ID "
           "CRC_META=1 CRC_FRAMES=1 CRC_PALETTE=1 CRC_OAM_ANIMS=1 "
           "NO_TRUNCATION=1 NO_UNVERIFIED_STAGE=1 REFUSED=%u\n",r.refused);
    return 0;
}

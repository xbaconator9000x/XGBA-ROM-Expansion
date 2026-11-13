/* R53 native original-source tileset streaming contract.
 * All source bytes are synthetic authored fixtures, not private ROM contents.
 */
#include "../integration/common/xgba_r53_original_tileset_reader.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t scratch[16384],source_graphics[32768];
static uint8_t source_metatiles[10240],source_attributes[1280];
static uint8_t source_palettes[224],meta[64],destination[32768];
static unsigned fetches,corrupt_graphics,expected_fail,seen_bytes;
static void le16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void le32(uint8_t *p,uint32_t v){le16(p,v);le16(p+2,v>>16);}
static int fetch(void *ctx,const char *id,uint8_t *dst,uint16_t count)
{
    const uint8_t *asset=0;
    unsigned length=0,page=0;
    (void)ctx;
    if(strncmp(id,"r53.w1.v2.t00000040.",20))return 0;
    if(!strcmp(id+20,"meta")){
        if(count!=64u)return 0;
        memcpy(dst,meta,count);++fetches;return 1;
    }
    if(count!=16384u)return 0;
    if(id[22]<'0'||id[22]>'9'||id[23]!=0)return 0;
    page=(unsigned)(id[21]-'0')*10u+(unsigned)(id[22]-'0');
    switch(id[20]){
    case 'g':asset=source_graphics;length=20480u;break;
    case 'm':asset=source_metatiles;length=10240u;break;
    case 'a':asset=source_attributes;length=1280u;break;
    case 'p':asset=source_palettes;length=224u;break;
    default:return 0;
    }
    if(page*16384u>=length)return 0;
    memset(dst,0,16384u);
    if(length-page*16384u>16384u)
        memcpy(dst,asset+page*16384u,16384u);
    else
        memcpy(dst,asset+page*16384u,length-page*16384u);
    if(id[20]=='g'&&corrupt_graphics&&fetches>3u)dst[0]^=1u;
    ++fetches;
    return 1;
}
static int writer(void *ctx,uint8_t section,const uint8_t *src,uint32_t off,uint32_t size)
{
    (void)ctx;
    if(section!=0u||off+size>sizeof(destination))return 0;
    memcpy(destination+off,src,size);
    seen_bytes+=(unsigned)size;
    return 1;
}
static void setup(void)
{
    unsigned i;
    const uint8_t *parts[]={source_graphics,source_metatiles,source_attributes,source_palettes};
    const unsigned sizes[]={20480,10240,1280,224};
    for(i=0;i<sizeof(source_graphics);i++)source_graphics[i]=(uint8_t)(i*3u+11u);
    for(i=0;i<sizeof(source_metatiles);i++)source_metatiles[i]=(uint8_t)(i*5u+3u);
    for(i=0;i<sizeof(source_attributes);i++)source_attributes[i]=(uint8_t)(i+7u);
    for(i=0;i<sizeof(source_palettes);i++)source_palettes[i]=(uint8_t)(i*9u+1u);
    memcpy(meta,"X53T",4);
    meta[4]=1u;meta[5]=2u;meta[6]=0u;meta[7]=1u;
    le32(meta+8,0x40u);
    for(i=0;i<4u;i++){
        le32(meta+12u+4u*i,sizes[i]);
        le32(meta+40u+4u*i,XgbaR49Crc32(parts[i],sizes[i]));
        meta[34u+i]=(uint8_t)((sizes[i]+16383u)/16384u);
    }
    le16(meta+28,640u);le16(meta+30,640u);
    meta[32]=2u;meta[33]=7u;
    le32(meta+56,UINT32_C(0x12345678));
    le32(meta+60,XgbaR49Crc32(meta,60));
}
int main(void)
{
    struct XgbaR53Reader reader={.fetch=fetch,.scratch=scratch};
    struct XgbaR53Tileset m={0},prior;
    char id[32];
    setup();
    XgbaR53ResourceId(id,1u,2u,0x40u,'g',1u);
    assert(!strcmp(id,"r53.w1.v2.t00000040.g01"));
    assert(XgbaR53MetaLoad(&reader,1u,2u,0x40u,0u,&m));
    assert(m.tiles==640u && m.palettes==7u && m.pages[0]==2u);
    assert(m.attribute_bytes==2u && m.original_compression==1u);
    for(unsigned i=0;i<4u;i++)
        assert(XgbaR53VisitSection(&reader,&m,i,0,0));
    seen_bytes=0u;
    assert(XgbaR53VisitSection(&reader,&m,0,writer,0));
    assert(seen_bytes==20480u && !memcmp(destination,source_graphics,20480u));
    prior=m;
    assert(!XgbaR53MetaLoad(&reader,2u,2u,0x40u,0u,&m));
    assert(m.descriptor_offset==prior.descriptor_offset);
    meta[12]^=1u;
    assert(!XgbaR53MetaLoad(&reader,1u,2u,0x40u,0u,&m));
    meta[12]^=1u;le32(meta+60,XgbaR49Crc32(meta,60));
    assert(!XgbaR53MetaLoad(&reader,1u,2u,0x40u,1u,&m));
    assert(XgbaR53MetaLoad(&reader,1u,2u,0x40u,0u,&m));
    source_graphics[0]^=1u;
    assert(!XgbaR53VisitSection(&reader,&m,0,0,0));
    source_graphics[0]^=1u;
    corrupt_graphics=1u;fetches=0u;
    expected_fail=XgbaR53VisitSection(&reader,&m,0,writer,0);
    assert(!expected_fail);
    printf("PASS_R53_REAL_SOURCE_PAGE_DECODING_CONTRACT "
        "source_identity=1 graphics_20KiB_paged=1 "
        "metatiles=1 collision_attributes=1 palettes=1 "
        "CRC_fail_closed=1 reads=%u\n",reader.fetches);
    return 0;
}

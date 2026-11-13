/* R53: source-authenticated 3-ROM genuine tileset loader.
 * Importer keeps original asset bytes PRIVATE, host SHA verifies each page,
 * guest checks metadata AND per-original-content CRC before publishing.
 * One caller-owned 16 KiB scratch: no new hidden static page buffers.
 * Original 640/512 tile-index splits and BG palette banks from R52.
 */
#ifndef XGBA_R53_ORIGINAL_TILESET_READER_H
#define XGBA_R53_ORIGINAL_TILESET_READER_H
#include "xgba_r49_full_original_map_events.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define XGBA_R53_BYTES 16384u
#define XGBA_R53_HEADER 64u
#define XGBA_R53_SECTIONS 4u
#define XGBA_R53_INVALID_WORLD 3u
typedef int (*XgbaR53Fetch)(void *,const char *,uint8_t *,uint16_t);
typedef int (*XgbaR53Write)(void *,uint8_t,const uint8_t *,uint32_t,uint32_t);
struct XgbaR53Reader{
    XgbaR53Fetch fetch;
    void *ctx;
    uint8_t *scratch;
    uint32_t fetches,verified_sections,refused;
};
struct XgbaR53Tileset{
    uint8_t world,version,is_secondary,original_compression;
    uint32_t descriptor_offset,sizes[XGBA_R53_SECTIONS];
    uint16_t tiles,metatiles;
    uint8_t attribute_bytes,palettes,pages[XGBA_R53_SECTIONS];
    uint32_t crc[XGBA_R53_SECTIONS],original_descriptor_crc,metadata_crc;
};
static inline void XgbaR53ResourceId(char id[32],unsigned world,unsigned version,
                                     uint32_t offset,char part,unsigned page)
{
    unsigned i;
    static const char digits[]="0123456789abcdef";
    const char base[]="r53.w0.v0.t00000000.meta";
    for(i=0;i<sizeof(base);i++)id[i]=base[i];
    id[5]=(char)('0'+world);id[8]=(char)('0'+version);
    for(i=0;i<8u;i++)id[11+i]=digits[(offset>>(28u-4u*i))&15u];
    if(part){
        id[20]=part;
        id[21]=(char)('0'+(page/10u)%10u);
        id[22]=(char)('0'+page%10u);
        id[23]=0;
    }
}
static inline int XgbaR53MetaLoad(struct XgbaR53Reader *r,
    unsigned world,unsigned version,uint32_t offset,unsigned secondary,
    struct XgbaR53Tileset *result)
{
    uint32_t counts[4],i;
    uint16_t primary;
    uint8_t *p;
    char id[32];
    struct XgbaR53Tileset next={0};
    if(!r || !r->fetch || !r->scratch || !result || world>=3u ||
       version>2u || secondary>1u || offset>0x01ffffffu)return 0;
    XgbaR53ResourceId(id,world,version,offset,0,0);
    if(r->fetch(r->ctx,id,r->scratch,XGBA_R53_HEADER)!=1){
        ++r->refused;return 0;
    }
    ++r->fetches;p=r->scratch;
    if(memcmp(p,"X53T",4) || p[4]!=world || p[5]!=version ||
       p[6]!=secondary || p[7]>1u ||
       XgbaR49Le32(p+8)!=offset ||
       XgbaR49Le32(p+60)!=XgbaR49Crc32(p,60)){
        ++r->refused;return 0;
    }
    next.world=(uint8_t)world;next.version=(uint8_t)version;
    next.is_secondary=(uint8_t)secondary;next.original_compression=p[7];
    next.descriptor_offset=offset;
    for(i=0;i<4u;i++)next.sizes[i]=XgbaR49Le32(p+12+4u*i);
    next.tiles=XgbaR49Le16(p+28);next.metatiles=XgbaR49Le16(p+30);
    next.attribute_bytes=p[32];next.palettes=p[33];
    for(i=0;i<4u;i++)next.pages[i]=p[34+i];
    for(i=0;i<4u;i++)next.crc[i]=XgbaR49Le32(p+40u+4u*i);
    next.original_descriptor_crc=XgbaR49Le32(p+56);
    next.metadata_crc=XgbaR49Le32(p+60);
    primary=version?640u:512u;
    counts[0]=secondary?1024u-primary:primary;
    counts[1]=counts[0];
    counts[2]=version==1u?4u:2u;
    counts[3]=secondary?13u-(version?7u:6u):(version?7u:6u);
    if(next.tiles!=counts[0] || next.metatiles!=counts[1] ||
       next.attribute_bytes!=counts[2] || next.palettes!=counts[3] ||
       next.sizes[0]!=next.tiles*32u ||
       next.sizes[1]!=next.metatiles*16u ||
       next.sizes[2]!=next.metatiles*next.attribute_bytes ||
       next.sizes[3]!=next.palettes*32u){
        ++r->refused;return 0;
    }
    for(i=0;i<4u;i++){
        if(next.pages[i]!=(next.sizes[i]+XGBA_R53_BYTES-1u)/XGBA_R53_BYTES ||
           !next.pages[i] || next.pages[i]>4u){
            ++r->refused;return 0;
        }
    }
    *result=next;
    return 1;
}
/* Verify full original section before invoking a writer. This requires two
 * passes because the shared scratch is overwritten after every XGBA fetch.
 * On second pass CRC is checked again; a provider mismatch rejects map
 * commit, even if a destination cache was modified during that pass.
 */
static inline int XgbaR53VisitSection(struct XgbaR53Reader *r,
  const struct XgbaR53Tileset *meta,unsigned section,
  XgbaR53Write writer,void *writer_ctx)
{
    unsigned pass,page,pages;
    uint32_t size,crc,offset,chunk;
    char id[32];
    const char types[]="gmap";
    if(!r || !r->fetch || !r->scratch || !meta || section>=4u ||
       meta->world>=3u || meta->version>2u || !meta->pages[section] ||
       meta->pages[section]>4u)return 0;
    size=meta->sizes[section];pages=meta->pages[section];
    for(pass=0;pass<(writer?2u:1u);pass++){
        crc=0xffffffffu;offset=0u;
        for(page=0;page<pages;page++){
            uint32_t i;
            XgbaR53ResourceId(id,meta->world,meta->version,
                               meta->descriptor_offset,types[section],page);
            if(r->fetch(r->ctx,id,r->scratch,XGBA_R53_BYTES)!=1){
                ++r->refused;return 0;
            }
            ++r->fetches;
            chunk=size-offset;
            if(chunk>XGBA_R53_BYTES)chunk=XGBA_R53_BYTES;
            for(i=0;i<chunk;i++){
                unsigned bit;
                crc^=r->scratch[i];
                for(bit=0;bit<8u;bit++)
                    crc=(crc>>1u)^((crc&1u)?UINT32_C(0xedb88320):0u);
            }
            if(pass && !writer(writer_ctx,(uint8_t)section,r->scratch,offset,chunk)){
                ++r->refused;return 0;
            }
            offset+=chunk;
        }
        if(offset!=size || ~crc!=meta->crc[section]){
            ++r->refused;return 0;
        }
    }
    ++r->verified_sections;
    return 1;
}
#endif

/* R56 private ORIGINAL source-OBJ byte contract.
 * Host verifies SHA-256 per 16KiB resource; native verifies exact source
 * metadata and all section CRCs before publication to R55. This reader
 * DOES NOT invent Emerald sprite art/OAM or certify that foreign Fly works.
 *
 * No private source pixels, palettes, scripts or ROM bytes in this file.
 */
#ifndef XGBA_R56_ORIGINAL_OBJ_READER_H
#define XGBA_R56_ORIGINAL_OBJ_READER_H
#include "xgba_r49_full_original_map_events.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define XGBA_R56_PAGE_BYTES 16384u
#define XGBA_R56_META_BYTES 64u
#define XGBA_R56_SECTIONS 4u
#define XGBA_R56_MAX_FRAMES_BYTES 8192u
typedef int (*XgbaR56Fetch)(void *,const char *,uint8_t *,uint16_t);
typedef int (*XgbaR56Write)(void *,unsigned,const uint8_t *,uint32_t,uint32_t);
struct XgbaR56Reader {
    XgbaR56Fetch fetch;
    void *context;
    uint8_t *scratch; /* BORROWED 16 KiB, no hidden second arena */
    uint32_t page_reads,refused;
};
struct XgbaR56SourceObject {
    uint8_t world,width,height,frame_count,original_compression;
    uint16_t original_id;
    uint32_t descriptor_offset;
    uint32_t sizes[XGBA_R56_SECTIONS],crc[XGBA_R56_SECTIONS];
    uint8_t pages[XGBA_R56_SECTIONS];
    uint32_t metadata_crc;
};
static inline void XgbaR56ResourceId(char id[32],unsigned world,
    uint16_t original_id,char section,unsigned page)
{
    static const char hex[]="0123456789abcdef";
    const char model[]="r56.w0.s0000.meta";
    unsigned i;
    for(i=0;i<sizeof(model);i++)id[i]=model[i];
    id[5]=(char)('0'+world);
    for(i=0;i<4u;i++)id[8+i]=hex[(original_id>>(12u-4u*i))&15u];
    if(section){
        id[13]=section;
        id[14]=(char)('0'+(page/10u)%10u);
        id[15]=(char)('0'+page%10u);
        id[16]=0;
    }
}
static inline int XgbaR56ValidGbaObjectShape(unsigned w,unsigned h)
{
    return (w==8u && (h==8u || h==16u || h==32u)) ||
           (w==16u && (h==8u || h==16u || h==32u)) ||
           (w==32u && (h==8u || h==16u || h==32u || h==64u)) ||
           (w==64u && (h==32u || h==64u));
}
static inline int XgbaR56ReadMeta(struct XgbaR56Reader *reader,
    unsigned world,uint16_t original_id,struct XgbaR56SourceObject *result)
{
    struct XgbaR56SourceObject next={0};
    char id[32];
    unsigned i;
    const uint8_t *p;
    uint32_t frame_bytes;
    if(!reader || !reader->fetch || !reader->scratch || !result ||
       world>=3u)return 0;
    XgbaR56ResourceId(id,world,original_id,0,0);
    if(reader->fetch(reader->context,id,reader->scratch,
                      XGBA_R56_META_BYTES)!=1){
        ++reader->refused;return 0;
    }
    ++reader->page_reads;
    p=reader->scratch;
    if(memcmp(p,"X56S",4)!=0 || p[4]!=1u || p[5]!=world ||
       XgbaR49Le16(p+6)!=original_id ||
       XgbaR49Le32(p+60)!=XgbaR49Crc32(p,60) ||
       p[49]!=1u || p[48]>6u || p[54]!=0u ||
       p[55]!=0u || XgbaR49Le32(p+56)!=0u){
        ++reader->refused;return 0;
    }
    next.world=(uint8_t)world;
    next.original_id=original_id;
    next.descriptor_offset=XgbaR49Le32(p+8);
    next.original_compression=p[48];
    next.width=p[50];next.height=p[51];
    next.frame_count=(uint8_t)XgbaR49Le16(p+52);
    next.metadata_crc=XgbaR49Le32(p+60);
    if(!XgbaR56ValidGbaObjectShape(next.width,next.height) ||
       next.width>64u || next.height>64u ||
       (next.width&7u) || (next.height&7u) ||
       !next.frame_count || next.frame_count>16u ||
       next.descriptor_offset>0x01ffffffu){
        ++reader->refused;return 0;
    }
    frame_bytes=(uint32_t)next.width*next.height/2u*
                next.frame_count;
    for(i=0;i<XGBA_R56_SECTIONS;i++){
        next.sizes[i]=XgbaR49Le32(p+12u+4u*i);
        next.crc[i]=XgbaR49Le32(p+28u+4u*i);
        next.pages[i]=p[44u+i];
        if(!next.sizes[i] ||
           next.pages[i]!=(next.sizes[i]+XGBA_R56_PAGE_BYTES-1u)/
                                  XGBA_R56_PAGE_BYTES ||
           next.pages[i]!=1u){
            ++reader->refused;return 0;
        }
    }
    if(next.sizes[0]!=frame_bytes ||
       frame_bytes>XGBA_R56_MAX_FRAMES_BYTES ||
       next.sizes[1]!=32u ||
       next.sizes[2]<4u || next.sizes[2]>512u ||
       (next.sizes[2]&3u) ||
       next.sizes[3]<4u || next.sizes[3]>1024u ||
       (next.sizes[3]&1u)){
        ++reader->refused;return 0;
    }
    *result=next; /* Never expose partially verified metadata. */
    return 1;
}
/* All four authentic sections are source-keyed; the caller MUST retain any
 * staged frames/palette/OAM/animation backing until Emerald's OBJ/DMA lifetime
 * ends. A writer does not commit a live sprite; only successful 4-section
 * verification can authorize the separate R55 registry callback. */
static inline int XgbaR56VisitSection(struct XgbaR56Reader *reader,
    const struct XgbaR56SourceObject *m,unsigned section,
    XgbaR56Write writer,void *writer_ctx)
{
    const char parts[]="fpoa";
    char id[32];
    uint32_t pass,crc,i;
    if(!reader || !reader->fetch || !reader->scratch || !m ||
       m->world>=3u || section>=4u ||
       m->pages[section]!=1u || !m->sizes[section] ||
       m->sizes[section]>XGBA_R56_PAGE_BYTES)return 0;
    XgbaR56ResourceId(id,m->world,m->original_id,parts[section],0);
    for(pass=0;pass<(writer?2u:1u);pass++){
        if(reader->fetch(reader->context,id,reader->scratch,
                         XGBA_R56_PAGE_BYTES)!=1){
            ++reader->refused;return 0;
        }
        ++reader->page_reads;
        crc=XgbaR49Crc32(reader->scratch,m->sizes[section]);
        if(crc!=m->crc[section]){
            ++reader->refused;return 0;
        }
        if(pass && !writer(writer_ctx,section,reader->scratch,
                           0u,m->sizes[section])){
            ++reader->refused;return 0;
        }
    }
    /* Reject differing data between CRC-verified preflight and staging
     * through a second on-use check; no stale scratch page pointers. */
    for(i=m->sizes[section];i<XGBA_R56_PAGE_BYTES;i++){
        if(reader->scratch[i]!=0u){++reader->refused;return 0;}
    }
    return 1;
}
#endif

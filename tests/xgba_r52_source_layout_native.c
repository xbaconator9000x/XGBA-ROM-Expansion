/* R52: authored full original-layout ABI fixture — 512 vs 640 split,
 * source identity collisions and CRC failure. No Nintendo ROM data.
 */
#include "../integration/common/xgba_r52_source_layout_profile.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t page[XGBA_R52_PAGE],scratch[XGBA_R52_PAGE];
static unsigned reads,missing;
static void le16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void le32(uint8_t *p,uint32_t v){le16(p,v);le16(p+2,v>>16);}
static int fetch(void *ctx,const char *id,uint8_t *out,uint16_t n)
{
    (void)ctx;
    if(missing || strcmp(id,"r52.mapmeta.000") || n!=XGBA_R52_PAGE)return 0;
    memcpy(out,page,n);++reads;return 1;
}
static void row(unsigned i,uint32_t key,unsigned version,unsigned supported)
{
    uint8_t *p=page+32u*i;
    unsigned wide=version!=0u;
    le32(p,key);p[4]=(uint8_t)version;
    p[5]=version==1u?2u:0u;p[6]=version==1u?2u:0u;
    le16(p+8,wide?640:512);le16(p+10,wide?640:512);
    p[12]=wide?7u:6u;p[13]=version==1u?4u:2u;
    p[14]=(uint8_t)(supported?(1u | (wide?2u:0u)):0u);
    p[15]=3u;
    le32(p+16,0x1000+i*0x100);
    le32(p+20,0x2000+i*0x100);
    le32(p+24,0x3000+i*0x100);
    le32(p+28,XgbaR49Crc32(p,28));
}
int main(void)
{
    struct XgbaR52Reader rd={.fetch=fetch,.scratch=scratch,
        .indexed_maps=3u,.cached_page=XGBA_R52_PAGE_INVALID};
    struct XgbaR52MapProfile p={0},prior;
    uint16_t attr;
    row(0,0x000009u,0,1);
    row(1,0x010009u,2,1);
    row(2,0x020004u,2,1);
    assert(XgbaR52LoadProfile(&rd,0x000009u,&p) && p.metatiles_in_primary==512u);
    assert(XgbaR52NativePrimarySplit(&p)==512u && p.attribute_bytes==2u);
    assert(XgbaR52LoadProfile(&rd,0x010009u,&p) && p.version==2u);
    assert(p.metatiles_in_primary==640u && p.tiles_in_primary==640u);
    assert(p.attribute_bytes==2u && p.palettes_in_primary==7u);
    assert(XgbaR52LoadProfile(&rd,0x020004u,&p) && p.version==2u);
    assert(XgbaR52TranslateAttribute(&p,0x2002u,&attr) && attr==0x2002u);
    assert(!XgbaR52TranslateAttribute(&p,0x1002002u,&attr));
    prior=p;
    assert(!XgbaR52LoadProfile(&rd,0x020009u,&p) && p.key==prior.key);
    assert(!XgbaR52LoadProfile(&rd,0x030004u,&p) && p.key==prior.key);
    le32(page+32u+16,0u);rd.cached_page=XGBA_R52_PAGE_INVALID;
    assert(!XgbaR52LoadProfile(&rd,0x010009u,&p) && p.key==prior.key);
    row(1,0x010009u,2,1);rd.cached_page=XGBA_R52_PAGE_INVALID;
    assert(XgbaR52LoadProfile(&rd,0x010009u,&p));
    row(1,0x010009u,3,0);rd.cached_page=XGBA_R52_PAGE_INVALID;
    assert(!XgbaR52LoadProfile(&rd,0x010009u,&p));
    row(1,0x010009u,1,1);rd.cached_page=XGBA_R52_PAGE_INVALID;
    assert(XgbaR52LoadProfile(&rd,0x010009u,&p));
    assert(p.attribute_bytes==4u);
    assert(XgbaR52TranslateAttribute(&p,0x40000142u,&attr) &&
           attr==(0x42u|0x2000u));
    assert(!XgbaR52TranslateAttribute(&p,0x00000142u,&attr));
    missing=1u;rd.cached_page=XGBA_R52_PAGE_INVALID;
    assert(!XgbaR52LoadProfile(&rd,0x020004u,&p));
    printf("PASS_R52_SOURCE_MAP_LAYOUT_VERSIONS native_split_512_640=1 "
           "source_namespace=1 CRC_fail_closed=1 no_truncation=1 reads=%u\n",reads);
    return 0;
}

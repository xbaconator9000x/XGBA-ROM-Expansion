/* R19: native original Emerald Littleroot <-> Route101 transitions.
 * Both source packs are simultaneously resident in real guest EWRAM.
 * No emulator-side map warp or CPU-RAM injection is permitted.
 */
#ifndef XGBA_R19_CONNECTED_MAPS_H
#define XGBA_R19_CONNECTED_MAPS_H
static uint32_t r19_word(struct mCore *core,uint32_t proof,unsigned field)
{
    return core->busRead32(core,proof+field*4u);
}
static void r19_wait(struct mCore *c,uint32_t p,unsigned map,unsigned limit)
{
    for(unsigned i=0;i<limit && r19_word(c,p,3)!=map;++i) {
        c->setKeys(c,0);
        c->runFrame(c);
    }
    if(r19_word(c,p,3)!=map) {
        fprintf(stderr,"R19_NATIVE_MAP_DIAG expected=%u got=%u x=%u y=%u "
                       "transitions=%u tick=%u\n",map,r19_word(c,p,3),
                r19_word(c,p,15),r19_word(c,p,16),
                r19_word(c,p,4),r19_word(c,p,17));
        fail("R19 Emerald genuine connected map crossing never happened");
    }
}
static void r19_verify(struct mCore *c,uint32_t p,
                       const struct ResourceFile *r,
                       uint64_t routeOffset,uint32_t routeLen,unsigned map)
{
    if(r19_word(c,p,0)!=XGBA_R7_MMIO_MAGIC ||
       r19_word(c,p,1)!=3u || r19_word(c,p,2)!=0u ||
       r19_word(c,p,3)!=map || r19_word(c,p,5)<2u ||
       (r19_word(c,p,5)&1u))
        fail("R19 source-built Emerald map/loader proof missing");
    uint32_t a=r19_word(c,p,21),b=r19_word(c,p,22);
    if(a<0x02000000u || b<a+r->length ||
       b+routeLen>0x02040000u ||
       r19_word(c,p,7)!=(map==9?a:b))
        fail("R19 both external map resident arenas overlap/outside real EWRAM");
    if(routeLen>16384 || r->length>16384)
        fail("R19 native map resource exceeds physical guest transfer contract");
    FILE *file=fopen(r->path,"rb");
    if(!file)fail("R19 original resource file cannot be read");
    uint8_t data[16384];
    uint64_t offsets[2]={r->offset,routeOffset};
    unsigned lengths[2]={(unsigned)r->length,routeLen};
    uint32_t arenas[2]={a,b};
    for(unsigned k=0;k<2;++k) {
        if(fseeko(file,(off_t)offsets[k],SEEK_SET) ||
           fread(data,1,lengths[k],file)!=lengths[k])
            fail("R19 cannot independently read original source map pack");
        for(unsigned i=0;i<lengths[k];++i)
            if(c->busRead8(c,arenas[k]+i)!=data[i])
                fail("R19 concurrently live external pack changed or collided");
    }
    unsigned which=map==9?0:1;
    if(fseeko(file,(off_t)offsets[which],SEEK_SET) ||
       fread(data,1,lengths[which],file)!=lengths[which])
        fail("R19 cannot independently inspect active Emerald map");
    fclose(file);
    unsigned offs[8];
    for(unsigned i=0;i<8;++i)offs[i]=r14_le(data+4*i);
    if(offs[0]!=0x52313450u || offs[1]!=lengths[which] ||
       offs[2]+800>lengths[which] ||
       r19_word(c,p,10)!=arenas[which]+offs[3] ||
       r19_word(c,p,11)!=arenas[which]+offs[4] ||
       r19_word(c,p,12)!=arenas[which]+offs[5] ||
       r19_word(c,p,13)!=arenas[which]+offs[6] ||
       r19_word(c,p,14)!=arenas[which]+offs[7])
        fail("R19 original Emerald active map/secondary pointers not external");
    uint32_t grid=r19_word(c,p,8),stride=r19_word(c,p,9);
    if(grid<0x02000000u || stride!=35u || grid+35*34*2>0x02040000u)
        fail("R19 actual original Emerald field camera map is not EWRAM");
    for(unsigned y=0;y<20;++y)
        for(unsigned x=0;x<20;++x) {
            unsigned real=c->busRead16(c,grid+2*((y+7)*stride+x+7));
            unsigned index=offs[2]+2*(y*20+x);
            unsigned expected=data[index]|((unsigned)data[index+1]<<8);
            if(real!=expected) {
                fprintf(stderr,"R19 original map data mismatch map=%u at %u,%u actual=%04x wanted=%04x\n",
                        map,x,y,real,expected);
                fail("R19 native Emerald map geometry did not survive transition");
            }
        }
    r17_check_tiles(c,data+offs[4],offs[5]-offs[4]);
}
static void xgba_r19_connected_run(struct mCore *core,uint32_t p,
    const char *dir,const struct XgbaGbaDevice *device,
    const struct ResourceFile *resource,uint64_t routeOffset,
    uint32_t routeLen,int enabled)
{
    if(!p || !dir || !resource->second_id || !routeLen)
        fail("R19 original Emerald connection requires two real external map packs");
    if(!enabled) {
        if(r19_word(core,p,1)!=0xE19u || device->successful_reads ||
           device->failed_reads || resource->reads || resource->lookups)
            fail("R19 disabled mode must fail closed with zero native provider reads");
        puts("PASS_R19_DISABLED_CONNECTED_MAPS_ZERO_READS");
        return;
    }
    r14_wait(core,150);
    r19_verify(core,p,resource,routeOffset,routeLen,9);
    if(device->failed_reads || device->successful_reads!=3u)
        fail("R19 Emerald startup must acquire bridge plus both connected maps");
    r17_frame(core,dir,"01-original-littleroot-two-maps-loaded");
    unsigned x0=r19_word(core,p,15),y0=r19_word(core,p,16);
    fprintf(stderr,"R19_START_MAP original_littleroot x=%u y=%u packs=%u\n",
            x0,y0,device->successful_reads);
    for(unsigned i=0;i<22 && r19_word(core,p,3)!=16u;++i) {
        r14_press(core,1u<<6,16); /* GBA D-pad UP */
        r14_wait(core,8);
    }
    r19_wait(core,p,16,160);
    r19_verify(core,p,resource,routeOffset,routeLen,16);
    r17_frame(core,dir,"02-real-route101-external-crossing");
    if(r19_word(core,p,4)<1u || !r19_word(core,p,18))
        fail("R19 physical boundary navigation did not transition real Emerald");
    unsigned entered_y=r19_word(core,p,16);
    for(unsigned i=0;i<23 && r19_word(core,p,3)!=9u;++i) {
        r14_press(core,1u<<7,16); /* GBA D-pad DOWN */
        r14_wait(core,8);
    }
    r19_wait(core,p,9,120);
    r19_verify(core,p,resource,routeOffset,routeLen,9);
    r17_frame(core,dir,"03-return-littleroot-live-packs");
    if(r19_word(core,p,4)<2u || !r19_word(core,p,19) ||
       device->successful_reads!=3u || device->failed_reads)
        fail("R19 return crossing or simultaneous pack retention failed");
    printf("PASS_R19_REAL_EMERALD_CONNECTED_DPAD world=original_emerald "
           "map_sequence=9,16,9 transitions=%u player_x=%u player_y=%u "
           "route_arrival_y=%u concurrent_packs=2 provider_reads=%u "
           "native_bg_vram=1 native_map_grid=1\n",
           r19_word(core,p,4),r19_word(core,p,15),r19_word(core,p,16),
           entered_y,device->successful_reads);
}
#endif

/* R28: real pinned Pokemon Emerald three-map physical D-pad cache witness.
 * Read the original guest's EWRAM, backup map, tile sources and LCD:
 * no host pokes, teleportation, fabricated framebuffers or simulated maps. */
#ifndef XGBA_R28_THREE_MAPS_H
#define XGBA_R28_THREE_MAPS_H

static uint32_t r28_key(unsigned map)
{
    if(map==9u)return 0u;
    if(map==16u)return 1u;
    if(map==10u)return 2u;
    fail("R28 invalid map target");
    return UINT32_MAX;
}
static void r28_verify(struct mCore *core,uint32_t proof,
    const struct ResourceFile *res,uint64_t route_offset,uint32_t route_length,
    uint64_t oldale_offset,uint32_t oldale_length,unsigned map)
{
    if(r19_word(core,proof,0)!=XGBA_R7_MMIO_MAGIC ||
       r19_word(core,proof,1)!=3u || r19_word(core,proof,2)!=0u ||
       r19_word(core,proof,3)!=map || r19_word(core,proof,32)!=0u ||
       r19_word(core,proof,36)!=0u)
        fail("R28 original Emerald map state, group or cache errors");
    uint32_t a=r19_word(core,proof,21),b=r19_word(core,proof,22);
    uint32_t slot=r19_word(core,proof,38);
    uint32_t slots[2]={a,b},ids[2]={r19_word(core,proof,39),r19_word(core,proof,40)};
    uint32_t active=r28_key(map);
    uint64_t offsets[3]={res->offset,route_offset,oldale_offset};
    uint32_t lengths[3]={(uint32_t)res->length,route_length,oldale_length};
    unsigned active_slots=0;
    if(slot>=2u || a<0x02000000u || b<a+lengths[0] ||
       b+lengths[1]>0x02040000u || b+lengths[2]>0x02040000u ||
       r19_word(core,proof,7)!=slots[slot] ||
       ids[slot]!=active || ids[0]>=3u || ids[1]>=3u ||
       ids[0]==ids[1] || r19_word(core,proof,37)<2u)
        fail("R28 active source is not inside real two-slot EWRAM cache");
    FILE *fp=fopen(res->path,"rb");
    if(!fp)fail("R28 pinned external source file could not be opened");
    uint8_t buf[16384];
    uint32_t active_offsets[8]={0};
    for(unsigned s=0;s<2u;++s) {
        unsigned k=ids[s],n=lengths[k];
        if(n>16384u || !n ||
           fseeko(fp,(off_t)offsets[k],SEEK_SET) ||
           fread(buf,1,n,fp)!=n)
            fail("R28 external source offset or exact transfer failed");
        for(unsigned i=0;i<n;++i)
            if(core->busRead8(core,slots[s]+i)!=buf[i])
                fail("R28 cache resident bytes differ from source SHA-backed sidecar");
        ++active_slots;
        if(k==active) {
            for(unsigned i=0;i<8u;++i)active_offsets[i]=r14_le(buf+4*i);
            if(active_offsets[0]!=0x52313450u ||
               active_offsets[1]!=n ||
               active_offsets[2]+800u>active_offsets[3] ||
               r19_word(core,proof,10)!=slots[s]+active_offsets[3] ||
               r19_word(core,proof,11)!=slots[s]+active_offsets[4] ||
               r19_word(core,proof,12)!=slots[s]+active_offsets[5] ||
               r19_word(core,proof,13)!=slots[s]+active_offsets[6] ||
               r19_word(core,proof,14)!=slots[s]+active_offsets[7])
                fail("R28 original-game tileset descriptor points to stale resource");
            uint32_t grid=r19_word(core,proof,8),stride=r19_word(core,proof,9);
            if(grid<0x02000000u || stride!=35u ||
               grid+35u*34u*2u>0x02040000u)
                fail("R28 original Emerald backup map not in bounded EWRAM");
            for(unsigned y=0;y<20u;++y)
                for(unsigned x=0;x<20u;++x) {
                    unsigned off=active_offsets[2]+2u*(20u*y+x);
                    unsigned expected=buf[off] | ((unsigned)buf[off+1u]<<8);
                    unsigned actual=core->busRead16(core,grid+2u*((y+7u)*stride+x+7u));
                    if(actual!=expected) {
                        fprintf(stderr,"R28 grid mismatch target=%u at %u,%u have=%04x expected=%04x\n",
                                map,x,y,actual,expected);
                        fail("R28 original Emerald camera grid does not match external bytes");
                    }
                }
            r17_check_tiles(core,buf+active_offsets[4],
                            active_offsets[5]-active_offsets[4]);
        }
    }
    fclose(fp);
    if(active_slots!=2u)fail("R28 must keep exactly two real resource packs resident");
}
static void r28_walk(struct mCore *core,uint32_t proof,unsigned target,
                     unsigned key,unsigned limit)
{
    unsigned i;
    for(i=0;i<limit && r19_word(core,proof,3)!=target;++i) {
        r14_press(core,key,16);
        r14_wait(core,8);
        if(r19_word(core,proof,1)==0xE19u)
            fail("R28 original Emerald game reported unsafe arena/map source");
    }
    if(r19_word(core,proof,3)!=target) {
        fprintf(stderr,"R28_NAV_STALL wanted=%u got=%u x=%u y=%u cache_miss=%u evict=%u\n",
                target,r19_word(core,proof,3),r19_word(core,proof,15),
                r19_word(core,proof,16),r19_word(core,proof,34),
                r19_word(core,proof,35));
        fail("R28 physical D-pad traversal did not reach connected map");
    }
    r19_wait(core,proof,target,80u);
}
static void xgba_r28_three_map_run(struct mCore *core,uint32_t proof,
    const char *dir,const struct XgbaGbaDevice *device,
    const struct ResourceFile *res,uint64_t route_offset,uint32_t route_length,
    uint64_t oldale_offset,uint32_t oldale_length,int enabled)
{
    if(!proof || !dir || !res->second_id || !route_offset ||
       !route_length || !oldale_offset || !oldale_length ||
       !enabled && (!device || !res))
        fail("R28 requires three independently hashed original maps and original ELF proof");
    if(!enabled) {
        if(r19_word(core,proof,1)!=0xE19u || device->successful_reads ||
           device->failed_reads || res->reads || res->lookups)
            fail("R28 disabled source bridge did not fail closed with zero reads");
        puts("PASS_R28_DISABLED_EMERALD_ZERO_PROVIDER_READS");
        return;
    }
    r14_wait(core,150);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,9u);
    r17_frame(core,dir,"01-r28-original-littleroot-initial");
    r28_walk(core,proof,16u,1u<<6,23u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,16u);
    r17_frame(core,dir,"02-r28-original-route101-enter");
    r28_walk(core,proof,10u,1u<<6,32u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,10u);
    r17_frame(core,dir,"03-r28-original-oldale-third-map");
    if(r19_word(core,proof,34)<3u || r19_word(core,proof,35)<1u)
        fail("R28 original Emerald Oldale visit did not evict a live source");
    r28_walk(core,proof,16u,1u<<7,35u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,16u);
    r17_frame(core,dir,"04-r28-route101-return");
    r28_walk(core,proof,9u,1u<<7,28u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,9u);
    r17_frame(core,dir,"05-r28-littleroot-reacquired");
    unsigned loads=r19_word(core,proof,37);
    unsigned evicts=r19_word(core,proof,35);
    if(loads<4u || evicts<2u || r19_word(core,proof,32)!=0u ||
       device->failed_reads ||
       device->successful_reads!=loads+1u ||
       r19_word(core,proof,27)!=0u)
        fail("R28 real game reload, source byte recovery or EWRAM lease count drift");
    printf("PASS_R28_REAL_EMERALD_THREE_MAP_EVICTION "
           "map_sequence=9,16,10,16,9 native_dpad=1 "
           "guest_map_loads=%u evictions=%u cache_hits=%u "
           "provider_reads=%u exact_two_slots=1 source_verified=1 "
           "bg_vram_verified=1 backup_grids_verified=5\n",
           loads,evicts,r19_word(core,proof,33),device->successful_reads);
}
#endif

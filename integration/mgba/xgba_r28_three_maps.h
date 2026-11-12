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
/* Route101 is NOT a straight corridor. Its original map has ledges,
 * fences and a winding traversable path. Compute the next physical GBA
 * D-pad move from the genuine external 20x20 map grid. Actual motion must
 * advance Emerald's own player coordinates; no host-originated writes. */
static unsigned r28_route_next_step(const uint16_t grid[400],
    const uint8_t blocked[400],unsigned x,unsigned y,unsigned north)
{
    static const int dx[4]={0,1,-1,0};
    static const int dy[4]={-1,0,0,1};
    static const unsigned keys[4]={1u<<6,1u<<4,1u<<5,1u<<7};
    int queue[400],parent[400],first[400];
    int front=0,end=0,found=-1;
    if(x>=20u || y>=20u)fail("R28 original player outside Route101 20x20 geometry");
    if((north && y==0u && x>=8u && x<=11u) ||
       (!north && y==19u && x>=10u && x<=11u))
        return north?(1u<<6):(1u<<7);
    for(unsigned i=0;i<400u;++i) {parent[i]=-1;first[i]=-1;}
    unsigned start=y*20u+x;
    parent[start]=(int)start;
    queue[end++]=(int)start;
    while(front<end) {
        int node=queue[front++];
        unsigned xx=(unsigned)node%20u, yy=(unsigned)node/20u;
        if((north && yy==0u && xx>=8u && xx<=11u) ||
           (!north && yy==19u && xx>=10u && xx<=11u)) {
            found=node;break;
        }
        for(unsigned n=0;n<4u;++n) {
            unsigned d=north?n:(3u-n);
            int nx=(int)xx+dx[d],ny=(int)yy+dy[d];
            if(nx<0 || ny<0 || nx>=20 || ny>=20)continue;
            unsigned k=(unsigned)ny*20u+(unsigned)nx;
            uint16_t tile=grid[k];
            if(parent[k]!=-1 || blocked[k] || (tile&0x0c00u) ||
               ((tile>>12u)&15u)!=3u)continue;
            parent[k]=node;
            first[k]=node==(int)start?(int)d:first[node];
            if(end>=400)fail("R28 bounded 20x20 navigator queue overflow");
            queue[end++]=(int)k;
        }
    }
    if(found<0 || first[found]<0 || first[found]>3) {
        unsigned blocked_count=0u;
        for(unsigned i=0;i<400u;++i)blocked_count+=blocked[i]!=0;
        fprintf(stderr,"R28_PATH_DIAG x=%u y=%u north=%u reached=%d "
                       "visited=%d blocked=%u current_tile=%04x\\n",
                x,y,north,found,end,blocked_count,grid[y*20u+x]);
        fail("R28 original Route101 collision-aware path does not reach connection");
    }
    return keys[first[found]];
}
static void r28_walk_route_connection(struct mCore *core,uint32_t proof,
    const struct ResourceFile *res,uint64_t route_offset,
    uint32_t route_length,unsigned destination)
{
    if(destination!=10u && destination!=9u)
        fail("R28 unknown original Emerald route connection");
    FILE *fp=fopen(res->path,"rb");
    if(!fp)fail("R28 cannot read exact original Route101 resource");
    if(route_length>16384u || !route_length ||
       fseeko(fp,(off_t)route_offset,SEEK_SET))
        fail("R28 invalid original Route101 external source");
    uint8_t raw[16384];
    if(fread(raw,1,route_length,fp)!=route_length)
        fail("R28 Route101 sidecar truncated");
    fclose(fp);
    uint32_t off=r14_le(raw+8);
    if(off<32u || off+800u>route_length)
        fail("R28 Route101 bounded metatile-grid offset invalid");
    uint16_t cells[400];
    uint8_t unavailable[400]={0};
    for(unsigned i=0;i<400u;++i)
        cells[i]=(uint16_t)(raw[off+2u*i]|((unsigned)raw[off+2u*i+1u]<<8u));
    unsigned old_x=UINT32_MAX,old_y=UINT32_MAX,last_key=0u,stall=0u;
    for(unsigned i=0;i<300u && r19_word(core,proof,3)==16u;++i) {
        unsigned x=r19_word(core,proof,15),y=r19_word(core,proof,16);
        unsigned key=r28_route_next_step(cells,unavailable,x,y,destination==10u);
        r14_press(core,key,16);
        r14_wait(core,8);
        if(r19_word(core,proof,1)==0xE19u)
            fail("R28 genuine original-game route cache rejected unsafe source");
        if(r19_word(core,proof,3)!=16u)break;
        unsigned nx=r19_word(core,proof,15),ny=r19_word(core,proof,16);
        if(nx==x && ny==y) {
            if(last_key==key && old_x==x && old_y==y)++stall;
            else stall=1u;
            if(stall>=3u) {
                int dx=key==(1u<<4)?1:key==(1u<<5)?-1:0;
                int dy=key==(1u<<6)?-1:key==(1u<<7)?1:0;
                int bx=(int)x+dx,by=(int)y+dy;
                if(bx>=0 && bx<20 && by>=0 && by<20)
                    unavailable[(unsigned)by*20u+(unsigned)bx]=1;
                stall=0u;
            }
        } else stall=0u;
        old_x=x;old_y=y;last_key=key;
    }
    if(r19_word(core,proof,3)!=destination) {
        fprintf(stderr,"R28_ROUTE_STALL destination=%u map=%u x=%u y=%u "
                       "cache_loads=%u evictions=%u\n",
                destination,r19_word(core,proof,3),
                r19_word(core,proof,15),r19_word(core,proof,16),
                r19_word(core,proof,37),r19_word(core,proof,35));
        fail("R28 original player did not complete mapped Route101 connection");
    }
    r19_wait(core,proof,destination,80u);
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
    r28_walk_route_connection(core,proof,res,route_offset,route_length,10u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,10u);
    r17_frame(core,dir,"03-r28-original-oldale-third-map");
    if(r19_word(core,proof,34)<3u || r19_word(core,proof,35)<1u)
        fail("R28 original Emerald Oldale visit did not evict a live source");
    r28_walk(core,proof,16u,1u<<7,35u);
    r28_verify(core,proof,res,route_offset,route_length,
               oldale_offset,oldale_length,16u);
    r17_frame(core,dir,"04-r28-route101-return");
    r28_walk_route_connection(core,proof,res,route_offset,route_length,9u);
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

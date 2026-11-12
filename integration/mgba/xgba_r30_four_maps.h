/* R30: genuine original Pokémon Emerald four-map two-slot physical traversal.
 * Uses original game D-pad and native guest memory, not teleport or host writes.
 * R28 source code and regression remain a separate three-map acceptance mode. */
#ifndef XGBA_R30_FOUR_MAPS_H
#define XGBA_R30_FOUR_MAPS_H
static unsigned r30_key(unsigned map)
{
    switch(map) {
    case 9u:return 0u;  /* Littleroot */
    case 16u:return 1u; /* Route101 */
    case 10u:return 2u; /* Oldale */
    case 17u:return 3u; /* Route102 */
    default:fail("R30 non-external map in original-game four-map proof");
    }
    return UINT32_MAX;
}
static void r30_verify(struct mCore *core,uint32_t proof,
    const struct ResourceFile *res,
    const uint64_t off[4],const uint32_t len[4],unsigned map)
{
    const uint32_t slot0=r19_word(core,proof,21);
    const uint32_t slot1=r19_word(core,proof,22);
    const uint32_t physical[2]={slot0,slot1};
    const uint32_t ids[2]={r19_word(core,proof,39),r19_word(core,proof,40)};
    const unsigned active=r30_key(map);
    const uint32_t selected=r19_word(core,proof,38);
    if(r19_word(core,proof,0)!=XGBA_R7_MMIO_MAGIC ||
       r19_word(core,proof,1)!=3u || r19_word(core,proof,2)!=0u ||
       r19_word(core,proof,3)!=map ||
       r19_word(core,proof,32)!=0u || r19_word(core,proof,36)!=0u ||
       selected>=2u || physical[0]<0x02000000u ||
       physical[1]!=physical[0]+8192u ||
       physical[1]+8192u>0x02040000u ||
       ids[0]>=4u || ids[1]>=4u || ids[0]==ids[1] ||
       ids[selected]!=active || r19_word(core,proof,7)!=physical[selected] ||
       r19_word(core,proof,37)<2u)
        fail("R30 original Emerald actual guest arena/map/cache state mismatch");
    FILE *fp=fopen(res->path,"rb");
    if(!fp)fail("R30 original external resource sidecar cannot be opened");
    uint8_t buf[8192];
    for(unsigned s=0;s<2u;++s) {
        unsigned id=ids[s],n=len[id];
        if(!n || n>8192u || !off[id] ||
           fseeko(fp,(off_t)off[id],SEEK_SET) || fread(buf,1,n,fp)!=n)
            fail("R30 exact SHA-checked source range invalid");
        for(unsigned i=0;i<n;++i)
            if(core->busRead8(core,physical[s]+i)!=buf[i])
                fail("R30 EWRAM bytes differ from actual external resource");
        if(id!=active)continue;
        uint32_t q[8];
        for(unsigned j=0;j<8u;++j)q[j]=r14_le(buf+4u*j);
        unsigned width=id==3u?50u:20u, height=20u;
        unsigned grid_bytes=2u*width*height;
        if(q[0]!=0x52313450u || q[1]!=n ||
           q[2]<32u || q[2]+grid_bytes>q[3] ||
           q[3]+8u>q[4] || q[4]>=q[5] || q[5]+512u>q[6] ||
           q[6]>=q[7] || q[7]>=n ||
           r19_word(core,proof,10)!=physical[s]+q[3] ||
           r19_word(core,proof,11)!=physical[s]+q[4] ||
           r19_word(core,proof,12)!=physical[s]+q[5] ||
           r19_word(core,proof,13)!=physical[s]+q[6] ||
           r19_word(core,proof,14)!=physical[s]+q[7])
            fail("R30 guest tileset descriptors are not from active source");
        uint32_t map_grid=r19_word(core,proof,8), stride=r19_word(core,proof,9);
        if(map_grid<0x02000000u || stride!=width+15u ||
           map_grid+2u*stride*(height+15u)>0x02040000u)
            fail("R30 guest backup map geometry violates bounded EWRAM");
        for(unsigned y=0;y<height;++y)
            for(unsigned x=0;x<width;++x) {
                uint32_t p=q[2]+2u*(y*width+x);
                unsigned expected=(unsigned)buf[p]|((unsigned)buf[p+1u]<<8u);
                unsigned actual=core->busRead16(core,
                    map_grid+2u*((y+7u)*stride+x+7u));
                if(actual!=expected) {
                    fprintf(stderr,"R30_GRID_MISMATCH map=%u x=%u y=%u expected=%04x actual=%04x\n",
                            map,x,y,expected,actual);
                    fail("R30 original Emerald backup-grid source mismatch");
                }
            }
        r17_check_tiles(core,buf+q[4],q[5]-q[4]);
    }
    fclose(fp);
}
/* Bounded shortest-path search on the ORIGINAL Oldale 20×20 metatile grid.
 * Target x=0,y=10 is original west connection to Route102. Dynamic NPC
 * collision is discovered through genuine no-movement D-pad responses. */
static unsigned r30_oldale_next(const uint16_t grid[400],
    const uint8_t blocked[400],unsigned x,unsigned y,unsigned destination)
{
    static const int dx[4]={-1,0,0,1};
    static const int dy[4]={0,-1,1,0};
    static const unsigned keys[4]={1u<<5,1u<<6,1u<<7,1u<<4};
    int queue[400],parent[400],first[400],front=0,end=0,goal=-1;
    if(x>=20u || y>=20u || (destination!=17u && destination!=16u))
        fail("R30 original Oldale target/coords invalid");
    unsigned goal_x=destination==17u?0u:10u;
    unsigned goal_y=destination==17u?10u:19u;
    if(x==goal_x && y==goal_y)
        return destination==17u?1u<<5:1u<<7;
    for(unsigned i=0;i<400u;++i)parent[i]=first[i]=-1;
    unsigned start=y*20u+x;
    parent[start]=(int)start;queue[end++]=(int)start;
    while(front<end) {
        int cur=queue[front++],cx=cur%20,cy=cur/20;
        if(cx==(int)goal_x && cy==(int)goal_y) {goal=cur;break;}
        for(int d=0;d<4;++d) {
            int nx=cx+dx[d],ny=cy+dy[d];
            if(nx<0 || nx>=20 || ny<0 || ny>=20)continue;
            unsigned pos=(unsigned)ny*20u+(unsigned)nx;
            uint16_t tile=grid[pos];
            if(parent[pos]!=-1 || blocked[pos] || (tile&0x0c00u) ||
               ((tile>>12u)&15u)!=3u)continue;
            parent[pos]=cur;
            first[pos]=cur==(int)start?d:first[cur];
            queue[end++]=(int)pos;
        }
    }
    if(goal<0 || first[goal]<0) {
        fprintf(stderr,"R30_OLDALE_PATH_STALL dest=%u x=%u y=%u visited=%d tile=%04x\n",
                destination,x,y,end,grid[y*20u+x]);
        fail("R30 original Oldale terrain has no legal connected-map path");
    }
    return keys[first[goal]];
}
static void r30_walk_oldale(struct mCore *core,uint32_t proof,
    const struct ResourceFile *res,uint64_t offset,uint32_t length,
    unsigned destination)
{
    FILE *fp=fopen(res->path,"rb");
    if(!fp || length>8192u || !length ||
       fseeko(fp,(off_t)offset,SEEK_SET))
        fail("R30 original Oldale source unavailable for pathfinder");
    uint8_t pack[8192];
    if(fread(pack,1,length,fp)!=length)
        fail("R30 cannot read full original Oldale source");
    fclose(fp);
    uint32_t start=r14_le(pack+8);
    if(start<32u || start+800u>length)
        fail("R30 Oldale original source metatile-grid bounds");
    uint16_t cells[400]; uint8_t blocked[400]={0};
    for(unsigned i=0;i<400u;++i)
        cells[i]=(uint16_t)(pack[start+2u*i] |
                    ((unsigned)pack[start+2u*i+1u]<<8u));
    unsigned old_x=UINT32_MAX,old_y=UINT32_MAX,prev_key=0u,stalls=0u;
    for(unsigned i=0;i<200u && r19_word(core,proof,3)==10u;++i) {
        unsigned x=r19_word(core,proof,15),y=r19_word(core,proof,16);
        unsigned key=r30_oldale_next(cells,blocked,x,y,destination);
        r14_press(core,key,16);r14_wait(core,8);
        if(r19_word(core,proof,1)==0xE19u)
            fail("R30 original guest refused external map/arena");
        if(r19_word(core,proof,3)!=10u)break;
        unsigned xx=r19_word(core,proof,15),yy=r19_word(core,proof,16);
        if(xx==x && yy==y) {
            if(prev_key==key && old_x==x && old_y==y)++stalls;
            else stalls=1u;
            if(stalls>=3u) {
                int dx=key==(1u<<4)?1:key==(1u<<5)?-1:0;
                int dy=key==(1u<<6)?-1:key==(1u<<7)?1:0;
                int nx=(int)x+dx,ny=(int)y+dy;
                if(nx>=0 && nx<20 && ny>=0 && ny<20)
                    blocked[(unsigned)ny*20u+(unsigned)nx]=1u;
                stalls=0u;
            }
        } else stalls=0u;
        prev_key=key;old_x=x;old_y=y;
    }
    if(r19_word(core,proof,3)!=destination) {
        fprintf(stderr,"R30_OLDALE_NAV_STALL target=%u map=%u x=%u y=%u loads=%u evictions=%u\n",
                destination,r19_word(core,proof,3),r19_word(core,proof,15),
                r19_word(core,proof,16),r19_word(core,proof,37),
                r19_word(core,proof,35));
        fail("R30 genuine Oldale connected-map D-pad traversal incomplete");
    }
    r19_wait(core,proof,destination,80u);
}
static void xgba_r30_four_map_run(struct mCore *core,uint32_t proof,
    const char *dir,const struct XgbaGbaDevice *device,
    const struct ResourceFile *res,const uint64_t off[4],
    const uint32_t len[4],int enabled)
{
    if(!core || !proof || !dir || !device || !res ||
       !off[0] || !off[1] || !off[2] || !off[3] ||
       !len[0] || !len[1] || !len[2] || !len[3])
        fail("R30 four source spans are mandatory");
    if(!enabled) {
        if(r19_word(core,proof,1)!=0xE19u ||
           device->successful_reads || device->failed_reads ||
           res->reads || res->lookups)
            fail("R30 disabled provider did not fail closed without reads");
        puts("PASS_R30_DISABLED_ORIGINAL_EMERALD_ZERO_PROVIDER_READS");
        return;
    }
    r14_wait(core,150);
    const unsigned route[]={9u,16u,10u,17u,10u,16u,9u};
    r30_verify(core,proof,res,off,len,route[0]);
    r17_frame(core,dir,"01-r30-littleroot");
    r28_walk(core,proof,16u,1u<<6,23u);
    r30_verify(core,proof,res,off,len,route[1]);
    r17_frame(core,dir,"02-r30-route101");
    r28_walk_route_connection(core,proof,res,off[1],len[1],10u);
    r30_verify(core,proof,res,off,len,route[2]);
    r17_frame(core,dir,"03-r30-oldale");
    r30_walk_oldale(core,proof,res,off[2],len[2],17u);
    r30_verify(core,proof,res,off,len,route[3]);
    r17_frame(core,dir,"04-r30-original-route102-fourth");
    r28_walk(core,proof,10u,1u<<4,32u);
    r30_verify(core,proof,res,off,len,route[4]);
    r17_frame(core,dir,"05-r30-oldale-reacquired");
    /* Re-entered Oldale on its WEST edge: route by real collisions to the
     * south exit instead of R28's straight-down shortcut from Route101. */
    r30_walk_oldale(core,proof,res,off[2],len[2],16u);
    r30_verify(core,proof,res,off,len,route[5]);
    r17_frame(core,dir,"06-r30-route101-reacquired");
    r28_walk_route_connection(core,proof,res,off[1],len[1],9u);
    r30_verify(core,proof,res,off,len,route[6]);
    r17_frame(core,dir,"07-r30-littleroot-returned");
    unsigned loads=r19_word(core,proof,37),evicts=r19_word(core,proof,35);
    if(loads<7u || evicts<5u || device->failed_reads ||
       r19_word(core,proof,32)!=0u || r19_word(core,proof,27)!=0u ||
       device->successful_reads!=loads+1u)
        fail("R30 four-map source read/reacquisition and live leases invalid");
    printf("PASS_R30_REAL_EMERALD_FOUR_MAP_EVICTION "
           "map_sequence=9,16,10,17,10,16,9 logical_maps=4 physical_slots=2 "
           "native_dpad=1 guest_map_loads=%u evictions=%u "
           "source_verified=1 backup_grids_verified=7 bg_vram_verified=1 "
           "provider_reads=%u\n",loads,evicts,device->successful_reads);
}
#endif

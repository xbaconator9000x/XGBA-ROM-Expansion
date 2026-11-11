/* R14: physical controller navigation, native map and tileset verification. */
#ifndef XGBA_R14_NAV_H
#define XGBA_R14_NAV_H
static uint32_t r14_u32(struct mCore *c,uint32_t p,unsigned i){return c->busRead32(c,p+4*i);}
static void r14_wait(struct mCore *c,unsigned n){c->setKeys(c,0);for(unsigned i=0;i<n;++i)c->runFrame(c);}
static void r14_press(struct mCore *c,unsigned key,unsigned n){c->setKeys(c,key);for(unsigned i=0;i<n;++i)c->runFrame(c);c->setKeys(c,0);}
static void r14_expect(struct mCore *c,uint32_t p,unsigned g,unsigned m)
{
    if(r14_u32(c,p,0)!=XGBA_R7_MMIO_MAGIC||r14_u32(c,p,1)!=3||
       r14_u32(c,p,2)!=g||r14_u32(c,p,3)!=m){
        fprintf(stderr,"R14 expected %u:%u actual %u:%u state=%u pos=%u,%u\n",g,m,
            r14_u32(c,p,2),r14_u32(c,p,3),r14_u32(c,p,1),r14_u32(c,p,6),r14_u32(c,p,7));
        fail("R14 native navigation did not reach expected map");
    }
}
static void r14_png(struct mCore *c,const char *d,const char *n)
{
    char path[1024];
    if(snprintf(path,sizeof(path),"%s/%s.png",d,n)>=(int)sizeof(path))fail("R14 path");
    save_native_frame(c,path);
}
static unsigned r14_le(const uint8_t *b){return (unsigned)b[0]|((unsigned)b[1]<<8)|((unsigned)b[2]<<16)|((unsigned)b[3]<<24);}
static void r14_tiles_vram(struct mCore *c,const uint8_t *data,unsigned available)
{
    if(available<4||data[0]!=0x10)fail("R14 expected native GBA LZ77 tileset");
    unsigned len=r14_le(data)>>8,pos=4,out=0;
    if(!len||len>384*32)fail("R14 secondary tile graphics length");
    uint8_t decoded[384*32];
    while(out<len){
        if(pos>=available)fail("R14 truncated tile LZ flags");
        unsigned flag=data[pos++];
        for(unsigned bit=0;bit<8&&out<len;++bit){
            if(flag&(0x80u>>bit)){
                if(pos+2>available)fail("R14 truncated tile LZ run");
                unsigned a=data[pos++],b=data[pos++],count=(a>>4)+3,back=((a&15)<<8)+b+1;
                if(back>out)fail("R14 invalid LZ back-reference");
                while(count--&&out<len){decoded[out]=decoded[out-back];++out;}
            }else{
                if(pos>=available)fail("R14 truncated tile LZ byte");
                decoded[out++]=data[pos++];
            }
        }
    }
    for(unsigned i=0;i<len;++i)
        if((uint8_t)c->busRead8(c,0x06000000u+640u*32u+i)!=decoded[i])
            fail("R14 actual native secondary BG VRAM differs from external tileset");
}
static void r14_verify(struct mCore *c,uint32_t p,const struct ResourceFile *r,
                       unsigned house,unsigned map_width,unsigned map_height)
{
    uint64_t offset=house?r->second_offset:r->offset,length=house?r->second_length:r->length;
    uint32_t address=r14_u32(c,p,11);
    if(length>16384||length<32||address<0x02000000u||address+length>0x02040000u)
        fail("R14 EWRAM staging bounds");
    uint8_t expected[16384],actual[16384],hash[32];
    FILE *f=fopen(r->path,"rb");
    if(!f||fseeko(f,(off_t)offset,SEEK_SET)||fread(expected,1,length,f)!=length)
        fail("R14 expected external pack read");
    fclose(f);
    for(unsigned i=0;i<length;++i)actual[i]=c->busRead8(c,address+i);
    XgbaProviderSha256(actual,length,hash);
    if(memcmp(actual,expected,length)||memcmp(hash,house?r->second_digest:r->digest,32))
        fail("R14 actual guest pack SHA mismatch");
    unsigned h[8];for(unsigned i=0;i<8;++i)h[i]=r14_le(expected+4*i);
    if(h[0]!=0x52313450u||h[1]!=length)fail("R14 pack header");
    for(unsigned i=2;i<8;++i)if(h[i]>=length)fail("R14 pack offsets");
    for(unsigned i=4;i<8;++i)
        if(r14_u32(c,p,i+8)!=address+h[i])fail("R14 native tileset pointers not external EWRAM");
    r14_tiles_vram(c,expected+h[4],h[5]-h[4]);
    if(map_width){
        uint32_t grid=r14_u32(c,p,8),stride=r14_u32(c,p,9),border=r14_u32(c,p,10);
        if(stride!=map_width+14||border!=address+h[3])fail("R14 native layout pointers");
        for(unsigned y=0;y<map_height;++y)
            for(unsigned x=0;x<map_width*2;++x)
                if((uint8_t)c->busRead8(c,grid+((y+7)*stride+7)*2+x)!=expected[h[2]+y*map_width*2+x])
                    fail("R14 actual native map grid mismatch");
    }
}
static int r14_walkable(struct mCore *c,uint32_t p,unsigned x,unsigned y)
{
    uint32_t grid=r14_u32(c,p,8),stride=r14_u32(c,p,9);
    return !(c->busRead16(c,grid+2*((y+7)*stride+x+7))&0x0C00u);
}
/* BFS through native Pallet Town collision grid; inputs only, no RAM writes. */
static void r14_walk_north(struct mCore *c,uint32_t p)
{
    enum {W=24,H=20,N=W*H};
    int blocked[N]={0};
    for(unsigned attempt=0;attempt<100;++attempt){
        r14_expect(c,p,3,0);
        unsigned x=r14_u32(c,p,6),y=r14_u32(c,p,7);
        if(x>=W||y>=H)fail("R14 Pallet coordinates invalid");
        if(y==0&&(x==12||x==13)){
            r14_press(c,1u<<6,24);r14_wait(c,150);
            return;
        }
        int parent[N],queue[N],first[N];
        for(int i=0;i<N;++i)parent[i]=-1;
        int start=y*W+x,head=0,tail=0,target=-1;
        parent[start]=start;queue[tail++]=start;first[start]=-1;
        const int dx[]={0,0,-1,1},dy[]={-1,1,0,0};
        const unsigned keys[]={1u<<6,1u<<7,1u<<5,1u<<4};
        while(head<tail){
            int at=queue[head++],ax=at%W,ay=at/W;
            if(ay==0&&(ax==12||ax==13)){target=at;break;}
            for(int k=0;k<4;++k){
                int nx=ax+dx[k],ny=ay+dy[k];
                if(nx<0||nx>=W||ny<0||ny>=H)continue;
                int next=ny*W+nx;
                if(parent[next]>=0||blocked[next]||!r14_walkable(c,p,nx,ny))continue;
                parent[next]=at;first[next]=at==start?k:first[at];queue[tail++]=next;
            }
        }
        if(target<0)fail("R14 no traversable native Pallet path to Route 1");
        int k=first[target];
        if(k<0)fail("R14 invalid path");
        unsigned nx=x+dx[k],ny=y+dy[k];
        c->setKeys(c,keys[k]);
        for(unsigned i=0;i<24;++i){
            c->runFrame(c);
            if(r14_u32(c,p,6)!=x||r14_u32(c,p,7)!=y)break;
        }
        r14_wait(c,18);
        if(r14_u32(c,p,2)!=3||r14_u32(c,p,3)!=0)return;
        if(r14_u32(c,p,6)==x&&r14_u32(c,p,7)==y)blocked[ny*W+nx]=1;
    }
    fail("R14 navigation exceeded bounded path steps");
}
static void xgba_r14_run(struct mCore *c,uint32_t p,const char *dir,
                         const struct XgbaGbaDevice *d,const struct ResourceFile *r,int enabled)
{
    if(!enabled||!p||!dir||!r->second_id)fail("R14 requires both external packs and enabled core");
    r14_wait(c,110);r14_expect(c,p,3,0);
    r14_verify(c,p,r,0,0,0);r14_png(c,dir,"01-pallet-external-tiles");
    r14_press(c,1u<<6,18);r14_wait(c,180);
    r14_expect(c,p,4,0);r14_verify(c,p,r,1,13,10);r14_png(c,dir,"02-house-door-external");
    r14_press(c,1u<<7,18);r14_wait(c,180);
    r14_expect(c,p,3,0);r14_verify(c,p,r,0,0,0);r14_png(c,dir,"03-pallet-door-return");
    r14_walk_north(c,p);
    r14_expect(c,p,3,18);r14_wait(c,45);
    r14_verify(c,p,r,0,24,40);r14_png(c,dir,"04-route1-connected-external");
    if(d->successful_reads!=2||d->failed_reads||r->reads!=2||r->lookups!=2||
        r14_u32(c,p,5)!=2)fail("R14 external resource acquisition lifecycle");
    printf("PASS_R14_REAL_DOOR_AND_CONNECTED_ROUTE_EXTERNAL_TILESETS reads=2 physical_dpad=1 native_map_grid=1 native_bg_vram=1\n");
}
#endif

/* Native Emerald R17: inspect real CPU-loaded map, BG VRAM and controller.
 * Original pinned Emerald produced every LCD pixel, no simulated overlays.
 */
#ifndef XGBA_R17_EMERALD_MAP_H
#define XGBA_R17_EMERALD_MAP_H
static uint32_t r17_word(struct mCore *c,uint32_t p,unsigned n){return c->busRead32(c,p+4*n);}
static void r17_frame(struct mCore *c,const char *d,const char *n)
{
    char path[1024];
    if(snprintf(path,sizeof(path),"%s/%s.png",d,n)>=(int)sizeof(path))
        fail("R17 native LCD file path overflow");
    save_native_frame(c,path);
}
static void r17_check_tiles(struct mCore *c,const uint8_t *data,unsigned available)
{
    if(available<4||data[0]!=0x10)
        fail("R17 expected original Emerald secondary tiles LZ77 data");
    unsigned len=r14_le(data)>>8,idx=4,out=0;
    if(len<32 || len>16384u)
        fail("R17 Emerald decompressed secondary BG graphics size invalid");
    uint8_t decoded[16384];
    while(out<len) {
        if(idx>=available) fail("R17 truncated LZ flag data");
        unsigned flags=data[idx++];
        for(unsigned bit=0;bit<8 && out<len;++bit) {
            if(flags&(0x80u>>bit)) {
                if(idx+2>available)fail("R17 truncated LZ copy");
                unsigned a=data[idx++],b=data[idx++],num=(a>>4)+3,back=((a&15)<<8)+b+1;
                if(back>out)fail("R17 invalid LZ backref");
                while(num-- && out<len){decoded[out]=decoded[out-back];++out;}
            }else{
                if(idx>=available)fail("R17 truncated LZ literal");
                decoded[out++]=data[idx++];
            }
        }
    }
    /* Emerald NUM_TILES_IN_PRIMARY is 512 (not FireRed's 640). */
    for(unsigned i=0;i<len;++i) {
        unsigned b=c->busRead8(c,0x06000000u+512u*32u+i);
        if((uint8_t)b!=decoded[i]) {
            fprintf(stderr,"R17 Emerald BG VRAM mismatch +%u actual=%02x expected=%02x\n",
                    i,b,decoded[i]);
            fail("R17 real Emerald native BG VRAM not loaded from external tiles");
        }
    }
}
static void r17_check_map(struct mCore *c,uint32_t p,const struct ResourceFile *r)
{
    if(r17_word(c,p,0)!=XGBA_R7_MMIO_MAGIC ||
       r17_word(c,p,1)!=3u ||
       r17_word(c,p,2)!=0u || r17_word(c,p,3)!=9u)
        fail("R17 original Emerald Littleroot map is not active");
    uint32_t arena=r17_word(c,p,11);
    unsigned length=(unsigned)r->length;
    if(arena<0x02000000u || arena+length>0x02040000u ||
       length>16384u || length<32u)
        fail("R17 real guest EWRAM arena outside native 256 KiB");
    uint8_t expected[16384],hash[32];
    FILE *file=fopen(r->path,"rb");
    if(!file || fseeko(file,(off_t)r->offset,SEEK_SET) ||
       fread(expected,1,length,file)!=length)
        fail("R17 external pack identity read failed");
    fclose(file);
    uint8_t actual[16384];
    for(unsigned i=0;i<length;++i)
        actual[i]=(uint8_t)c->busRead8(c,arena+i);
    XgbaProviderSha256(actual,length,hash);
    if(memcmp(expected,actual,length) || memcmp(hash,r->digest,32))
        fail("R17 actual native EWRAM external pack SHA mismatch");
    unsigned offsets[8];
    for(unsigned i=0;i<8;++i)offsets[i]=r14_le(expected+4*i);
    if(offsets[0]!=0x52313450u || offsets[1]!=length ||
       offsets[2]>=length || offsets[3]>=length)
        fail("R17 external map/tileset header corruption");
    if(r17_word(c,p,10)!=arena+offsets[3])
        fail("R17 actual Emerald layout border not external guest memory");
    for(unsigned i=4;i<8;++i) {
        if(offsets[i]>=length || r17_word(c,p,i+8)!=arena+offsets[i])
            fail("R17 original Emerald tileset pointers are not in validated pack");
    }
    unsigned width=r17_word(c,p,18u),height=r17_word(c,p,19u);
    /* Zero means historical R17's unmodified 20x20 source layout. */
    if(!width && !height) {width=20u;height=20u;}
    if(!width || !height || width>65535u || height>65535u)
        fail("R27 invalid game-authored native layout geometry");
    const uint64_t stride=(uint64_t)width+15u;
    const uint64_t backup_height=(uint64_t)height+14u;
    const uint64_t cells=stride*backup_height;
    uint32_t grid=r17_word(c,p,8);
    if(cells>0x2800u || (uint64_t)offsets[2]+2ull*width*height>offsets[3] ||
       (uint64_t)r17_word(c,p,9)!=stride ||
       grid<0x02000000u || (uint64_t)grid+cells*2u>0x02040000u)
        fail("R27 Emerald original backup-grid or sidecar geometry violates 0x2800-cell bound");
    for(unsigned y=0;y<height;++y)
        for(unsigned x=0;x<width;++x) {
            unsigned actualmap=c->busRead16(c,grid+2u*((y+7u)*(unsigned)stride+x+7u));
            unsigned source=expected[offsets[2]+2u*(y*width+x)]|
                            ((unsigned)expected[offsets[2]+2u*(y*width+x)+1u]<<8);
            if(actualmap!=source){
                fprintf(stderr,"R17 real Emerald map differs at %u,%u actual=%04x source=%04x\n",
                        x,y,actualmap,source);
                fail("R17 Emerald native collision/tile grid not original external map");
            }
        }
    r17_check_tiles(c,expected+offsets[4],offsets[5]-offsets[4]);
}
static void xgba_r17_emerald_run(struct mCore *c,uint32_t probe,
        const char *directory,const struct XgbaGbaDevice *device,
        const struct ResourceFile *resource,int enabled)
{
    if(!probe||!directory||!resource->second_id)
        fail("R17 needs Emerald proof address, real LCD path and bootstrap pack");
    if(!enabled) {
        if(r17_word(c,probe,1)!=0xE17u || device->successful_reads ||
           device->failed_reads || resource->reads || resource->lookups)
            fail("R17 disabled XGBA failed to refuse stripped external Emerald map");
        printf("PASS_R17_DISABLED_EMERALD_MAP_FAIL_CLOSED host_reads=0\n");
        return;
    }
    r14_wait(c,190u);
    r17_check_map(c,probe,resource);
    if(r17_word(c,probe,5)!=1u || device->successful_reads!=2u ||
       device->failed_reads || resource->reads!=2u)
        fail("R17 native Emerald original boot/sidecar lifecycle unexpected");
    r17_frame(c,directory,"01-littleroot-real-external-map");
    unsigned old_x=r17_word(c,probe,6),old_y=r17_word(c,probe,7);
    unsigned moves=0;
    const unsigned key[]={1u<<4,1u<<5,1u<<6,1u<<7};
    for(unsigned direction=0;direction<4 && !moves;++direction) {
        r14_press(c,key[direction],28);
        r14_wait(c,16);
        if(r17_word(c,probe,6)!=old_x || r17_word(c,probe,7)!=old_y)
            moves=1;
    }
    r17_check_map(c,probe,resource);
    r17_frame(c,directory,"02-littleroot-after-real-dpad");
    if(!moves)fail("R17 original Emerald player did not move from real D-pad input");
    if (r17_word(c,probe,18u) || r17_word(c,probe,19u))
        printf("PASS_R27_REAL_EMERALD_HUGE_MAP width=%u height=%u "
               "backup_cells=%u full_grid_verified=1 complete_secondary_tileset=1 "
               "native_bg_vram=1 original_dpad=1\n",
               r17_word(c,probe,18u),r17_word(c,probe,19u),
               (r17_word(c,probe,18u)+15u)*(r17_word(c,probe,19u)+14u));
    printf("PASS_R17_REAL_EMERALD_EXTERNAL_MAP_AND_SECONDARY_TILESET "
           "map=0:9 native_grid=1 native_bg_vram=1 physical_dpad=1 "
           "guest_requests=2 active_pack_reads=1 x=%u->%u y=%u->%u\n",
           old_x,r17_word(c,probe,6),old_y,r17_word(c,probe,7));
}
#endif

/* R13 native map transition and exact map-grid verification. */
#ifndef XGBA_R13_MAP_H
#define XGBA_R13_MAP_H
#define R13_SIZE 268u
static void r13_frame(struct mCore *core, const char *dir, const char *name)
{
    char path[1024];
    if (snprintf(path,sizeof(path),"%s/%s.png",dir,name) >= (int)sizeof(path))
        fail("R13 screenshot path");
    save_native_frame(core,path);
}
static void r13_advance(struct mCore *core, unsigned n)
{
    core->setKeys(core,0);
    for (unsigned i=0;i<n;++i) core->runFrame(core);
}
static void r13_select(struct mCore *core)
{
    core->setKeys(core,1u<<2);
    core->runFrame(core);
    core->setKeys(core,0);
}
static void r13_expect(struct mCore *core,uint32_t probe,unsigned group,
                       unsigned num,unsigned transitions,unsigned fetches,
                       unsigned rejects)
{
    if (core->busRead32(core,probe)!=XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core,probe+4)!=3 ||
        core->busRead32(core,probe+8)!=group ||
        core->busRead32(core,probe+12)!=num ||
        core->busRead32(core,probe+20)!=fetches ||
        core->busRead32(core,probe+24)!=rejects ||
        core->busRead32(core,probe+44)!=transitions ||
        core->busRead32(core,probe+40)!=(group==4))
        fail("R13 real native map/transition/fetch state mismatch");
}
static void r13_verify_map(struct mCore *core,uint32_t probe,
                           const struct ResourceFile *resource)
{
    uint32_t grid=core->busRead32(core,probe+28);
    uint32_t stride=core->busRead32(core,probe+32);
    uint32_t border=core->busRead32(core,probe+36);
    if (stride!=28 || grid<0x02000000u ||
        grid+28u*24u*2u>0x02040000u ||
        border<0x02000000u || border+8u>0x02040000u)
        fail("R13 native map grid/border not valid EWRAM");
    uint8_t actual[R13_SIZE],expected[R13_SIZE],hash[32];
    for(unsigned y=0;y<10;++y)
        for(unsigned x=0;x<26;++x)
            actual[y*26+x]=core->busRead8(core,grid+((y+7)*stride+7)*2+x);
    for(unsigned i=0;i<8;++i)
        actual[260+i]=core->busRead8(core,border+i);
    FILE *f=fopen(resource->path,"rb");
    if(!f || fseeko(f,(off_t)resource->offset,SEEK_SET) ||
        fread(expected,1,R13_SIZE,f)!=R13_SIZE)
        fail("R13 independently read external map");
    fclose(f);
    XgbaProviderSha256(actual,R13_SIZE,hash);
    if(memcmp(actual,expected,R13_SIZE)||memcmp(hash,resource->digest,32))
        fail("R13 actual native map grid and border differ from external payload");
}
static void xgba_r13_run(struct mCore *core,uint32_t probe,const char *dir,
                         const struct XgbaGbaDevice *device,
                         const struct ResourceFile *resource,int enabled)
{
    if(!probe||!dir||resource->length!=R13_SIZE||resource->second_id)
        fail("R13 requires one complete external house map payload");
    r13_advance(core,110);
    r13_expect(core,probe,3,0,0,0,0);
    if(device->successful_reads||resource->reads||resource->lookups)
        fail("R13 ROM-resident Pallet Town unexpectedly loaded external map");
    r13_frame(core,dir,"01-pallet");
    unsigned start=core->busRead32(core,probe+16);
    r13_select(core); r13_advance(core,240);
    if(enabled){
        r13_expect(core,probe,4,0,1,1,0);
        r13_verify_map(core,probe,resource);
        if(device->successful_reads!=1||resource->reads!=1||resource->lookups!=1)
            fail("R13 first entry did not read one external map");
        r13_frame(core,dir,"02-house-external");
        r13_select(core); r13_advance(core,240);
        r13_expect(core,probe,3,0,2,1,0);
        r13_frame(core,dir,"03-pallet-return");
        r13_select(core); r13_advance(core,240);
        r13_expect(core,probe,4,0,3,2,0);
        r13_verify_map(core,probe,resource);
        r13_frame(core,dir,"04-house-reloaded");
        if(device->successful_reads!=2||resource->reads!=2||
           resource->lookups!=2||device->failed_reads)
            fail("R13 external map re-entry lifecycle mismatch");
    }else{
        r13_expect(core,probe,3,0,0,0,1);
        r13_frame(core,dir,"02-entry-refused");
        if(device->successful_reads||device->failed_reads||
           resource->reads||resource->lookups)
            fail("R13 disabled fallback performed host I/O");
    }
    if(core->busRead32(core,probe+16)<=start)
        fail("R13 native overworld callbacks stalled");
    printf("PASS_R13_REAL_FIRERED_EXTERNAL_MAP mode=%s transitions=%u reads=%u native_grid_sha_verified=%u\n",
        enabled?"enabled":"disabled",core->busRead32(core,probe+44),
        device->successful_reads,(unsigned)enabled);
}
#endif

/* R24: native read-only proof of ORIGINAL Emerald's adversarial guest MMIO.
 * All requests are executed from the game's ARM instruction stream.
 * No host-side guest memory writes, emulated fake VRAM, or mocked provider.
 */
#ifndef XGBA_R24_EMERALD_BOUNDARY_H
#define XGBA_R24_EMERALD_BOUNDARY_H
#define XGBA_R24_NATIVE_MAGIC 0x52323442u
static uint32_t r24_word(struct mCore *c,uint32_t p,unsigned n)
{
    return c->busRead32(c,p+4u*n);
}
static uint32_t r24_fnv1a(const uint8_t *data,size_t n)
{
    uint32_t hash=2166136261u;
    for(size_t i=0;i<n;++i) {
        hash^=data[i];
        hash*=16777619u;
    }
    return hash;
}
static void xgba_r24_boundary_run(struct mCore *core,uint32_t boot,
    uint32_t proof,const char *directory,const struct XgbaGbaDevice *device,
    const struct ResourceFile *resource,int enabled)
{
    if (!directory || !proof || !resource ||
        proof<0x02000000u || proof>0x02040000u-68u)
        fail("R24 requires genuine ELF guest MMIO/EWRAM proof symbols");
    if (r24_word(core,proof,0)!=XGBA_R24_NATIVE_MAGIC ||
        r24_word(core,proof,1)!=3u ||
        r24_word(core,proof,2)!=0u ||
        r24_word(core,proof,8)!=16384u ||
        r24_word(core,proof,9)!=16383u ||
        r24_word(core,proof,10)!=16385u)
        fail("R24 source-built Emerald rejected a capacity/bounds scenario");
    if (boot && (r24_word(core,boot,0)!=XGBA_R7_MMIO_MAGIC ||
        r24_word(core,boot,1)!=3u ||
        r24_word(core,boot,5)!=0x454D5244u))
        fail("R24 original Emerald bridge did not reach guest CPU proof");
    if (enabled) {
        if (r24_word(core,proof,3)!=0u ||
            r24_word(core,proof,4)!=9u ||
            r24_word(core,proof,5)!=2u ||
            r24_word(core,proof,6)!=7u ||
            r24_word(core,proof,7)!=7u ||
            r24_word(core,proof,13)!=0u ||
            !r24_word(core,proof,14) ||
            r24_word(core,proof,14)<0x02000000u ||
            r24_word(core,proof,14)>0x02040000u-16384u ||
            r24_word(core,proof,11)!=r24_word(core,proof,12) ||
            device->successful_reads!=(boot?3u:2u) ||
            device->failed_reads!=7u ||
            device->actual_length!=16384u ||
            device->rejected_ranges!=3u ||
            device->rejected_ids!=1u ||
            device->provider_too_large!=1u ||
            device->provider_bad_sha256!=1u ||
            device->provider_not_found!=1u ||
            device->provider_other_failures!=0u)
            fail("R24 16KiB positive and seven unchanged-buffer refusals violated");
        const struct ExtraResourceFile *largest=NULL;
        for(unsigned k=0;k<resource->extra_count;++k)
            if(!strcmp(resource->extra[k].id,"emerald.r24.maximum"))
                largest=&resource->extra[k];
        if(!largest || largest->length!=16384u ||
            largest->offset<=32u*1024u*1024u)
            fail("R24 exact maximum 16KiB source was not a real external resource");
        uint8_t expected[16384u],digest[32];
        FILE *fp=fopen(resource->path,"rb");
        if(!fp || fseeko(fp,(off_t)largest->offset,SEEK_SET) ||
            fread(expected,1,sizeof(expected),fp)!=sizeof(expected))
            fail("R24 original maximum resource bytes missing");
        fclose(fp);
        XgbaProviderSha256(expected,sizeof(expected),digest);
        if(memcmp(digest,largest->digest,32) ||
            r24_fnv1a(expected,sizeof(expected))!=r24_word(core,proof,11))
            fail("R24 original source bytes do not equal original guest CPU hash");
    } else if (!r24_word(core,proof,3) ||
               r24_word(core,proof,4) ||
               r24_word(core,proof,5) ||
               r24_word(core,proof,6) ||
               device->successful_reads || device->failed_reads ||
               resource->reads || resource->lookups)
        fail("R24 disabled original Emerald issued external provider traffic");
    /* Original Emerald game continues after all nine synchronous MMIO
     * requests, proving the transaction failures didn't poison its loop. */
    for(unsigned i=0;i<900u;++i)
        core->runFrame(core);
    if(boot ? r24_word(core,boot,6)<100u :
              r24_word(core,proof,15)<100u)
        fail("R24 original source-built GBA game loop did not continue");
    char name[1024];
    if(snprintf(name,sizeof(name),"%s/%s-boundary-%s.png",
          directory,boot?"emerald":"firered",
          enabled?"enabled":"disabled") >= (int)sizeof(name))
        fail("R24 native LCD evidence path overflow");
    save_native_frame(core,name);
    printf("PASS_R24_ORIGINAL_%s_BOUNDARY enabled=%u ",
           boot?"EMERALD":"FIRERED",
           "successful_provider_reads=%u rejected_provider_reads=%u "
           "max_bytes=%u short_cap=%u over_cap=%u "
           "guest_attempts=%u accepted=%u rejected=%u "
           "unmodified_16k_checks=%u guest_guard_errors=%u "
           "source_hash_verified=%u original_loop_frames=900 "
           "native_ewram=1 range_rejections=%u id_rejections=%u "
           "provider_size_rejections=%u integrity_rejections=%u "
           "missing_id_rejections=%u other_failures=%u\n",
           (unsigned)enabled,device->successful_reads,device->failed_reads,
           r24_word(core,proof,8),r24_word(core,proof,9),
           r24_word(core,proof,10),r24_word(core,proof,4),
           r24_word(core,proof,5),r24_word(core,proof,6),
           r24_word(core,proof,7),r24_word(core,proof,13),
           enabled?1u:0u,device->rejected_ranges,device->rejected_ids,
           device->provider_too_large,device->provider_bad_sha256,
           device->provider_not_found,device->provider_other_failures);
}
#endif

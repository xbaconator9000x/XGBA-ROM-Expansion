/* R19: actual native Emerald four-battler sprite loading, ROM+XGBA.
 * Validation uses EWRAM bus reads of the original game's decompressed battle
 * sprite buffers, not a host-authored demonstration graphic.
 */
#ifndef XGBA_R19_MIXED_BATTLE_H
#define XGBA_R19_MIXED_BATTLE_H
static uint32_t r19_bword(struct mCore *c,uint32_t p,unsigned f)
{
    return c->busRead32(c,p+4u*f);
}
static unsigned r19_lz_decode(const uint8_t *source,unsigned size,
                              uint8_t *dest,unsigned capacity)
{
    if(size<4 || source[0]!=0x10)return 0;
    unsigned result=(unsigned)source[1]|((unsigned)source[2]<<8)|
                    ((unsigned)source[3]<<16),index=4,output=0;
    if(result<2048 || result>capacity)return 0;
    while(output<result) {
        if(index>=size)return 0;
        unsigned flags=source[index++];
        for(unsigned bit=0;bit<8u && output<result;++bit) {
            if(flags&(0x80u>>bit)) {
                if(index+2u>size)return 0;
                unsigned left=source[index++],right=source[index++];
                unsigned run=(left>>4)+3;
                unsigned back=((left&15u)<<8)+right+1;
                if(back>output)return 0;
                while(run-- && output<result) {
                    dest[output]=dest[output-back];
                    ++output;
                }
            }else{
                if(index>=size)return 0;
                dest[output++]=source[index++];
            }
        }
    }
    return result;
}
static void r19_verify_enemy_battle_sprite(struct mCore *c,uint32_t proof,
                                const struct ResourceFile *resource,
                                unsigned idx,uint64_t offset,uint32_t length)
{
    if(!length || length>8192u || offset>INT64_MAX)
        fail("R19 external battle source outside bounded host-file range");
    const uint32_t compressed=r19_bword(c,proof,13u+idx);
    const uint32_t decompressed=r19_bword(c,proof,7u+idx);
    if(compressed<0x02000000u || compressed+length>0x02040000u ||
       decompressed<0x02000000u || decompressed+2048u>0x02040000u)
        fail("R19 native enemy sprite pointers are not valid actual GBA EWRAM");
    uint8_t original[8192],decoded[8192];
    FILE *file=fopen(resource->path,"rb");
    if(!file || fseeko(file,(off_t)offset,SEEK_SET) ||
       fread(original,1,length,file)!=length)
        fail("R19 original external Pokémon graphic source unreadable");
    fclose(file);
    for(unsigned i=0;i<length;++i)
        if(c->busRead8(c,compressed+i)!=original[i])
            fail("R19 guest external Pokémon compressed bytes differ from real source");
    unsigned result=r19_lz_decode(original,length,decoded,sizeof(decoded));
    if(result<2048u)
        fail("R19 original Pokemon compressed front sprite LZ77 decode failed");
    for(unsigned i=0;i<2048u;++i) {
        if(c->busRead8(c,decompressed+i)!=decoded[i]) {
            fprintf(stderr,"R19_BATTLE_GRAPHICS_DIFF mon=%u offset=%u\n",idx,i);
            fail("R19 original Emerald battle engine did not decompress external front sprite");
        }
    }
}
static void xgba_r19_mixed_battle_run(struct mCore *core,uint32_t map,
    uint32_t battle,const char *dir,const struct XgbaGbaDevice *device,
    const struct ResourceFile *resource,uint64_t routeOffset,uint32_t routeLen,
    uint64_t sprite0Offset,uint32_t sprite0Len,
    uint64_t sprite1Offset,uint32_t sprite1Len,int enabled,int r20_reentry)
{
    if(!map || !battle || !dir || !resource->second_id)
        fail("R19 battle requires actual Emerald map plus independent opponent sprite sources");
    if(!enabled)fail("R19 disabled-mode battle is tested through connected map fail-closed");
    r14_wait(core,110);
    r19_verify(core,map,resource,routeOffset,routeLen,9);
    r17_frame(core,dir,"01-native-emerald-before-mixed-battle");
    r14_press(core,1u<<8,3); /* actual R key triggers the game's battle setup */
    unsigned frames=0;
    for(;frames<3600u;++frames) {
        if(r19_bword(core,battle,0)==0x52313942u &&
           (r19_bword(core,battle,3)&3u)==3u &&
           r19_bword(core,battle,4)!=0u &&
           r19_bword(core,battle,10)==1u)
            break;
        /* Original Emerald pauses at battle-introduction and send-out
         * dialogue. Use real GBA A-button presses; never force player
         * sprites into VRAM through emulator memory writes. */
        unsigned a=((frames>80u && (frames%100u)<3u)?1u:0u);
        core->setKeys(core,a);
        core->runFrame(core);
    }
    fprintf(stderr,"R19_BATTLE_NATIVE_DIAG frames=%u request=%u ext=%u bits=%u "
            "local=%u double=%u game_flags=0x%x host_success=%u host_fail=%u\n",
            frames,r19_bword(core,battle,1),r19_bword(core,battle,2),
            r19_bword(core,battle,3),r19_bword(core,battle,4),
            r19_bword(core,battle,10),r19_bword(core,battle,16),
            device->successful_reads,device->failed_reads);
    if(frames>=3600u || r19_bword(core,battle,11) ||
       r19_bword(core,battle,1)!=1u ||
       r19_bword(core,battle,2)!=2u ||
       (r19_bword(core,battle,3)&3u)!=3u ||
       r19_bword(core,battle,4)==0 ||
       r19_bword(core,battle,10)!=1u ||
       device->failed_reads || device->successful_reads<5u ||
       device->successful_reads>9u)
        fail("R19 original Emerald double battle did not concurrently load local and two external Pokémon sprites");
    uint32_t localSource=r19_bword(core,battle,12);
    uint32_t localDest=r19_bword(core,battle,9);
    if(localSource<0x08000000u || localSource>=0x0A000000u ||
       localDest<0x02000000u || localDest+2048u>0x02040000u)
        fail("R19 original Emerald local Pokémon did not load through vanilla ROM sprite path");
    r19_verify_enemy_battle_sprite(core,battle,resource,0,sprite0Offset,sprite0Len);
    r19_verify_enemy_battle_sprite(core,battle,resource,1,sprite1Offset,sprite1Len);
    r14_wait(core,45);
    r17_frame(core,dir,"02-original-emerald-local-plus-two-external-opponents");
    if (r20_reentry) {
        /* Continue genuine source-built Emerald from its first native battle.
         * Only original GBA keypad input is used; no host RAM patch or warp. */
        const uint32_t first_tick=r19_word(core,map,17);
        unsigned exit_frames=0;
        for (;exit_frames<6500u;++exit_frames) {
            /* A selects Fight, an original first move and first target. */
            core->setKeys(core,((exit_frames%26u)<3u)?1u:0u);
            core->runFrame(core);
            if (r19_word(core,map,17)>first_tick+20u &&
                r19_word(core,map,24)==1u &&
                r19_word(core,map,27)>=1u)
                break;
        }
        if (exit_frames>=6500u) {
            fprintf(stderr,"R20_RETURN_DIAG frames=%u ticks=%u last_world_owner=%u "
                    "last_world_epoch=%u map_claims=%u battle_claims=%u "
                    "sprite_epoch=%u sprite_claims=%u sprite_reads=%u\n",exit_frames,
                    r19_word(core,map,17),r19_word(core,map,24),
                    r19_word(core,map,25),r19_word(core,map,26),
                    r19_word(core,map,27),r19_bword(core,battle,19),
                    r19_bword(core,battle,17),r19_bword(core,battle,2));
            r17_frame(core,dir,"03-r20-diagnostic-original-battle-not-returned");
            fail("R20 original Emerald did not return to a map-owned arena");
        }
        core->setKeys(core,0);
        r14_wait(core,70);
        fprintf(stderr,"R20_WORLD_REACQUIRE_DIAG state=%u map=%u loads=%u "
                "epoch=%u owner=%u world_claims=%u battle_claims=%u reads=%u\n",
                r19_word(core,map,1),r19_word(core,map,3),
                r19_word(core,map,5),r19_word(core,map,25),
                r19_word(core,map,24),r19_word(core,map,26),
                r19_word(core,map,27),device->successful_reads);
        r19_verify(core,map,resource,routeOffset,routeLen,9);
        if (r19_word(core,map,5)<4u ||
            r19_word(core,map,26)<2u ||
            r19_word(core,map,25)<3u ||
            r19_bword(core,battle,17)!=1u ||
            r19_bword(core,battle,18)!=2u)
            fail("R20 first battle-to-overworld ownership / map reacquisition failed");
        r17_frame(core,dir,"03-r20-original-emerald-map-after-battle");
        /* Second real R-button encounter: old READY sprite descriptors MUST
         * be rejected after map packs rewrote their former EWRAM bytes. */
        r14_press(core,1u<<8,3);
        unsigned second_frames=0;
        for (;second_frames<4500u;++second_frames) {
            unsigned a=((second_frames>80u && (second_frames%100u)<3u)?1u:0u);
            core->setKeys(core,a);
            core->runFrame(core);
            if (r19_bword(core,battle,1)==2u &&
                r19_bword(core,battle,2)==4u &&
                r19_bword(core,battle,17)==2u &&
                r19_bword(core,battle,18)==4u &&
                r19_bword(core,battle,10)==1u)
                break;
        }
        if (second_frames>=4500u || r19_bword(core,battle,11)!=0u ||
            device->failed_reads ||
            r19_bword(core,battle,19)<4u)
            fail("R20 second native Emerald battle reused stale sprite bytes or missed phase reacquisition");
        r19_verify_enemy_battle_sprite(core,battle,resource,0,sprite0Offset,sprite0Len);
        r19_verify_enemy_battle_sprite(core,battle,resource,1,sprite1Offset,sprite1Len);
        r17_frame(core,dir,"04-r20-second-native-mixed-source-battle");
        printf("PASS_R20_EWRAM_ARENA_REENTRY real_original_battles=2 "
               "external_sprite_fetches=%u ownership_epochs=%u "
               "map_loads=%u battle_cache_reloads=%u provider_reads=%u "
               "return_frames=%u second_frames=%u native_ewram=1\n",
               r19_bword(core,battle,2),r19_bword(core,battle,19),
               r19_word(core,map,5),r19_bword(core,battle,18),
               device->successful_reads,exit_frames,second_frames);
    }
    printf("PASS_R19_REAL_EMERALD_MIXED_SOURCE_BATTLE player_original_rom=1 "
           "enemy_external_poochyena=1 enemy_external_zigzagoon=1 "
           "original_battle_double=1 decompress_verified=2 "
           "native_ewram=1 current_assets=rom_plus_two_sidecars "
           "provider_reads=%u\n",device->successful_reads);
}
#endif

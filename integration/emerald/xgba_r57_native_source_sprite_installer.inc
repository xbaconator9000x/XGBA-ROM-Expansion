/* R57: original-source NPC graphics installed in the genuine Emerald heap.
 * Source key is the ORIGINAL (world,u16 graphics ID), never a substitute.
 * Host SHA + R56 native content CRC for F/P/O/A is required. OAM/animation
 * source bytes are verified against actual guest OAM and first-animation
 * backing, then admitted through a bounds-checked native GBA adapter.
 * Other original directional animation tables still need source ingestion.
 * Four standard Emerald NPC palette slots only; refuse any fifth unique
 * source palette or unavailable source page before native map commit.
 */
#ifndef XGBA_R54_REAL_WARP_ADMISSION
#error R57 requires the original Emerald faded warp admission
#endif
struct XgbaR57SourceSprite {
    struct XgbaR57SourceSprite *next;
    struct ObjectEventGraphicsInfo info;
    struct SpriteFrameImage images[8];
    u16 palette[16];
    struct OamData original_oam;
    union AnimCmd original_anims[XGBA_R66_ANIM_MAX_COMMANDS];
    const union AnimCmd *native_anim_table[64];
    u16 original_id;
    u8 native_slot;
    u8 frames[];
};
static EWRAM_DATA struct XgbaR57SourceSprite *sXgbaR57SourceSprites=NULL;
struct XgbaR57SourceSpriteProof {
    volatile u32 map_attempts,original_sprite_ids,frames_installed;
    volatile u32 source_frame_bytes,palette_reuses,unique_palettes;
    volatile u32 source_page_reads,refused_pages,refused_heap,refused_palettes;
    volatile u32 real_original_npc_palette_copies;
};
EWRAM_DATA volatile struct XgbaR57SourceSpriteProof gXgbaR57SourceSpriteProof={0};

struct XgbaR57StageContext {
    struct XgbaR57SourceSprite *sprite;
    u32 frame_bytes,oam_bytes,animation_bytes;
};
static int XgbaR57CopyOriginalBytes(void *context,unsigned section,
                                   const u8 *data,u32 offset,u32 length)
{
    struct XgbaR57StageContext *ctx=(struct XgbaR57StageContext *)context;
    if(!ctx || !ctx->sprite || !data || offset!=0u)return 0;
    if(section==0u){
        if(length!=ctx->frame_bytes)return 0;
        memcpy(ctx->sprite->frames,data,length);
        return 1;
    }
    if(section==1u){
        if(length!=32u)return 0;
        memcpy(ctx->sprite->palette,data,32u);
        return 1;
    }
    if(section==2u){
        if(length!=XGBA_R66_OAM_BYTES || length!=ctx->oam_bytes ||
           sizeof(ctx->sprite->original_oam)!=XGBA_R66_OAM_BYTES)
            return 0;
        memcpy(&ctx->sprite->original_oam,data,length);
        return 1;
    }
    if(section==3u){
        if(length!=ctx->animation_bytes ||
           length>XGBA_R66_ANIM_MAX_BYTES ||
           sizeof(union AnimCmd)!=4u)
            return 0;
        memcpy(ctx->sprite->original_anims,data,length);
        return 1;
    }
    return 0;
}
static int XgbaR57AssignNativePalette(struct XgbaR57SourceSprite *next,
                                     u8 *slot)
{
    struct XgbaR57SourceSprite *p;
    unsigned i;
    u8 occupied=0u;
    if(!next || !slot)return 0;
    for(p=sXgbaR57SourceSprites;p;p=p->next){
        if(memcmp(p->palette,next->palette,32u)==0){
            *slot=p->info.paletteSlot;
            ++gXgbaR57SourceSpriteProof.palette_reuses;
            return 1;
        }
        if(p->info.paletteSlot<PALSLOT_NPC_1 ||
           p->info.paletteSlot>PALSLOT_NPC_4)return 0;
        occupied|=(u8)(1u<<(p->info.paletteSlot-PALSLOT_NPC_1));
    }
    for(i=0;i<4u;i++)
        if(!(occupied&(1u<<i))){
            *slot=(u8)(PALSLOT_NPC_1+i);
            ++gXgbaR57SourceSpriteProof.unique_palettes;
            return 1;
        }
    ++gXgbaR57SourceSpriteProof.refused_palettes;
    return 0;
}
static void XgbaR57ReleasePendingMapSprites(void)
{
    while(sXgbaR57SourceSprites){
        struct XgbaR57SourceSprite *next=sXgbaR57SourceSprites->next;
        Free(sXgbaR57SourceSprites);
        sXgbaR57SourceSprites=next;
    }
}
static int XgbaR57InstallOne(u8 world,u16 original_id)
{
    struct XgbaR56Reader reader={0};
    struct XgbaR56SourceObject original={0};
    struct XgbaR57SourceSprite *out;
    struct XgbaR57StageContext ctx={0};
    u8 slot;
    unsigned i;
    reader.fetch=XgbaR53FetchNativePage;
    reader.scratch=(u8 *)gXgbaR17Arena;
    if(!XgbaR56ReadMeta(&reader,world,original_id,&original)){
        ++gXgbaR57SourceSpriteProof.refused_pages;return 0;
    }
    if(original.sizes[2]!=XGBA_R66_OAM_BYTES ||
       original.sizes[3]>XGBA_R66_ANIM_MAX_BYTES ||
       original.sizes[0]>XGBA_R56_MAX_FRAMES_BYTES ||
       original.frame_count>8u)return 0;
    out=AllocZeroed(sizeof(*out)+original.sizes[0]);
    if(!out){++gXgbaR57SourceSpriteProof.refused_heap;return 0;}
    out->original_id=original_id;
    ctx.sprite=out;ctx.frame_bytes=original.sizes[0];
    ctx.oam_bytes=original.sizes[2];
    ctx.animation_bytes=original.sizes[3];
    for(i=0;i<XGBA_R56_SECTIONS;i++){
        if(!XgbaR56VisitSection(&reader,&original,i,
              XgbaR57CopyOriginalBytes,&ctx)){
            ++gXgbaR57SourceSpriteProof.refused_pages;
            Free(out);return 0;
        }
    }
    gXgbaR57SourceSpriteProof.source_page_reads+=reader.page_reads;
    if(!XgbaR66OriginalOamValid(
           (const u8 *)&out->original_oam,original.sizes[2],
           original.width,original.height) ||
       !XgbaR66OriginalFirstAnimationValid(
           (const u8 *)out->original_anims,original.sizes[3],
           original.frame_count)){
        ++gXgbaR57SourceSpriteProof.refused_pages;
        Free(out);return 0;
    }
    for(i=0u;i<64u;i++)
        out->native_anim_table[i]=out->original_anims;
    if(!XgbaR57AssignNativePalette(out,&slot)){Free(out);return 0;}
    out->info.tileTag=TAG_NONE;
    out->info.paletteTag=TAG_NONE;
    out->info.reflectionPaletteTag=TAG_NONE;
    out->info.width=original.width;
    out->info.height=original.height;
    out->info.size=(u16)((u32)original.width*original.height/2u);
    out->info.paletteSlot=slot;
    out->info.inanimate=(original.frame_count==1u); /* authentic first anim only */
    out->info.disableReflectionPaletteLoad=TRUE;
    out->info.oam=&out->original_oam;
    out->info.anims=out->native_anim_table;
    out->info.images=out->images;
    out->info.affineAnims=gDummySpriteAffineAnimTable;
    for(i=0;i<original.frame_count;i++){
        out->images[i].data=out->frames+i*out->info.size;
        out->images[i].size=out->info.size;
    }
    /* R55 calls R56 again and compares original bytes directly to the
     * memory backing the native Emerald object sprite. */
    if(!XgbaR55RegisterOriginalSpriteGraphics(world,original_id,
        &out->info,out->palette,original.crc[1],original.crc[0])){
        ++gXgbaR57SourceSpriteProof.refused_pages;
        Free(out);return 0;
    }
    if(!XgbaR55FindVerifiedSprite(sXgbaR55OriginalSprites,world,
                                  original_id,&out->native_slot)){
        Free(out);return 0;
    }
    out->next=sXgbaR57SourceSprites;
    sXgbaR57SourceSprites=out;
    ++gXgbaR57SourceSpriteProof.frames_installed;
    gXgbaR57SourceSpriteProof.source_frame_bytes+=original.sizes[0];
    return 1;
}
static bool8 XgbaR57InstallPendingMapSprites(u8 world,u8 group,u8 map)
{
    struct XgbaR49Reader reader={0};
    struct XgbaR49OriginalEvents events={0};
    struct XgbaR51Reader terrain_index={0};
    struct XgbaR51IndexRow terrain={0};
    u16 ids[XGBA_R50_MAX_OBJECTS];
    unsigned count=0u,i,j;
    u32 key=((u32)world<<16)|((u32)group<<8)|map;
    if(world==0u)return TRUE;
    if(world>=3u || sXgbaR57SourceSprites ||
       !sXgbaR54OriginalHeapPreReset ||
       sXgbaR54SourceMapPreparedInWarp)return FALSE;
    ++gXgbaR57SourceSpriteProof.map_attempts;
    if(!XgbaR55BeginOriginalSourceSpriteRegistration(world,group,map))
        return FALSE;
    terrain_index.fetch=XgbaR51FetchRealPage;
    terrain_index.scratch=(u8 *)gXgbaR17Arena;
    terrain_index.indexed_maps=XGBA_R51_ALL_SOURCE_MAPS;
    terrain_index.cached_index_page=XGBA_R51_INVALID_PAGE;
    if(!XgbaR51FindSourceMap(&terrain_index,key,&terrain))
        goto fail;
    reader.fetch=XgbaR50FetchOriginalPage;
    reader.scratch=(u8 *)gXgbaR17Arena;
    reader.indexed_maps=XGBA_R49_ALL_MAPS;
    reader.cached_index_page=XGBA_R49_INVALID_PAGE;
    if(!XgbaR49LoadOriginalMapEvents(&reader,key,&events) ||
       events.object_count>XGBA_R50_MAX_OBJECTS)goto fail;
    /* The next resource overwrites event scratch: copy only unique u16 IDs. */
    for(i=0;i<events.object_count;i++){
        const u8 *raw=events.objects+i*24u;
        u16 graphics=XgbaR49Le16(raw+1u);
        s16 x=(s16)XgbaR49Le16(raw+4u);
        s16 y=(s16)XgbaR49Le16(raw+6u);
        if(!XgbaR60OriginalNpcIsInLandingView(
            world,group,map,terrain.width,terrain.height,x,y))
            continue;
        for(j=0;j<count;j++)if(ids[j]==graphics)break;
        if(j==count){
            if(count>=XGBA_R55_SPRITE_SLOTS)goto fail;
            ids[count++]=graphics;
        }
    }
    gXgbaR57SourceSpriteProof.original_sprite_ids+=count;
    for(i=0;i<count;i++)
        if(!XgbaR57InstallOne(world,ids[i]))goto fail;
    return TRUE;
fail:
    XgbaR57ReleasePendingMapSprites();
    XgbaR55ForgetSourceSpriteRegistrations();
    return FALSE;
}
/* Hooked into actual original NPC spawn after hardware palette slot is
 * assigned. Copies the authenticated ORIGINAL source colors into OBJ PLTT.
 * No palette mutation for vanilla Emerald or uncommitted foreign worlds. */
bool8 XgbaR57ApplyOriginalObjectPalette(u8 graphics_id,u8 palette_slot)
{
    struct XgbaR57SourceSprite *p;
    if(!sXgbaR54SourceMapPreparedInWarp || !sXgbaR50Ready ||
       graphics_id<XGBA_R55_SPRITE_FIRST ||
       graphics_id>XGBA_R55_SPRITE_LAST)return TRUE;
    for(p=sXgbaR57SourceSprites;p;p=p->next){
        if(p->native_slot==graphics_id &&
           p->info.paletteSlot==palette_slot){
            LoadPalette(p->palette,OBJ_PLTT_ID(palette_slot),
                        PLTT_SIZE_4BPP);
            ++gXgbaR57SourceSpriteProof.real_original_npc_palette_copies;
            return TRUE;
        }
    }
    return FALSE;
}

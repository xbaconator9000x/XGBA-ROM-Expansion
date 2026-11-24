/*
 * Native trainer battle entry for the pinned RHH pokeemerald-expansion build.
 * Included into src/main.c only by the explicit --trainer-battle build.
 *
 * The real overworld runs first. The trigger then configures the original
 * trainer-battle parameters and calls the original BattleSetup_StartTrainerBattle,
 * which schedules the stock transition and CB2_InitBattle. Nothing here draws
 * or loads trainer graphics: the witnesses only observe the original engine.
 */
#include "battle_main.h"
#include "battle_setup.h"
#include "battle.h"
#include "palette.h"
#include "pokemon.h"
#include "script_pokemon_util.h"
#include "sprite.h"
#include "constants/items.h"
#include "constants/opponents.h"
#include "constants/species.h"

/* Original Hiker per target: trainer id 1 is a Youngster in FRLG, so FRLG uses
 * its own Hiker (TRAINER_PIC_HIKER_FRLG) and Emerald uses TRAINER_PIC_HIKER. */
#if IS_FRLG
#define XGBA_TRAINER_BATTLE_OPPONENT TRAINER_HIKER_MARCOS
#else
#define XGBA_TRAINER_BATTLE_OPPONENT TRAINER_SAWYER_1
#endif
#define XGBA_TRAINER_BATTLE_FIELD_FRAMES 40u

void XgbaExpansionTrainerBattleTick(void)
{
    if (gXgbaExpansionProof.battle_flow_state != 0u
        || gXgbaExpansionProof.live_frames < XGBA_TRAINER_BATTLE_FIELD_FRAMES)
        return;
    if (gPartiesCount[B_TRAINER_PLAYER] == 0)
        ScriptGiveMon(SPECIES_BULBASAUR, 5, ITEM_NONE);
    TRAINER_BATTLE_PARAM.opponentA = XGBA_TRAINER_BATTLE_OPPONENT;
    gXgbaExpansionProof.battle_opponent_id = XGBA_TRAINER_BATTLE_OPPONENT;
    gXgbaExpansionProof.battle_flow_state = 1u;
    BattleSetup_StartTrainerBattle();
}

static void XgbaExpansionTrainerBattleWitness(void)
{
    enum BattlerId battler;
    struct Sprite *sprite;
    s32 x;

    if (gXgbaExpansionProof.battle_flow_state == 0u
        || !(gBattleTypeFlags & BATTLE_TYPE_TRAINER)
        || gMain.callback2 != BattleMainCB2
        || gBattleMainFunc == NULL || gBattleStruct == NULL)
        return;
    gXgbaExpansionProof.battle_flow_state = 2u;
    ++gXgbaExpansionProof.battle_main_frames;
    gXgbaExpansionProof.battle_sprite_visible = 0u;
    /* Sprite state is meaningful only after the original trainer-pic loader ran. */
    if (gXgbaExpansionProof.battle_attempt_count == 0u)
        return;
    battler = GetBattlerAtPosition(B_POSITION_OPPONENT_LEFT);
    sprite = &gSprites[gBattleStruct->trainerSlideSpriteIds[battler]];
    /* oam.affineParam is assigned only by the original trainer-pic draw. */
    if (!sprite->inUse || sprite->invisible
        || sprite->oam.affineParam != gXgbaExpansionProof.battle_attempt_last_id)
        return;
    x = sprite->x + sprite->x2;
    gXgbaExpansionProof.battle_sprite_pic = sprite->oam.affineParam;
    if (x >= 16 && x <= 224)
        gXgbaExpansionProof.battle_sprite_visible = 1u;
    if (sprite->x2 == 0 && x >= 140 && x <= 230)
        gXgbaExpansionProof.battle_sprite_arrived = 1u;
}

static u32 XgbaExpansionPokemonSliceHash(const void *data, u32 bytes)
{
    const u8 *p = data;
    u32 hash = 2166136261u;
    u32 i;
    for (i = 0; i < bytes; ++i)
        hash = (hash ^ p[i]) * 16777619u;
    return hash;
}

/* Observe one battler's live sprite. A latch is set only once the sprite's
 * OBJ VRAM tiles equal the engine-owned buffer and its OBJ palette equals the
 * original species palette; sprite_live is refreshed every frame. */
static void XgbaExpansionPokemonSideWitness(u32 isFront)
{
    enum BattlerId battler = GetBattlerAtPosition(isFront ? B_POSITION_OPPONENT_LEFT : B_POSITION_PLAYER_LEFT);
    enum BattlerPosition position = GetBattlerPosition(battler);
    volatile u32 *live = isFront ? &gXgbaExpansionProof.mon_front_sprite_live : &gXgbaExpansionProof.mon_back_sprite_live;
    volatile u32 *ok = isFront ? &gXgbaExpansionProof.mon_front_sprite_ok : &gXgbaExpansionProof.mon_back_sprite_ok;
    struct Sprite *sprite;
    const u8 *buffer;
    const u16 *palette;
    u32 spriteId, tile, species, frame = 0u;
    s32 x;

    *live = 0u;
    if (gMonSpritesGfxPtr == NULL || position >= MAX_BATTLERS_COUNT)
        return;
    species = gBattleMons[battler].species;
    spriteId = gBattlerSpriteIds[battler];
    if (species == SPECIES_NONE || spriteId >= MAX_SPRITES)
        return;
    sprite = &gSprites[spriteId];
    x = sprite->x + sprite->x2;
    if (!sprite->inUse || sprite->invisible || x < 16 || x > 224)
        return;
    *live = 1u;
    if (*ok)
        return;
    tile = sprite->oam.tileNum;
    if (tile > 1024u - 64u)
        return;
    buffer = gMonSpritesGfxPtr->spritesGfx[position];
    if (XgbaExpansionPokemonSliceHash((const u8 *)OBJ_VRAM0 + tile * 32u, 2048u)
        == XgbaExpansionPokemonSliceHash(buffer, 2048u))
        frame = 1u;
    else if (isFront && XgbaExpansionPokemonSliceHash((const u8 *)OBJ_VRAM0 + tile * 32u, 2048u)
        == XgbaExpansionPokemonSliceHash(buffer + 2048u, 2048u))
        frame = 2u;
    if (frame == 0u)
        return;
    palette = GetMonFrontSpritePal(GetBattlerMon(battler));
    if (palette == NULL
        || XgbaExpansionPokemonSliceHash(&gPlttBufferUnfaded[OBJ_PLTT_ID(battler)], 32u)
           != XgbaExpansionPokemonSliceHash(palette, 32u))
        return;
    if (isFront)
    {
        gXgbaExpansionProof.mon_front_sprite_species = species;
        gXgbaExpansionProof.mon_front_sprite_tile = tile;
        gXgbaExpansionProof.mon_front_palette_hash = XgbaExpansionPokemonSliceHash(palette, 32u);
        gXgbaExpansionProof.mon_front_vram_frame = frame;
    }
    else
    {
        gXgbaExpansionProof.mon_back_sprite_species = species;
        gXgbaExpansionProof.mon_back_sprite_tile = tile;
        gXgbaExpansionProof.mon_back_palette_hash = XgbaExpansionPokemonSliceHash(palette, 32u);
        gXgbaExpansionProof.mon_back_vram_frame = frame;
    }
    *ok = 1u;
}

static void XgbaExpansionPokemonBattleWitness(void)
{
    if (gXgbaExpansionProof.battle_flow_state == 0u
        || !(gBattleTypeFlags & BATTLE_TYPE_TRAINER)
        || gMain.callback2 != BattleMainCB2
        || gBattleMainFunc == NULL || gBattleStruct == NULL)
        return;
    XgbaExpansionPokemonSideWitness(1u);
    XgbaExpansionPokemonSideWitness(0u);
}

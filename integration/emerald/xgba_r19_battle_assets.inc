/* R19 mixed-source battle: actual Emerald wild double battle.
 *
 * Player Treecko and Torchic backs, battle UI, move animations and palettes
 * remain original ROM assets. Enemy Poochyena and Zigzagoon compressed fronts
 * are removed from the ROM and supplied as two independently verified XGBA
 * resources at distinct external offsets. This is not a host-drawn mock battle.
 */
#include "battle.h"
#include "battle_setup.h"
#include "pokemon.h"
#include "data.h"
#include "constants/species.h"

#define XGBA_R19_BATTLE_MAGIC 0x52313942u
#define XGBA_R19_BATTLE_BUFFER_CAP 2048u
struct XgbaR19BattleProof {
    volatile u32 magic,requested,external_reads,external_species_bits,local_species_bits;
    volatile u32 foe_species0,foe_species1,foe_gfx0,foe_gfx1,local_back_gfx;
    volatile u32 double_battle,errors,original_rom_front,external_front0,external_front1;
    volatile u32 overworld_map,game_battle_flags,original_player_species;
};
EWRAM_DATA volatile struct XgbaR19BattleProof gXgbaR19BattleProof = {0};
EWRAM_DATA ALIGNED(4) u8 gXgbaR19FrontCompressed[2][XGBA_R19_BATTLE_BUFFER_CAP]={0};
EWRAM_DATA char gXgbaR19BattleId[2][40]={{0}};
static EWRAM_DATA struct CompressedSpriteSheet sXgbaR19FrontSheet[2]={{0}};
static EWRAM_DATA bool8 sXgbaR19FrontReady[2]={FALSE,FALSE};

static void XgbaR19BattleReject(void)
{
    gXgbaR19BattleProof.magic=XGBA_R19_BATTLE_MAGIC;
    ++gXgbaR19BattleProof.errors;
    for(;;) {}
}
const struct CompressedSpriteSheet *XgbaR19BattleFrontSheet(
    u16 species,const struct CompressedSpriteSheet *original)
{
    s32 slot=-1;
    u32 bytes;
    u32 i;
    const char *name;
    if(species==SPECIES_POOCHYENA)slot=0;
    if(species==SPECIES_ZIGZAGOON)slot=1;
    if(slot<0)return original; /* original ROM-resident Pokémon remain untouched */
    bytes=slot?XGBA_R19_ZIGZAGOON_FRONT_BYTES:XGBA_R19_POOCHYENA_FRONT_BYTES;
    name=slot?"emerald.battle.zigzagoon.front":"emerald.battle.poochyena.front";
    if(bytes<16u || bytes>XGBA_R19_BATTLE_BUFFER_CAP)
        XgbaR19BattleReject();
    if(!sXgbaR19FrontReady[slot]) {
        for(i=0;i<40u;i++)gXgbaR19BattleId[slot][i]=0;
        for(i=0;name[i] && i<39u;i++)
            gXgbaR19BattleId[slot][i]=name[i];
        if(XgbaGuestFetch(gXgbaR19BattleId[slot],
                          gXgbaR19FrontCompressed[slot],bytes)!=bytes)
            XgbaR19BattleReject();
        if(gXgbaR19FrontCompressed[slot][0]!=0x10u)
            XgbaR19BattleReject();
        sXgbaR19FrontSheet[slot]=*original;
        sXgbaR19FrontSheet[slot].data=(const u32 *)gXgbaR19FrontCompressed[slot];
        sXgbaR19FrontReady[slot]=TRUE;
        ++gXgbaR19BattleProof.external_reads;
        gXgbaR19BattleProof.external_species_bits|=1u<<slot;
        if(!slot)gXgbaR19BattleProof.external_front0=(u32)gXgbaR19FrontCompressed[slot];
        else gXgbaR19BattleProof.external_front1=(u32)gXgbaR19FrontCompressed[slot];
    }
    gXgbaR19BattleProof.magic=XGBA_R19_BATTLE_MAGIC;
    return &sXgbaR19FrontSheet[slot];
}
void XgbaR19BattleOpponentRendered(u16 species,const void *destination)
{
    if(species==SPECIES_POOCHYENA) {
        gXgbaR19BattleProof.foe_gfx0=(u32)destination;
        gXgbaR19BattleProof.foe_species0=species;
    } else if(species==SPECIES_ZIGZAGOON) {
        gXgbaR19BattleProof.foe_gfx1=(u32)destination;
        gXgbaR19BattleProof.foe_species1=species;
    }
    gXgbaR19BattleProof.game_battle_flags=gBattleTypeFlags;
    gXgbaR19BattleProof.double_battle=(gBattleTypeFlags&BATTLE_TYPE_DOUBLE)!=0;
}
void XgbaR19BattleLocalRendered(u16 species,const void *destination)
{
    if(species==SPECIES_TREECKO || species==SPECIES_TORCHIC) {
        gXgbaR19BattleProof.local_species_bits|=
            species==SPECIES_TREECKO?1u:2u;
        gXgbaR19BattleProof.local_back_gfx=(u32)destination;
        gXgbaR19BattleProof.original_player_species=species;
        gXgbaR19BattleProof.original_rom_front=
            (u32)gMonBackPicTable[species].data;
    }
}
static void XgbaR19BattleTrigger(void)
{
    if(gXgbaR19BattleProof.requested || !(gMain.newKeys & R_BUTTON))
        return;
    /* Test-only entry retains Emerald's actual wild battle transition,
     * controller callbacks and battle sprite decompression routines. */
    ZeroPlayerPartyMons();
    ZeroEnemyPartyMons();
    CreateMon(&gPlayerParty[0],SPECIES_TREECKO,18,0,FALSE,0,OT_ID_PLAYER_ID,0);
    CreateMon(&gPlayerParty[1],SPECIES_TORCHIC,18,0,FALSE,0,OT_ID_PLAYER_ID,0);
    CreateMon(&gEnemyParty[0],SPECIES_POOCHYENA,5,0,FALSE,0,OT_ID_RANDOM_NO_SHINY,0);
    CreateMon(&gEnemyParty[1],SPECIES_ZIGZAGOON,5,0,FALSE,0,OT_ID_RANDOM_NO_SHINY,0);
    gPlayerPartyCount=2;
    gEnemyPartyCount=2;
    gXgbaR19BattleProof.magic=XGBA_R19_BATTLE_MAGIC;
    gXgbaR19BattleProof.requested=1u;
    gXgbaR19BattleProof.overworld_map=gSaveBlock1Ptr->location.mapNum;
    BattleSetup_StartWildBattle();
    /* Normal wild battle resets flags inside DoStandardWildBattle. Enable
     * the original game's 4-battler renderer AFTER that reset. */
    gBattleTypeFlags|=BATTLE_TYPE_DOUBLE;
    gXgbaR19BattleProof.game_battle_flags=gBattleTypeFlags;
}

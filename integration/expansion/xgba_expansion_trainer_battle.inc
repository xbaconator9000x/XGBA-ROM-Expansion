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
#include "script_pokemon_util.h"
#include "sprite.h"
#include "constants/items.h"
#include "constants/opponents.h"
#include "constants/species.h"

/* Original Hiker (TRAINER_PIC_HIKER) opponent present in all three targets. */
#define XGBA_TRAINER_BATTLE_OPPONENT TRAINER_SAWYER_1
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

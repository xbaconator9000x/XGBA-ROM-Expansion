#!/usr/bin/env python3
"""R90 opt-in capability fixture: give the real Emerald party the genuine Fly HM.

This never performs a warp, source switch or Fly callback. It ONLY makes a
legitimate native party-menu Fly selection possible on a new-game test build.
The original game's PARTY -> FLY -> region map -> bird field effect remains
the entire travel path. Production/R84 save and original world loads unchanged.
"""
from __future__ import annotations
from pathlib import Path
import xgba_r16_emerald_decomp_patch as r16

def enable_original_emerald_fly_party_fixture(emerald:Path)->dict[Path,str]:
    path=Path(emerald)/"src/new_game.c"
    original=path.read_text()
    s=r16.one(original,
       '#include "constants/items.h"',
       '#include "constants/items.h"\n'
       '#include "constants/moves.h"\n'
       '#include "constants/species.h"\n'
       '#include "constants/flags.h"',
       "R90 original Emerald native party/field move constants")
    s=r16.one(s,
       "    ResetContestLinkResults();\n}",
       """    ResetContestLinkResults();
    /* R90 test fixture ONLY. Original native party menu must be used:
     * START -> POKEMON -> SWELLOW -> FLY -> region map -> A.
     * Do not set a pending warp, mutate source map ID or skip field-effect
     * graphics. Six badges aren't required; this Fly-only badge is.
     * The original NewGameInitData first clears party and event flags, so
     * append this AFTER all its normal initialization and reset scripts. */
    CreateMon(&gPlayerParty[0], SPECIES_SWELLOW, 40, 31, FALSE, 0,
              OT_ID_PLAYER_ID, 0);
    SetMonMoveSlot(&gPlayerParty[0], MOVE_FLY, 0);
    gPlayerPartyCount = CalculatePlayerPartyCount();
    FlagSet(FLAG_BADGE06_GET);
}""",
       "R90 enable authentic native party menu Fly without any teleport")
    path.write_text(s)
    return {path:original}

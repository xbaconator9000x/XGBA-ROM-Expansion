# R91 — distinguish genuine original Emerald Fly from source-door loading

The original R54 proof field `actual_native_fly_success` was declared and read but **never incremented**. A correct original source map could be staged by a physical door, leaving the true Fly achievement ambiguous.

R91 wires it to exactly one path: after original `src/field_effect.c` calls `XgbaR48ConfirmActualFlyArrival()`, **and only when** that confirms a physical original world+map and authentic active original NPC, increment a separate R54 counter. Recheck the source-qualified target, monotonically increasing original R48 fly count, native original R51 terrain/R53 art for foreign worlds and correct R54 loaded source. This does **not** count R80 physically walked Rocket doors or debug Fly pending selection. R90 also makes a real Pokémon HM Fly option accessible in the native Emerald test party via standard Start/party UI.

A **genuine 3-world Fly** requires: (1) Fly selected from actual Pokémon party, (2) R58 menu `SELECT` + `A` queue, (3) original Fly-out engine field effect, (4) destination native faded map/art/actor load, (5) original Fly-in callback, (6) R48 and R54 counts increment together, worlds **1 → 2 → 0**, and (7) real visible mGBA LCD at each landing.

This commit fixes genuine runtime accounting, **not** an already-completed user-private 3-world Fly playthrough. Heart & Soul original BG and source sprite assets still have to be admitted safely; never substitute Emerald art and claim an original Heart & Soul landing.

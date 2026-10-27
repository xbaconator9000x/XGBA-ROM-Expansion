# Analyst whole-file candidate 0080 — Bike movement speed, transition and slope-state ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/bike.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/bike.h); exact pinned Git blob SHA-1 `cd079477e53382ff72b56a7397a3c010bc2f36eb`. Inspected the **entire 53-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

Three enum groups define player speed (5), bike transition (5), bike state (3) and Acro bike state (7); exported functions manage direction history, disallow checks, get-on/off, speed, slope jump and bike movement using u8 directions and u16 key masks.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_BIKE_H`
- L2: `#define GUARD_BIKE_H`
- L7: `enum`
- L8: `{`
- L9: `PLAYER_SPEED_STANDING,`
- L10: `PLAYER_SPEED_NORMAL,`
- L11: `PLAYER_SPEED_FAST,`
- L12: `PLAYER_SPEED_FASTER,`
- L13: `PLAYER_SPEED_FASTEST,`
- L14: `};`
- L16: `enum {`
- L17: `BIKE_TRANS_FACE_DIRECTION,`
- L18: `BIKE_TRANS_TURNING,`
- L19: `BIKE_TRANS_MOVE,`
- L20: `BIKE_TRANS_DOWNHILL,`
- L21: `BIKE_TRANS_UPHILL`
- L22: `};`
- L24: `enum {`
- L25: `BIKE_STATE_NORMAL,`
- L26: `BIKE_STATE_TURNING,`
- L27: `BIKE_STATE_SLOPE`
- L28: `};`
- L31: `enum`
- L32: `{`
- L33: `ACRO_STATE_NORMAL,`
- L34: `ACRO_STATE_TURNING,`
- L35: `ACRO_STATE_WHEELIE_STANDING,`
- L36: `ACRO_STATE_BUNNY_HOP,`
- L37: `ACRO_STATE_WHEELIE_MOVING,`
- L38: `ACRO_STATE_SIDE_JUMP,`
- L39: `ACRO_STATE_TURN_JUMP,`
- L40: `};`
- L42: `void BikeClearState(u32 directionHistory, u32 abStartSelectHistory);`
- L43: `bool8 IsBikingDisallowedByPlayer(void);`
- L44: `void GetOnOffBike(u8 flags);`
- L45: `s16 GetPlayerSpeed(void);`
- L46: `bool8 RS_IsRunningDisallowed(u8 r0);`
- L47: `void MovePlayerOnBike(u8 direction, u16 newKeys, u16 heldKeys);`
- L48: `bool32 IsRunningDisallowed(u8 metatileBehavior);`
- L49: `void Bike_HandleBumpySlopeJump(void);`
- L50: `void Bike_UpdateBikeCounterSpeed(u8 counter);`
- L51: `bool8 IsPlayerNotUsingAcroBikeOnBumpySlope(void);`
- L53: `#endif //GUARD_BIKE_H`

## Dependencies, expansion relevance and independent review

Trace movement enum values to consumers, slope metatile behavior, Acro versus FRLG variant dead paths, direction-history encoding, collision callbacks and signed speed semantics; TODO in source explicitly questions applicability. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

# Analyst whole-file candidate 0066 — Player movement, collision and avatar transition ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_player_avatar.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_player_avatar.h); exact pinned Git blob SHA-1 `0c078fc6e767c73fa26c5cb54e24e705fd619cd4`. Inspected the **entire 67-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The full header exposes player state, movement speed variants, bike/surf/fishing/teleport transitions, sprite animation, collision checks and coordinate/elevation queries. Collision takes signed tile coordinates plus u8 direction/metatile behavior; input uses 16-bit key masks.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_PLAYER_AVATAR_H`
- L2: `#define GUARD_FIELD_PLAYER_AVATAR_H`
- L4: `#include "global.h"`
- L6: `void ClearPlayerAvatarInfo(void);`
- L7: `void SetPlayerAvatarExtraStateTransition(u8, u8);`
- L8: `u8 GetPlayerAvatarGenderByGraphicsId(u8);`
- L9: `bool8 TestPlayerAvatarFlags(u8);`
- L10: `void PlayerGetDestCoords(s16 *, s16 *);`
- L11: `u8 GetPlayerFacingDirection(void);`
- L12: `u8 GetPlayerMovementDirection(void);`
- L13: `u8 PlayerGetCopyableMovement(void);`
- L14: `void MovePlayerNotOnBike(u8 direction, u16 heldKeys);`
- L16: `void MovementType_Player(struct Sprite *sprite);`
- L17: `void HandleEnforcedLookDirectionOnPlayerStopMoving(void);`
- L18: `void StopPlayerAvatar(void);`
- L19: `void GetXYCoordsOneStepInFrontOfPlayer(s16 *xPtr, s16 *yPtr);`
- L20: `u8 GetPlayerAvatarGraphicsIdByStateId(u8);`
- L21: `void SetPlayerAvatarStateMask(u8 mask);`
- L22: `void AlignFishingAnimationFrames(struct Sprite *sprite);`
- L23: `void CreateStopSurfingTask_NoMusicChange(u8 direction);`
- L24: `void SavePlayerFacingDirectionForTeleport(u8 direction);`
- L25: `void SetPlayerAvatarTransitionFlags(u16 flags);`
- L26: `bool8 IsPlayerFacingSurfableFishableWater(void);`
- L27: `void StartFishing(u8 secondaryId);`
- L28: `u8 GetPlayerAvatarObjectId(void);`
- L29: `u8 PlayerGetElevation(void);`
- L30: `u8 GetPlayerAvatarGraphicsIdByCurrentState(void);`
- L31: `void StartPlayerAvatarSummonMonForFieldMoveAnim(void);`
- L32: `void SetPlayerInvisibility(bool8);`
- L33: `void StartTeleportInPlayerAnim(void);`
- L34: `void StartTeleportWarpOutPlayerAnim(void);`
- L35: `bool32 WaitTeleportWarpOutPlayerAnim(void);`
- L36: `bool32 WaitTeleportInPlayerAnim(void);`
- L37: `bool8 PartyHasMonWithSurf(void);`
- L38: `bool8 IsPlayerSurfingNorth(void);`
- L39: `u8 player_get_pos_including_state_based_drift(s16 *x, s16 *y);`
- L40: `void StartPlayerAvatarVsSeekerAnim(void);`
- L41: `u8 GetRivalAvatarGraphicsIdByStateIdAndGender(u8 state, u8 gender);`
- L42: `u8 GetPlayerAvatarGraphicsIdByStateIdAndGender(u8 state, u8 gender);`
- L43: `u8 CheckForObjectEventCollision(struct ObjectEvent *objectEvent, s16 x, s16 y, u8 direction, u8 metatileBehavior);`
- L44: `void PlayerWalkSlower(u8 direction);`
- L45: `void PlayerWalkSlow(u8 direction);`
- L46: `void PlayerWalkNormal(u8 direction);`
- L47: `void PlayerWalkFast(u8 direction);`
- L48: `void PlayerGlide(u8 direction);`
- L49: `void PlayerRideWaterCurrent(u8 direction);`
- L50: `void PlayerWalkFaster(u8 direction);`
- L51: `void PlayerRun(u8 direction);`
- L52: `void PlayerRunSlow(u8 direction);`
- L53: `void PlayerOnBikeCollide(u8 direction);`
- L54: `void PlayerNotOnBikeCollide(u8 direction);`
- L55: `void PlayerFaceDirection(u8 direction);`
- L56: `void PlayerFaceDirectionFast(u8 direction);`
- L57: `void PlayerTurnInPlace(u8 direction);`
- L58: `void PlayerJumpLedge(u8 direction);`
- L59: `void PlayerShakeHeadOrWalkInPlace(void);`
- L60: `void player_step(u8 direction, u16 newKeys, u16 heldKeys);`
- L61: `bool32 PlayerIsMovingOnRockStairs(u8 direction);`
- L62: `void UpdatePlayerAvatarTransitionState(void);`
- L63: `void InitPlayerAvatar(s16 x, s16 y, u8 direction, u8 gender);`
- L64: `void PlayerUseAcroBikeOnBumpySlope(u8 direction);`
- L65: `u8 GetRSAvatarGraphicsIdByGender(u8 gender);`
- L67: `#endif //GUARD_FIELD_PLAYER_AVATAR_H`

## Dependencies, expansion relevance and independent review

Independently trace every implementation/consumer, movement-state transitions, ledge and terrain collision, player-sprite ID mapping, warp synchronization, signed coordinates, map layers, and special movement under expanded maps. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

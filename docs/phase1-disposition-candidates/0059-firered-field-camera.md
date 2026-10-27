# Analyst whole-file candidate 0059 — Camera state and metatile redraw ABI

**ANALYST-PREPARED ONLY; independent verdict pending.** Source: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_camera.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/field_camera.h); exact pinned Git blob SHA-1 `e48d1c8a7aac148bb8c06ca8b1bc8c973b3907dd`. Inspected the **entire 42-line header**; all nonblank, non-comment source lines are enumerated below, including guards, types, enumerators, globals and prototypes. This is not a source-implementation review or approval.

## Whole-file semantic disposition (source-level)

The CameraObject embeds a callback function pointer, u32 spriteId, signed 32-bit movement speeds and coordinates; three exported RAM globals expose camera state and pixel offsets. APIs combine whole-map redraw, per-metatile redraw, door tile writes, camera panning and tracked-sprite callback initialization.

## Exhaustive non-comment source-line inventory

- L1: `#ifndef GUARD_FIELD_CAMERA_H`
- L2: `#define GUARD_FIELD_CAMERA_H`
- L4: `#include "global.h"`
- L8: `struct CameraObject`
- L9: `{`
- L10: `void (*callback)(struct CameraObject *);`
- L11: `u32 spriteId;`
- L12: `s32 movementSpeedX;`
- L13: `s32 movementSpeedY;`
- L14: `s32 x;`
- L15: `s32 y;`
- L16: `};`
- L20: `extern struct CameraObject gFieldCamera;`
- L21: `extern u16 gTotalCameraPixelOffsetX;`
- L22: `extern u16 gTotalCameraPixelOffsetY;`
- L23: `extern bool8 gBikeCameraAheadPanback;`
- L27: `void DrawWholeMapView(void);`
- L28: `void CurrentMapDrawMetatileAt(int x, int y);`
- L29: `void FieldCameraGetPixelOffsetAtGround(s16 *x, s16 *y);`
- L30: `void SetCameraPanningCallback(void (*cb)(void));`
- L31: `void SetCameraPanning(s16 x, s16 y);`
- L32: `void UpdateCameraPanning(void);`
- L33: `void InstallCameraPanAheadCallback(void);`
- L34: `void DrawDoorMetatileAt(int x, int y, const u16 *data);`
- L35: `void move_tilemap_camera_to_upper_left_corner(void);`
- L36: `void CameraUpdate(void);`
- L37: `void FieldUpdateBgTilemapScroll(void);`
- L38: `void ResetCameraUpdateInfo(void);`
- L39: `u32 InitCameraUpdateCallback(u8 trackedSpriteId);`
- L40: `void CameraUpdateNoObjectRefresh(void);`
- L42: `#endif //GUARD_FIELD_CAMERA_H`

## Dependencies, expansion relevance and independent review

Trace camera struct consumers and layout, sprite ID validity, tile coordinate clipping, pixel-offset overflow, callback lifetime and map-transition redraw before certifying editor or expanded-map compatibility. This declaration-only file does not itself prove caller preconditions, linker/compiled behavior, save persistence, emulator execution or editor round-trip. Validate exact symbol definitions, conditional compilation and consumers against the pinned upstream revision. No independent reviewer has attested this file.

**Disposition: prepared for independent whole-file review; approved 0; authoritative Phase 1 gate FAIL_INCOMPLETE.**

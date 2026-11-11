/*
 * XGBA FireRed R4: optional, bounded staged static sprite-sheet adapter.
 * Build against pinned pret/pokefirered (no copied or patched upstream code).
 * This is GAME-SIDE C. The emulator-side resource handshake is R5; an external
 * file cannot become a GBA pointer. Only already-staged EWRAM bytes are read.
 * The native LoadSpriteSheet() synchronously copies tiles to OBJ_VRAM0.
 */
#include "global.h"
#include "sprite.h"
#include <stdint.h>

#define XGBA_STATIC_SPRITE_ABI_VERSION 1u
#define XGBA_STATIC_SPRITE_MAX_BYTES 0x4000u

struct XgbaStagedSprite
{
    u32 abiVersion;
    u32 resourceId;
    const void *ewramData;
    u32 byteLength;
    bool8 validatedByProvider;
};

static bool8 XgbaIsBoundedEwram(const void *address, u32 byteLength)
{
    uintptr_t start = (uintptr_t)address;
    if (byteLength == 0 || byteLength > XGBA_STATIC_SPRITE_MAX_BYTES)
        return FALSE;
    if ((start & 1u) != 0 || start < EWRAM_START || start >= EWRAM_END)
        return FALSE;
    return byteLength <= (u32)(EWRAM_END - start);
}

/*
 * The expected resource ID is selected by FireRed's own callsite. The R5
 * provider must authenticate the ROM/manifest, verify SHA-256, stage the bytes
 * into this EWRAM window, and mark validatedByProvider only after success.
 * The flag is NOT a cryptographic check on its own. Without a valid opt-in
 * resource request, the original SpriteSheet is passed to the native loader.
 * Note: LoadSpriteSheet returns 0 on allocation failure and can also return
 * tile index zero on success; usedStaging reports selection, not allocation.
 */
u16 XgbaLoadStagedSpriteSheet(const struct SpriteSheet *original,
                              u32 expectedResourceId,
                              const struct XgbaStagedSprite *stage,
                              bool8 *usedStaging)
{
    struct SpriteSheet selected;
    if (usedStaging != NULL)
        *usedStaging = FALSE;
    if (original == NULL || original->data == NULL || original->size == 0)
        return 0;
    if (expectedResourceId == 0 || stage == NULL
        || stage->abiVersion != XGBA_STATIC_SPRITE_ABI_VERSION
        || stage->resourceId != expectedResourceId
        || stage->validatedByProvider != TRUE
        || stage->byteLength != original->size
        || (stage->byteLength % TILE_SIZE_4BPP) != 0
        || !XgbaIsBoundedEwram(stage->ewramData, stage->byteLength))
        return LoadSpriteSheet(original);
    selected = *original;
    selected.data = stage->ewramData;
    if (usedStaging != NULL)
        *usedStaging = TRUE;
    return LoadSpriteSheet(&selected);
}

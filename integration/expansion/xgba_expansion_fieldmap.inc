/*
 * Source-integrated opt-in external map / tileset reader for pinned RHH.
 * Included in fieldmap.c after its normal headers. Vanilla assets remain the
 * fallback; missing external resources must never produce partial map data.
 *
 * A caller binds a real MapLayout and SHA-validated provider IDs before a
 * normal map transition. No resource IDs or original map IDs are rewritten.
 * This first slice supports maps <= 8192 metatiles and <= 512 4bpp tiles per
 * tileset; larger assets require a later staged/segmented implementation.
 */
#include "XGBA_EXPANSION_MAP_API_PLACEHOLDER"

static const struct MapLayout *sXgbaMapLayout;
static const char *sXgbaMapResource;
static const char *sXgbaPrimaryResource;
static const char *sXgbaSecondaryResource;

void XgbaExpansionBindMapTilesets(const struct MapLayout *layout,
                                 const char *mapId,
                                 const char *primaryId,
                                 const char *secondaryId)
{
    /* Invalidate previous single-map binding on every transition. */
    XgbaExpansionPageRelease();
    sXgbaMapLayout = layout;
    sXgbaMapResource = mapId;
    sXgbaPrimaryResource = primaryId;
    sXgbaSecondaryResource = secondaryId;
}

void XgbaExpansionUnbindMapTilesets(void)
{
    XgbaExpansionBindMapTilesets(NULL, NULL, NULL, NULL);
}

static bool8 XgbaExpansionTryMapCopy(const struct MapLayout *layout)
{
    u32 bytes;
    u32 y;
    const u8 *data;
    u16 *dest;
    if (layout != sXgbaMapLayout || !sXgbaMapResource || !layout)
        return FALSE;
    if (!layout->width || !layout->height
        || layout->width > XGBA_EXPANSION_PAGE_CAPACITY / 2u / layout->height)
        return FALSE;
    bytes = layout->width * layout->height * 2u;
    if (XgbaExpansionPageAcquire(sXgbaMapResource, bytes) != bytes)
        return FALSE;
    data = XgbaExpansionPageData();
    if (!data)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    dest = gBackupMapLayout.map
         + gBackupMapLayout.width * MAP_OFFSET + MAP_OFFSET;
    for (y = 0; y < layout->height; ++y)
    {
        CpuCopy16(data + y * layout->width * 2u, dest, layout->width * 2u);
        dest += gBackupMapLayout.width;
    }
    XgbaExpansionPageRelease();
    return TRUE;
}

/*
 * The external page is invalidated by the next acquire. Unlike LoadBgTiles,
 * which may schedule a DMA from its input pointer, this path copies directly
 * while display is forced blank, then releases the page synchronously.
 * When the display is live, or the external page is absent, the regular RHH
 * loader is used without changing the original graphics.
 */
static bool8 XgbaExpansionTryTilesetCopy(const struct Tileset *tileset,
                                         u16 numTiles, u16 offset)
{
    const char *id = NULL;
    const u8 *data;
    u32 bytes = (u32)numTiles * 32u;
    if (!sXgbaMapLayout || !tileset)
        return FALSE;
    if (tileset == sXgbaMapLayout->primaryTileset)
        id = sXgbaPrimaryResource;
    else if (tileset == sXgbaMapLayout->secondaryTileset)
        id = sXgbaSecondaryResource;
    if (!id || !numTiles || bytes > XGBA_EXPANSION_PAGE_CAPACITY)
        return FALSE;
    if (!(REG_DISPCNT & DISPCNT_FORCED_BLANK))
        return FALSE;
    if (XgbaExpansionPageAcquire(id, bytes) != bytes)
        return FALSE;
    data = XgbaExpansionPageData();
    if (!data)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    CpuCopy16(data, (void *)(BG_VRAM + (u32)offset * 32u), bytes);
    XgbaExpansionPageRelease();
    return TRUE;
}

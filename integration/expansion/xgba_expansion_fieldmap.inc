/*
 * RHH 1.17.2 map/tileset XGBA source integration.
 *
 * The actual InitMapLayoutData and both normal tileset loaders call these
 * handlers. Source-owned resources are identified by original layout ID.
 * An absent/incomplete external provider falls back to unchanged ROM assets.
 * Every external 16KiB page is acquired, synchronously copied and released.
 */
#include "XGBA_EXPANSION_MAP_API_PLACEHOLDER"

#define XGBA_FIELD_CHUNK 16384u
#define XGBA_FIELD_ID_SIZE 40u

static const struct MapLayout *sXgbaMapLayout;
static const char *sXgbaMapResource;
static const char *sXgbaPrimaryResource;
static const char *sXgbaSecondaryResource;
static char sXgbaAutoMapId[20];
static char sXgbaAutoPrimaryId[20];
static char sXgbaAutoSecondaryId[20];
static bool8 sXgbaSmokeMapUsed;
static bool8 sXgbaSmokePrimaryUsed;
extern void XgbaExpansionMapSmokeReport(u32 layout, u32 mapUsed, u32 tilesUsed,
                                        u32 mapHash, u32 tilesHash,
                                        u32 mapBytes, u32 tilesBytes);
extern void XgbaExpansionSourceTransfer(u32 kind, u32 bytes);

/* The provider manifest holds one entry per original-source page, including
 * the short final page. Never change or recatalogue original map/layout IDs. */
static void XgbaExpansionMakeLayoutId(char *out, char kind, u16 layoutId)
{
    static const char hex[] = "0123456789abcdef";
    out[0] = 'r'; out[1] = 'h'; out[2] = 'h'; out[3] = '.';
    out[4] = kind; out[5] = '.';
    out[6] = hex[(layoutId >> 12) & 15u];
    out[7] = hex[(layoutId >> 8) & 15u];
    out[8] = hex[(layoutId >> 4) & 15u];
    out[9] = hex[layoutId & 15u];
    out[10] = '\0';
}

/* Reject long, malformed or ambiguous source IDs rather than truncate. */
static bool8 XgbaExpansionChunkId(char out[XGBA_FIELD_ID_SIZE],
                                   const char *base, u32 chunk)
{
    static const char hex[] = "0123456789abcdef";
    u32 i;
    if (!base || chunk > 255u)
        return FALSE;
    for (i = 0; i < XGBA_FIELD_ID_SIZE - 4u && base[i]; ++i)
        out[i] = base[i];
    if (i == 0u || i >= XGBA_FIELD_ID_SIZE - 4u || base[i])
        return FALSE;
    out[i++] = '.';
    out[i++] = hex[(chunk >> 4) & 15u];
    out[i++] = hex[chunk & 15u];
    out[i] = '\0';
    return TRUE;
}

void XgbaExpansionBindMapTilesets(const struct MapLayout *layout,
                                 const char *mapId,
                                 const char *primaryId,
                                 const char *secondaryId)
{
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

/* Called on the authentic map-init path for all three variants. Disable
 * overrides for dynamic layouts where the source ID cannot be substantiated. */
static void XgbaExpansionBindOriginalMap(const struct MapHeader *header)
{
    u16 id;
    if (!header || !header->mapLayout)
    {
        XgbaExpansionUnbindMapTilesets();
        return;
    }
    id = header->mapLayoutId;
    if (!id || GetMapLayout(id) != header->mapLayout)
    {
        XgbaExpansionSourceTransfer(10u, 0u);
        XgbaExpansionUnbindMapTilesets();
        return;
    }
    XgbaExpansionSourceTransfer(11u, 0u);
    XgbaExpansionMakeLayoutId(sXgbaAutoMapId, 'm', id);
    XgbaExpansionMakeLayoutId(sXgbaAutoPrimaryId, 'p', id);
    XgbaExpansionMakeLayoutId(sXgbaAutoSecondaryId, 's', id);
    XgbaExpansionBindMapTilesets(header->mapLayout, sXgbaAutoMapId,
                                 sXgbaAutoPrimaryId, sXgbaAutoSecondaryId);
}

/* The untouched ROM layout has already been copied to the backup grid.  If
 * any page fails after earlier pages were installed, restore the entire
 * original grid to avoid mixed-source map data. */
static bool8 XgbaExpansionTryMapCopy(const struct MapLayout *layout)
{
    u32 total, start, n, at, copied = 0u;
    char id[XGBA_FIELD_ID_SIZE];
    const u8 *data;
    u16 *dest;
    if (layout != sXgbaMapLayout || !sXgbaMapResource || !layout)
        return FALSE;
    if (layout->width <= 0 || layout->height <= 0 ||
        (u32)layout->width > MAX_MAP_DATA_SIZE / (u32)layout->height)
        return FALSE;
    total = (u32)layout->width * (u32)layout->height * 2u;
    dest = gBackupMapLayout.map + gBackupMapLayout.width * MAP_OFFSET + MAP_OFFSET;
    for (start = 0; start < total; start += XGBA_FIELD_CHUNK)
    {
        if (!XgbaExpansionChunkId(id, sXgbaMapResource,
                                  start / XGBA_FIELD_CHUNK))
            break;
        n = total - start;
        if (n > XGBA_FIELD_CHUNK)
            n = XGBA_FIELD_CHUNK;
        if (XgbaExpansionPageAcquire(id, n) != n)
            break;
        data = XgbaExpansionPageData();
        if (!data)
            break;
        /* Copy in row-bounded segments. A chunk may start in a partial row. */
        for (at = 0; at < n;)
        {
            u32 index = (start + at) / 2u;
            u32 col = index % (u32)layout->width;
            u32 segment = ((u32)layout->width - col) * 2u;
            if (segment > n - at)
                segment = n - at;
            CpuCopy16(data + at, dest + (index / (u32)layout->width)
                      * gBackupMapLayout.width + col, segment);
            at += segment;
        }
        XgbaExpansionPageRelease();
        copied += n;
    }
    if (copied == total)
    {
        sXgbaSmokeMapUsed = TRUE;
        XgbaExpansionSourceTransfer(1u, total);
        return TRUE;
    }
    XgbaExpansionPageRelease();
    InitBackupMapLayoutData(layout->map, layout->width, layout->height);
    return FALSE;
}

/* A native RHH BG loader owns the DMA scheduling and BG charbase offset.
 * External pages are transient: assemble the complete original tileset in
 * a heap-owned staging lease, then enqueue it ONCE through LoadBgTiles.
 * Never free the source until the engine reports its BG DMA complete.
 * No direct VRAM writes, forced blank toggles, or retained page pointers.
 * Two bounded leases cover the primary and secondary loads in one map. */
#define XGBA_GRAPHICS_LEASES 2u
struct XgbaGraphicsLease
{
    void *data;
};
static struct XgbaGraphicsLease sXgbaGraphicsLeases[XGBA_GRAPHICS_LEASES];

static void XgbaExpansionGraphicsPoll(void)
{
    u32 i;
    if (IsDma3ManagerBusyWithBgCopy())
        return;
    for (i = 0; i < XGBA_GRAPHICS_LEASES; ++i)
    {
        if (sXgbaGraphicsLeases[i].data)
        {
            Free(sXgbaGraphicsLeases[i].data);
            sXgbaGraphicsLeases[i].data = NULL;
        }
    }
}

static bool8 XgbaExpansionTryTilesetCopy(const struct Tileset *tileset,
                                         u16 numTiles, u16 offset)
{
    const char *base = NULL;
    u8 *staging;
    const u8 *page;
    u32 total = (u32)numTiles * 32u;
    u32 start, n, slot;
    char id[XGBA_FIELD_ID_SIZE];
    if (tileset && sXgbaMapLayout)
    {
        if (tileset == sXgbaMapLayout->primaryTileset)
            base = sXgbaPrimaryResource;
        else if (tileset == sXgbaMapLayout->secondaryTileset)
            base = sXgbaSecondaryResource;
    }
    if (!base || !numTiles || !total || (u32)offset + numTiles > NUM_TILES_TOTAL)
        return FALSE;
    XgbaExpansionGraphicsPoll();
    for (slot = 0; slot < XGBA_GRAPHICS_LEASES; ++slot)
        if (!sXgbaGraphicsLeases[slot].data)
            break;
    if (slot == XGBA_GRAPHICS_LEASES)
        return FALSE; /* never overwrite a pending DMA source */
    staging = Alloc(total);
    if (!staging)
        return FALSE;
    for (start = 0; start < total; start += XGBA_FIELD_CHUNK)
    {
        if (!XgbaExpansionChunkId(id, base, start / XGBA_FIELD_CHUNK))
            break;
        n = total - start;
        if (n > XGBA_FIELD_CHUNK)
            n = XGBA_FIELD_CHUNK;
        if (XgbaExpansionPageAcquire(id, n) != n)
            break;
        page = XgbaExpansionPageData();
        if (!page)
            break;
        CpuCopy16(page, staging + start, n);
        XgbaExpansionPageRelease();
    }
    XgbaExpansionPageRelease();
    if (start < total)
    {
        Free(staging);
        return FALSE; /* original loader may safely use ROM assets */
    }
    /* RHH's own BG loader schedules DMA, handles charbase and tile tracking.
     * Retain the staging lease until its completion is observed. */
    if (LoadBgTiles(2, staging, total, offset) == 0xFFFFu)
    {
        Free(staging);
        return FALSE;
    }
    sXgbaGraphicsLeases[slot].data = staging;
    if (tileset == sXgbaMapLayout->primaryTileset)
    {
        sXgbaSmokePrimaryUsed = TRUE;
        XgbaExpansionSourceTransfer(2u, total);
    }
    else
        XgbaExpansionSourceTransfer(3u, total);
    return TRUE;
}

/*
 * Explicit test-only native entrypoint, invoked by --map-smoke builds once
 * after InitHeap. It calls the real original map and primary tile loaders;
 * it is NOT a scripted gameplay transition, and its pixels are not claimed
 * to be an in-game map screenshot. Normal builds do not invoke this routine.
 */
void XgbaExpansionNativeMapTileSmoke(void)
{
    struct MapHeader header = {0};
    const struct MapLayout *layout;
    u32 mapHash = 2166136261u;
    u32 tileHash = 2166136261u;
    u32 mapBytes, tileBytes, y, x, i;
    const u8 *grid;
    const volatile u8 *vram = (const volatile u8 *)BG_VRAM;
    u16 oldDisplay;
#if defined(EMERALD)
    const u16 layoutId = 10u;  /* LAYOUT_LITTLEROOT_TOWN in pinned RHH */
#else
    const u16 layoutId = 481u; /* LAYOUT_PALLET_TOWN in pinned RHH */
#endif

    layout = GetMapLayout(layoutId);
    if (!layout || layout->width <= 0 || layout->height <= 0)
        return;
    sXgbaSmokeMapUsed = FALSE;
    sXgbaSmokePrimaryUsed = FALSE;
    header.mapLayout = layout;
    header.mapLayoutId = layoutId;
    InitMapLayoutData(&header); /* genuine original RHH fieldmap entrypoint */
    mapBytes = (u32)layout->width * (u32)layout->height * 2u;
    grid = (const u8 *)gBackupMapLayout.map;
    for (y = 0; y < (u32)layout->height; ++y)
    {
        const u32 row = ((y + MAP_OFFSET) * gBackupMapLayout.width + MAP_OFFSET) * 2u;
        for (x = 0; x < (u32)layout->width * 2u; ++x)
            mapHash = (mapHash ^ grid[row + x]) * 16777619u;
    }
    oldDisplay = REG_DISPCNT;
    REG_DISPCNT = oldDisplay | DISPCNT_FORCED_BLANK;
    CopyPrimaryTilesetToVram(layout); /* genuine original RHH tileset path */
    tileBytes = GetNumTilesInPrimary(layout) * 32u;
    for (i = 0; i < tileBytes; ++i)
        tileHash = (tileHash ^ vram[i]) * 16777619u;
    REG_DISPCNT = oldDisplay;
    XgbaExpansionUnbindMapTilesets();
    XgbaExpansionMapSmokeReport(layoutId, sXgbaSmokeMapUsed,
                                sXgbaSmokePrimaryUsed, mapHash, tileHash,
                                mapBytes, tileBytes);
}

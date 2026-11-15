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
        XgbaExpansionUnbindMapTilesets();
        return;
    }
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
    u32 total, start, n, at;
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
    }
    if (start == total)
        return TRUE;
    XgbaExpansionPageRelease();
    InitBackupMapLayoutData(layout->map, layout->width, layout->height);
    return FALSE;
}

/* A tileset can exceed one 16 KiB page (FRLG primary = 20 KiB).
 * Page bytes are raw original 4bpp tiles, never LZ77. Copy directly to VRAM
 * only under forced blank, so no queued BG loader/DMA retains a page pointer.
 * If a later page is unavailable the caller executes the full ROM loader,
 * replacing any partially transferred external graphics. */
static bool8 XgbaExpansionTryTilesetCopy(const struct Tileset *tileset,
                                         u16 numTiles, u16 offset)
{
    const char *base = NULL;
    const u8 *data;
    u32 total = (u32)numTiles * 32u;
    u32 start, n;
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
    if (!(REG_DISPCNT & DISPCNT_FORCED_BLANK))
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
        data = XgbaExpansionPageData();
        if (!data)
            break;
        CpuCopy16(data, (void *)(BG_VRAM + (u32)offset * 32u + start), n);
        XgbaExpansionPageRelease();
    }
    if (start == total)
        return TRUE;
    XgbaExpansionPageRelease();
    return FALSE;
}

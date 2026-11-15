/*
 * XGBA on RH-Hideout pokeemerald-expansion (Emerald / FireRed / LeafGreen).
 *
 * Phase 2: a reusable protected 16KiB external-resource page leased from the
 * existing RH-Hideout heap, not a new unbudgeted EWRAM allocation.  Each
 * versioned resource is fetched by the REAL game CPU using the shared MMIO.
 * Gameplay map/tileset/battle hooks remain separate acceptance work.
 */
#if (defined(EMERALD) + defined(FIRERED) + defined(LEAFGREEN)) != 1
#error "XGBA expansion adapter requires exactly one game build target"
#endif

#include "__XGBA_SHARED_GUEST__"
#include "__XGBA_PAGE_API__"

#define XGBA_EXPANSION_PROBE_MAGIC 0x58474241u
#define XGBA_EXPANSION_PAGE_BYTES 0x4000u
#if XGBA_EXPANSION_PAGE_CAPACITY != XGBA_EXPANSION_PAGE_BYTES
#error "XGBA runtime page size diverged from public ABI"
#endif
#if HEAP_SIZE <= XGBA_EXPANSION_PAGE_BYTES
#error "XGBA protected page exceeds RH-Hideout allocator"
#endif
#define XGBA_EXPANSION_HEAP_BYTES (HEAP_SIZE - XGBA_EXPANSION_PAGE_BYTES)
#define XGBA_EXPANSION_PAGE (gHeap + XGBA_EXPANSION_HEAP_BYTES)

#if defined(EMERALD)
#define XGBA_EXPANSION_RESOURCE_ID "expansion.emerald.bridge"
#define XGBA_EXPANSION_GAME_MARKER 0x454D5244u
#elif defined(FIRERED)
#define XGBA_EXPANSION_RESOURCE_ID "expansion.firered.bridge"
#define XGBA_EXPANSION_GAME_MARKER 0x46525244u
#else
#define XGBA_EXPANSION_RESOURCE_ID "expansion.leafgreen.bridge"
#define XGBA_EXPANSION_GAME_MARKER 0x4C464752u
#endif

struct XgbaExpansionProof {
    volatile u32 magic;
    volatile u32 build_marker;
    volatile u32 state;          /* 1 before fetch; 3 after fetch */
    volatile u32 received;
    volatile u32 valid;
    volatile u32 buffer_address; /* native guest EWRAM pointer */
    volatile u32 main_loop_ticks;
    volatile u32 arena_capacity; /* exact bounded hardware-facing page */
    volatile u32 heap_usable_bytes;
    volatile u32 page_generation;
    volatile u32 page_resident;
    /* Only the explicit --map-smoke source-build calls the real map loader
     * at boot. The ordinary game build leaves these values zero. */
    volatile u32 map_smoke_state;   /* 3 after original loader execution */
    volatile u32 map_smoke_layout;
    volatile u32 map_smoke_map_used;
    volatile u32 map_smoke_tiles_used;
    volatile u32 map_smoke_map_hash;     /* FNV-1a over copied live grid */
    volatile u32 map_smoke_tiles_hash;   /* FNV-1a over physical BG VRAM */
    volatile u32 map_smoke_map_bytes;
    volatile u32 map_smoke_tiles_bytes;
    /* Test-only real overworld witness. Appended: all legacy offsets stable. */
    volatile u32 live_state;
    volatile u32 live_frames;
    volatile u32 live_layout;
    volatile u32 live_first_layout;
    volatile u32 live_x;
    volatile u32 live_y;
    volatile u32 live_movements;
    volatile u32 live_transitions;
    volatile u32 live_source_maps;
    volatile u32 live_source_primary;
    volatile u32 live_source_secondary;
    volatile u32 live_source_bytes;
    volatile u32 live_stage; /* opt-in deterministic native startup checkpoints */
};

/* Small metadata only. The 16KiB payload itself resides inside the
 * existing gHeap EWRAM region, outside the allocator's reduced ownership. */
EWRAM_DATA volatile struct XgbaExpansionProof gXgbaExpansionProof = {0};
EWRAM_DATA ALIGNED(4) char gXgbaExpansionId[40] = {0};

static void XgbaExpansionPageReset(void)
{
    u32 i;
    for (i = 0; i < XGBA_EXPANSION_PAGE_BYTES; ++i)
        XGBA_EXPANSION_PAGE[i] = 0xA5u;
    gXgbaExpansionProof.page_resident = 0u;
    ++gXgbaExpansionProof.page_generation;
}

/* Reusable one-page ownership API for runtime graphics/map integrations.
 * Never disclose a page as valid after a short, missing or corrupt fetch.
 * The host manifest validates source and SHA-256 before writing into EWRAM.
 * Each acquire explicitly invalidates prior residency/cache generations. */
u32 XgbaExpansionPageAcquire(const char *resource, u32 length)
{
    u32 i;
    u32 got;
    if (!resource || length == 0u || length > XGBA_EXPANSION_PAGE_BYTES)
    {
        XgbaExpansionPageReset();
        return 0u;
    }
    for (i = 0; i < sizeof(gXgbaExpansionId); ++i)
        gXgbaExpansionId[i] = 0;
    for (i = 0; i < sizeof(gXgbaExpansionId)-1u && resource[i]; ++i)
        gXgbaExpansionId[i] = resource[i];
    if (resource[i])
    {
        XgbaExpansionPageReset();
        return 0u; /* reject truncation/ambiguous source resource ID */
    }
    XgbaExpansionPageReset();
    got = XgbaGuestFetch(gXgbaExpansionId, XGBA_EXPANSION_PAGE, length);
    if (got != length)
    {
        XgbaExpansionPageReset();
        return 0u;
    }
    gXgbaExpansionProof.page_resident = length;
    return got;
}

void XgbaExpansionPageRelease(void)
{
    XgbaExpansionPageReset();
}

const u8 *XgbaExpansionPageData(void)
{
    return gXgbaExpansionProof.page_resident ? XGBA_EXPANSION_PAGE : NULL;
}

u32 XgbaExpansionPageResidentBytes(void)
{
    return gXgbaExpansionProof.page_resident;
}

u32 XgbaExpansionPageGeneration(void)
{
    return gXgbaExpansionProof.page_generation;
}

void XgbaExpansionMapSmokeReport(u32 layout, u32 mapUsed, u32 tilesUsed,
                                 u32 mapHash, u32 tilesHash,
                                 u32 mapBytes, u32 tilesBytes)
{
    gXgbaExpansionProof.map_smoke_layout = layout;
    gXgbaExpansionProof.map_smoke_map_used = mapUsed;
    gXgbaExpansionProof.map_smoke_tiles_used = tilesUsed;
    gXgbaExpansionProof.map_smoke_map_hash = mapHash;
    gXgbaExpansionProof.map_smoke_tiles_hash = tilesHash;
    gXgbaExpansionProof.map_smoke_map_bytes = mapBytes;
    gXgbaExpansionProof.map_smoke_tiles_bytes = tilesBytes;
    gXgbaExpansionProof.map_smoke_state = 3u;
}


/* Updated ONLY by the genuine CB2_Overworld and actual fieldmap loaders.
 * The emulator never injects game state, memory or a fake controller event. */
void XgbaExpansionLiveTick(u32 layout, s32 x, s32 y)
{
    if (!layout || !gXgbaExpansionProof.state)
        return;
    if (!gXgbaExpansionProof.live_state)
    {
        gXgbaExpansionProof.live_first_layout = layout;
        gXgbaExpansionProof.live_state = 1u;
    }
    else
    {
        if (gXgbaExpansionProof.live_x != (u32)x ||
            gXgbaExpansionProof.live_y != (u32)y)
            ++gXgbaExpansionProof.live_movements;
        if (gXgbaExpansionProof.live_layout != layout)
            ++gXgbaExpansionProof.live_transitions;
    }
    ++gXgbaExpansionProof.live_frames;
    gXgbaExpansionProof.live_layout = layout;
    gXgbaExpansionProof.live_x = (u32)x;
    gXgbaExpansionProof.live_y = (u32)y;
}

void XgbaExpansionLiveStage(u32 stage)
{
    gXgbaExpansionProof.live_stage = stage;
}

void XgbaExpansionSourceTransfer(u32 kind, u32 bytes)
{
    if (kind == 1u)
        ++gXgbaExpansionProof.live_source_maps;
    else if (kind == 2u)
        ++gXgbaExpansionProof.live_source_primary;
    else if (kind == 3u)
        ++gXgbaExpansionProof.live_source_secondary;
    else
        return;
    gXgbaExpansionProof.live_source_bytes += bytes;
}

static void XgbaExpansionProbeBoot(void)
{
    static const char resourceId[] = XGBA_EXPANSION_RESOURCE_ID;
    u32 got;

    gXgbaExpansionProof.magic = XGBA_EXPANSION_PROBE_MAGIC;
    gXgbaExpansionProof.build_marker = XGBA_EXPANSION_GAME_MARKER;
    gXgbaExpansionProof.state = 1u;
    gXgbaExpansionProof.received = 0u;
    gXgbaExpansionProof.valid = 0u;
    gXgbaExpansionProof.buffer_address = (u32)XGBA_EXPANSION_PAGE;
    gXgbaExpansionProof.main_loop_ticks = 0u;
    gXgbaExpansionProof.arena_capacity = XGBA_EXPANSION_PAGE_BYTES;
    gXgbaExpansionProof.heap_usable_bytes = XGBA_EXPANSION_HEAP_BYTES;
    gXgbaExpansionProof.page_generation = 0u;
    gXgbaExpansionProof.page_resident = 0u;

    got = XgbaExpansionPageAcquire(resourceId, XGBA_EXPANSION_PAGE_BYTES);
    gXgbaExpansionProof.received = got;
    gXgbaExpansionProof.valid = (got == XGBA_EXPANSION_PAGE_BYTES);
    gXgbaExpansionProof.state = 3u;

    /* Continue unmodified RHH game boot, even if the provider is disabled. */
}

static void XgbaExpansionProbeTick(void)
{
    ++gXgbaExpansionProof.main_loop_ticks;
}

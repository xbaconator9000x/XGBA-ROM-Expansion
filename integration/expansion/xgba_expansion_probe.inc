/*
 * XGBA on RH-Hideout pokeemerald-expansion (Emerald / FireRed / LeafGreen).
 *
 * Source-only bootstrap: prove the EXISTING opt-in XGBA guest MMIO ABI can
 * be linked into every supported upstream game variant. NOT a map loader.
 * The resource ID and the destination must live in actual guest EWRAM.
 * No vendor assets, ROM bytes, save files or new emulator protocol.
 */
#if (defined(EMERALD) + defined(FIRERED) + defined(LEAFGREEN)) != 1
#error "XGBA expansion bootstrap requires exactly one game build target"
#endif

#include "__XGBA_SHARED_GUEST__"

#define XGBA_EXPANSION_PROBE_MAGIC 0x58474241u
#define XGBA_EXPANSION_PROBE_SIZE 64u

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
    volatile u32 state;          /* 1 before fetch, 3 afterwards */
    volatile u32 received;
    volatile u32 valid;          /* 1 ONLY after exact length */
    volatile u32 buffer_address; /* native guest EWRAM pointer */
    volatile u32 main_loop_ticks;
};

EWRAM_DATA volatile struct XgbaExpansionProof gXgbaExpansionProof = {0};
EWRAM_DATA ALIGNED(4) u8 gXgbaExpansionData[XGBA_EXPANSION_PROBE_SIZE] = {0};
EWRAM_DATA ALIGNED(4) char gXgbaExpansionId[40] = {0};

static void XgbaExpansionProbeBoot(void)
{
    static const char resourceId[] = XGBA_EXPANSION_RESOURCE_ID;
    u32 i;
    u32 received;

    gXgbaExpansionProof.magic = XGBA_EXPANSION_PROBE_MAGIC;
    gXgbaExpansionProof.build_marker = XGBA_EXPANSION_GAME_MARKER;
    gXgbaExpansionProof.state = 1;
    gXgbaExpansionProof.valid = 0;
    gXgbaExpansionProof.received = 0;
    gXgbaExpansionProof.main_loop_ticks = 0;
    gXgbaExpansionProof.buffer_address = (u32)gXgbaExpansionData;

    /* EWRAM_DATA can be NOLOAD: initialize both arrays explicitly. */
    for (i = 0; i < sizeof(gXgbaExpansionData); ++i)
        gXgbaExpansionData[i] = 0xA5u;
    for (i = 0; i < sizeof(resourceId); ++i)
        gXgbaExpansionId[i] = resourceId[i];

    received = XgbaGuestFetch(gXgbaExpansionId, gXgbaExpansionData,
                              sizeof(gXgbaExpansionData));
    gXgbaExpansionProof.received = received;
    gXgbaExpansionProof.valid = (received == XGBA_EXPANSION_PROBE_SIZE);
    gXgbaExpansionProof.state = 3;

    /* Return to the unmodified upstream boot path even if no sidecar exists. */
}

static void XgbaExpansionProbeTick(void)
{
    ++gXgbaExpansionProof.main_loop_ticks;
}

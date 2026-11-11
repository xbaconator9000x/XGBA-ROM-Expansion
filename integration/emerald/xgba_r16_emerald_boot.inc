/*
 * R16: XGBA shared ABI probe inside real pret/pokeemerald decomp code.
 * This is not a copied FireRed binary offset or a standalone fake ROM.
 * Emerald continues executing its original game loop after the request.
 * The emulator/provider is exactly the same opt-in mGBA R7–R15 bridge.
 */
#include "__XGBA_SHARED_GUEST__"
#define XGBA_EMERALD_PROBE_MAGIC 0x58474241u
#define XGBA_EMERALD_RESOURCE_SIZE 64u

struct XgbaEmeraldProbe {
    volatile u32 magic;          /* +0 */
    volatile u32 state;          /* +4, 3 = guest boot request returned */
    volatile u32 resource_valid; /* +8 */
    volatile u32 received;       /* +12 */
    volatile u32 resource_data;  /* +16: EWRAM destination address */
    volatile u32 engine_marker;  /* +20: 0x454D5244 = Emerald */
    volatile u32 original_main_ticks; /* +24: actual Emerald main loop iterations */
    volatile u32 game_callback2;      /* +28: Emerald-selected callback pointer */
    volatile u32 flash_present;       /* +32: original Emerald flash detection */
};
EWRAM_DATA volatile struct XgbaEmeraldProbe gXgbaEmeraldProbe = {0};
EWRAM_DATA ALIGNED(4) u8 gXgbaEmeraldResource[XGBA_EMERALD_RESOURCE_SIZE] = {0};
EWRAM_DATA char gXgbaEmeraldResourceId[32] = {0};

static void XgbaEmeraldProbeRun(void)
{
    static const char resourceName[] = "emerald.bridge";
    u32 i;
    u32 result;
    gXgbaEmeraldProbe.magic = XGBA_EMERALD_PROBE_MAGIC;
    gXgbaEmeraldProbe.state = 1u;
    /* These buffers are inside actual 256 KiB guest EWRAM, not host memory.
     * Initialise them explicitly because Emerald's EWRAM_DATA is NOLOAD. */
    for (i = 0; i < XGBA_EMERALD_RESOURCE_SIZE; ++i)
        gXgbaEmeraldResource[i] = 0xA5u;
    for (i = 0; i < sizeof(resourceName); ++i)
        gXgbaEmeraldResourceId[i] = resourceName[i];

    result = XgbaGuestFetch(gXgbaEmeraldResourceId,
                            gXgbaEmeraldResource,
                            XGBA_EMERALD_RESOURCE_SIZE);
    gXgbaEmeraldProbe.resource_valid = result == XGBA_EMERALD_RESOURCE_SIZE;
    gXgbaEmeraldProbe.received = result;
    gXgbaEmeraldProbe.resource_data = (u32)gXgbaEmeraldResource;
    gXgbaEmeraldProbe.engine_marker = 0x454D5244u; /* "EMRD" */
    gXgbaEmeraldProbe.original_main_ticks = 0;
    gXgbaEmeraldProbe.game_callback2 = (u32)gMain.callback2;
    gXgbaEmeraldProbe.flash_present = gFlashMemoryPresent;
    gXgbaEmeraldProbe.state = 3u;
    /* Continue to standard Emerald game entry / title callbacks. */
}

static void XgbaEmeraldMainLoopTick(void)
{
    ++gXgbaEmeraldProbe.original_main_ticks;
    gXgbaEmeraldProbe.game_callback2 = (u32)gMain.callback2;
}

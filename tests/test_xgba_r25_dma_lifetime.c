/* R25: exercise REAL xgba_mgba_device.c with the R24 isolated host fixture.
 *
 * This is a portable production-device contract test. It is NOT evidence of
 * actual DMA timing on the pinned original Emerald/FireRed ARM game cores.
 * Native regression runs must be checked separately before promoting R25.
 */
#define main xgba_r24_base_contract_main
#include "test_xgba_r24_mmio_unit.c"
#undef main

#define R25_DEST (0x02000000u + R24_DST_OFF)
#define R25_ENABLE 0x8000u
#define R25_WIDTH32 0x0400u

static unsigned sR25Cases;

static void init_dma_test(struct GBA *gba, struct XgbaGbaDevice *dev)
{
    struct XgbaMgbaProviderV1 host = {0};
    uint8_t sha[32] = {0};
    memset(gba, 0, sizeof(*gba));
    gba->memory.wram = sMemory;
    gba->memory.activeDMA = -1;
    gba->xgbaDevice = dev;
    host.abi_version = 1;
    host.struct_size = sizeof(host);
    assert(XgbaDeviceInit(dev, &host, 1, "native-fixture", sha) == 0);
    XgbaDeviceReset(dev);
}

static void require_dma_busy(struct GBA *gba, struct XgbaGbaDevice *dev)
{
    const size_t reads_before = sMockLookups;
    const uint32_t rejected_before = dev->rejected_dma_aliases;
    reset_destination(gba);
    guest_request(gba, "r24.maximum", R25_DEST, R24_LENGTH,
                  XGBA_R7_DMA_BUSY, 0u);
    verify_unchanged(gba);
    assert(sMockLookups == reads_before);
    assert(dev->rejected_dma_aliases == rejected_before + 1u);
    assert(dev->failed_reads >= dev->rejected_dma_aliases);
    ++sR25Cases;
}

static void require_available(struct GBA *gba, struct XgbaGbaDevice *dev)
{
    const size_t before = sMockLookups;
    const uint32_t successes = dev->successful_reads;
    reset_destination(gba);
    guest_request(gba, "r24.maximum", R25_DEST, R24_LENGTH,
                  XGBA_R7_SUCCESS, R24_LENGTH);
    verify_payload(gba);
    assert(sMockLookups == before + 1u);
    assert(dev->successful_reads == successes + 1u);
    ++sR25Cases;
}

int main(void)
{
    /* Verify the unchanged R24 contract before testing our additional guard. */
    assert(xgba_r24_base_contract_main() == 0);
    struct GBA gba;
    struct XgbaGbaDevice device;
    init_dma_test(&gba, &device);
    struct GBADMA *const d = gba.memory.dma;

    /* Armed IMMEDIATE DMA: source starts just inside destination boundary. */
    d[0].reg = R25_ENABLE;
    d[0].source = R25_DEST + R24_LENGTH - 2u;
    d[0].nextSource = d[0].source;
    d[0].count = 2;
    require_dma_busy(&gba, &device);
    d[0].reg = 0;
    require_available(&gba, &device);

    /* HBlank 32-bit fixed-source repeat: no active cycles required to pin. */
    d[1].reg = R25_ENABLE | R25_WIDTH32 | (2u << 7u) | 0x2000u | 0x0200u;
    d[1].source = R25_DEST + 0x200u;
    d[1].nextSource = d[1].source;
    d[1].count = 16;
    require_dma_busy(&gba, &device);
    d[1].reg = 0;

    /* VBlank decrement: the initial source can sit above overwritten bytes. */
    d[2].reg = R25_ENABLE | R25_WIDTH32 | (1u << 7u) | 0x1000u;
    d[2].source = R25_DEST + 8u;
    d[2].nextSource = d[2].source;
    d[2].count = 16;
    require_dma_busy(&gba, &device);
    d[2].reg = 0;

    /* DMA3 repeat: current nextSource aliases even when configured source is disjoint. */
    d[3].reg = R25_ENABLE | R25_WIDTH32 | 0x0200u;
    d[3].source = 0x02020000u;
    d[3].nextSource = R25_DEST + 0x600u;
    d[3].count = 32;
    require_dma_busy(&gba, &device);
    d[3].reg = 0;
    require_available(&gba, &device);

    /* An in-progress transfer remains protected even if register disabled. */
    d[2].reg = 0;
    d[2].source = R25_DEST + 0x40u;
    d[2].nextSource = d[2].source;
    d[2].count = 8;
    d[2].nextCount = 8;
    gba.memory.activeDMA = 2;
    require_dma_busy(&gba, &device);
    gba.memory.activeDMA = -1;
    d[2].nextCount = 0;
    require_available(&gba, &device);

    /* True disjoint enabled DMA (e.g. audio in IWRAM) must not be refused. */
    d[1].reg = R25_ENABLE | R25_WIDTH32;
    d[1].source = 0x03000000u;
    d[1].nextSource = d[1].source;
    d[1].count = 512;
    require_available(&gba, &device);
    d[1].reg = 0;

    /* R25 protection is calculated in 64 bits for broad source footprints. */
    d[3].reg = R25_ENABLE | R25_WIDTH32;
    d[3].source = R25_DEST - 0x100u;
    d[3].nextSource = d[3].source;
    d[3].count = 65536;
    require_dma_busy(&gba, &device);
    d[3].reg = 0;
    require_available(&gba, &device);

    /* An enabled channel with fixed source inside EWRAM but beyond the
     * staging buffer is not the same as a region-wide DMA lock. */
    d[0].reg = R25_ENABLE | (2u << 7u);
    d[0].source = 0x02030000u;
    d[0].nextSource = d[0].source;
    d[0].count = 16384;
    require_available(&gba, &device);
    d[0].reg = 0;

    /* Catches the case of first byte outside the start of the destination:
     * incremental DMA still crosses into the memory that XGBA would write. */
    d[0].reg = R25_ENABLE;
    d[0].source = R25_DEST - 2u;
    d[0].nextSource = d[0].source;
    d[0].count = 4;
    require_dma_busy(&gba, &device);
    d[0].reg = 0;
    require_available(&gba, &device);

    /* GBA EWRAM is physically 256 KiB mirrored throughout 0x02xxxxxx.
     * A check against unmasked DMA CPU addresses would miss all these. */
    d[0].reg = R25_ENABLE;
    d[0].source = R25_DEST + 0x40000u + 0x10u;
    d[0].nextSource = d[0].source;
    d[0].count = 4;
    require_dma_busy(&gba, &device); /* source uses a mirror */
    d[0].reg = 0;

    d[0].reg = R25_ENABLE;
    d[0].source = 0x02047ff0u;
    d[0].nextSource = d[0].source;
    d[0].count = 32;
    require_dma_busy(&gba, &device); /* crosses into destination */
    d[0].reg = 0;

    d[2].reg = R25_ENABLE | (1u << 7u);
    d[2].source = 0x02048004u;
    d[2].nextSource = d[2].source;
    d[2].count = 8;
    require_dma_busy(&gba, &device); /* mirrored decrement */
    d[2].reg = 0;

    d[3].reg = R25_ENABLE | R25_WIDTH32;
    d[3].source = 0x02088000u;
    d[3].nextSource = d[3].source;
    d[3].count = 65536;
    require_dma_busy(&gba, &device); /* entire 256KiB physical span */
    d[3].reg = 0;

    d[1].reg = R25_ENABLE;
    d[1].source = 0x02050000u;
    d[1].nextSource = d[1].source;
    d[1].count = 8;
    require_available(&gba, &device); /* mirrored but genuinely disjoint */
    d[1].reg = 0;

    /* The old seven R24 negative paths and 256 edge probes were exercised
     * first by xgba_r24_base_contract_main(), without any altered statuses. */
    assert(sR25Cases == 19u);
    puts("PASS_R25_DMA_SOURCE_LIFETIME portable_cases=19 "
         "pending_dma_no_commit=1 recovery_after_disarm=1 "
         "r24_baseline_preserved=1 native_game_dma_not_yet_proven=1");
    return 0;
}

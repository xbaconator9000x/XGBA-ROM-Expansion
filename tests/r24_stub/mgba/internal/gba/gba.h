/* Minimal PORTABLE unit-test shape for the MMIO device only.
 * Not a replacement for real mGBA or an authoritative emulation test.
 */
#ifndef XGBA_R24_STUB_GBA_H
#define XGBA_R24_STUB_GBA_H
#include <stdint.h>
struct XgbaGbaDevice;
/* Minimal shapes of the pinned mGBA DMA fields read by the R25 guard.
 * This is not an emulator substitute; native pinned-mGBA CI must run too. */
struct GBADMA {
    uint16_t reg;
    uint32_t source, nextSource;
    int32_t count, nextCount;
};
struct GBA {
    struct {
        uint32_t *wram;
        struct GBADMA dma[4];
        int activeDMA;
    } memory;
    struct XgbaGbaDevice *xgbaDevice;
};
#endif

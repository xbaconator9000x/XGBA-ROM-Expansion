/* Minimal PORTABLE unit-test shape for the MMIO device only.
 * Not a replacement for real mGBA or an authoritative emulation test.
 */
#ifndef XGBA_R24_STUB_GBA_H
#define XGBA_R24_STUB_GBA_H
#include <stdint.h>
struct XgbaGbaDevice;
struct GBA {
    struct { uint32_t *wram; } memory;
    struct XgbaGbaDevice *xgbaDevice;
};
#endif

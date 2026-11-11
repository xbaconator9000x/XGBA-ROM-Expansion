/*
 * XGBA R7 guest-side resource request interface for an explicitly patched,
 * opted-in mGBA build. This address is NOT real Game Boy Advance hardware.
 *
 * Caller owns the EWRAM resource ID and destination buffers. Do not invoke
 * from an interrupt handler. Fetch is synchronous; 0 means unavailable,
 * invalid, or refused, and the destination is left untouched on failure.
 */
#ifndef XGBA_FIRE_RED_GUEST_H
#define XGBA_FIRE_RED_GUEST_H

#define XGBA_GUEST_MMIO_BASE 0x04FF8000u
#define XGBA_GUEST_MMIO_MAGIC 0x58474241u
#define XGBA_GUEST_ABI_VERSION 1u

static unsigned XgbaGuestFetch(const char *ewramResourceId,
                               void *ewramDestination,
                               unsigned destinationCapacity)
{
    volatile unsigned *registers =
        (volatile unsigned *)XGBA_GUEST_MMIO_BASE;
    if (registers[0] != XGBA_GUEST_MMIO_MAGIC ||
        registers[1] != XGBA_GUEST_ABI_VERSION)
        return 0;

    registers[2] = (unsigned)ewramResourceId;
    registers[3] = (unsigned)ewramDestination;
    registers[4] = destinationCapacity;
    registers[5] = 1u; /* command */
    if (registers[6] != 1u) /* success */
        return 0;
    unsigned received = registers[7];
    return received <= destinationCapacity ? received : 0;
}
#endif

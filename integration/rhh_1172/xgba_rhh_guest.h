/* XGBA opt-in guest adapter for RH-Hideout pokeemerald-expansion 1.17.2.
 * Upstream pin: 79dd436920845ebc145577649de624f65298c209.
 * Use from an expanded game's native resource loader, never an IRQ/DMA callback.
 * No ROM bytes or upstream copyrighted assets are embedded here.
 *
 * Integration requires defining BOTH XGBA_RHH_1172_OPT_IN=1 and exactly one
 * XGBA_RHH_TARGET_EMERALD / XGBA_RHH_TARGET_FIRERED /
 * XGBA_RHH_TARGET_LEAFGREEN as 1. Unrecognised builds fail compilation.
 * This does NOT automatically hook upstream graphics or map loaders.
 */
#ifndef XGBA_RHH_1172_GUEST_H
#define XGBA_RHH_1172_GUEST_H
#include <stdint.h>
#include <stddef.h>

#if !defined(XGBA_RHH_1172_OPT_IN) || XGBA_RHH_1172_OPT_IN != 1
#error "XGBA RHH adapter requires explicit opt-in"
#endif
#if (defined(XGBA_RHH_TARGET_EMERALD) + defined(XGBA_RHH_TARGET_FIRERED) + defined(XGBA_RHH_TARGET_LEAFGREEN)) != 1
#error "Select exactly one RHH 1.17.2 game target"
#endif
#if defined(XGBA_RHH_TARGET_EMERALD) && XGBA_RHH_TARGET_EMERALD != 1
#error "Invalid Emerald target value"
#endif
#if defined(XGBA_RHH_TARGET_FIRERED) && XGBA_RHH_TARGET_FIRERED != 1
#error "Invalid FireRed target value"
#endif
#if defined(XGBA_RHH_TARGET_LEAFGREEN) && XGBA_RHH_TARGET_LEAFGREEN != 1
#error "Invalid LeafGreen target value"
#endif
#if UINTPTR_MAX != 0xffffffffu
#error "XGBA guest MMIO requires a 32-bit GBA target, not host compilation"
#endif

#define XGBA_RHH_MMIO_BASE 0x04FF8000u
#define XGBA_RHH_MMIO_MAGIC 0x58474241u
#define XGBA_RHH_MMIO_ABI 1u
#define XGBA_RHH_PAGE_LIMIT 16384u
#define XGBA_RHH_EWRAM_START 0x02000000u
#define XGBA_RHH_EWRAM_END 0x02040000u

/* Caller must hold a valid exclusive EWRAM lease for destination and ID,
 * and must release it only after all DMA/decompression consumers finish.
 * Provider identity/sha verification is enforced by the existing mGBA host.
 * A 0 return means no bytes are safe to consume.
 */
static inline uint32_t XgbaRhhFetchPage(const char *id, void *dst, uint32_t capacity)
{
    uintptr_t idAddr = (uintptr_t)id;
    uintptr_t dstAddr = (uintptr_t)dst;
    volatile uint32_t *const mmio = (volatile uint32_t *)XGBA_RHH_MMIO_BASE;
    if (!id || !dst || !capacity || capacity > XGBA_RHH_PAGE_LIMIT)
        return 0;
    if (idAddr < XGBA_RHH_EWRAM_START || idAddr >= XGBA_RHH_EWRAM_END ||
        dstAddr < XGBA_RHH_EWRAM_START || dstAddr >= XGBA_RHH_EWRAM_END ||
        capacity > XGBA_RHH_EWRAM_END - dstAddr)
        return 0;
    if (mmio[0] != XGBA_RHH_MMIO_MAGIC || mmio[1] != XGBA_RHH_MMIO_ABI)
        return 0;
    mmio[2] = (uint32_t)idAddr;
    mmio[3] = (uint32_t)dstAddr;
    mmio[4] = capacity;
    mmio[5] = 1u;
    if (mmio[6] != 1u || mmio[7] == 0 || mmio[7] > capacity)
        return 0;
    return mmio[7];
}
#endif

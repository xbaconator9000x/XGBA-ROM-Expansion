/*
 * XGBA external-resource page lease for RH-Hideout pokeemerald-expansion.
 * Validated against expansion/1.17.2 for EMERALD, FIRERED, LEAFGREEN.
 *
 * Include this file from ordinary RHH source modules to request verified
 * external assets. The existing gHeap owns the EWRAM allocation, but its
 * last 16KiB is excluded from InitHeap and belongs only to this API.
 *
 * A successful Acquire makes precisely length bytes available until the next
 * Acquire/Release. Invalidate all saved pointers on a generation change.
 * A missing or invalid provider returns 0 and exposes no resident page.
 * No GBA hardware without a compatible opt-in XGBA provider is supported.
 */
#ifndef XGBA_EXPANSION_PAGE_API_H
#define XGBA_EXPANSION_PAGE_API_H

#include "global.h"

#define XGBA_EXPANSION_PAGE_CAPACITY 16384u

/* Caller must be in the normal game loop (never HBlank/VBlank/IRQ). */
u32 XgbaExpansionPageAcquire(const char *resourceId, u32 bytes);
void XgbaExpansionPageRelease(void);

/* NULL unless a complete SHA-validated page is resident. */
const u8 *XgbaExpansionPageData(void);
u32 XgbaExpansionPageResidentBytes(void);
u32 XgbaExpansionPageGeneration(void);

#endif /* XGBA_EXPANSION_PAGE_API_H */

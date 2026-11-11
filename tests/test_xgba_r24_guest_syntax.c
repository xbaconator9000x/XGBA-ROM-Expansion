/* R24 static guest-source syntax check, not a real ARM compilation.
 * Compile the exact shared Emerald/FireRed ARM source on host with the
 * original game's public u8/u32/heap ABI shapes for early regressions.
 * Real native pokefirered/pokeemerald builds remain mandatory.
 */
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define EWRAM_DATA
#define XGBA_GUEST_MMIO_BASE 0x04FF8000u
#define XGBA_GUEST_MMIO_MAGIC 0x58474241u
#define XGBA_GUEST_ABI_VERSION 1u
extern u8 gHeap[];
void *Alloc(u32 bytes);
void Free(void *ptr);
#include "../integration/emerald/xgba_r24_boundary.inc"

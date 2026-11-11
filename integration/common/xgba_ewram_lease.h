/* XGBA R26: portable, fail-closed ownership generations for a physically
 * fixed EWRAM arena. No heap allocation, host APIs or emulator dependencies.
 * Game code may only switch phases when every issued borrow was released.
 * A token is valid ONLY for its original slot/serial/owner/generation.
 * This does not track arbitrary CPU pointers or hardware DMA itself. */
#ifndef XGBA_EWRAM_LEASE_H
#define XGBA_EWRAM_LEASE_H
#include <stdint.h>
#include <limits.h>

#define XGBA_LEASE_SLOTS 8u
enum XgbaLeaseResult {
    XGBA_LEASE_OK=0, XGBA_LEASE_BUSY=1, XGBA_LEASE_STALE=2,
    XGBA_LEASE_NO_SLOT=3, XGBA_LEASE_INVALID=4, XGBA_LEASE_EXHAUSTED=5
};
struct XgbaLeaseToken {
    uint32_t owner, generation, serial, slot;
};
struct XgbaArenaLease {
    uint32_t owner, generation, serial, borrowed;
    uint32_t active_serials[XGBA_LEASE_SLOTS];
};
static inline void XgbaLeaseInit(struct XgbaArenaLease *a)
{
    unsigned i;
    if (!a) return;
    a->owner=0u; a->generation=0u; a->serial=0u; a->borrowed=0u;
    for(i=0;i<XGBA_LEASE_SLOTS;++i) a->active_serials[i]=0u;
}
static inline enum XgbaLeaseResult XgbaLeaseSwitch(
    struct XgbaArenaLease *a, uint32_t owner)
{
    unsigned i;
    if (!a || !owner) return XGBA_LEASE_INVALID;
    if (a->owner==owner) return XGBA_LEASE_OK;
    if (a->borrowed) return XGBA_LEASE_BUSY;
    for(i=0;i<XGBA_LEASE_SLOTS;++i)
        if (a->active_serials[i]) return XGBA_LEASE_INVALID;
    if (a->generation==UINT32_MAX) return XGBA_LEASE_EXHAUSTED;
    ++a->generation;
    a->owner=owner;
    return XGBA_LEASE_OK;
}
static inline enum XgbaLeaseResult XgbaLeaseBorrow(
    struct XgbaArenaLease *a, uint32_t owner, struct XgbaLeaseToken *token)
{
    unsigned i;
    if (!a || !token || !owner) return XGBA_LEASE_INVALID;
    if (a->owner!=owner || !a->generation) return XGBA_LEASE_STALE;
    if (a->borrowed>=XGBA_LEASE_SLOTS) return XGBA_LEASE_NO_SLOT;
    if (a->serial==UINT32_MAX) return XGBA_LEASE_EXHAUSTED;
    for(i=0;i<XGBA_LEASE_SLOTS;++i)
        if(!a->active_serials[i]) {
            ++a->serial;
            a->active_serials[i]=a->serial;
            ++a->borrowed;
            token->owner=owner;
            token->generation=a->generation;
            token->serial=a->serial;
            token->slot=i;
            return XGBA_LEASE_OK;
        }
    return XGBA_LEASE_INVALID;
}
static inline enum XgbaLeaseResult XgbaLeaseValidate(
    const struct XgbaArenaLease *a, const struct XgbaLeaseToken *token)
{
    if (!a || !token || token->slot>=XGBA_LEASE_SLOTS)
        return XGBA_LEASE_INVALID;
    if (!token->serial || token->owner!=a->owner ||
        token->generation!=a->generation ||
        a->active_serials[token->slot]!=token->serial)
        return XGBA_LEASE_STALE;
    return XGBA_LEASE_OK;
}
static inline enum XgbaLeaseResult XgbaLeaseRelease(
    struct XgbaArenaLease *a, const struct XgbaLeaseToken *token)
{
    enum XgbaLeaseResult result=XgbaLeaseValidate(a,token);
    if(result!=XGBA_LEASE_OK) return result;
    if(!a->borrowed) return XGBA_LEASE_INVALID;
    a->active_serials[token->slot]=0u;
    --a->borrowed;
    return XGBA_LEASE_OK;
}
#endif

/* XGBA R28: exact two-slot / three-resource EWRAM cache residency contract.
 *
 * This header is portable across original GBA source and host C tests. It
 * supplies deterministic LRU eviction and generation/serial guarded source
 * pins; it does NOT claim to manage game-owned raw pointers or hardware DMA.
 * All resource bytes remain inside the existing protected 16 KiB arena.
 */
#ifndef XGBA_MAP_CACHE_H
#define XGBA_MAP_CACHE_H
#include <stdint.h>
#include <limits.h>

#define XGBA_MAP_CACHE_SLOTS 2u
#define XGBA_MAP_CACHE_KEYS 3u
#define XGBA_MAP_CACHE_PINS 8u
#define XGBA_MAP_CACHE_NONE UINT32_MAX
#define XGBA_MAP_CACHE_EMPTY 0u
#define XGBA_MAP_CACHE_READY 1u
#define XGBA_MAP_CACHE_LOADING 2u

enum XgbaMapCacheResult {
    XGBA_CACHE_HIT=0, XGBA_CACHE_MISS=1, XGBA_CACHE_BUSY=2,
    XGBA_CACHE_STALE=3, XGBA_CACHE_INVALID=4, XGBA_CACHE_EXHAUSTED=5
};
struct XgbaMapCacheSlot {
    uint32_t key, state, generation, touched, pins;
};
struct XgbaMapCachePinRecord {
    uint32_t serial, slot, generation, key;
};
struct XgbaMapCachePin {
    uint32_t serial, slot, generation, key;
};
struct XgbaMapCache {
    struct XgbaMapCacheSlot slots[XGBA_MAP_CACHE_SLOTS];
    struct XgbaMapCachePinRecord borrowers[XGBA_MAP_CACHE_PINS];
    uint32_t tick, generation, serial, borrowed;
    uint32_t hits, misses, evictions, refusals, loads;
};
static inline void XgbaCacheInit(struct XgbaMapCache *c)
{
    unsigned i;
    if(!c)return;
    c->tick=0u;c->generation=0u;c->serial=0u;c->borrowed=0u;
    c->hits=0u;c->misses=0u;c->evictions=0u;c->refusals=0u;c->loads=0u;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i) {
        c->slots[i].key=XGBA_MAP_CACHE_NONE;
        c->slots[i].state=0u;c->slots[i].generation=0u;
        c->slots[i].touched=0u;c->slots[i].pins=0u;
    }
    for(i=0;i<XGBA_MAP_CACHE_PINS;++i) {
        c->borrowers[i].serial=0u;c->borrowers[i].slot=0u;
        c->borrowers[i].generation=0u;c->borrowers[i].key=0u;
    }
}
static inline int XgbaCacheFind(const struct XgbaMapCache *c, uint32_t key)
{
    unsigned i;
    if(!c || key>=XGBA_MAP_CACHE_KEYS)return -1;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i)
        if(c->slots[i].state==XGBA_MAP_CACHE_READY &&
           c->slots[i].key==key)return (int)i;
    return -1;
}
/* Begin returns HIT or MISS. A miss owns a LOADING slot, which must be
 * committed only AFTER the provider resource is validated and descriptor
 * pointers have been safely constructed. Evicted key returned to caller.
 * 'protected_key' must be the current live map: refuse to evict it.
 */
static inline enum XgbaMapCacheResult XgbaCacheBegin(
    struct XgbaMapCache *c,uint32_t key,uint32_t protected_key,
    uint32_t *out_slot,uint32_t *out_evicted)
{
    unsigned i,victim=XGBA_MAP_CACHE_SLOTS;
    uint32_t oldest=UINT32_MAX;
    if(!c || !out_slot || !out_evicted || key>=XGBA_MAP_CACHE_KEYS ||
       (protected_key!=XGBA_MAP_CACHE_NONE &&
        protected_key>=XGBA_MAP_CACHE_KEYS))
        return XGBA_CACHE_INVALID;
    *out_slot=XGBA_MAP_CACHE_NONE;
    *out_evicted=XGBA_MAP_CACHE_NONE;
    if(c->tick==UINT32_MAX)return XGBA_CACHE_EXHAUSTED;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i) {
        if(c->slots[i].key==key && c->slots[i].state==XGBA_MAP_CACHE_LOADING)
            return XGBA_CACHE_BUSY;
        if(c->slots[i].key==key && c->slots[i].state==XGBA_MAP_CACHE_READY) {
            ++c->tick;
            c->slots[i].touched=c->tick;
            ++c->hits;
            *out_slot=i;
            return XGBA_CACHE_HIT;
        }
    }
    if(c->generation==UINT32_MAX)return XGBA_CACHE_EXHAUSTED;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i)
        if(c->slots[i].state==XGBA_MAP_CACHE_EMPTY) {
            victim=i;
            break;
        }
    if(victim==XGBA_MAP_CACHE_SLOTS)
        for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i)
            if(c->slots[i].state==XGBA_MAP_CACHE_READY &&
               !c->slots[i].pins && c->slots[i].key!=protected_key &&
               c->slots[i].touched<oldest) {
                oldest=c->slots[i].touched;
                victim=i;
            }
    if(victim==XGBA_MAP_CACHE_SLOTS) {
        ++c->refusals;
        return XGBA_CACHE_BUSY;
    }
    if(c->slots[victim].state!=XGBA_MAP_CACHE_EMPTY) {
        *out_evicted=c->slots[victim].key;
        ++c->evictions;
    }
    ++c->tick;
    ++c->generation;
    c->slots[victim].key=key;
    c->slots[victim].state=XGBA_MAP_CACHE_LOADING;
    c->slots[victim].generation=c->generation;
    c->slots[victim].touched=c->tick;
    c->slots[victim].pins=0u;
    ++c->misses;
    *out_slot=victim;
    return XGBA_CACHE_MISS;
}
static inline enum XgbaMapCacheResult XgbaCacheCommit(
    struct XgbaMapCache *c,uint32_t slot,uint32_t key)
{
    if(!c || slot>=XGBA_MAP_CACHE_SLOTS || key>=XGBA_MAP_CACHE_KEYS)
        return XGBA_CACHE_INVALID;
    if(c->slots[slot].key!=key ||
       c->slots[slot].state!=XGBA_MAP_CACHE_LOADING)
        return XGBA_CACHE_STALE;
    c->slots[slot].state=XGBA_MAP_CACHE_READY;
    ++c->loads;
    return XGBA_CACHE_HIT;
}
static inline enum XgbaMapCacheResult XgbaCachePin(
    struct XgbaMapCache *c,uint32_t key,struct XgbaMapCachePin *token)
{
    int slot;
    unsigned i;
    if(!c || !token || key>=XGBA_MAP_CACHE_KEYS)return XGBA_CACHE_INVALID;
    slot=XgbaCacheFind(c,key);
    if(slot<0)return XGBA_CACHE_STALE;
    if(c->serial==UINT32_MAX)return XGBA_CACHE_EXHAUSTED;
    if(c->borrowed>=XGBA_MAP_CACHE_PINS)return XGBA_CACHE_BUSY;
    for(i=0;i<XGBA_MAP_CACHE_PINS;++i)
        if(!c->borrowers[i].serial) {
            ++c->serial;
            c->borrowers[i].serial=c->serial;
            c->borrowers[i].slot=(uint32_t)slot;
            c->borrowers[i].generation=c->slots[slot].generation;
            c->borrowers[i].key=key;
            token->serial=c->serial;
            token->slot=(uint32_t)slot;
            token->generation=c->slots[slot].generation;
            token->key=key;
            ++c->slots[slot].pins;
            ++c->borrowed;
            return XGBA_CACHE_HIT;
        }
    return XGBA_CACHE_BUSY;
}
static inline enum XgbaMapCacheResult XgbaCacheRelease(
    struct XgbaMapCache *c,const struct XgbaMapCachePin *token)
{
    unsigned i;
    if(!c || !token || !token->serial ||
       token->slot>=XGBA_MAP_CACHE_SLOTS)return XGBA_CACHE_INVALID;
    for(i=0;i<XGBA_MAP_CACHE_PINS;++i)
        if(c->borrowers[i].serial==token->serial &&
           c->borrowers[i].slot==token->slot &&
           c->borrowers[i].generation==token->generation &&
           c->borrowers[i].key==token->key) {
            struct XgbaMapCacheSlot *s=&c->slots[token->slot];
            if(s->state!=XGBA_MAP_CACHE_READY ||
               s->key!=token->key || s->generation!=token->generation ||
               !s->pins || !c->borrowed)return XGBA_CACHE_STALE;
            c->borrowers[i].serial=0u;
            --s->pins;
            --c->borrowed;
            return XGBA_CACHE_HIT;
        }
    return XGBA_CACHE_STALE;
}
static inline enum XgbaMapCacheResult XgbaCacheInvalidate(
    struct XgbaMapCache *c)
{
    unsigned i;
    if(!c)return XGBA_CACHE_INVALID;
    if(c->borrowed)return XGBA_CACHE_BUSY;
    if(c->generation==UINT32_MAX)return XGBA_CACHE_EXHAUSTED;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i)
        if(c->slots[i].state==XGBA_MAP_CACHE_LOADING ||
           c->slots[i].pins)return XGBA_CACHE_BUSY;
    ++c->generation;
    for(i=0;i<XGBA_MAP_CACHE_SLOTS;++i) {
        c->slots[i].key=XGBA_MAP_CACHE_NONE;
        c->slots[i].state=XGBA_MAP_CACHE_EMPTY;
        c->slots[i].generation=c->generation;
        c->slots[i].touched=0u;
    }
    return XGBA_CACHE_HIT;
}
#endif

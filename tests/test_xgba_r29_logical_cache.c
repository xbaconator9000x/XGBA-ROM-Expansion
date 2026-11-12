/* R29 portable contract: many independently addressed logical resources
 * through only two physical EWRAM slots. This is not a native Emerald proof
 * of arbitrary connected map enumeration, packs or cartridge patching. */
#include "../integration/common/xgba_map_cache.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

_Static_assert(XGBA_MAP_CACHE_KEYS == UINT32_MAX,
               "R29 default must admit the full non-sentinel 32-bit key range");
_Static_assert(XGBA_MAP_CACHE_SLOTS == 2u,
               "R29 must retain the exact two physical resource slots");
_Static_assert(sizeof(struct XgbaMapCache) <= 256u,
               "R29 key-space growth must never allocate per-resource RAM");

static uint32_t load(struct XgbaMapCache *cache, uint32_t key,
                     uint32_t protected_key)
{
    uint32_t slot = XGBA_MAP_CACHE_NONE, evicted = XGBA_MAP_CACHE_NONE;
    assert(XgbaCacheBegin(cache,key,protected_key,&slot,&evicted)
           == XGBA_CACHE_MISS);
    assert(slot < XGBA_MAP_CACHE_SLOTS);
    assert(XgbaCacheFind(cache,key) == -1); /* LOADING is never public */
    assert(XgbaCacheCommit(cache,slot,key) == XGBA_CACHE_HIT);
    return evicted;
}

int main(void)
{
    struct XgbaMapCache cache;
    struct XgbaMapCachePin pin;
    uint32_t slot,evicted;
    XgbaCacheInit(&cache);
    assert(load(&cache,0u,XGBA_MAP_CACHE_NONE)==XGBA_MAP_CACHE_NONE);
    assert(load(&cache,1u,0u)==XGBA_MAP_CACHE_NONE);
    for(uint32_t key=2u;key<=10000u;++key) {
        /* Keep the current map, evict its predecessor, enter a new map.
         * The number of logical maps grows but the two resident slots don't. */
        assert(load(&cache,key,key-1u)==key-2u);
        assert(XgbaCacheFind(&cache,key)>=0);
        assert(XgbaCacheFind(&cache,key-1u)>=0);
        assert(XgbaCacheFind(&cache,key-2u)==-1);
        assert(cache.borrowed==0u);
    }
    assert(cache.loads==10001u && cache.evictions==9999u);
    assert(cache.misses==10001u && cache.hits==0u);

    /* Sparse resource IDs are as valid as consecutive map IDs; the sentinel
     * is never accepted as a resource and must not modify residency. */
    assert(load(&cache,UINT32_MAX-1u,10000u)==9999u);
    assert(XgbaCacheFind(&cache,UINT32_MAX-1u)>=0);
    assert(XgbaCacheBegin(&cache,XGBA_MAP_CACHE_NONE,10000u,
                          &slot,&evicted)==XGBA_CACHE_INVALID);
    assert(XgbaCachePin(&cache,XGBA_MAP_CACHE_NONE,&pin)==XGBA_CACHE_INVALID);
    assert(XgbaCacheFind(&cache,10000u)>=0);

    /* A pinned resource plus an independently protected current map must
     * refuse a third load without changing either of the two residents. */
    assert(XgbaCachePin(&cache,UINT32_MAX-1u,&pin)==XGBA_CACHE_HIT);
    assert(XgbaCacheBegin(&cache,123456789u,10000u,&slot,&evicted)
           == XGBA_CACHE_BUSY);
    assert(cache.refusals==1u);
    assert(XgbaCacheRelease(&cache,&pin)==XGBA_CACHE_HIT);
    assert(XgbaCacheRelease(&cache,&pin)==XGBA_CACHE_STALE);
    assert(load(&cache,123456789u,10000u)==UINT32_MAX-1u);
    assert(XgbaCacheFind(&cache,10000u)>=0);
    assert(cache.loads==10003u && cache.evictions==10001u);
    assert(cache.borrowed==0u);
    puts("PASS_R29_PORTABLE_LOGICAL_KEYSPACE 10003_loads 10001_evictions "
         "two_slots sparse32bit_ids sentinel_refused stale_pin_refused "
         "protected_current_unchanged no_per_key_allocation");
    return 0;
}

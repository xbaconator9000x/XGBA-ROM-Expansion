/* Real portable R28 cache implementation tests, not a native Emerald result. */
#include "../integration/common/xgba_map_cache.h"
#include <assert.h>
#include <stdio.h>

static uint32_t put(struct XgbaMapCache *c,uint32_t key,uint32_t protect)
{
    uint32_t slot=77u,evicted=77u;
    enum XgbaMapCacheResult r=XgbaCacheBegin(c,key,protect,&slot,&evicted);
    assert(r==XGBA_CACHE_HIT || r==XGBA_CACHE_MISS);
    assert(slot<2u);
    if(r==XGBA_CACHE_MISS)assert(XgbaCacheCommit(c,slot,key)==XGBA_CACHE_HIT);
    return evicted;
}
static void assert_slots(const struct XgbaMapCache *c,uint32_t a,uint32_t b)
{
    unsigned i,ready=0;
    for(i=0;i<2u;++i)if(c->slots[i].state==XGBA_MAP_CACHE_READY) {
        assert(c->slots[i].key==a || c->slots[i].key==b);
        ++ready;
    }
    assert(ready==2);
}
static void test_three_map_eviction_and_reacquisition(void)
{
    struct XgbaMapCache c;
    XgbaCacheInit(&c);
    assert(put(&c,0u,XGBA_MAP_CACHE_NONE)==XGBA_MAP_CACHE_NONE);
    assert(put(&c,1u,0u)==XGBA_MAP_CACHE_NONE);
    assert_slots(&c,0u,1u);
    /* Current Route101=1: loading Oldale=2 must evict Littleroot=0. */
    assert(put(&c,2u,1u)==0u);
    assert_slots(&c,1u,2u);
    assert(XgbaCacheFind(&c,0u)==-1);
    /* Return via Route101; reacquire Littleroot, retire Oldale. */
    assert(put(&c,1u,2u)==XGBA_MAP_CACHE_NONE);
    assert(put(&c,0u,1u)==2u);
    assert_slots(&c,0u,1u);
    assert(c.misses==4u && c.loads==4u && c.hits==1u);
    assert(c.evictions==2u && c.borrowed==0u);
}
static void test_real_lru_choice_and_latest_hit(void)
{
    struct XgbaMapCache c;
    XgbaCacheInit(&c);
    put(&c,0u,XGBA_MAP_CACHE_NONE);put(&c,1u,XGBA_MAP_CACHE_NONE);
    assert(put(&c,0u,XGBA_MAP_CACHE_NONE)==XGBA_MAP_CACHE_NONE);
    assert(put(&c,2u,XGBA_MAP_CACHE_NONE)==1u);
    assert(XgbaCacheFind(&c,0u)>=0 && XgbaCacheFind(&c,1u)<0);
}
static void test_both_pins_block_eviction(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p0,p1;uint32_t slot,evicted;
    XgbaCacheInit(&c);
    put(&c,0u,XGBA_MAP_CACHE_NONE);put(&c,1u,XGBA_MAP_CACHE_NONE);
    assert(XgbaCachePin(&c,0u,&p0)==XGBA_CACHE_HIT);
    assert(XgbaCachePin(&c,1u,&p1)==XGBA_CACHE_HIT);
    assert(XgbaCacheBegin(&c,2u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_BUSY);
    assert(c.refusals==1u && c.evictions==0u);
    assert(XgbaCacheRelease(&c,&p1)==XGBA_CACHE_HIT);
    assert(put(&c,2u,0u)==1u);
    assert(XgbaCacheRelease(&c,&p0)==XGBA_CACHE_HIT);
}
static void test_protected_live_map_never_evicts(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;uint32_t slot,evicted;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);put(&c,1u,0u);
    assert(XgbaCachePin(&c,1u,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheBegin(&c,2u,0u,&slot,&evicted)==XGBA_CACHE_BUSY);
    assert(c.evictions==0u && XgbaCacheFind(&c,0u)>=0);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
    assert(put(&c,2u,0u)==1u);
}
static void test_duplicate_release_fails_closed(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_STALE);
}
static void test_stale_pin_after_reacquisition(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
    put(&c,1u,XGBA_MAP_CACHE_NONE);put(&c,2u,1u);
    put(&c,0u,2u);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_STALE);
}
static void test_phase_invalidation_rejects_pins(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheInvalidate(&c)==XGBA_CACHE_BUSY);
    assert(XgbaCacheFind(&c,0u)>=0);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheInvalidate(&c)==XGBA_CACHE_HIT);
    assert(XgbaCacheFind(&c,0u)==-1);
}
static void test_generation_identity_and_no_aba(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p,q;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_HIT);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
    assert(XgbaCachePin(&c,0u,&q)==XGBA_CACHE_HIT);
    assert(q.serial!=p.serial);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_STALE);
    assert(XgbaCacheRelease(&c,&q)==XGBA_CACHE_HIT);
}
static void test_pin_slot_capacity(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p[9];
    unsigned i;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    for(i=0;i<8u;++i)assert(XgbaCachePin(&c,0u,&p[i])==XGBA_CACHE_HIT);
    assert(c.borrowed==8u);
    assert(XgbaCachePin(&c,0u,&p[8])==XGBA_CACHE_BUSY);
    for(i=0;i<8u;++i)assert(XgbaCacheRelease(&c,&p[i])==XGBA_CACHE_HIT);
    assert(c.borrowed==0u);
}
static void test_protected_and_pinned_victim_priority(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    put(&c,1u,0u);
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_HIT);
    assert(put(&c,2u,XGBA_MAP_CACHE_NONE)==1u);
    assert(XgbaCacheRelease(&c,&p)==XGBA_CACHE_HIT);
}
static void test_pending_source_not_public(void)
{
    struct XgbaMapCache c;uint32_t slot,evicted;
    XgbaCacheInit(&c);
    assert(XgbaCacheBegin(&c,0u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_MISS);
    assert(XgbaCacheFind(&c,0u)<0);
    assert(XgbaCacheBegin(&c,0u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_BUSY);
    assert(XgbaCacheInvalidate(&c)==XGBA_CACHE_BUSY);
    assert(XgbaCachePin(&c,0u,(struct XgbaMapCachePin *)&evicted)==XGBA_CACHE_STALE);
    assert(XgbaCacheCommit(&c,0u,0u)==XGBA_CACHE_HIT);
    assert(XgbaCacheFind(&c,0u)==0);
}
static void test_malformed_source_keys(void)
{
    struct XgbaMapCache c;uint32_t slot,evicted;
    XgbaCacheInit(&c);
    assert(XgbaCacheBegin(&c,3u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_INVALID);
    assert(XgbaCacheBegin(&c,0u,3u,&slot,&evicted)==XGBA_CACHE_INVALID);
    assert(XgbaCacheBegin(0,0u,0u,&slot,&evicted)==XGBA_CACHE_INVALID);
    assert(XgbaCacheBegin(&c,0u,0u,0,&evicted)==XGBA_CACHE_INVALID);
    assert(XgbaCacheCommit(&c,2u,0u)==XGBA_CACHE_INVALID);
    assert(XgbaCachePin(&c,3u,0)==XGBA_CACHE_INVALID);
}
static void test_reject_generation_wrap(void)
{
    struct XgbaMapCache c;uint32_t slot,evicted;
    XgbaCacheInit(&c);c.generation=UINT32_MAX;
    assert(XgbaCacheBegin(&c,0u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_EXHAUSTED);
    assert(XgbaCacheInvalidate(&c)==XGBA_CACHE_EXHAUSTED);
    assert(c.misses==0u);
}
static void test_reject_clock_wrap(void)
{
    struct XgbaMapCache c;uint32_t slot,evicted;
    XgbaCacheInit(&c);c.tick=UINT32_MAX;
    assert(XgbaCacheBegin(&c,0u,XGBA_MAP_CACHE_NONE,&slot,&evicted)==XGBA_CACHE_EXHAUSTED);
    assert(c.loads==0u);
}
static void test_reject_pin_serial_wrap(void)
{
    struct XgbaMapCache c;struct XgbaMapCachePin p;
    XgbaCacheInit(&c);put(&c,0u,XGBA_MAP_CACHE_NONE);
    c.serial=UINT32_MAX;
    assert(XgbaCachePin(&c,0u,&p)==XGBA_CACHE_EXHAUSTED);
    assert(c.borrowed==0u);
}
static void test_repeated_churn_no_extra_residency(void)
{
    struct XgbaMapCache c;unsigned i;
    XgbaCacheInit(&c);
    put(&c,0u,XGBA_MAP_CACHE_NONE);put(&c,1u,0u);
    for(i=0;i<1000u;++i) {
        uint32_t k=(i%2u)?0u:2u;
        put(&c,k,1u);
        assert(XgbaCacheFind(&c,1u)>=0);
        assert(c.borrowed==0u);
    }
    assert(c.loads==1002u && c.evictions==1000u && c.misses==1002u);
}
int main(void)
{
    test_three_map_eviction_and_reacquisition();
    test_real_lru_choice_and_latest_hit();
    test_both_pins_block_eviction();
    test_protected_live_map_never_evicts();
    test_duplicate_release_fails_closed();
    test_stale_pin_after_reacquisition();
    test_phase_invalidation_rejects_pins();
    test_generation_identity_and_no_aba();
    test_pin_slot_capacity();
    test_protected_and_pinned_victim_priority();
    test_pending_source_not_public();
    test_malformed_source_keys();
    test_reject_generation_wrap();
    test_reject_clock_wrap();
    test_reject_pin_serial_wrap();
    test_repeated_churn_no_extra_residency();
    puts("PASS_R28_PORTABLE_CACHE_CONTRACT 16/16 protected_active=1 live_pins=1 "
         "generation=1 three_logical_maps=1 max_physical_slots=2 "
         "churn_cycles=1000 stale_rejected=1");
    return 0;
}

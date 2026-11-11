/* R26 portable contract tests compile and execute the SAME lease header used
 * inside Emerald's actual overworld and opponent sprite loader. This alone is
 * NOT an original-game test: see R26 native four-battle workflow. */
#include <assert.h>
#include <stdio.h>
#include "../integration/common/xgba_ewram_lease.h"
static unsigned assertions;
#define EXPECT(expr) do { assert((expr)); ++assertions; } while(0)
int main(void)
{
    struct XgbaArenaLease a;
    struct XgbaLeaseToken t[XGBA_LEASE_SLOTS],wrong,stale;
    XgbaLeaseInit(&a);
    EXPECT(a.owner==0u && a.generation==0u && a.borrowed==0u);
    EXPECT(XgbaLeaseBorrow(&a,1u,&t[0])==XGBA_LEASE_STALE);
    EXPECT(XgbaLeaseSwitch(&a,0u)==XGBA_LEASE_INVALID);
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_OK);
    EXPECT(a.generation==1u && a.owner==1u);
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_OK);
    for(unsigned i=0;i<XGBA_LEASE_SLOTS;i++) {
        EXPECT(XgbaLeaseBorrow(&a,1u,&t[i])==XGBA_LEASE_OK);
        EXPECT(XgbaLeaseValidate(&a,&t[i])==XGBA_LEASE_OK);
    }
    EXPECT(a.borrowed==XGBA_LEASE_SLOTS);
    EXPECT(XgbaLeaseBorrow(&a,1u,&wrong)==XGBA_LEASE_NO_SLOT);
    EXPECT(XgbaLeaseSwitch(&a,2u)==XGBA_LEASE_BUSY);
    EXPECT(a.owner==1u && a.generation==1u);
    wrong=t[0];
    wrong.owner=2u;
    EXPECT(XgbaLeaseRelease(&a,&wrong)==XGBA_LEASE_STALE);
    wrong=t[0];
    wrong.generation=2u;
    EXPECT(XgbaLeaseRelease(&a,&wrong)==XGBA_LEASE_STALE);
    wrong=t[0];
    wrong.slot=XGBA_LEASE_SLOTS;
    EXPECT(XgbaLeaseValidate(&a,&wrong)==XGBA_LEASE_INVALID);
    stale=t[0];
    EXPECT(XgbaLeaseRelease(&a,&t[0])==XGBA_LEASE_OK);
    EXPECT(XgbaLeaseRelease(&a,&t[0])==XGBA_LEASE_STALE);
    EXPECT(XgbaLeaseBorrow(&a,1u,&wrong)==XGBA_LEASE_OK);
    EXPECT(XgbaLeaseValidate(&a,&stale)==XGBA_LEASE_STALE);
    EXPECT(XgbaLeaseSwitch(&a,2u)==XGBA_LEASE_BUSY);
    EXPECT(XgbaLeaseRelease(&a,&wrong)==XGBA_LEASE_OK);
    for(unsigned i=1;i<XGBA_LEASE_SLOTS;i++)
        EXPECT(XgbaLeaseRelease(&a,&t[i])==XGBA_LEASE_OK);
    EXPECT(a.borrowed==0u);
    EXPECT(XgbaLeaseSwitch(&a,2u)==XGBA_LEASE_OK);
    EXPECT(a.owner==2u && a.generation==2u);
    EXPECT(XgbaLeaseValidate(&a,&stale)==XGBA_LEASE_STALE);
    EXPECT(XgbaLeaseBorrow(&a,1u,&wrong)==XGBA_LEASE_STALE);
    EXPECT(XgbaLeaseBorrow(&a,2u,&wrong)==XGBA_LEASE_OK);
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_BUSY);
    EXPECT(XgbaLeaseRelease(&a,&wrong)==XGBA_LEASE_OK);
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_OK);
    EXPECT(a.generation==3u);
    EXPECT(XgbaLeaseSwitch(NULL,2u)==XGBA_LEASE_INVALID);
    EXPECT(XgbaLeaseBorrow(NULL,1u,&wrong)==XGBA_LEASE_INVALID);
    EXPECT(XgbaLeaseRelease(&a,NULL)==XGBA_LEASE_INVALID);
    XgbaLeaseInit(&a);
    a.generation=UINT32_MAX;
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_EXHAUSTED);
    XgbaLeaseInit(&a);
    EXPECT(XgbaLeaseSwitch(&a,1u)==XGBA_LEASE_OK);
    a.serial=UINT32_MAX;
    EXPECT(XgbaLeaseBorrow(&a,1u,&wrong)==XGBA_LEASE_EXHAUSTED);
    EXPECT(a.borrowed==0u);
    printf("PASS_R26_PORTABLE_EWRAM_LEASE tests=%u "
           "busy_refuses=1 stale_tokens=1 slot_exhaustion=1 "
           "phase_generation=1 counter_wrap_failclosed=1\n", assertions);
    return 0;
}

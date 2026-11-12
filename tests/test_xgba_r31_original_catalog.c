/* R31: strict-C resolver regression, unrelated to an emulator success claim. */
#include "../integration/common/xgba_original_map_catalog.h"
#include <assert.h>
#include <stdio.h>
static const struct XgbaOriginalMapResource maps[] = {
    {0u,9u,20u,20u,4096u,"emerald.littleroot",1u},
    {0u,16u,20u,20u,4096u,"emerald.route101",0u},
    {0u,10u,20u,20u,4096u,"emerald.oldale",1u},
    {0u,17u,50u,20u,6000u,"emerald.route102",2u},
    {3u,65000u,3u,4u,256u,"mod.external.65000",XGBA_CATALOG_NO_NEIGHBOR},
};
static const struct XgbaOriginalMapLocator original_index[] = {
    {0x00000009u,0u}, {0x0000000au,2u}, {0x00000010u,1u},
    {0x00000011u,3u}, {0x0003fde8u,4u},
};
int main(void)
{
    struct XgbaOriginalMapLocator bad[5];
    struct XgbaOriginalMapResource broken[5];
    size_t i;
    const size_t n=sizeof(maps)/sizeof(maps[0]);
    assert(XgbaOriginalMapCatalogValidate(maps,original_index,n,8192u));
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,9u)==0);
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,10u)==2);
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,16u)==1);
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,17u)==3);
    assert(XgbaOriginalMapCatalogFind(original_index,n,3u,65000u)==4);
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,18u)==-1);
    assert(XgbaOriginalMapCatalogFind(original_index,n,1u,9u)==-1);
    assert(XgbaOriginalMapCatalogFind(original_index,n,0u,65535u)==-1);
    assert(XgbaOriginalMapCatalogFind(original_index,0,0u,9u)==-1);
    assert(XgbaOriginalMapCatalogFind(0,n,0u,9u)==-1);
    for(i=0;i<n;++i)bad[i]=original_index[i];
    bad[2].original_identity=bad[1].original_identity;
    assert(!XgbaOriginalMapCatalogValidate(maps,bad,n,8192u));
    bad[2]=original_index[2];
    bad[1].resource_index=4u;
    assert(!XgbaOriginalMapCatalogValidate(maps,bad,n,8192u));
    for(i=0;i<n;++i)broken[i]=maps[i];
    broken[3].packed_bytes=8193u;
    assert(!XgbaOriginalMapCatalogValidate(broken,original_index,n,8192u));
    broken[3]=maps[3];
    broken[1].resource_id="../outside";
    assert(!XgbaOriginalMapCatalogValidate(broken,original_index,n,8192u));
    broken[1]=maps[1];
    broken[2].prefetch_index=2u;
    assert(!XgbaOriginalMapCatalogValidate(broken,original_index,n,8192u));
    puts("PASS_R31_ORIGINAL_MAP_IDENTITY 17/17 source_ids_unchanged=1 fallback=1");
    return 0;
}

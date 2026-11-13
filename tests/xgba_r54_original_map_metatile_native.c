/* R54 true GBA 16-bit original map + border data against *physical*
 * source definitions. All data in this test are authored; the real
 * 518 original Emerald private source grids were verified separately.
 */
#include "../integration/common/xgba_r54_source_map_metatile_contract.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void cell(uint8_t *p,unsigned n,unsigned id,unsigned flags)
{
    unsigned word=(id&1023u)|(flags&0xfc00u);
    p[n*2u]=(uint8_t)word;
    p[n*2u+1u]=(uint8_t)(word>>8u);
}
int main(void)
{
    uint8_t source[4u*3u*2u+8u]={0};
    struct XgbaR54OriginalMapUse proof={0};
    unsigned i;
    for(i=0u;i<16u;i++)cell(source,i,0u,0xf400u);
    cell(source,0u,143u,0x8000u);
    cell(source,2u,512u+158u,0xa400u);
    cell(source,12u,512u+158u,0x5000u);
    assert(XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,512,144,159,&proof));
    assert(proof.cells_verified==16u);
    assert(proof.primary_cells==14u && proof.secondary_cells==2u);
    assert(proof.max_primary_id==143u && proof.max_secondary_relative_id==158u);
    cell(source,13u,512u+159u,0xc000u);
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,512,144,159,&proof));
    assert(proof.cells_verified==16u); /* not partially overwritten */
    cell(source,13u,0u,0u);
    cell(source,0u,144u,0u);
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,512,144,159,&proof));
    cell(source,0u,639u,0u);
    cell(source,1u,1023u,0xfc00u);
    cell(source,2u,640u+382u,0u);
    cell(source,12u,1023u,0u);
    assert(XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,640,640,384,&proof));
    assert(proof.max_primary_id==639u &&
           proof.max_secondary_relative_id==383u);
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,22,640,640,384,&proof));
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,700,640,384,&proof));
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,640,641,384,&proof));
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,640,640,385,&proof));
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,0,3,24,640,640,384,&proof));
    assert(!XgbaR54OriginalMapUsesOnlyAuthoredMetatiles(
             source,4,3,24,512,144,159,0));
    printf("PASS_R54_ORIGINAL_GBA_SOURCE_METATILE_BOUNDS "
           "512_640=1 border=1 physical_sparsity=1 "
           "original_16bit_flags_preserved=1 reject=1\n");
    return 0;
}

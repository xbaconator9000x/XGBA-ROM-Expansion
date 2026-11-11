/* R24 PORTABLE MMIO DEVICE CONTRACT, no mGBA/ARM build required.
 *
 * Compile the REAL integration/mgba/xgba_mgba_device.c in an isolated, tiny
 * GBA-shaped host unit environment to catch regressions while GitHub package
 * servers are unreachable. This is NOT original FireRed/Emerald or native mGBA.
 *
 * For original-game evidence, BOTH separate R24 14-test native suites MUST
 * pass; do not substitute this fast unit test for their results.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Source under test, not a copied implementation. */
#include "../integration/mgba/xgba_mgba_device.c"

#define R24_GUEST_RAM 0x40000u
#define R24_DST_OFF   0x8000u
#define R24_ID_OFF    0x1000u
#define R24_LENGTH    16384u
static uint32_t sMemory[R24_GUEST_RAM/4u];
static size_t sMockLookups = 0u;

enum XgbaMgbaProviderStatus xgba_mgba_provider_open(
    struct XgbaMgbaProvider *out, const struct XgbaMgbaProviderV1 *host,
    int enabled,const char *source_id,const uint8_t game_sha256[32])
{
    (void)source_id;
    (void)game_sha256;
    if(!out || !host)
        return XGBA_MGBA_INVALID;
    out->abi_version=1u;
    out->enabled=!!enabled;
    out->host=*host;
    return XGBA_MGBA_OK;
}

enum XgbaMgbaProviderStatus xgba_mgba_provider_read(
    const struct XgbaMgbaProvider *provider,const char *id,
    uint8_t *dst,size_t cap,size_t *got)
{
    ++sMockLookups;
    if(!provider || !id || !dst || !got)
        return XGBA_MGBA_INVALID;
    *got=0u;
    if(!strcmp(id,"r24.missing"))
        return XGBA_MGBA_NOT_FOUND;
    if(!strcmp(id,"r24.badsha"))
        return XGBA_MGBA_INTEGRITY_ERROR;
    if(!strcmp(id,"r24.empty"))
        return XGBA_MGBA_OK; /* Malformed provider OK+0 must fail closed. */
    if(strcmp(id,"r24.maximum"))
        return XGBA_MGBA_NOT_FOUND;
    if(cap<R24_LENGTH)
        return XGBA_MGBA_LIMIT_EXCEEDED;
    for(size_t i=0;i<R24_LENGTH;++i)
        dst[i]=(uint8_t)(29u*i+7u);
    *got=R24_LENGTH;
    return XGBA_MGBA_OK;
}

static void require_write(struct GBA *gba,uint32_t reg,uint32_t value)
{
    if(!XgbaDeviceStore32(gba,reg,value)) {
        fprintf(stderr,"FAILED MMIO register write %08x\n",reg);
        exit(2);
    }
}
static uint32_t read_reg(struct GBA *gba,uint32_t reg)
{
    uint32_t value=0xffffffffu;
    assert(XgbaDeviceLoad32(gba,reg,&value));
    return value;
}
static void guest_request(struct GBA *gba,const char *id,uint32_t dest,
                          uint32_t cap,uint32_t expected_status,
                          uint32_t expected_length)
{
    uint8_t *ram=(uint8_t *)gba->memory.wram;
    if(strlen(id)>40u)abort();
    strcpy((char *)ram+R24_ID_OFF,id);
    require_write(gba,XGBA_R7_REG_ID_ADDR,0x02000000u+R24_ID_OFF);
    require_write(gba,XGBA_R7_REG_DST_ADDR,dest);
    require_write(gba,XGBA_R7_REG_CAPACITY,cap);
    require_write(gba,XGBA_R7_REG_COMMAND,1u);
    const uint32_t status=read_reg(gba,XGBA_R7_REG_STATUS);
    const uint32_t length=read_reg(gba,XGBA_R7_REG_LENGTH);
    if(status!=expected_status || length!=expected_length) {
        fprintf(stderr,"FAILED guest request %s dest=%08x cap=%u status %u/%u length %u/%u\n",
                id,dest,cap,status,expected_status,length,expected_length);
        exit(3);
    }
}
static void verify_unchanged(struct GBA *gba)
{
    uint8_t *ram=(uint8_t *)gba->memory.wram;
    for(unsigned i=0;i<R24_LENGTH;++i)
        assert(ram[R24_DST_OFF+i]==0xC3u);
    for(unsigned i=0;i<16u;++i) {
        assert(ram[R24_DST_OFF-16u+i]==0xD5u);
        assert(ram[R24_DST_OFF+R24_LENGTH+i]==0xD5u);
    }
}
static void verify_payload(struct GBA *gba)
{
    uint8_t *ram=(uint8_t *)gba->memory.wram;
    for(unsigned i=0;i<R24_LENGTH;++i)
        assert(ram[R24_DST_OFF+i]==(uint8_t)(29u*i+7u));
    for(unsigned i=0;i<16u;++i) {
        assert(ram[R24_DST_OFF-16u+i]==0xD5u);
        assert(ram[R24_DST_OFF+R24_LENGTH+i]==0xD5u);
    }
}
static void reset_destination(struct GBA *gba)
{
    uint8_t *ram=(uint8_t *)gba->memory.wram;
    memset(ram+R24_DST_OFF-16u,0xD5,16u);
    memset(ram+R24_DST_OFF,0xC3,R24_LENGTH);
    memset(ram+R24_DST_OFF+R24_LENGTH,0xD5,16u);
}

int main(void)
{
    struct XgbaMgbaProviderV1 host={0};
    struct XgbaGbaDevice device;
    struct GBA gba={0};
    uint8_t sha[32]={0};
    gba.memory.wram=sMemory;
    gba.xgbaDevice=&device;
    host.abi_version=1;
    host.struct_size=sizeof(host);
    assert(XgbaDeviceInit(&device,&host,1,"native-fixture",sha)==XGBA_MGBA_OK);
    XgbaDeviceReset(&device);

    reset_destination(&gba);
    guest_request(&gba,"r24.maximum",0x02000000u+R24_DST_OFF,
                  R24_LENGTH,XGBA_R7_SUCCESS,R24_LENGTH);
    verify_payload(&gba);

    reset_destination(&gba);
    guest_request(&gba,"r24.maximum",0x02000000u+R24_DST_OFF,
                  R24_LENGTH-1u,XGBA_R7_RESOURCE_FAILURE,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"r24.maximum",0x02000000u+R24_DST_OFF,
                  R24_LENGTH+1u,XGBA_R7_BAD_RANGE,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"r24.maximum",0x02000000u+R24_DST_OFF,
                  0u,XGBA_R7_BAD_RANGE,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"r24.maximum",0x0203fff0u,
                  64u,XGBA_R7_BAD_RANGE,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"bad/identifier",0x02000000u+R24_DST_OFF,
                  64u,XGBA_R7_BAD_ID,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"r24.missing",0x02000000u+R24_DST_OFF,
                  64u,XGBA_R7_RESOURCE_FAILURE,0u);
    verify_unchanged(&gba);
    guest_request(&gba,"r24.badsha",0x02000000u+R24_DST_OFF,
                  32u,XGBA_R7_RESOURCE_FAILURE,0u);
    verify_unchanged(&gba);

    guest_request(&gba,"r24.maximum",0x02000000u+R24_DST_OFF,
                  R24_LENGTH,XGBA_R7_SUCCESS,R24_LENGTH);
    verify_payload(&gba);
    assert(device.successful_reads==2u);
    assert(device.failed_reads==7u);
    assert(device.rejected_ranges==3u);
    assert(device.rejected_ids==1u);
    assert(device.provider_too_large==1u);
    assert(device.provider_not_found==1u);
    assert(device.provider_bad_sha256==1u);
    assert(device.provider_other_failures==0u);
    assert(sMockLookups==5u);

    /* Additional adversarial case: provider lies about an empty success. */
    reset_destination(&gba);
    guest_request(&gba,"r24.empty",0x02000000u+R24_DST_OFF,
                  R24_LENGTH,XGBA_R7_RESOURCE_FAILURE,0u);
    verify_unchanged(&gba);
    assert(device.provider_other_failures==1u);
    assert(device.failed_reads==8u);

    /* Disabled mode: no request or guest buffer modification is possible. */
    struct XgbaGbaDevice disabled;
    assert(XgbaDeviceInit(&disabled,&host,0,"disabled",sha)==XGBA_MGBA_OK);
    XgbaDeviceReset(&disabled);
    gba.xgbaDevice=&disabled;
    const size_t before=sMockLookups;
    assert(XgbaDeviceStore32(&gba,XGBA_R7_REG_COMMAND,1u)==0);
    uint32_t ignored=0;
    assert(XgbaDeviceLoad32(&gba,XGBA_R7_REG_MAGIC,&ignored)==0);
    assert(sMockLookups==before);
    assert(disabled.successful_reads==0u && disabled.failed_reads==0u);

    puts("PASS_R24_PORTABLE_ORIGINAL_DEVICE_CONTRACT positive=2 rejected=8 "
         "range=3 invalid_id=1 oversized_source=1 bad_sha=1 missing=1 "
         "empty_success_refused=1 guard_unchanged=1 disabled_zero_reads=1");
    return 0;
}

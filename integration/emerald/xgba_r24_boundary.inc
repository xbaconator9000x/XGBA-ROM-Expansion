/* R24 opt-in ORIGINAL Emerald MMIO transfer boundary test.
 * Runs synchronously after the original game's InitHeap and before
 * gameplay begins. Every attempted request is emitted by the guest CPU,
 * never by host-side patching or a fabricated mGBA register fixture.
 *
 * Caller uses original Alloc/Free for an ephemeral 16 KiB scratch region:
 * no extra permanent EWRAM globals beyond the small proof and ID.
 */
#define XGBA_R24_MAGIC 0x52323442u /* R24B */
#define XGBA_R24_LIMIT 16384u
#define XGBA_R24_REDZONE 16u
#define XGBA_R24_STATUS_SUCCESS 1u
#define XGBA_R24_STATUS_BAD_RANGE 3u
#define XGBA_R24_STATUS_BAD_ID 4u
#define XGBA_R24_STATUS_RESOURCE_FAILURE 5u

struct XgbaR24Proof {
    volatile u32 magic, state, errors, disabled;
    volatile u32 attempts, accepted, rejected, unchanged_checks;
    volatile u32 limit, short_capacity, plus_one_capacity;
    volatile u32 accepted_hash, final_hash, guard_errors;
    volatile u32 final_buffer, ewram_heap_start, main_ticks_at_end;
};
EWRAM_DATA volatile struct XgbaR24Proof gXgbaR24Proof = {0};
EWRAM_DATA char gXgbaR24Id[40] = {0};

static u32 XgbaR24Hash(const u8 *b,u32 bytes)
{
    u32 h=2166136261u;
    u32 i;
    for(i=0;i<bytes;++i) {
        h^=b[i];
        h*=16777619u;
    }
    return h;
}
static void XgbaR24SetId(const char *text)
{
    u32 i;
    for(i=0;i<sizeof(gXgbaR24Id);++i)gXgbaR24Id[i]=0;
    for(i=0;text[i] && i+1<sizeof(gXgbaR24Id);++i)
        gXgbaR24Id[i]=text[i];
}
static u32 XgbaR24Fetch(const char *id, void *dest, u32 cap,
                       u32 expectedStatus, u32 expectedLength)
{
    volatile u32 *const r=(volatile u32 *)XGBA_GUEST_MMIO_BASE;
    u32 status,length;
    XgbaR24SetId(id);
    r[2]=(u32)gXgbaR24Id;
    r[3]=(u32)dest;
    r[4]=cap;
    r[5]=1u;
    status=r[6];
    length=r[7];
    ++gXgbaR24Proof.attempts;
    if(status!=expectedStatus || length!=expectedLength)
        ++gXgbaR24Proof.errors;
    if(status==XGBA_R24_STATUS_SUCCESS)
        ++gXgbaR24Proof.accepted;
    else
        ++gXgbaR24Proof.rejected;
    return status;
}
static void XgbaR24CheckGuards(const u8 *ptr)
{
    u32 i;
    for(i=0;i<XGBA_R24_REDZONE;++i)
        if(ptr[i]!=0xD5u ||
           ptr[XGBA_R24_REDZONE+XGBA_R24_LIMIT+i]!=0xD5u)
            ++gXgbaR24Proof.guard_errors;
}
static void XgbaR24CheckUnchanged(const u8 *data)
{
    u32 i;
    for(i=0;i<XGBA_R24_LIMIT;++i)
        if(data[i]!=0xC3u)
            ++gXgbaR24Proof.errors;
    ++gXgbaR24Proof.unchanged_checks;
}
static void XgbaR24Run(void)
{
    volatile u32 *const r=(volatile u32 *)XGBA_GUEST_MMIO_BASE;
    u8 *region,*data;
    u32 i;
    gXgbaR24Proof.magic=XGBA_R24_MAGIC;
    gXgbaR24Proof.state=1u;
    gXgbaR24Proof.limit=XGBA_R24_LIMIT;
    gXgbaR24Proof.short_capacity=XGBA_R24_LIMIT-1u;
    gXgbaR24Proof.plus_one_capacity=XGBA_R24_LIMIT+1u;
    gXgbaR24Proof.ewram_heap_start=(u32)gHeap;
    if(r[0]!=XGBA_GUEST_MMIO_MAGIC ||
       r[1]!=XGBA_GUEST_ABI_VERSION) {
        gXgbaR24Proof.disabled=1u;
        gXgbaR24Proof.state=3u;
        return;
    }
    region=Alloc(XGBA_R24_LIMIT+2u*XGBA_R24_REDZONE);
    if(!region) {
        ++gXgbaR24Proof.errors;
        gXgbaR24Proof.state=0xE24u;
        return;
    }
    data=region+XGBA_R24_REDZONE;
    gXgbaR24Proof.final_buffer=(u32)data;
    for(i=0;i<XGBA_R24_REDZONE;++i) {
        region[i]=0xD5u;
        data[XGBA_R24_LIMIT+i]=0xD5u;
    }

    /* Exact 16 KiB capacity is legal. Verify all 16384 bytes, then hash. */
    for(i=0;i<XGBA_R24_LIMIT;++i)data[i]=0xC3u;
    XgbaR24Fetch("emerald.r24.maximum",data,XGBA_R24_LIMIT,
                  XGBA_R24_STATUS_SUCCESS,XGBA_R24_LIMIT);
    gXgbaR24Proof.accepted_hash=XgbaR24Hash(data,XGBA_R24_LIMIT);
    XgbaR24CheckGuards(region);

    /* Seven independent rejection paths must not mutate the destination.
     * Host provider hashes source BEFORE writing guest EWRAM. */
    for(i=0;i<XGBA_R24_LIMIT;++i)data[i]=0xC3u;
    XgbaR24Fetch("emerald.r24.maximum",data,XGBA_R24_LIMIT-1u,
                  XGBA_R24_STATUS_RESOURCE_FAILURE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    XgbaR24Fetch("emerald.r24.maximum",data,XGBA_R24_LIMIT+1u,
                  XGBA_R24_STATUS_BAD_RANGE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    XgbaR24Fetch("emerald.r24.maximum",data,0u,
                  XGBA_R24_STATUS_BAD_RANGE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    /* The address itself is in EWRAM, but [address, address+64) is not. */
    XgbaR24Fetch("emerald.bridge",(void *)0x0203FFF0u,64u,
                  XGBA_R24_STATUS_BAD_RANGE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    XgbaR24Fetch("bad/identifier",data,64u,
                  XGBA_R24_STATUS_BAD_ID,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    XgbaR24Fetch("emerald.r24.missing",data,64u,
                  XGBA_R24_STATUS_RESOURCE_FAILURE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    /* The metadata was valid, but the host's source SHA-256 is deliberately
     * wrong. Provider must reject before changing any emulated EWRAM bytes. */
    XgbaR24Fetch("emerald.r24.badsha",data,32u,
                  XGBA_R24_STATUS_RESOURCE_FAILURE,0u);
    XgbaR24CheckUnchanged(data);
    XgbaR24CheckGuards(region);

    /* Recovery must still work after all seven failures. */
    XgbaR24Fetch("emerald.r24.maximum",data,XGBA_R24_LIMIT,
                  XGBA_R24_STATUS_SUCCESS,XGBA_R24_LIMIT);
    gXgbaR24Proof.final_hash=XgbaR24Hash(data,XGBA_R24_LIMIT);
    XgbaR24CheckGuards(region);
    if(gXgbaR24Proof.final_hash!=gXgbaR24Proof.accepted_hash ||
       gXgbaR24Proof.attempts!=9u ||
       gXgbaR24Proof.accepted!=2u ||
       gXgbaR24Proof.rejected!=7u ||
       gXgbaR24Proof.unchanged_checks!=7u ||
       gXgbaR24Proof.guard_errors)
        ++gXgbaR24Proof.errors;
    Free(region);
    gXgbaR24Proof.state=(gXgbaR24Proof.errors?0xE24u:3u);
}

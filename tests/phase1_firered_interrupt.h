/* Phase 1-only: abrupt emulator process exit during game-initiated Flash1M.
 * This does NOT model physical cartridge power loss or storage durability.
 * Must be included after die(), with mGBA GBA/GBASavedata types visible. */
static uint32_t phase1_le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static unsigned phase1_le16(const uint8_t *p) {
    return (unsigned)p[0] | ((unsigned)p[1]<<8);
}
static unsigned phase1_count_counter3(const struct GBASavedata *s) {
    if (!s->data || s->type != GBA_SAVEDATA_FLASH1M ||
        GBASavedataSize(s) != 131072) return 0;
    unsigned count=0, seen=0;
    for (unsigned physical=14; physical<28; ++physical) {
        const uint8_t *p=s->data+physical*4096U;
        unsigned id=phase1_le16(p+0xFF4U);
        if (id>=14 || (seen & (1U<<id)) ||
            phase1_le32(p+0xFF8U)!=0x08012025U ||
            phase1_le32(p+0xFFCU)!=3U) continue;
        uint32_t sum=0;
        for (unsigned j=0; j<0xF80U; j+=4)
            sum+=phase1_le32(p+j);
        if ((((sum>>16)+sum)&0xFFFFU)==phase1_le16(p+0xFF6U)) {
            seen|=1U<<id;
            ++count;
        }
    }
    return count;
}
static unsigned phase1_cut_selector(int argc) {
    const char *env=getenv("XGBA_PHASE1_CUT_COUNTER3_AFTER");
    if (!env) return 0;
    char *tail;
    unsigned long n=strtoul(env,&tail,10);
    if (!*env || *tail || n<1 || n>13 || argc!=23)
        die("invalid in-flight cut threshold (must be 1..13 with tracing)");
    return (unsigned)n;
}
static void phase1_maybe_interrupt(unsigned cut, unsigned entries, unsigned returns,
                                  uint32_t pending, unsigned long long steps,
                                  unsigned frame, struct GBA *gba, uint32_t counter) {
    if (!cut || !entries || returns || !pending || steps%2048ULL || counter!=3)
        return;
    unsigned n=phase1_count_counter3(&gba->memory.savedata);
    if (n<cut || n>=14) return;
    printf("{\"mode\":\"interrupted_save\",\"cut_threshold\":%u,"
           "\"valid_counter3_sectors\":%u,\"frame\":%u,"
           "\"trace_steps\":%llu,\"try_save_entries\":%u,"
           "\"try_save_returns\":%u,\"counter\":3,"
           "\"no_host_writes\":true,\"no_graceful_close\":true}\n",
           cut,n,frame,steps,entries,returns);
    fflush(stdout);
    _exit(86);
}

/* R12: real FireRed native mGBA save-state rollback and live resource re-fetch.
 * Two SELECT presses, one native savestate; not an endurance benchmark.
 * The temporary state contains game RAM and MUST NOT be published.
 */
#ifndef XGBA_R12_SAVESTATE_H
#define XGBA_R12_SAVESTATE_H
#define R12_BYTES 2048u

static void r12_verify_vram(struct mCore *core, uint32_t probe,
                            const struct ResourceFile *resource,
                            int enabled, unsigned pack, char hexout[65])
{
    if (resource->length != R12_BYTES ||
        resource->second_length != R12_BYTES)
        fail("R12 requires the two genuine R10 2048-byte resources");
    uint32_t tile = core->busRead32(core, probe + 16);
    if (tile > 1022u || tile*32u + R12_BYTES > 0x8000u)
        fail("R12 invalid native FireRed OBJ VRAM allocation");
    uint8_t expected[R12_BYTES] = {0}, actual[R12_BYTES];
    if (enabled) {
        uint64_t offset = pack ? resource->second_offset : resource->offset;
        FILE *f = fopen(resource->path, "rb");
        if (!f || offset > INT64_MAX ||
            fseeko(f, (off_t)offset, SEEK_SET) ||
            fread(expected, 1, R12_BYTES, f) != R12_BYTES)
            fail("R12 unable to independently read expected sidecar data");
        if (fclose(f))
            fail("R12 sidecar close failure");
    }
    for (unsigned i = 0; i < R12_BYTES; ++i)
        actual[i] = core->busRead8(core, 0x06010000u + tile*32u + i);
    if (memcmp(actual, expected, R12_BYTES))
        fail("R12 real OBJ VRAM does not match active external pack/fallback");
    uint8_t hash[32];
    XgbaProviderSha256(actual, R12_BYTES, hash);
    if (enabled && memcmp(hash, pack ? resource->second_digest
                                     : resource->digest, 32))
        fail("R12 loaded graphics SHA does not match sidecar manifest");
    static const char digits[] = "0123456789abcdef";
    for (unsigned i = 0; i < 32; ++i) {
        hexout[i*2] = digits[hash[i] >> 4];
        hexout[i*2+1] = digits[hash[i] & 15];
    }
    hexout[64] = 0;
}
static void r12_expect_game(struct mCore *core, uint32_t probe,
                            int enabled, unsigned pack,
                            unsigned switches, unsigned requests)
{
    if (core->busRead32(core, probe) != XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core, probe + 4) != 3u ||
        core->busRead32(core, probe + 8) != (unsigned)enabled ||
        core->busRead32(core, probe + 12) != (unsigned)enabled ||
        core->busRead32(core, probe + 20) != requests ||
        core->busRead32(core, probe + 24) != switches ||
        core->busRead32(core, probe + 28) != pack ||
        core->busRead32(core, probe + 36) != 3u ||
        core->busRead32(core, probe + 40) != 0u ||
        core->busRead32(core, probe + 44) >= 64u)
        fail("R12 genuine FireRed Pallet Town guest proof diverged");
}
static void r12_capture(struct mCore *core, const char *dir, const char *name)
{
    char path[1024];
    if (snprintf(path, sizeof(path), "%s/%s.png", dir, name)
        >= (int)sizeof(path))
        fail("R12 screenshot path too long");
    save_native_frame(core, path);
}
static void r12_select(struct mCore *core)
{
    core->setKeys(core, 1u << 2); /* real GBA SELECT */
    for (unsigned i = 0; i < 3; ++i) core->runFrame(core);
    core->setKeys(core, 0u);
    for (unsigned i = 0; i < 16; ++i) core->runFrame(core);
}
static void xgba_r12_run(struct mCore *core, uint32_t probe, const char *dir,
                         struct XgbaGbaDevice *device,
                         const struct ResourceFile *resource, int enabled)
{
    if (!probe || !dir || !resource->second_id ||
        device->successful_reads != (unsigned)enabled ||
        device->failed_reads ||
        resource->reads != (unsigned)enabled ||
        resource->lookups != (unsigned)enabled)
        fail("R12 initial genuine game/provider state invalid");
    core->setKeys(core, 0u);
    for (unsigned i = 0; i < 80; ++i) core->runFrame(core);
    r12_expect_game(core, probe, enabled, 0, 0, enabled ? 1 : 0);
    char sha0[65], sha1[65], sha2[65], sha3[65];
    r12_verify_vram(core, probe, resource, enabled, 0, sha0);
    r12_capture(core, dir, "01-initial");
    unsigned tick0 = core->busRead32(core, probe + 32);
    char statepath[1024];
    if (snprintf(statepath, sizeof(statepath), "%s/.native-state.tmp", dir)
        >= (int)sizeof(statepath))
        fail("R12 temporary state path too long");

    struct VFile *state = VFileOpen(statepath, O_CREAT | O_TRUNC | O_RDWR);
    if (!state) fail("R12 native savestate file creation failed");
    bool saved = mCoreSaveStateNamed(core, state, 0);
    bool closed = state->close(state);
    if (!saved || !closed)
        fail("R12 mGBA native saveStateNamed failed");

    r12_select(core);
    r12_expect_game(core, probe, enabled, enabled ? 1 : 0,
                    enabled ? 1 : 0, enabled ? 2 : 0);
    if (device->successful_reads != (enabled ? 2u : 0u) ||
        resource->reads != (enabled ? 2u : 0u) ||
        resource->lookups != (enabled ? 2u : 0u) ||
        device->failed_reads)
        fail("R12 first SELECT external provider lifecycle failed");
    r12_verify_vram(core, probe, resource, enabled, enabled ? 1 : 0, sha1);
    r12_capture(core, dir, "02-after-select");
    unsigned tick1 = core->busRead32(core, probe + 32);
    if (tick1 <= tick0) fail("R12 FireRed overworld failed to advance");

    state = VFileOpen(statepath, O_RDONLY);
    if (!state) fail("R12 saved native mGBA state disappeared");
    bool loaded = mCoreLoadStateNamed(core, state, 0);
    closed = state->close(state);
    if (!loaded || !closed)
        fail("R12 mGBA native loadStateNamed failed");
    if (((struct GBA *)core->board)->xgbaDevice != device)
        fail("R12 load state disconnected the per-instance XGBA provider");
    core->setKeys(core, 0u);
    for (unsigned i = 0; i < 6; ++i) core->runFrame(core);
    r12_expect_game(core, probe, enabled, 0, 0, enabled ? 1 : 0);
    if (device->successful_reads != (enabled ? 2u : 0u) ||
        resource->reads != (enabled ? 2u : 0u) ||
        resource->lookups != (enabled ? 2u : 0u) ||
        device->failed_reads)
        fail("R12 rollback spuriously issued or reversed external file I/O");
    r12_verify_vram(core, probe, resource, enabled, 0, sha2);
    r12_capture(core, dir, "03-restored");
    unsigned tick2 = core->busRead32(core, probe + 32);
    if (tick2 <= tick0 || tick2 >= tick1)
        fail("R12 guest callbacks did not rewind on native state load");

    r12_select(core);
    r12_expect_game(core, probe, enabled, enabled ? 1 : 0,
                    enabled ? 1 : 0, enabled ? 2 : 0);
    if (device->successful_reads != (enabled ? 3u : 0u) ||
        resource->reads != (enabled ? 3u : 0u) ||
        resource->lookups != (enabled ? 3u : 0u) ||
        device->failed_reads)
        fail("R12 post-rollback external resource re-acquisition failed");
    r12_verify_vram(core, probe, resource, enabled, enabled ? 1 : 0, sha3);
    r12_capture(core, dir, "04-replayed");
    if (core->busRead32(core, probe + 32) <= tick2)
        fail("R12 game overworld stopped after replay");
    if (remove(statepath)) fail("R12 temporary native state not removed");

    char report[1024];
    if (snprintf(report, sizeof(report), "%s/proof.json", dir)
        >= (int)sizeof(report))
        fail("R12 proof output path too long");
    FILE *f = fopen(report, "wb");
    if (!f) fail("R12 cannot open machine-readable evidence");
    fprintf(f,
      "{\n"
      "\"milestone\":\"R12_FIRERED_SAVESTATE_ROLLBACK\",\n"
      "\"mode\":\"%s\",\n"
      "\"map\":\"MAP_PALLET_TOWN\",\n"
      "\"native_save_and_load\":true,\n"
      "\"one_rom_one_emulator_process\":true,\n"
      "\"state_file_deleted\":true,\n"
      "\"reads_initial\":%u,\n"
      "\"reads_first_select\":%u,\n"
      "\"reads_after_restore\":%u,\n"
      "\"reads_after_replay\":%u,\n"
      "\"sha_initial\":\"%s\",\n"
      "\"sha_after_select\":\"%s\",\n"
      "\"sha_restored\":\"%s\",\n"
      "\"sha_replayed\":\"%s\",\n"
      "\"ticks_initial\":%u,\n"
      "\"ticks_after_select\":%u,\n"
      "\"ticks_restored\":%u\n"
      "}\n",
      enabled ? "enabled" : "disabled",
      enabled ? 1u : 0u, enabled ? 2u : 0u,
      enabled ? 2u : 0u, device->successful_reads,
      sha0, sha1, sha2, sha3, tick0, tick1, tick2);
    if (fclose(f)) fail("R12 JSON evidence write failed");
    printf("PASS_R12_REAL_FIRERED_SAVESTATE_ROLLBACK mode=%s reads=%u map=3:0\n",
           enabled ? "enabled" : "disabled", device->successful_reads);
}
#endif

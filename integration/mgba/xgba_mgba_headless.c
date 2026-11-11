/*
 * XGBA R7: runnable headless mGBA build, with in-core opt-in guest mailbox.
 *
 * Build with integration/mgba/CMakeLists.txt after applying the pinned patch.
 * This is a developer-facing emulator executable, not the mGBA GUI.
 * Usage: xgba-mgba-headless ROM DATA SOURCE_ID SOURCE_SHA256 RESOURCE_ID
 *        OFFSET LENGTH RESOURCE_SHA256 FRAMES PROBE_ADDR [--disabled]
 *
 * Manifest/source integrity is validated again by the Python launcher. This
 * native executable independently checks ROM SHA-256, all file bounds, and
 * per-resource SHA-256 through the R5 provider. No Python game-memory writes.
 */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <mgba-util/vfs.h>
#include "xgba_mgba_device.h"

#include <errno.h>
#include <inttypes.h>
#include <mgba-util/image.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

extern void XgbaProviderSha256(const uint8_t *, size_t, uint8_t[32]);

struct ResourceFile {
    const char *path;
    const char *id;
    uint64_t offset;
    uint64_t length;
    uint8_t digest[32];
    uint32_t lookups;
    uint32_t reads;
    const char *second_id;
    uint64_t second_offset;
    uint64_t second_length;
    uint8_t second_digest[32];
};

static void fail(const char *message)
{
    fprintf(stderr, "XGBA_R7_FAIL: %s\n", message);
    exit(2);
}

static uint64_t parse_number(const char *text)
{
    char *end = NULL;
    errno = 0;
    unsigned long long number = strtoull(text, &end, 0);
    if (errno || text[0] == '-' || !text[0] || !end || *end)
        fail("invalid numeric argument");
    return (uint64_t)number;
}

static uint8_t nibble(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c-'0');
    if (c >= 'a' && c <= 'f') return (uint8_t)(c-'a'+10);
    if (c >= 'A' && c <= 'F') return (uint8_t)(c-'A'+10);
    fail("invalid SHA-256 hexadecimal byte");
    return 0;
}
static void parse_sha(const char *text, uint8_t result[32])
{
    if (strlen(text) != 64)
        fail("SHA-256 must be 64 hex characters");
    for (size_t i=0; i<32; i++)
        result[i] = (uint8_t)((nibble(text[i*2]) << 4) | nibble(text[i*2+1]));
}

static int file_lookup(void *context, const char *id,
                       uint64_t *length, uint8_t hash[32])
{
    struct ResourceFile *f = context;
    ++f->lookups;
    if (!strcmp(id, f->id)) {
        *length = f->length;
        memcpy(hash, f->digest, 32);
        return 0;
    }
    if (f->second_id && !strcmp(id, f->second_id)) {
        *length = f->second_length;
        memcpy(hash, f->second_digest, 32);
        return 0;
    }
    return 1;
}

static int file_read(void *context, const char *id, uint8_t *dst,
                     size_t cap, size_t *actual)
{
    struct ResourceFile *f = context;
    ++f->reads;
    uint64_t offset, length;
    if (!strcmp(id, f->id)) {
        offset = f->offset;
        length = f->length;
    } else if (f->second_id && !strcmp(id, f->second_id)) {
        offset = f->second_offset;
        length = f->second_length;
    } else {
        return 1;
    }
    if (length > cap || offset > INT64_MAX)
        return 1;
    FILE *fp = fopen(f->path, "rb");
    if (!fp)
        return 1;
    int bad = fseeko(fp, (off_t)offset, SEEK_SET);
    if (!bad)
        *actual = fread(dst, 1, (size_t)length, fp);
    bad |= ferror(fp);
    fclose(fp);
    return bad ? 1 : 0;
}

static uint8_t *read_rom(const char *path, size_t *size)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) fail("cannot open ROM");
    if (fseeko(fp, 0, SEEK_END)) fail("ROM seek");
    off_t total = ftello(fp);
    if (total <= 0 || total > 32u*1024u*1024u)
        fail("ROM size invalid or above cartridge window");
    rewind(fp);
    uint8_t *rom = malloc((size_t)total);
    if (!rom || fread(rom, 1, (size_t)total, fp) != (size_t)total)
        fail("ROM read failed");
    fclose(fp);
    *size = (size_t)total;
    return rom;
}

/* An optional test-only probe address is read, never written, by the host.
 * The guest issues actual MMIO writes independently during ARM execution.
 * Layout: magic, state (3 = completed), verified, used, native tile.
 */
static void verify_game_copy(struct mCore *core, uint32_t probe,
                             const struct XgbaGbaDevice *device,
                             const struct ResourceFile *resource, int enabled)
{
    if (!probe)
        return;
    if (core->busRead32(core, probe) != XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core, probe+4) != 3u)
        fail("actual game never completed native sprite load");
    uint32_t verified = core->busRead32(core, probe+8);
    uint32_t used = core->busRead32(core, probe+12);
    uint32_t tile = core->busRead32(core, probe+16);
    if (!!verified != !!enabled || !!used != !!enabled) {
        fprintf(stderr,
                "XGBA_R7_DIAG: enabled=%d guest_verified=%u guest_used=%u "
                "native_successes=%u native_failures=%u host_lookups=%u "
                "host_reads=%u native_status=%u native_length=%u tile=%u "
                "guest_magic=%08x\\n",
                enabled, verified, used, device->successful_reads,
                device->failed_reads, resource->lookups, resource->reads,
                device->status, device->actual_length, tile,
                core->busRead32(core, XGBA_R7_REG_MAGIC));
        fail("wrong original/external backing chosen by actual game");
    }
    if (enabled && (device->successful_reads != 1 || device->failed_reads))
        fail("game did not issue exactly one validated guest request");
    if (!enabled && (device->successful_reads || device->failed_reads ||
                     resource->lookups || resource->reads))
        fail("disabled emulator unexpectedly accessed host resources");
    if (tile > 1022)
        fail("native OBJ sprite tile index out of range");
    if (resource->length > XGBA_R7_MAX_GUEST_BYTES ||
        (uint64_t)tile*32u + resource->length > 0x8000u)
        fail("sprite graphics allocation exceeds OBJ VRAM");
    uint8_t *expected = calloc((size_t)resource->length, 1);
    if (!expected)
        fail("sprite verification allocation failed");
    expected[0] = 0x11;
    if (resource->length > 3) {
        expected[1] = 0x22;
        expected[2] = 0x33;
        expected[3] = 0x44;
    }
    if (enabled) {
        FILE *fp = fopen(resource->path, "rb");
        if (!fp || fseeko(fp, (off_t)resource->offset, SEEK_SET) ||
            fread(expected, 1, (size_t)resource->length, fp) != resource->length)
            fail("positive proof resource read");
        fclose(fp);
    }
    const uint32_t vram = 0x06010000u + tile*32u;
    for (uint64_t i=0; i<resource->length; i++) {
        if ((uint8_t)core->busRead8(core, vram+i) != expected[i])
            fail("real FireRed native OBJ VRAM differs from external source");
    }
    free(expected);
    puts("PASS_R7_NATIVE_FIRERED_MMIO_LOAD_TO_OBJ_VRAM");
}

static void save_native_frame(struct mCore *core, const char *path)
{
    struct VFile *vf = VFileOpen(path, O_CREAT | O_TRUNC | O_WRONLY);
    if (!vf)
        fail("R9 cannot create mGBA render frame");
    int ok = mCoreTakeScreenshotVF(core, vf);
    vf->close(vf);
    if (!ok)
        fail("R9 native mGBA screenshot encoder failed");
}

static void run_r9_movement_scene(struct mCore *core, uint32_t probe,
                                   const char *directory,
                                   const struct XgbaGbaDevice *device,
                                   int enabled)
{
    if (!probe || !directory)
        fail("R9 scene requires probe symbol and frame directory");
    if (core->busRead32(core, probe+4) != 3u)
        fail("R9 game scene never announced readiness");
    uint32_t start_x = core->busRead32(core, probe+20);
    uint32_t start_y = core->busRead32(core, probe+24);
    char filename[1024];
    for (unsigned i=0; i<16; ++i) {
        /* GBA KEYINPUT bit 4=Right, bit 7=Down.
         * These are real controller input events, not host memory writes. */
        unsigned buttons = (i>=3 && i<10) ? (1u<<4) :
                           (i>=10 && i<15) ? (1u<<7) : 0u;
        core->setKeys(core, buttons);
        core->runFrame(core);
        if (snprintf(filename, sizeof(filename), "%s/frame-%02u.png",
                     directory, i) >= (int)sizeof(filename))
            fail("R9 screenshot filename too long");
        save_native_frame(core, filename);
    }
    core->setKeys(core, 0u);
    uint32_t finish_x = core->busRead32(core, probe+20);
    uint32_t finish_y = core->busRead32(core, probe+24);
    uint32_t updates = core->busRead32(core, probe+28);
    if (finish_x <= start_x || finish_y <= start_y ||
        finish_x-start_x > 50 || finish_y-start_y > 50 || updates < 8)
        fail("R9 did not observe genuine game-controlled directional movement");
    if (enabled && (device->successful_reads != 1 || device->failed_reads))
        fail("R9 enabled pack not fetched exactly once by FireRed");
    if (!enabled && (device->successful_reads || device->failed_reads))
        fail("R9 disabled emulator unexpectedly fetched external assets");
    printf("PASS_R9_REAL_GBA_KEY_INPUT_MOVEMENT enabled=%d x=%u->%u y=%u->%u "
           "updates=%u 16_native_mgba_frames=1\\n",
           enabled, start_x, finish_x, start_y, finish_y, updates);
}

static void run_r10_real_firered_live_swap(struct mCore *core, uint32_t probe,
                                           const char *directory,
                                           const struct XgbaGbaDevice *device,
                                           const struct ResourceFile *resource)
{
    if (!probe || !directory || !resource->second_id)
        fail("R10 real FireRed map needs probe, directory and two resources");
    /* gXgbaR10Proof: magic,ready,verified,used,tile,requests,switches,pack,
     * live native overworld ticks, map group, map num, sprite ID. */
    if (core->busRead32(core, probe) != XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core, probe+4) != 3u) {
        fprintf(stderr,
                "R10_BOOT_DIAGNOSTIC magic=%08x stage=%08x validated=%u "
                "sprite_used=%u tile=%u host_success=%u host_fail=%u "
                "host_lookups=%u host_reads=%u map=%u:%u\\n",
                core->busRead32(core,probe),
                core->busRead32(core,probe+4),
                core->busRead32(core,probe+8),
                core->busRead32(core,probe+12),
                core->busRead32(core,probe+16),
                device->successful_reads,device->failed_reads,
                resource->lookups,resource->reads,
                core->busRead32(core,probe+36),
                core->busRead32(core,probe+40));
        fail("R10 never entered FireRed's real native overworld");
    }
    if (core->busRead32(core, probe+36) != 3u ||
        core->busRead32(core, probe+40) != 0u)
        fail("R10 game not running actual MAP_PALLET_TOWN group3 map0");
    if (core->busRead32(core, probe+44) >= 64u)
        fail("R10 FireRed sprite engine did not create live OBJ sprite");
    if (core->busRead32(core, probe+20) != 1u ||
        core->busRead32(core, probe+28) != 0u)
        fail("R10 FireRed did not load first external resource as crystal");
    char filename[1024];
    core->setKeys(core, 0u);
    /* Let FireRed's native field fade, NPC creation and map rendering settle
     * before recording either side of the same-session resource switch. */
    for (unsigned warmup=0; warmup<70; ++warmup)
        core->runFrame(core);
    unsigned early_tick = core->busRead32(core, probe+32);
    /* Record actual Pallet Town frames with the first resource displayed. */
    for (unsigned i=0; i<12; ++i) {
        core->setKeys(core, 0u);
        core->runFrame(core);
        if (snprintf(filename,sizeof(filename),"%s/before-%02u.png",directory,i)
            >= (int)sizeof(filename))
            fail("R10 before capture path overflow");
        save_native_frame(core,filename);
    }
    unsigned before_count = core->busRead32(core, probe+32);
    if (before_count <= early_tick)
        fail("R10 FireRed map callback did not advance before swap");

    /* Real GBA SELECT button (bit 2), not a host-side game RAM edit. */
    core->setKeys(core, 1u<<2);
    for (unsigned i=0; i<3; ++i)
        core->runFrame(core);
    core->setKeys(core, 0u);
    for (unsigned i=0; i<16; ++i) {
        core->runFrame(core);
        if (snprintf(filename,sizeof(filename),"%s/after-%02u.png",directory,i)
            >= (int)sizeof(filename))
            fail("R10 after capture path overflow");
        save_native_frame(core,filename);
    }
    unsigned after_count=core->busRead32(core,probe+32);
    if (after_count <= before_count ||
        core->busRead32(core,probe+24) != 1u ||
        core->busRead32(core,probe+28) != 1u ||
        core->busRead32(core,probe+20) != 2u ||
        device->successful_reads != 2u || device->failed_reads ||
        resource->lookups != 2u || resource->reads != 2u)
        fail("R10 genuine SELECT did not request and display second resource");
    if (core->busRead32(core,probe+36) != 3u ||
        core->busRead32(core,probe+40) != 0u)
        fail("R10 exited real Pallet Town instead of swapping live");
    puts("PASS_R10_FIRERED_REAL_PALLET_TOWN_LIVE_MMIO_SWITCH: same-game "
         "group3 map0 2_external_fetches 1_Select 1_continuous_session "
         "28_genuine_mGBA_LCDC_frames");
}

#include "xgba_r11_benchmark.h"
#include "xgba_r12_savestate.h"
#include "xgba_r13_map.h"
#include "xgba_r14_nav.h"
#include "xgba_r15_save.h"
#include "xgba_r16_emerald.h"

static void save_actual_game_frame(struct mCore *core, const char *path, int enabled)
{
    if (!path)
        return;
    const void *pixels = NULL;
    size_t stride = 0;
    core->getPixels(core, &pixels, &stride);
    if (!pixels || stride < 240)
        fail("mGBA did not produce a native framebuffer");
    const mColor *frame = (const mColor*)pixels;
    mColor backdrop = frame[16*stride+16];
    unsigned visual_pixels = 0;
    for (unsigned y=48; y<112; ++y)
        for (unsigned x=88; x<152; ++x)
            visual_pixels += frame[y*stride+x] != backdrop;
    if (enabled && visual_pixels < 160)
        fail("R8 external 64x64 sprite is not visible in real mGBA framebuffer");
    if (!enabled && visual_pixels > 80)
        fail("R8 fallback unexpectedly rendered external sprite");
    struct VFile *image = VFileOpen(path, O_CREAT | O_TRUNC | O_WRONLY);
    if (!image)
        fail("cannot create real mGBA screenshot file");
    int saved = mCoreTakeScreenshotVF(core, image);
    image->close(image);
    if (!saved)
        fail("mGBA native framebuffer PNG encoding failed");
    printf("PASS_R8_REAL_MGBA_RENDERED_PNG enabled=%d center_pixels=%u output=%s\\n",
           enabled, visual_pixels, path);
}

int main(int argc, char **argv)
{
    if (argc < 11 || argc > 40)
        fail("usage: ROM DATA SOURCE_ID SOURCE_SHA RESOURCE_ID OFFSET LENGTH RESOURCE_SHA FRAMES PROBE_ADDR [--screenshot path] [--scene-dir path] [--r10-dir path] [--r11-perf path] [--r12-dir path] [--r13-dir path] [--r14-dir path] [--second-resource ID OFFSET LENGTH SHA] [--disabled]");
    const char *screenshot = NULL;
    const char *scene_dir = NULL;
    const char *r10_dir = NULL;
    const char *r11_perf = NULL;
    const char *r12_dir = NULL;
    const char *r13_dir = NULL;
    const char *r14_dir = NULL;
    const char *r15_dir = NULL;
    const char *r16_dir = NULL;
    const char *r15_savefile = NULL;
    const char *r15_phase = NULL;
    uint64_t r15_save_probe = 0;
    const char *second_id = NULL;
    uint64_t second_offset = 0, second_length = 0;
    uint8_t second_sha[32] = {0};
    int enabled = 1;
    for (int i=11; i<argc; ++i) {
        if (!strcmp(argv[i], "--disabled"))
            enabled = 0;
        else if (!strcmp(argv[i], "--screenshot") && ++i < argc && !screenshot)
            screenshot = argv[i];
        else if (!strcmp(argv[i], "--scene-dir") && ++i < argc && !scene_dir)
            scene_dir = argv[i];
        else if (!strcmp(argv[i], "--r10-dir") && ++i < argc && !r10_dir)
            r10_dir = argv[i];
        else if (!strcmp(argv[i], "--r11-perf") && ++i < argc && !r11_perf)
            r11_perf = argv[i];
        else if (!strcmp(argv[i], "--r12-dir") && ++i < argc && !r12_dir)
            r12_dir = argv[i];
        else if (!strcmp(argv[i], "--r13-dir") && ++i < argc && !r13_dir)
            r13_dir = argv[i];
        else if (!strcmp(argv[i], "--r14-dir") && ++i < argc && !r14_dir)
            r14_dir = argv[i];
        else if (!strcmp(argv[i], "--r15-dir") && ++i < argc && !r15_dir)
            r15_dir = argv[i];
        else if (!strcmp(argv[i], "--r16-emerald-dir") && ++i < argc && !r16_dir)
            r16_dir = argv[i];
        else if (!strcmp(argv[i], "--r15-savefile") && ++i < argc && !r15_savefile)
            r15_savefile = argv[i];
        else if (!strcmp(argv[i], "--r15-phase") && ++i < argc && !r15_phase)
            r15_phase = argv[i];
        else if (!strcmp(argv[i], "--r15-save-probe") && ++i < argc && !r15_save_probe)
            r15_save_probe = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--second-resource") && i+4 < argc &&
                 !second_id) {
            second_id = argv[++i];
            second_offset = parse_number(argv[++i]);
            second_length = parse_number(argv[++i]);
            parse_sha(argv[++i], second_sha);
        } else
            fail("unknown or malformed option");
    }
    uint64_t offset = parse_number(argv[6]), length = parse_number(argv[7]);
    uint64_t frames = parse_number(argv[9]);
    uint64_t probe = parse_number(argv[10]);
    if (offset <= (uint64_t)32*1024*1024 ||
        length == 0 || length > XGBA_R7_MAX_GUEST_BYTES ||
        offset > INT64_MAX || offset > UINT64_MAX-length ||
        frames == 0 || frames > 36000 || probe > UINT32_MAX)
        fail("resource range or frame budget invalid");
    if (second_id &&
        (strlen(second_id) > 128u || !*second_id ||
         second_offset <= 32u*1024u*1024u ||
         second_offset > INT64_MAX ||
         !second_length || second_length > XGBA_R7_MAX_GUEST_BYTES))
        fail("R10 second resource outside bounded sidecar contract");
    size_t rom_size = 0;
    uint8_t *rom = read_rom(argv[1], &rom_size);
    uint8_t actual_rom_digest[32], supplied_rom_digest[32];
    XgbaProviderSha256(rom, rom_size, actual_rom_digest);
    parse_sha(argv[4], supplied_rom_digest);
    if (memcmp(actual_rom_digest, supplied_rom_digest, 32))
        fail("source ROM hash does not match sidecar identity");

    struct ResourceFile resource = {
        .path = argv[2], .id = argv[5], .offset = offset, .length = length
    };
    parse_sha(argv[8], resource.digest);
    resource.second_id = second_id;
    resource.second_offset = second_offset;
    resource.second_length = second_length;
    memcpy(resource.second_digest, second_sha, 32);
    struct XgbaMgbaProviderV1 host = {
        .abi_version = 1u,
        .struct_size = sizeof(host),
        .context = &resource,
        .lookup = file_lookup,
        .read = file_read,
    };
    if (strlen(argv[3]) > 128u || !strlen(argv[3]))
        fail("source ID length");
    strcpy(host.source_id, argv[3]);
    memcpy(host.source_sha256, actual_rom_digest, 32);
    struct XgbaGbaDevice device;
    if (XgbaDeviceInit(&device, &host, enabled, argv[3],
                       supplied_rom_digest) != 0)
        fail("versioned native host provider handshake refused");

    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core))
        fail("mGBA core initialization failed");
    mColor *video = (screenshot || scene_dir || r10_dir || r11_perf || r12_dir || r13_dir || r14_dir || r15_dir || r16_dir)
                   ? calloc(240u*160u, sizeof(mColor)) : NULL;
    if ((screenshot || scene_dir || r10_dir || r11_perf || r12_dir || r13_dir || r14_dir || r15_dir || r16_dir) && !video)
        fail("cannot allocate GBA framebuffer");
    if (video)
        core->setVideoBuffer(core, video, 240);
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, rom_size);
    if (!vf || !core->loadROM(core, vf))
        fail("mGBA could not load source-built FireRed ROM");
    /* R15 uses a real on-disk Flash save, not a native emulator savestate.
     * File persists between separate emulator subprocesses, never exported. */
    if (r15_dir) {
        if (!r15_phase || !r15_savefile || !r15_save_probe ||
            r15_save_probe > UINT32_MAX)
            fail("R15 requires phase, Flash save file and guest proof");
        if (!mCoreLoadSaveFile(core,r15_savefile,false))
            fail("R15 could not attach real mGBA Flash save file");
    }
    core->reset(core);
    struct GBA *gba = (struct GBA *)core->board;
    if (!gba) fail("mGBA GBA board inaccessible");
    gba->xgbaDevice = &device; /* opt-in per emulator instance; no global */
    for (uint64_t frame=0; frame<frames; ++frame) {
        core->runFrame(core);
        if (probe && core->busRead32(core, (uint32_t)probe+4) == 3u)
            break;
        if (r15_phase && !strcmp(r15_phase,"corrupt") && probe &&
            core->busRead32(core,(uint32_t)probe+4)==0xE14u)
            break;
    }
    if ((r10_dir && (r11_perf || r12_dir)) || (r11_perf && r12_dir))
        fail("R10/R11/R12 execution modes are mutually exclusive");
    if (r10_dir) {
        if (!enabled)
            fail("R10 live swap requires extension enabled");
        run_r10_real_firered_live_swap(core, (uint32_t)probe, r10_dir,
                                      &device, &resource);
    } else if (r11_perf) {
        if (!second_id)
            fail("R11 requires both post-32MiB resources");
        xgba_r11_run(core, (uint32_t)probe, r11_perf,
                     &device, &resource, enabled);
    } else if (r12_dir) {
        if (!second_id)
            fail("R12 requires both post-32MiB resources");
        xgba_r12_run(core, (uint32_t)probe, r12_dir,
                     &device, &resource, enabled);
    } else if (r13_dir) {
        xgba_r13_run(core, (uint32_t)probe, r13_dir, &device, &resource, enabled);
    } else if (r14_dir) {
        xgba_r14_run(core, (uint32_t)probe, r14_dir, &device, &resource, enabled);
    } else if (r15_dir) {
        xgba_r15_run(core,(uint32_t)probe,(uint32_t)r15_save_probe,
                     r15_dir,r15_phase,&device,&resource,enabled);
    } else if (r16_dir) {
        xgba_r16_emerald_run(core,(uint32_t)probe,r16_dir,&device,&resource,enabled);
    } else if (!scene_dir) {
        verify_game_copy(core, (uint32_t)probe, &device, &resource, enabled);
    }
    if (scene_dir)
        run_r9_movement_scene(core, (uint32_t)probe, scene_dir, &device, enabled);
    if (screenshot) {
        /* Present multiple actual LCD frames after the GBA game sets OAM and
         * registers. No host graphics manipulation is permitted. */
        for (int frame=0; frame<4; ++frame)
            core->runFrame(core);
        save_actual_game_frame(core, screenshot, enabled);
    }
    printf("PASS_R7_XGBA_MGBA_BUILD enabled=%u requests=%u failures=%u host_lookups=%u bytes=%u\n",
           (unsigned)enabled, device.successful_reads, device.failed_reads,
           resource.lookups, device.actual_length);
    gba->xgbaDevice = NULL;
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(video);
    free(rom);
    return 0;
}

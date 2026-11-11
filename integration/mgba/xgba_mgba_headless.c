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
    if (strcmp(id, f->id))
        return 1;
    *length = f->length;
    memcpy(hash, f->digest, 32);
    return 0;
}

static int file_read(void *context, const char *id, uint8_t *dst,
                     size_t cap, size_t *actual)
{
    struct ResourceFile *f = context;
    ++f->reads;
    if (strcmp(id, f->id) || f->length > cap || f->offset > INT64_MAX)
        return 1;
    FILE *fp = fopen(f->path, "rb");
    if (!fp)
        return 1;
    int bad = fseeko(fp, (off_t)f->offset, SEEK_SET);
    if (!bad)
        *actual = fread(dst, 1, (size_t)f->length, fp);
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
    if (!!verified != !!enabled || !!used != !!enabled)
        fail("wrong original/external backing chosen by actual game");
    if (enabled && (device->successful_reads != 1 || device->failed_reads))
        fail("game did not issue exactly one validated guest request");
    if (!enabled && (device->successful_reads || device->failed_reads ||
                     resource->lookups || resource->reads))
        fail("disabled emulator unexpectedly accessed host resources");
    if (tile > 1022)
        fail("native OBJ sprite tile index out of range");
    uint8_t expected[64] = {0x11, 0x22, 0x33, 0x44};
    if (enabled) {
        FILE *fp = fopen(resource->path, "rb");
        if (!fp || fseeko(fp, (off_t)resource->offset, SEEK_SET) ||
            fread(expected, 1, sizeof(expected), fp) != sizeof(expected))
            fail("positive proof resource read");
        fclose(fp);
    }
    const uint32_t vram = 0x06010000u + tile*32u;
    for (unsigned i=0; i<sizeof(expected); i++) {
        if ((uint8_t)core->busRead8(core, vram+i) != expected[i])
            fail("real FireRed native OBJ VRAM differs from external source");
    }
    puts("PASS_R7_NATIVE_FIRERED_MMIO_LOAD_TO_OBJ_VRAM");
}

int main(int argc, char **argv)
{
    if (argc != 11 && argc != 12)
        fail("usage: ROM DATA SOURCE_ID SOURCE_SHA RESOURCE_ID OFFSET LENGTH RESOURCE_SHA FRAMES PROBE_ADDR [--disabled]");
    if (argc == 12 && strcmp(argv[11], "--disabled"))
        fail("unknown mode");
    const int enabled = argc == 11;
    uint64_t offset = parse_number(argv[6]), length = parse_number(argv[7]);
    uint64_t frames = parse_number(argv[9]);
    uint64_t probe = parse_number(argv[10]);
    if (offset <= (uint64_t)32*1024*1024 ||
        length == 0 || length > XGBA_R7_MAX_GUEST_BYTES ||
        offset > INT64_MAX || offset > UINT64_MAX-length ||
        frames == 0 || frames > 36000 || probe > UINT32_MAX)
        fail("resource range or frame budget invalid");
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
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, rom_size);
    if (!vf || !core->loadROM(core, vf))
        fail("mGBA could not load source-built FireRed ROM");
    core->reset(core);
    struct GBA *gba = (struct GBA *)core->board;
    if (!gba) fail("mGBA GBA board inaccessible");
    gba->xgbaDevice = &device; /* opt-in per emulator instance; no global */
    for (uint64_t frame=0; frame<frames; ++frame) {
        core->runFrame(core);
        if (probe && core->busRead32(core, (uint32_t)probe+4) == 3u)
            break;
    }
    verify_game_copy(core, (uint32_t)probe, &device, &resource, enabled);
    printf("PASS_R7_XGBA_MGBA_BUILD enabled=%u requests=%u failures=%u host_lookups=%u bytes=%u\n",
           (unsigned)enabled, device.successful_reads, device.failed_reads,
           resource.lookups, device.actual_length);
    gba->xgbaDevice = NULL;
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(rom);
    return 0;
}

/*
 * XGBA R7 opt-in guest MMIO device for a modified mGBA build.
 * See xgba_mgba_device.h. No ROM address mapping and no save flash hooks.
 */
#include "xgba_mgba_device.h"

#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <stdlib.h>
#include <string.h>

enum XgbaMgbaProviderStatus {
    XGBA_MGBA_OK = 0,
    XGBA_MGBA_INVALID = 1,
    XGBA_MGBA_DISABLED = 2,
    XGBA_MGBA_IDENTITY_MISMATCH = 3,
    XGBA_MGBA_NOT_FOUND = 4,
    XGBA_MGBA_TRUNCATED = 5,
    XGBA_MGBA_INTEGRITY_ERROR = 6,
    XGBA_MGBA_LIMIT_EXCEEDED = 7,
};
extern enum XgbaMgbaProviderStatus xgba_mgba_provider_open(
    struct XgbaMgbaProvider *, const struct XgbaMgbaProviderV1 *, int,
    const char *, const uint8_t[32]);
extern enum XgbaMgbaProviderStatus xgba_mgba_provider_read(
    const struct XgbaMgbaProvider *, const char *, uint8_t *, size_t, size_t *);

#define EWRAM_START 0x02000000u
#define EWRAM_SIZE  0x00040000u

static int ewram_range(uint32_t address, uint32_t size)
{
    return address >= EWRAM_START && size <= EWRAM_SIZE &&
           address - EWRAM_START <= EWRAM_SIZE - size;
}

static int guest_id(struct GBA *gba, uint32_t address,
                    char output[XGBA_R7_MAX_RESOURCE_ID + 1u])
{
    if (!ewram_range(address, 1))
        return 0;
    const uint8_t *mem = (const uint8_t *)gba->memory.wram;
    if (!mem)
        return 0;
    uint32_t offset = address - EWRAM_START;
    for (size_t i = 0; i <= XGBA_R7_MAX_RESOURCE_ID; ++i) {
        if (offset + i >= EWRAM_SIZE)
            return 0;
        uint8_t c = mem[offset + i];
        if (!c)
            return i > 0;
        int valid = (c >= 'A' && c <= 'Z') ||
                    (c >= 'a' && c <= 'z') ||
                    (c >= '0' && c <= '9') ||
                    (i && (c == '.' || c == '_' || c == '-'));
        if (!valid || i == XGBA_R7_MAX_RESOURCE_ID)
            return 0;
        output[i] = (char)c;
        output[i + 1] = 0;
    }
    return 0;
}

int XgbaDeviceInit(struct XgbaGbaDevice *device,
                   const struct XgbaMgbaProviderV1 *host, int enabled,
                   const char *source_id, const uint8_t game_sha256[32])
{
    if (!device)
        return XGBA_MGBA_INVALID;
    memset(device, 0, sizeof(*device));
    if (xgba_mgba_provider_open(&device->provider, host, enabled,
                                source_id, game_sha256) != XGBA_MGBA_OK)
        return XGBA_MGBA_INVALID;
    return XGBA_MGBA_OK;
}

void XgbaDeviceReset(struct XgbaGbaDevice *device)
{
    if (!device)
        return;
    device->id_addr = 0;
    device->dst_addr = 0;
    device->capacity = 0;
    device->status = XGBA_R7_IDLE;
    device->actual_length = 0;
    device->successful_reads = 0;
    device->failed_reads = 0;
    device->rejected_ranges = 0;
    device->rejected_ids = 0;
    device->provider_too_large = 0;
    device->provider_bad_sha256 = 0;
    device->provider_not_found = 0;
    device->provider_other_failures = 0;
}

static void execute_request(struct GBA *gba, struct XgbaGbaDevice *device)
{
    device->actual_length = 0;
    if (!device->capacity || device->capacity > XGBA_R7_MAX_GUEST_BYTES ||
        !ewram_range(device->dst_addr, device->capacity)) {
        device->status = XGBA_R7_BAD_RANGE;
        ++device->rejected_ranges;
        ++device->failed_reads;
        return;
    }
    char id[XGBA_R7_MAX_RESOURCE_ID + 1u] = {0};
    if (!guest_id(gba, device->id_addr, id)) {
        device->status = XGBA_R7_BAD_ID;
        ++device->rejected_ids;
        ++device->failed_reads;
        return;
    }
    uint8_t *candidate = malloc(device->capacity);
    if (!candidate) {
        device->status = XGBA_R7_RESOURCE_FAILURE;
        ++device->failed_reads;
        return;
    }
    size_t length = 0;
    enum XgbaMgbaProviderStatus status = xgba_mgba_provider_read(
        &device->provider, id, candidate, device->capacity, &length);
    /* Never report a zero-byte provider response as successful guest load.
     * A partial or refused read must leave the guest buffer unchanged. */
    if (status != XGBA_MGBA_OK || !length || length > device->capacity ||
        !ewram_range(device->dst_addr, (uint32_t)length)) {
        device->status = XGBA_R7_RESOURCE_FAILURE;
        if (status == XGBA_MGBA_LIMIT_EXCEEDED)
            ++device->provider_too_large;
        else if (status == XGBA_MGBA_INTEGRITY_ERROR)
            ++device->provider_bad_sha256;
        else if (status == XGBA_MGBA_NOT_FOUND)
            ++device->provider_not_found;
        else
            ++device->provider_other_failures;
        ++device->failed_reads;
        free(candidate);
        return;
    }
    uint8_t *mem = (uint8_t *)gba->memory.wram;
    memcpy(mem + (device->dst_addr - EWRAM_START), candidate, length);
    free(candidate);
    device->status = XGBA_R7_SUCCESS;
    device->actual_length = (uint32_t)length;
    ++device->successful_reads;
}

int XgbaDeviceLoad32(struct GBA *gba, uint32_t address, uint32_t *value)
{
    if (!gba || !gba->xgbaDevice || !gba->xgbaDevice->provider.enabled)
        return 0;
    struct XgbaGbaDevice *d = gba->xgbaDevice;
    uint32_t result;
    switch (address) {
    case XGBA_R7_REG_MAGIC: result = XGBA_R7_MMIO_MAGIC; break;
    case XGBA_R7_REG_VERSION: result = XGBA_R7_MMIO_VERSION; break;
    case XGBA_R7_REG_ID_ADDR: result = d->id_addr; break;
    case XGBA_R7_REG_DST_ADDR: result = d->dst_addr; break;
    case XGBA_R7_REG_CAPACITY: result = d->capacity; break;
    case XGBA_R7_REG_STATUS: result = d->status; break;
    case XGBA_R7_REG_LENGTH: result = d->actual_length; break;
    default: return 0;
    }
    if (value)
        *value = result;
    return 1;
}

int XgbaDeviceStore32(struct GBA *gba, uint32_t address, uint32_t value)
{
    if (!gba || !gba->xgbaDevice || !gba->xgbaDevice->provider.enabled)
        return 0;
    struct XgbaGbaDevice *d = gba->xgbaDevice;
    switch (address) {
    case XGBA_R7_REG_ID_ADDR:
        d->id_addr = value;
        d->status = XGBA_R7_IDLE;
        d->actual_length = 0;
        break;
    case XGBA_R7_REG_DST_ADDR:
        d->dst_addr = value;
        d->status = XGBA_R7_IDLE;
        d->actual_length = 0;
        break;
    case XGBA_R7_REG_CAPACITY:
        d->capacity = value;
        d->status = XGBA_R7_IDLE;
        d->actual_length = 0;
        break;
    case XGBA_R7_REG_COMMAND:
        if (value == 1u) {
            execute_request(gba, d);
        } else {
            d->status = XGBA_R7_BAD_COMMAND;
            d->actual_length = 0;
            ++d->failed_reads;
        }
        break;
    default:
        return 0;
    }
    return 1;
}

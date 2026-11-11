/*
 * XGBA R7 guest-initiated, opt-in mGBA resource interface.
 *
 * Experimental extension of pinned mGBA, NOT a regular GBA hardware register.
 * Only activated by the host after explicit opt-in and verified ROM identity.
 * All addresses are 32-bit word-aligned. Disabled emulator cores behave as
 * unmodified mGBA for every guest memory operation.
 *
 * This file is authored for the XGBA project; it includes NO upstream game
 * or mGBA source code. Upstream mGBA is MPL-2.0.
 */
#ifndef XGBA_MGBA_DEVICE_H
#define XGBA_MGBA_DEVICE_H

#include <stddef.h>
#include <stdint.h>

#define XGBA_R7_MMIO_BASE     0x04FF8000u
#define XGBA_R7_MMIO_MAGIC    0x58474241u /* 'XGBA' */
#define XGBA_R7_MMIO_VERSION  1u

#define XGBA_R7_REG_MAGIC     (XGBA_R7_MMIO_BASE + 0x00u) /* R */
#define XGBA_R7_REG_VERSION   (XGBA_R7_MMIO_BASE + 0x04u) /* R */
#define XGBA_R7_REG_ID_ADDR   (XGBA_R7_MMIO_BASE + 0x08u) /* W: EWRAM NUL-terminated ID */
#define XGBA_R7_REG_DST_ADDR  (XGBA_R7_MMIO_BASE + 0x0Cu) /* W: EWRAM destination */
#define XGBA_R7_REG_CAPACITY  (XGBA_R7_MMIO_BASE + 0x10u) /* W: bounded byte capacity */
#define XGBA_R7_REG_COMMAND   (XGBA_R7_MMIO_BASE + 0x14u) /* W: 1 -> fetch */
#define XGBA_R7_REG_STATUS    (XGBA_R7_MMIO_BASE + 0x18u) /* R */
#define XGBA_R7_REG_LENGTH    (XGBA_R7_MMIO_BASE + 0x1Cu) /* R */

#define XGBA_R7_MAX_GUEST_BYTES 16384u
#define XGBA_R7_MAX_RESOURCE_ID 128u

enum XgbaR7Status {
    XGBA_R7_IDLE = 0,
    XGBA_R7_SUCCESS = 1,
    XGBA_R7_BAD_COMMAND = 2,
    XGBA_R7_BAD_RANGE = 3,
    XGBA_R7_BAD_ID = 4,
    XGBA_R7_RESOURCE_FAILURE = 5
};

/* Identical public ABI to the R5 C host-provider contract. */
#define XGBA_MGBA_SHA256_LENGTH 32u
#define XGBA_MGBA_MAX_ID_LENGTH 128u
struct XgbaMgbaProviderV1 {
    uint32_t abi_version;
    uint32_t struct_size;
    char source_id[XGBA_MGBA_MAX_ID_LENGTH + 1u];
    uint8_t source_sha256[XGBA_MGBA_SHA256_LENGTH];
    void *context;
    int (*lookup)(void *context, const char *resource_id,
                  uint64_t *length, uint8_t sha256[XGBA_MGBA_SHA256_LENGTH]);
    int (*read)(void *context, const char *resource_id, uint8_t *destination,
                size_t capacity, size_t *bytes_read);
};
struct XgbaMgbaProvider {
    uint32_t abi_version;
    uint32_t enabled;
    struct XgbaMgbaProviderV1 host;
};

struct GBA;
struct XgbaGbaDevice {
    struct XgbaMgbaProvider provider;
    uint32_t id_addr;
    uint32_t dst_addr;
    uint32_t capacity;
    uint32_t status;
    uint32_t actual_length;
    uint32_t successful_reads;
    uint32_t failed_reads;
    /* R24 diagnostic counters: distinguish guest bounds/ID errors from
     * provider truncation, missing IDs and verified SHA-256 mismatch.
     * Append-only host struct; the existing v1 guest MMIO ABI is unchanged. */
    uint32_t rejected_ranges;
    uint32_t rejected_ids;
    uint32_t provider_too_large;
    uint32_t provider_bad_sha256;
    uint32_t provider_not_found;
    uint32_t provider_other_failures;
};

/* Returns 0 on successful opt-in / opt-out, nonzero on ABI or identity error. */
int XgbaDeviceInit(struct XgbaGbaDevice *device,
                   const struct XgbaMgbaProviderV1 *host, int enabled,
                   const char *source_id, const uint8_t game_sha256[32]);
void XgbaDeviceReset(struct XgbaGbaDevice *device);
int XgbaDeviceLoad32(struct GBA *gba, uint32_t address, uint32_t *value);
int XgbaDeviceStore32(struct GBA *gba, uint32_t address, uint32_t value);

#endif

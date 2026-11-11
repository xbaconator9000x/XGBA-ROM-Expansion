/*
 * XGBA R5: opt-in native mGBA host-resource provider ABI.
 *
 * This extension is deliberately outside the GBA bus and does not replace or
 * intercept any mGBA cartridge, save, peripheral, or DMA route. The host
 * provider must expose bytes already validated by the R1/R2/R3 resource
 * pipeline. The adapter stages only into a caller-owned bounded host buffer.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define XGBA_MGBA_PROVIDER_ABI_VERSION 1u
#define XGBA_MGBA_MAX_ID_LENGTH 128u
#define XGBA_MGBA_SHA256_LENGTH 32u
#define XGBA_MGBA_MAX_RESOURCE_BYTES (16u * 1024u * 1024u)

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

enum XgbaMgbaProviderStatus xgba_mgba_provider_open(
    struct XgbaMgbaProvider *provider,
    const struct XgbaMgbaProviderV1 *host,
    int opt_in,
    const char *expected_source_id,
    const uint8_t expected_source_sha256[XGBA_MGBA_SHA256_LENGTH]);

enum XgbaMgbaProviderStatus xgba_mgba_provider_read(
    const struct XgbaMgbaProvider *provider,
    const char *resource_id,
    uint8_t *destination,
    size_t capacity,
    size_t *bytes_read);

static uint32_t xgba_rotr32(uint32_t value, unsigned count)
{
    return (value >> count) | (value << (32u - count));
}

static void xgba_sha256_block(uint32_t state[8], const uint8_t block[64])
{
    static const uint32_t k[64] = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
        0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
        0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
        0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
        0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
        0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
        0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
        0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
        0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
        0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
        0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
        0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
        0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
        0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
        0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
    };
    uint32_t w[64];
    for (unsigned i = 0; i < 16; ++i) {
        w[i] = ((uint32_t)block[i * 4] << 24) |
               ((uint32_t)block[i * 4 + 1] << 16) |
               ((uint32_t)block[i * 4 + 2] << 8) |
               (uint32_t)block[i * 4 + 3];
    }
    for (unsigned i = 16; i < 64; ++i) {
        uint32_t s0 = xgba_rotr32(w[i - 15], 7) ^
                      xgba_rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = xgba_rotr32(w[i - 2], 17) ^
                      xgba_rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = state[0], b = state[1], c = state[2], d = state[3];
    uint32_t e = state[4], f = state[5], g = state[6], h = state[7];
    for (unsigned i = 0; i < 64; ++i) {
        uint32_t s1 = xgba_rotr32(e, 6) ^ xgba_rotr32(e, 11) ^
                      xgba_rotr32(e, 25);
        uint32_t choice = (e & f) ^ (~e & g);
        uint32_t temp1 = h + s1 + choice + k[i] + w[i];
        uint32_t s0 = xgba_rotr32(a, 2) ^ xgba_rotr32(a, 13) ^
                      xgba_rotr32(a, 22);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temp2 = s0 + majority;
        h = g; g = f; f = e; e = d + temp1;
        d = c; c = b; b = a; a = temp1 + temp2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

static void xgba_sha256(const uint8_t *data, size_t length, uint8_t digest[32])
{
    uint32_t state[8] = {
        0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
        0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u,
    };
    const size_t original_length = length;
    while (length >= 64u) {
        xgba_sha256_block(state, data);
        data += 64u;
        length -= 64u;
    }
    uint8_t tail[128] = {0};
    if (length)
        memcpy(tail, data, length);
    tail[length] = 0x80u;
    size_t padded = length < 56u ? 64u : 128u;
    uint64_t bit_length = (uint64_t)original_length * 8u;
    for (unsigned i = 0; i < 8; ++i)
        tail[padded - 1u - i] = (uint8_t)(bit_length >> (i * 8u));
    xgba_sha256_block(state, tail);
    if (padded == 128u)
        xgba_sha256_block(state, tail + 64u);
    for (unsigned i = 0; i < 8; ++i) {
        digest[i * 4] = (uint8_t)(state[i] >> 24);
        digest[i * 4 + 1] = (uint8_t)(state[i] >> 16);
        digest[i * 4 + 2] = (uint8_t)(state[i] >> 8);
        digest[i * 4 + 3] = (uint8_t)state[i];
    }
}

static size_t xgba_bounded_string_length(const char *text, size_t maximum)
{
    if (!text)
        return maximum + 1u;
    size_t length = 0;
    while (length <= maximum && text[length] != '\0')
        ++length;
    return length;
}

static int xgba_valid_identifier(const char *text)
{
    size_t length = xgba_bounded_string_length(text, XGBA_MGBA_MAX_ID_LENGTH);
    if (length == 0 || length > XGBA_MGBA_MAX_ID_LENGTH)
        return 0;
    for (size_t i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)text[i];
        int alphanumeric = (c >= 'A' && c <= 'Z') ||
                           (c >= 'a' && c <= 'z') ||
                           (c >= '0' && c <= '9');
        if (!alphanumeric && (i == 0 || (c != '.' && c != '_' && c != '-')))
            return 0;
    }
    return 1;
}

enum XgbaMgbaProviderStatus xgba_mgba_provider_open(
    struct XgbaMgbaProvider *provider,
    const struct XgbaMgbaProviderV1 *host,
    int opt_in,
    const char *expected_source_id,
    const uint8_t expected_source_sha256[XGBA_MGBA_SHA256_LENGTH])
{
    if (!provider || (opt_in != 0 && opt_in != 1))
        return XGBA_MGBA_INVALID;
    memset(provider, 0, sizeof(*provider));
    provider->abi_version = XGBA_MGBA_PROVIDER_ABI_VERSION;
    if (!opt_in)
        return XGBA_MGBA_OK;
    if (!host || !expected_source_sha256 ||
        !xgba_valid_identifier(expected_source_id))
        return XGBA_MGBA_INVALID;
    if (host->abi_version != XGBA_MGBA_PROVIDER_ABI_VERSION ||
        host->struct_size < sizeof(*host) ||
        !host->lookup || !host->read ||
        !xgba_valid_identifier(host->source_id))
        return XGBA_MGBA_INVALID;
    if (strcmp(host->source_id, expected_source_id) != 0 ||
        memcmp(host->source_sha256, expected_source_sha256,
               XGBA_MGBA_SHA256_LENGTH) != 0)
        return XGBA_MGBA_IDENTITY_MISMATCH;
    provider->host = *host;
    provider->enabled = 1u;
    return XGBA_MGBA_OK;
}

enum XgbaMgbaProviderStatus xgba_mgba_provider_read(
    const struct XgbaMgbaProvider *provider,
    const char *resource_id,
    uint8_t *destination,
    size_t capacity,
    size_t *bytes_read)
{
    if (bytes_read)
        *bytes_read = 0;
    if (!provider || provider->abi_version != XGBA_MGBA_PROVIDER_ABI_VERSION ||
        !destination || !bytes_read || capacity == 0 ||
        !xgba_valid_identifier(resource_id))
        return XGBA_MGBA_INVALID;
    if (!provider->enabled)
        return XGBA_MGBA_DISABLED;

    uint64_t length = 0;
    uint8_t expected_digest[XGBA_MGBA_SHA256_LENGTH];
    if (provider->host.lookup(provider->host.context, resource_id, &length,
                               expected_digest) != 0)
        return XGBA_MGBA_NOT_FOUND;
    if (length == 0 || length > XGBA_MGBA_MAX_RESOURCE_BYTES ||
        length > capacity || length > SIZE_MAX)
        return XGBA_MGBA_LIMIT_EXCEEDED;

    size_t bounded_length = (size_t)length;
    uint8_t *candidate = malloc(bounded_length);
    if (!candidate)
        return XGBA_MGBA_LIMIT_EXCEEDED;
    size_t received = 0;
    int read_status = provider->host.read(provider->host.context, resource_id,
                                          candidate, bounded_length, &received);
    if (read_status != 0 || received != bounded_length) {
        free(candidate);
        return XGBA_MGBA_TRUNCATED;
    }
    uint8_t actual_digest[XGBA_MGBA_SHA256_LENGTH];
    xgba_sha256(candidate, bounded_length, actual_digest);
    if (memcmp(actual_digest, expected_digest, sizeof(actual_digest)) != 0) {
        free(candidate);
        return XGBA_MGBA_INTEGRITY_ERROR;
    }
    memcpy(destination, candidate, bounded_length);
    *bytes_read = bounded_length;
    free(candidate);
    return XGBA_MGBA_OK;
}


/* R7 uses the same SHA-256 implementation for source-ROM identity checking. */
void XgbaProviderSha256(const uint8_t *data, size_t size, uint8_t digest[32])
{
    if (!data || !digest)
        return;
    xgba_sha256(data, size, digest);
}

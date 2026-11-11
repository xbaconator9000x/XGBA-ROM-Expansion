/* R24 portable syntax/format check of the exact native mGBA proof header.
 * This is NOT original patched mGBA, and does not produce gameplay proof.
 * Real original FireRed/Emerald native CI remains required.
 */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include "../integration/mgba/xgba_mgba_device.h"

struct mCore {
    uint32_t (*busRead32)(struct mCore *,uint32_t);
    void (*runFrame)(struct mCore *);
};
struct ExtraResourceFile {
    char id[129];
    uint64_t offset,length;
    uint8_t digest[32];
};
struct ResourceFile {
    const char *path;
    const char *id;
    uint64_t offset,length;
    uint8_t digest[32];
    const char *second_id;
    uint64_t second_offset,second_length;
    uint8_t second_digest[32];
    struct ExtraResourceFile extra[16];
    unsigned extra_count;
    unsigned reads,lookups;
};
static void fail(const char *message)
{
    fprintf(stderr,"%s\n",message);
    abort();
}
static void save_native_frame(struct mCore *core,const char *filename)
{
    (void)core;
    (void)filename;
}
static void XgbaProviderSha256(const uint8_t *input,size_t count,uint8_t digest[32])
{
    (void)input;
    (void)count;
    memset(digest,0,32);
}
#include "../integration/mgba/xgba_r24_boundary.h"

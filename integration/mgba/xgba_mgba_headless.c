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

#define XGBA_MAX_EXTRA_RESOURCES 65535u /* dynamically allocated; source manifest governs actual residency */
struct ExtraResourceFile {
    char id[129];
    uint64_t offset;
    uint64_t length;
    uint8_t digest[32];
};
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
    struct ExtraResourceFile *extra; /* live dynamic host index, not guest EWRAM */
    unsigned extra_count;
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
    for(unsigned i=0;i<f->extra_count;++i)
        if(!strcmp(id,f->extra[i].id)){
            *length=f->extra[i].length;
            memcpy(hash,f->extra[i].digest,32);
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
        unsigned i;
        for(i=0;i<f->extra_count;++i)
            if(!strcmp(id,f->extra[i].id))break;
        if(i==f->extra_count)return 1;
        offset=f->extra[i].offset;
        length=f->extra[i].length;
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
#include "xgba_r17_emerald_map.h"
#include "xgba_r18_emerald_flash.h"
#include "xgba_r19_connected_maps.h"
#include "xgba_r28_three_maps.h"
#include "xgba_r30_four_maps.h"
#include "xgba_r19_mixed_battle.h"
#include "xgba_r24_boundary.h"

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


/* R45 authentic three-original-ROM map data viewer acceptance (not
 * Pokémon's original overworld controller/warps). All displayed pixels
 * come ONLY from host-verified original map tiles and metatile grids
 * already fetched by the running ARM7 game. This captures real mGBA LCD
 * pixels without manipulating or rendering any graphics on the host. */
static void r45_image(struct mCore *core,const char *folder,const char *name)
{
    char path[1024];
    const void *pixels=NULL;
    size_t stride=0;
    if(strlen(folder)+strlen(name)+10>=sizeof(path))
        fail("R45 output filename too long");
    snprintf(path,sizeof(path),"%s/%s.ppm",folder,name);
    core->getPixels(core,&pixels,&stride);
    const int native_video=(pixels!=NULL && stride>=240u);
    /* The authored R44 GBA cartridge uses genuine Mode 3/VRAM (240x160).
     * Some pinned headless mGBA builds do not expose core->getPixels, but
     * its *actual emulated GBA 0x06000000 VRAM* contains identical display
     * pixels. No host graphics renderer or fabricated sprites are used. */
    const unsigned dispcnt=core->busRead16(core,0x04000000u);
    if((dispcnt&7u)!=3u || !(dispcnt&(1u<<10)))
        fail("R45 actual GBA framebuffer is not Mode3 BG2-enabled");
    fprintf(stderr,"R45 real game frame source=%s GBA_DISPCNT=%04x\n",
            native_video?"native_mgba_video":"actual_emulated_GBA_VRAM",
            dispcnt);
    FILE *out=fopen(path,"wb");
    if(!out)fail("R45 original LCD image cannot be opened");
    if(fprintf(out,"P6\n240 160\n255\n")<0)
        fail("R45 original LCD PPM header write failed");
    const mColor *frame=(const mColor *)pixels;
    for(unsigned y=0;y<160u;y++){
        for(unsigned x=0;x<240u;x++){
            uint32_t color=native_video
                ? (uint32_t)frame[y*stride+x]
                : (uint32_t)core->busRead16(core,
                       0x06000000u+2u*(y*240u+x));
            uint8_t rgb[3];
#ifdef COLOR_16_BIT
            rgb[0]=(uint8_t)((color&31u)*255u/31u);
            rgb[1]=(uint8_t)(((color>>5u)&31u)*255u/31u);
            rgb[2]=(uint8_t)(((color>>10u)&31u)*255u/31u);
#else
            if(!native_video){
                rgb[0]=(uint8_t)((color&31u)*255u/31u);
                rgb[1]=(uint8_t)(((color>>5u)&31u)*255u/31u);
                rgb[2]=(uint8_t)(((color>>10u)&31u)*255u/31u);
            }else{
                rgb[0]=(uint8_t)color;
                rgb[1]=(uint8_t)(color>>8u);
                rgb[2]=(uint8_t)(color>>16u);
            }
#endif
            if(fwrite(rgb,1,3,out)!=3)
                fail("R45 genuine LCD pixel data truncated");
        }
    }
    if(fclose(out)!=0)fail("R45 original LCD image flush failed");
}
static void r45_press(struct mCore *core,unsigned button)
{
    core->setKeys(core,button);
    for(unsigned frame=0;frame<5u;frame++)core->runFrame(core);
    core->setKeys(core,0u);
    /* R44 renders all 240x144 Mode3 pixels from externally supplied
     * metatiles in actual ARM7 guest code, not cached GPU textures. This
     * is intentionally slower than a typical game frame: let it finish
     * drawing the full map and UI before issuing the next R/L press. */
    for(unsigned frame=0;frame<600u;frame++)core->runFrame(core);
}
static void r45_check(struct mCore *core,const struct XgbaGbaDevice *device,
                      unsigned selected,unsigned expected_reads)
{
    const uint32_t proof=0x0203F900u;
    const uint32_t state=0x0201A800u;
    const unsigned widths[3]={20u,24u,30u};
    const unsigned heights[3]={20u,25u,39u};
    const unsigned tile_counts[3]={63u,75u,142u};
    unsigned marker=core->busRead32(core,proof);
    unsigned good=core->busRead32(core,proof+4u);
    unsigned recorded=core->busRead32(core,proof+8u);
    unsigned world=core->busRead32(core,proof+16u);
    unsigned width=core->busRead32(core,proof+20u);
    unsigned height=core->busRead32(core,proof+24u);
    unsigned tiles=core->busRead32(core,proof+28u);
    unsigned issues=core->busRead32(core,state+16u);
    fprintf(stderr,"R45 real ROM-derived world=%u map=%ux%u tiles=%u "
                   "source_reads=%u guest_reads=%u issues=%u enabled=%u\n",
            world,width,height,tiles,device->successful_reads,recorded,issues,good);
    if(marker!=0x5234344du||good!=1u||world!=selected||
       width!=widths[selected]||height!=heights[selected]||
       tiles!=tile_counts[selected]||recorded!=expected_reads||
       device->successful_reads!=expected_reads||
       device->failed_reads!=0u||device->provider_bad_sha256!=0u||
       issues!=0u)
        fail("R45 genuine original three-ROM map source or guest graphics mismatch");
}
static void r45_3world_maps(struct mCore *core,
                            const struct XgbaGbaDevice *device,const char *folder)
{
    r45_check(core,device,0u,3u);
    r45_image(core,folder,"00-emerald-littleroot-original-map");
    r45_press(core,1u<<8); /* actual R -> original Team Rocket map assets */
    r45_check(core,device,1u,7u);
    r45_image(core,folder,"01-rocket-littleroot-original-map");
    r45_press(core,1u<<8); /* actual R -> original HnS New Bark assets */
    r45_check(core,device,2u,13u);
    r45_image(core,folder,"02-hns-new-bark-original-map");
    unsigned before=core->busRead32(core,0x0203F920u);
    r45_press(core,1u<<4); /* actual right D-pad, move viewport 1 metatile */
    unsigned after=core->busRead32(core,0x0203F920u);
    if(after!=before+16u || device->successful_reads!=13u)
        fail("R45 genuine GBA D-pad scrolling did not move imported source map");
    r45_image(core,folder,"03-hns-dpad-pan");
    r45_press(core,1u<<0); /* A toggles original map collision/attribute overlay */
    if(core->busRead32(core,0x0203F928u)!=2u||
       device->successful_reads!=13u)
        fail("R45 actual game A-button attribute display did not change");
    r45_image(core,folder,"04-hns-map-attributes-overlay");
    r45_press(core,1u<<9); /* L -> Rocket source, re-fetch from sidecar */
    r45_check(core,device,1u,17u);
    r45_image(core,folder,"05-return-to-rocket-reacquired");
    puts("PASS_R45_GENUINE_3_ORIGINAL_ROM_MAP_ASSETS_IN_LIVE_GBA "
         "emulator=patched_mgba worlds=3 verified_reads=17 sha_rejects=0 "
         "real_controller_map_switches=3 scroll=1 overlay=1 real_LCD_frames=6");
}


/* R86 owner-private actual controller/LCD acceptance.
 * All button events pass through the real mGBA GBA core; source map state is
 * READ ONLY in EWRAM. A screenshot is taken on each original loaded source
 * room, including the return. The test cannot be marked pass by static host
 * graph closure or by writing any fake guest RAM.
 *
 * Private script lines: <frames:decimal> <gba-key-mask:hex> <snapshot:0|1>
 * Key bits 0=A,1=B,2=SELECT,3=START,4=RIGHT,5=LEFT,6=UP,7=DOWN,
 *          8=R,9=L; 0 means release all buttons.
 */
static void xgba_r86_run_real_rocket_door(
    struct mCore *core, struct XgbaGbaDevice *device,
    const char *script_file,const char *lcd_dir,uint32_t proof_addr)
{
    char line[192],frame_name[1024];
    FILE *fp;
    uint32_t arrivals,observed,source_to;
    uint32_t saw_room=0u,saw_return=0u;
    unsigned line_number=0u,actions=0u,captures=0u,total_frames=0u;
    if(!core || !device || !script_file || !lcd_dir ||
       proof_addr<0x02000000u || proof_addr>0x0203ffe8u ||
       (proof_addr&3u) || device->failed_reads)
        fail("R86 requires real Emerald EWRAM proof and clean original-source provider");
    arrivals=core->busRead32(core,proof_addr+4u);
    if(arrivals || core->busRead32(core,proof_addr))
        fail("R86 source room input test must begin BEFORE any source-room transition");
    fp=fopen(script_file,"r");
    if(!fp)fail("R86 private controller input file cannot be opened");
    while(fgets(line,sizeof(line),fp)) {
        unsigned frames=0u,mask=0u,snapshot=0u;
        char trailing=0;
        ++line_number;
        if(line[0]=='#' || line[0]=='\n' || line[0]=='\r')continue;
        if(++actions>256u ||
           sscanf(line,"%u %x %u %c",&frames,&mask,&snapshot,&trailing)!=3 ||
           frames<1u || frames>2400u || mask>0x3ffu ||
           snapshot>1u || total_frames>36000u-frames){
            fclose(fp);
            fail("R86 private controller script unsafe/malformed input");
        }
        total_frames+=frames;
        core->setKeys(core,mask);
        for(unsigned i=0u;i<frames;i++){
            core->runFrame(core);
            observed=core->busRead32(core,proof_addr+4u);
            if(observed< arrivals || observed>arrivals+1u){
                fclose(fp);
                fail("R86 inconsistent original native room-arrival counter");
            }
            if(observed!=arrivals){
                arrivals=observed;
                source_to=core->busRead32(core,proof_addr+16u);
                if(source_to==0x00012304u && !saw_room && !saw_return)
                    saw_room=1u;
                else if(source_to==0x00010009u && saw_room && !saw_return)
                    saw_return=1u;
                else {
                    fclose(fp);
                    fail("R86 unsupported/wrong order original source-world loaded map");
                }
                if(snprintf(frame_name,sizeof(frame_name),
                       "%s/r86-native-arrival-%02u-source-%06x.png",
                       lcd_dir,arrivals,source_to)>= (int)sizeof(frame_name)){
                    fclose(fp);fail("R86 LCD capture path too long");
                }
                save_native_frame(core,frame_name);
                ++captures;
            }
        }
        if(snapshot){
            if(captures>=64u || snprintf(frame_name,sizeof(frame_name),
                "%s/r86-controller-%03u.png",lcd_dir,line_number)
                >=(int)sizeof(frame_name)){
                fclose(fp);fail("R86 controller LCD path/capture limit invalid");
            }
            save_native_frame(core,frame_name);
            ++captures;
        }
    }
    fclose(fp);
    core->setKeys(core,0u);
    if(!saw_room || !saw_return || arrivals!=2u ||
       core->busRead32(core,proof_addr)<2u ||
       core->busRead32(core,proof_addr+8u)!=0u ||
       core->busRead32(core,proof_addr+12u)!=0u ||
       core->busRead32(core,proof_addr+16u)!=0x00010009u ||
       core->busRead32(core,proof_addr+20u)!=0x0009u ||
       device->failed_reads){
        fail("R86 genuine Emerald original Rocket 0:9 -> 35:4 -> 0:9 playthrough NOT accepted");
    }
    printf("PASS_R86_ORIGINAL_ROCKET_DOOR_ROUNDTRIP_NATIVE_GBA "
           "real_player_doors=%u original_loaded_rooms=%u "
           "source_witnesses=0x012304,0x010009 lcd_frames=%u "
           "gba_controller_actions=%u frames=%u original_source_fetches=%u\n",
           core->busRead32(core,proof_addr),arrivals,captures,actions,
           total_frames,device->successful_reads);
}

int main(int argc, char **argv)
{
    if (argc < 11 || argc > (int)(11u + 4u*XGBA_MAX_EXTRA_RESOURCES + 128u))
        fail("usage: ROM DATA SOURCE_ID SOURCE_SHA RESOURCE_ID OFFSET LENGTH RESOURCE_SHA FRAMES PROBE_ADDR [--screenshot path] [--scene-dir path] [--r10-dir path] [--r11-perf path] [--r12-dir path] [--r13-dir path] [--r14-dir path] [--second-resource ID OFFSET LENGTH SHA] [--disabled]");
    const char *screenshot = NULL;
    const char *r43_probe = NULL; /* R43 original authored GBA homebrew CPU proof */
    const char *r45_probe = NULL; /* REAL original Emerald/TRE/HnS ROM-derived map test */
    const char *r86_dir = NULL; /* owner-private actual Rocket door LCD */
    const char *r86_script = NULL; /* physical GBA controller input, not memory edits */
    uint64_t r86_proof = 0u;
    const char *scene_dir = NULL;
    const char *r10_dir = NULL;
    const char *r11_perf = NULL;
    const char *r12_dir = NULL;
    const char *r13_dir = NULL;
    const char *r14_dir = NULL;
    const char *r15_dir = NULL;
    const char *r16_dir = NULL;
    const char *r24_dir = NULL;
    uint64_t r24_probe = 0;
    int r24_firered = 0;
    const char *r17_dir = NULL;
    const char *r18_dir = NULL;
    const char *r19_dir = NULL;
    const char *r28_dir = NULL;
    const char *r30_dir = NULL;
    uint64_t r30_route102_offset = 0, r30_route102_length = 0;
    uint64_t r28_oldale_offset = 0;
    uint64_t r28_oldale_length = 0;
    const char *r19_battle_dir = NULL;
    uint64_t r19_battle_probe = 0;
    uint64_t r21_heap_probe = 0;
    uint64_t r22_round_trips = 0;
    uint64_t r23_battles = 0;
    int r20_reentry = 0;
    uint64_t r19_battle0_offset = 0, r19_battle0_length = 0;
    uint64_t r19_battle1_offset = 0, r19_battle1_length = 0;
    uint64_t r19_route_offset = 0;
    uint64_t r19_route_length = 0;
    const char *r18_savefile = NULL;
    const char *r18_phase = NULL;
    uint64_t r18_save_probe = 0;
    const char *r15_savefile = NULL;
    const char *r15_phase = NULL;
    uint64_t r15_save_probe = 0;
    const char *second_id = NULL;
    uint64_t second_offset = 0, second_length = 0;
    uint8_t second_sha[32] = {0};
    struct ExtraResourceFile *extras=NULL;
    size_t extra_capacity=0u;
    unsigned extra_count=0;
    int enabled = 1;
    for (int i=11; i<argc; ++i) {
        if (!strcmp(argv[i], "--disabled"))
            enabled = 0;
        else if (!strcmp(argv[i], "--screenshot") && ++i < argc && !screenshot)
            screenshot = argv[i];
        else if (!strcmp(argv[i], "--r43-probe") && ++i < argc && !r43_probe)
            r43_probe = argv[i];
        else if (!strcmp(argv[i], "--r45-probe") && ++i < argc && !r45_probe)
            r45_probe = argv[i];
        else if (!strcmp(argv[i], "--r86-input-dir") && ++i < argc && !r86_dir)
            r86_dir = argv[i];
        else if (!strcmp(argv[i], "--r86-input-script") && ++i < argc && !r86_script)
            r86_script = argv[i];
        else if (!strcmp(argv[i], "--r86-proof") && ++i < argc && !r86_proof)
            r86_proof = parse_number(argv[i]);
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
        else if (!strcmp(argv[i], "--r24-firered"))
            r24_firered = 1;
        else if (!strcmp(argv[i], "--r24-boundary-dir") && ++i < argc && !r24_dir)
            r24_dir = argv[i];
        else if (!strcmp(argv[i], "--r24-boundary-probe") && ++i < argc && !r24_probe)
            r24_probe = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r16-emerald-dir") && ++i < argc && !r16_dir)
            r16_dir = argv[i];
        else if (!strcmp(argv[i], "--r17-emerald-map-dir") && ++i < argc && !r17_dir)
            r17_dir = argv[i];
        else if (!strcmp(argv[i], "--r18-dir") && ++i < argc && !r18_dir)
            r18_dir = argv[i];
        else if (!strcmp(argv[i], "--r19-connected-dir") && ++i < argc && !r19_dir)
            r19_dir = argv[i];
        else if (!strcmp(argv[i], "--r28-three-map-dir") && ++i < argc && !r28_dir)
            r28_dir = argv[i];
        else if (!strcmp(argv[i], "--r30-four-map-dir") && ++i < argc && !r30_dir)
            r30_dir = argv[i];
        else if (!strcmp(argv[i], "--r30-route102-offset") && ++i < argc && !r30_route102_offset)
            r30_route102_offset = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r30-route102-length") && ++i < argc && !r30_route102_length)
            r30_route102_length = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r28-oldale-offset") && ++i < argc && !r28_oldale_offset)
            r28_oldale_offset = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r28-oldale-length") && ++i < argc && !r28_oldale_length)
            r28_oldale_length = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-battle-dir") && ++i < argc && !r19_battle_dir)
            r19_battle_dir = argv[i];
        else if (!strcmp(argv[i], "--r23-battles") && ++i < argc && !r23_battles)
            r23_battles=parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r22-round-trips") && ++i < argc && !r22_round_trips)
            r22_round_trips=parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r21-heap-probe") && ++i < argc && !r21_heap_probe)
            r21_heap_probe=parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r20-reentry"))
            r20_reentry = 1;
        else if (!strcmp(argv[i], "--r19-battle-probe") && ++i < argc && !r19_battle_probe)
            r19_battle_probe = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-battle0-offset") && ++i < argc && !r19_battle0_offset)
            r19_battle0_offset = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-battle0-length") && ++i < argc && !r19_battle0_length)
            r19_battle0_length = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-battle1-offset") && ++i < argc && !r19_battle1_offset)
            r19_battle1_offset = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-battle1-length") && ++i < argc && !r19_battle1_length)
            r19_battle1_length = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-route-offset") && ++i < argc && !r19_route_offset)
            r19_route_offset = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r19-route-length") && ++i < argc && !r19_route_length)
            r19_route_length = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r18-savefile") && ++i < argc && !r18_savefile)
            r18_savefile = argv[i];
        else if (!strcmp(argv[i], "--r18-phase") && ++i < argc && !r18_phase)
            r18_phase = argv[i];
        else if (!strcmp(argv[i], "--r18-save-probe") && ++i < argc && !r18_save_probe)
            r18_save_probe = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--r15-savefile") && ++i < argc && !r15_savefile)
            r15_savefile = argv[i];
        else if (!strcmp(argv[i], "--r15-phase") && ++i < argc && !r15_phase)
            r15_phase = argv[i];
        else if (!strcmp(argv[i], "--r15-save-probe") && ++i < argc && !r15_save_probe)
            r15_save_probe = parse_number(argv[i]);
        else if (!strcmp(argv[i], "--extra-resource") && i+4 < argc) {
            if(extra_count>=XGBA_MAX_EXTRA_RESOURCES)
                fail("XGBA original resource manifest exceeds 65535 entries");
            if((size_t)extra_count==extra_capacity) {
                size_t grown=extra_capacity?extra_capacity*2u:32u;
                if(grown>XGBA_MAX_EXTRA_RESOURCES)grown=XGBA_MAX_EXTRA_RESOURCES;
                if(grown<extra_capacity || grown>SIZE_MAX/sizeof(*extras))
                    fail("XGBA extra resource registry multiplication overflow");
                void *updated=realloc(extras,grown*sizeof(*extras));
                if(!updated)fail("XGBA extra resource index allocation failed");
                extras=updated;
                extra_capacity=grown;
            }
            struct ExtraResourceFile *extra=&extras[extra_count++];
            const char *id=argv[++i];
            if(!*id || strlen(id)>128)
                fail("extra resource identifier invalid");
            strcpy(extra->id,id);
            extra->offset=parse_number(argv[++i]);
            extra->length=parse_number(argv[++i]);
            parse_sha(argv[++i],extra->digest);
        }
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
    for(unsigned i=0;i<extra_count;++i) {
        const struct ExtraResourceFile *e=&extras[i];
        if(e->offset<=32u*1024u*1024u || e->offset>INT64_MAX ||
           !e->length || e->length>XGBA_R7_MAX_GUEST_BYTES ||
           e->offset>UINT64_MAX-e->length ||
           !strcmp(e->id,argv[5]) || (second_id && !strcmp(e->id,second_id)))
            fail("extra resource outside bounded manifest or ID duplicates existing resources");
        for(unsigned j=0;j<i;++j)
            if(!strcmp(e->id,extras[j].id))
                fail("duplicate external resource identifiers");
    }
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
    resource.extra_count=extra_count;
    resource.extra=extras;
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
    mColor *video = (r86_dir || screenshot || r43_probe || scene_dir || r10_dir || r11_perf || r12_dir || r13_dir || r14_dir || r15_dir || r16_dir || r24_dir || r17_dir || r18_dir || r19_dir || r19_battle_dir || r28_dir || r30_dir)
                   ? calloc(240u*160u, sizeof(mColor)) : NULL;
    if ((r86_dir || screenshot || r43_probe || scene_dir || r10_dir || r11_perf || r12_dir || r13_dir || r14_dir || r15_dir || r16_dir || r24_dir || r17_dir || r18_dir || r19_dir || r19_battle_dir || r28_dir || r30_dir) && !video)
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
    if (r18_dir) {
        if (!r18_phase || !r18_savefile || !r18_save_probe ||
            r18_save_probe > UINT32_MAX)
            fail("R18 requires a genuine Emerald Flash .sav, phase and actual guest ELF proof");
        if (!mCoreLoadSaveFile(core,r18_savefile,false))
            fail("R18 could not attach durable native mGBA Flash save file");
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
        if ((r17_dir || r18_dir) && probe &&
            core->busRead32(core,(uint32_t)probe+4)==0xE17u)
            break;
        if ((r19_dir || r28_dir || r30_dir) && probe &&
            core->busRead32(core,(uint32_t)probe+4)==0xE19u)
            break;
    }
    if(r86_dir){
        if(!r86_script || r86_proof<0x02000000u ||
           r86_proof>0x0203ffe8u || (r86_proof&3u) ||
           !enabled || !resource.extra_count ||
           r15_dir || r18_dir || r19_dir || r19_battle_dir ||
           r24_dir || r45_probe || r43_probe || scene_dir ||
           r17_dir || r16_dir)
            fail("R86 original Rocket actual controller proof requires exclusive private mode");
    }
    if (r24_firered && !r24_dir)
        fail("R24 FireRed mode needs genuine original game boundary proof");
    if (r24_dir && (!r24_probe || r24_probe>UINT32_MAX ||
         r16_dir || r17_dir || r19_dir || r19_battle_dir))
        fail("R24 requires bounded original Emerald ELF proof and exclusive mode");
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
    } else if (r24_dir) {
        xgba_r24_boundary_run(core,r24_firered?0u:(uint32_t)probe,(uint32_t)r24_probe,
                              r24_dir,&device,&resource,enabled);
    } else if (r16_dir) {
        xgba_r16_emerald_run(core,(uint32_t)probe,r16_dir,&device,&resource,enabled);
    } else if (r17_dir) {
        xgba_r17_emerald_run(core,(uint32_t)probe,r17_dir,&device,&resource,enabled);
    } else if (r18_dir) {
        xgba_r18_emerald_run(core,(uint32_t)probe,(uint32_t)r18_save_probe,
                            r18_dir,r18_phase,&device,&resource,enabled);
    } else if (r30_dir) {
        if(!r19_route_offset || !r19_route_length || r19_route_length>8192u ||
           !r28_oldale_offset || !r28_oldale_length || r28_oldale_length>8192u ||
           !r30_route102_offset || !r30_route102_length || r30_route102_length>8192u ||
           r28_dir || r19_dir || r19_battle_dir || r17_dir || r18_dir || r24_dir)
            fail("R30 source-built original Emerald four-map fixture invalid");
        uint64_t off[4]={resource.offset,r19_route_offset,r28_oldale_offset,r30_route102_offset};
        uint32_t len[4]={(uint32_t)resource.length,(uint32_t)r19_route_length,
                         (uint32_t)r28_oldale_length,(uint32_t)r30_route102_length};
        xgba_r30_four_map_run(core,(uint32_t)probe,r30_dir,&device,
                               &resource,off,len,enabled);
    } else if (r28_dir) {
        if(!r19_route_offset || !r19_route_length ||
           r19_route_length>16384u ||
           !r28_oldale_offset || !r28_oldale_length ||
           r28_oldale_length>16384u || r19_battle_dir ||
           r19_dir || r17_dir || r18_dir || r24_dir)
            fail("R28 original Emerald three-map fixture invalid");
        xgba_r28_three_map_run(core,(uint32_t)probe,r28_dir,
                               &device,&resource,
                               r19_route_offset,(uint32_t)r19_route_length,
                               r28_oldale_offset,(uint32_t)r28_oldale_length,
                               enabled);
    } else if (r19_dir) {
        if(!r19_route_offset || !r19_route_length || r19_route_length>16384u)
            fail("R19 requires a bounded and exact original Emerald Route101 source span");
        if(r22_round_trips>64u)
            fail("R22 native bounded map-churn request exceeds 64 round trips");
        xgba_r19_connected_run(core,(uint32_t)probe,r19_dir,
                               &device,&resource,r19_route_offset,
                               (uint32_t)r19_route_length,enabled,
                               (unsigned)r22_round_trips);
    } else if (r19_battle_dir) {
        if(!r19_route_offset || !r19_route_length || r19_route_length>16384u ||
           r19_battle_probe<0x02000000u || r19_battle_probe>=0x02040000u ||
           !r19_battle0_offset || !r19_battle0_length ||
           !r19_battle1_offset || !r19_battle1_length ||
           r19_battle0_length>8192u || r19_battle1_length>8192u)
            fail("R19 requires two bounded external sprites and an original Emerald ELF battle proof");
        if (r21_heap_probe &&
            (!r20_reentry || r21_heap_probe<0x02000000u ||
             r21_heap_probe+17u*4u>0x02040000u))
            fail("R21 needs bounded original malloc proof and R20 two-battle context");
        if(r23_battles && (r23_battles!=4u || !r20_reentry ||
            !r21_heap_probe || !r19_battle_dir))
            fail("R23 requires exactly four original battles and original allocator proof");
        xgba_r19_mixed_battle_run(core,(uint32_t)probe,(uint32_t)r19_battle_probe,
                  r19_battle_dir,&device,&resource,
                  r19_route_offset,(uint32_t)r19_route_length,
                  r19_battle0_offset,(uint32_t)r19_battle0_length,
                  r19_battle1_offset,(uint32_t)r19_battle1_length,enabled,r20_reentry,
                  (uint32_t)r21_heap_probe,(unsigned)r23_battles);
    } else if (!scene_dir && !r43_probe && !r45_probe && !r86_dir) {
        verify_game_copy(core, (uint32_t)probe, &device, &resource, enabled);
    }
    if (scene_dir)
        run_r9_movement_scene(core, (uint32_t)probe, scene_dir, &device, enabled);
    if (r86_dir)
        xgba_r86_run_real_rocket_door(core,&device,r86_script,
                                     r86_dir,(uint32_t)r86_proof);
    if (r45_probe) {
        if(!enabled || !resource.extra_count || r43_probe || scene_dir)
            fail("R45 requires patched mGBA, external resource IDs and one dedicated fixture");
        r45_3world_maps(core,&device,r45_probe);
    }
    if (r43_probe) {
        /* R43 is a purpose-built, fully authored ARM7 CPU cartridge, not the
         * R7 FireRed sprite fixture. Verify the guest CPU itself wrote the
         * live proof in its EWRAM before reporting an external resource read. */
        unsigned magic=core->busRead32(core,0x0203F900u);
        unsigned status=core->busRead32(core,0x0203F904u);
        fprintf(stderr,"R43 homebrew diag: magic=%08x status=%u provider_reads=%u rejected=%u\n",
                magic,status,device.successful_reads,device.failed_reads);
        if(magic!=0x58474241u || status!=1u ||
           device.successful_reads!=1u || device.failed_reads!=0u)
            fail("R43 original ARM7 test cartridge did not fetch external bytes at >32MiB");
        const void *pixels=NULL;
        size_t stride=0;
        core->getPixels(core,&pixels,&stride);
        if(!pixels||stride<240u)
            fail("R43 original GBA video framebuffer was not produced");
        /* Native mGBA's generic screenshot encoder refuses this tiny
         * freestanding homebrew in some CI configurations, despite exposing
         * the real 240x160 game LCD. Capture raw RGB PPM from the actual
         * native pixel buffer; CI converts to PNG only after verifying bytes.
         * No host-rendered or invented game graphics. */
        FILE *image=fopen(r43_probe,"wb");
        if(!image)fail("R43 cannot open original mGBA framebuffer proof");
        if(fprintf(image,"P6\n240 160\n255\n")<0)fail("R43 cannot write screenshot PPM header");
        const mColor *frame=(const mColor *)pixels;
        for(unsigned y=0;y<160u;y++) {
            for(unsigned x=0;x<240u;x++) {
                uint32_t color=(uint32_t)frame[y*stride+x];
                uint8_t rgb[3];
#ifdef COLOR_16_BIT
                rgb[0]=(uint8_t)((color&31u)*255u/31u);
                rgb[1]=(uint8_t)(((color>>5u)&31u)*255u/31u);
                rgb[2]=(uint8_t)(((color>>10u)&31u)*255u/31u);
#else
                rgb[0]=(uint8_t)color;
                rgb[1]=(uint8_t)(color>>8u);
                rgb[2]=(uint8_t)(color>>16u);
#endif
                if(fwrite(rgb,1,3,image)!=3)fail("R43 original LCD framebuffer PPM payload truncated");
            }
        }
        if(fclose(image)!=0)fail("R43 cannot flush original game LCD evidence");

        /* Real L/R/A controller acceptance on the homebrew cartridge:
         * R steps Emerald -> Rocket -> Johto, each requiring a DISTINCT
         * source-id lookup, new SHA-verified >32MiB fetch, and actual guest
         * world-state change. A updates a third guest-side event counter.
         * This is a storage/input demonstration, NOT a claim that the
         * third-party source games' original event scripts execute. */
        for(unsigned target=1u;target<=2u;target++) {
            core->setKeys(core,1u<<8); /* GBA physical R */
            for(unsigned k=0;k<5u;k++)core->runFrame(core);
            core->setKeys(core,0u);
            for(unsigned k=0;k<25u;k++)core->runFrame(core);
            unsigned guest_world=core->busRead32(core,0x0203F910u);
            unsigned guest_count=core->busRead32(core,0x0203F908u);
            unsigned guest_status=core->busRead32(core,0x0203F904u);
            fprintf(stderr,"R43 actual R input source=%u reads=%u game_count=%u status=%u rejected=%u\n",
                    guest_world,device.successful_reads,guest_count,guest_status,device.failed_reads);
            if(guest_world!=target || device.successful_reads!=target+1u ||
               guest_count!=target+1u || guest_status!=1u || device.failed_reads!=0u)
                fail("R43 genuine GBA controller failed to switch verified source in guest game");
        }
        core->setKeys(core,1u<<0); /* native A guest event action */
        for(unsigned k=0;k<5u;k++)core->runFrame(core);
        core->setKeys(core,0u);
        for(unsigned k=0;k<25u;k++)core->runFrame(core);
        if(core->busRead32(core,0x0203F90Cu)!=1u ||
           device.successful_reads!=4u || device.failed_reads!=0u)
            fail("R43 real GBA A event counter or source refetch incorrect");
        puts("PASS_R43_NATIVE_CONTROLLER_3_EXTERNAL_SOURCE_SWITCHES_AND_GAME_EVENT count=4");
        puts("PASS_R43_GENUINE_ARM7_EXTERNAL_SOURCE_MMIO_AND_LCD source=sidecar original_game_cpu=1");
    }
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
    free(extras);
    return 0;
}

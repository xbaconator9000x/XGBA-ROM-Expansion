/*
 * XGBA R11: executed native mGBA + real FireRed Pallet Town frame profiler.
 * Include in xgba_mgba_headless.c after ResourceFile, save_native_frame and
 * fail() declarations. This measures actual host wall time spent in
 * core->runFrame(), never GIF frame durations or a simulated frame loop.
 *
 * This is an UNTHROTTLED Linux CI native-core throughput test: the results
 * are not a claim about the user's monitor/vsync/audio pacing or Android FPS.
 */
#ifndef XGBA_R11_BENCHMARK_H
#define XGBA_R11_BENCHMARK_H

#include <time.h>

#define XGBA_R11_WARMUP_FRAMES 120u
#define XGBA_R11_BEFORE_FRAMES 360u
#define XGBA_R11_SELECT_FRAMES 3u
#define XGBA_R11_AFTER_FRAMES 360u
#define XGBA_R11_TARGET_FRAME_MS (1000.0 / 59.727500569606)

struct XgbaR11Stats {
    double mean_ms;
    double median_ms;
    double p95_ms;
    double worst_ms;
    double effective_unthrottled_fps;
    unsigned over_budget;
};

static double xgba_r11_now_ms(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts))
        fail("R11 monotonic clock unavailable");
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1000000.0;
}

static int xgba_r11_compare_double(const void *a, const void *b)
{
    const double left = *(const double *)a, right = *(const double *)b;
    return (left > right) - (left < right);
}

static struct XgbaR11Stats xgba_r11_stats(const double *samples, unsigned n)
{
    if (!n || n > XGBA_R11_BEFORE_FRAMES)
        fail("R11 invalid benchmark sample size");
    double sorted[XGBA_R11_BEFORE_FRAMES];
    double sum = 0;
    unsigned over_budget = 0;
    for (unsigned i = 0; i < n; ++i) {
        if (samples[i] <= 0 || samples[i] > 2000.0)
            fail("R11 impossible native core frame time");
        sorted[i] = samples[i];
        sum += samples[i];
        if (samples[i] > XGBA_R11_TARGET_FRAME_MS)
            ++over_budget;
    }
    qsort(sorted, n, sizeof(double), xgba_r11_compare_double);
    const double avg = sum / n;
    struct XgbaR11Stats out = {
        .mean_ms = avg,
        .median_ms = (sorted[(n - 1)/2] + sorted[n/2]) / 2.0,
        .p95_ms = sorted[(unsigned)((double)(n-1) * 0.95)],
        .worst_ms = sorted[n-1],
        .effective_unthrottled_fps = 1000.0 / avg,
        .over_budget = over_budget
    };
    return out;
}

static void xgba_r11_stat_json(FILE *out, struct XgbaR11Stats s)
{
    fprintf(out,
            "{\"mean_ms\":%.6f,\"median_ms\":%.6f,\"p95_ms\":%.6f,"
            "\"worst_ms\":%.6f,\"unthrottled_fps\":%.3f,"
            "\"frames_over_16_74ms\":%u}",
            s.mean_ms, s.median_ms, s.p95_ms, s.worst_ms,
            s.effective_unthrottled_fps, s.over_budget);
}

static void xgba_r11_run(struct mCore *core,
                         uint32_t probe, const char *output,
                         const struct XgbaGbaDevice *device,
                         const struct ResourceFile *resource,
                         int enabled)
{
    if (!probe || !output)
        fail("R11 real Pallet Town core/probe/JSON output required");
    if (core->busRead32(core,probe) != XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core,probe + 4) != 3u ||
        core->busRead32(core,probe + 36) != 3u ||
        core->busRead32(core,probe + 40) != 0u)
        fail("R11 requires ACTUAL MAP_PALLET_TOWN game engine ready");
    if (!!device->successful_reads != !!enabled)
        fail("R11 initial resource state does not match extension status");

    core->setKeys(core, 0u);
    for (unsigned i = 0; i < XGBA_R11_WARMUP_FRAMES; ++i)
        core->runFrame(core);

    double before[XGBA_R11_BEFORE_FRAMES];
    double after[XGBA_R11_AFTER_FRAMES];
    double select[XGBA_R11_SELECT_FRAMES];
    double select_start_ms = 0;
    double swap_complete_ms = 0;
    unsigned select_frames_to_swap = 0;
    const unsigned total = XGBA_R11_BEFORE_FRAMES
                         + XGBA_R11_SELECT_FRAMES
                         + XGBA_R11_AFTER_FRAMES;
    const uint32_t start_ticks = core->busRead32(core,probe + 32);

    for (unsigned i = 0; i < total; ++i) {
        const int pressing = i >= XGBA_R11_BEFORE_FRAMES &&
                i < XGBA_R11_BEFORE_FRAMES + XGBA_R11_SELECT_FRAMES;
        core->setKeys(core, pressing ? 1u << 2 : 0u);
        const double start = xgba_r11_now_ms();
        if (i == XGBA_R11_BEFORE_FRAMES)
            select_start_ms = start;
        core->runFrame(core);
        const double end = xgba_r11_now_ms();
        const double elapsed = end - start;

        if (i < XGBA_R11_BEFORE_FRAMES) {
            before[i] = elapsed;
        } else if (i < XGBA_R11_BEFORE_FRAMES + XGBA_R11_SELECT_FRAMES) {
            select[i - XGBA_R11_BEFORE_FRAMES] = elapsed;
        } else {
            after[i - XGBA_R11_BEFORE_FRAMES - XGBA_R11_SELECT_FRAMES] = elapsed;
        }

        /* This comes from actual FireRed game memory, NOT a host marker. */
        if (enabled && !swap_complete_ms &&
            core->busRead32(core,probe + 24) == 1u) {
            swap_complete_ms = end;
            select_frames_to_swap = i - XGBA_R11_BEFORE_FRAMES + 1u;
        }
    }
    core->setKeys(core, 0u);
    const uint32_t end_ticks = core->busRead32(core,probe + 32);
    if (end_ticks <= start_ticks || end_ticks - start_ticks < total - 4u ||
        core->busRead32(core,probe + 36) != 3u ||
        core->busRead32(core,probe + 40) != 0u)
        fail("R11 overworld callbacks stopped or game left Pallet Town");
    const unsigned actual_switches = core->busRead32(core,probe + 24);
    if (enabled) {
        if (actual_switches != 1u || select_frames_to_swap < 1u ||
            select_frames_to_swap > XGBA_R11_SELECT_FRAMES ||
            device->successful_reads != 2u || device->failed_reads ||
            resource->lookups != 2u || resource->reads != 2u)
            fail("R11 game did not actually load second external pack");
    } else {
        if (actual_switches || select_frames_to_swap ||
            device->successful_reads || device->failed_reads ||
            resource->lookups || resource->reads)
            fail("R11 disabled baseline attempted external access");
    }

    const struct XgbaR11Stats pre = xgba_r11_stats(
        before, XGBA_R11_BEFORE_FRAMES);
    const struct XgbaR11Stats post = xgba_r11_stats(
        after, XGBA_R11_AFTER_FRAMES);
    const struct XgbaR11Stats during = xgba_r11_stats(
        select, XGBA_R11_SELECT_FRAMES);
    FILE *json = fopen(output, "wb");
    if (!json)
        fail("R11 cannot write profiler JSON");
    fprintf(json, "{\n  \"schema\": 1,\n  \"mode\": \"%s\",\n"
                  "  \"map\": \"Pallet Town\",\n"
                  "  \"game_map_group\": 3,\n  \"game_map_num\": 0,\n"
                  "  \"nominal_gba_hz\": 59.727500569606,\n"
                  "  \"host_clock\": \"CLOCK_MONOTONIC\",\n"
                  "  \"emulation_mode\": \"unthrottled native mGBA core, no PNG or GIF writing during measurements\",\n"
                  "  \"warmup_frames\": %u,\n"
                  "  \"steady_frames_before\": %u,\n"
                  "  \"steady_frames_after\": %u,\n"
                  "  \"select_frames\": %u,\n"
                  "  \"game_overworld_ticks\": %u,\n"
                  "  \"external_reads\": %u,\n"
                  "  \"provider_lookups\": %u,\n"
                  "  \"selected_pack_after\": %u,\n"
                  "  \"select_frames_until_external_ready\": %u,\n"
                  "  \"select_to_ready_wall_ms\": %.6f,\n"
                  "  \"select_first_frame_ms\": %.6f,\n"
                  "  \"before\": ",
            enabled ? "enabled" : "disabled",
            XGBA_R11_WARMUP_FRAMES, XGBA_R11_BEFORE_FRAMES,
            XGBA_R11_AFTER_FRAMES, XGBA_R11_SELECT_FRAMES,
            end_ticks-start_ticks,device->successful_reads,resource->lookups,
            core->busRead32(core,probe+28),select_frames_to_swap,
            enabled ? swap_complete_ms-select_start_ms : 0.0,
            select[0]);
    xgba_r11_stat_json(json,pre);
    fputs(",\n  \"select\": ",json);
    xgba_r11_stat_json(json,during);
    fputs(",\n  \"after\": ",json);
    xgba_r11_stat_json(json,post);
    fputs("\n}\n",json);
    if (fclose(json))
        fail("R11 failed to flush benchmark report");

    printf("PASS_R11_PALLET_NATIVE_PERF mode=%s before_fps=%.2f after_fps=%.2f "
           "before_p95_ms=%.4f after_p95_ms=%.4f "
           "select_frame_ms=%.4f swap_latency_ms=%.4f "
           "swap_frames=%u guest_ticks=%u\n",
           enabled ? "enabled" : "disabled",
           pre.effective_unthrottled_fps,post.effective_unthrottled_fps,
           pre.p95_ms,post.p95_ms,select[0],
           enabled ? swap_complete_ms-select_start_ms : 0.0,
           select_frames_to_swap,end_ticks-start_ticks);
}
#endif

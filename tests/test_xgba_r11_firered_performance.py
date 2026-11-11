"""R11 real FireRed Pallet Town XGBA-enabled vs disabled performance benchmark.

Uses exactly the R10 native FireRed and patched mGBA successful fixture:
- same ARM/Thumb FireRed ROM and same sidecar both modes
- same original FireRed MAP_PALLET_TOWN callbacks and LCD render target
- 120 untimed warmup frames, 360 timed pre-Select, 3 Select input frames,
  360 timed post-Select frames per repeated native emulator process
- native CLOCK_MONOTONIC wall time around each real mCore.runFrame call
- no screenshot, PNG compression, GIF encoding or artificial frame pacing
- SELECT event in enabled mode really reads Magma as second external asset
- disabled mode must issue zero external provider lookups/reads
- 3 alternating repetitions each mode to reduce runner timing noise.

Unthrottled host throughput is NOT user-observed on-screen FPS; an installed
GUI, audio, vsync, OS throttling and physical device need separate testing.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"tools"), str(ROOT/"tests"), str(ROOT/"integration/mgba")]
import test_xgba_r10_pallet_town_live_swap as r10
import xgba_mgba_run as launcher
import xgba_resource_sidecar as sidecar

RUN_ORDER = ["disabled","enabled","enabled","disabled","disabled","enabled"]
NOMINAL_FRAME_MS = 1000.0 / 59.727500569606


def aggregate(values: list[dict]) -> dict:
    return {
        "repetitions":len(values),
        "median_unthrottled_fps":round(statistics.median(
            d["unthrottled_fps"] for d in values), 3),
        "median_mean_ms":round(statistics.median(
            d["mean_ms"] for d in values), 6),
        "median_frame_p50_ms":round(statistics.median(
            d["median_ms"] for d in values), 6),
        "median_frame_p95_ms":round(statistics.median(
            d["p95_ms"] for d in values), 6),
        "worst_frame_ms":round(max(d["worst_ms"] for d in values), 6),
        "frames_above_16_74ms_total":sum(d["frames_over_16_74ms"] for d in values),
    }


class R11NativeFireRedPerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build the genuine pinned FireRed ROM and extended native mGBA core
        # once using the already proven R10 integration fixture. Its own
        # 28-frame Pallet Town live swap must pass BEFORE timing begins.
        fixture = r10.ActualFireRedPalletTownLiveSwap
        fixture.setUpClass()
        cls.addClassCleanup(fixture.doClassCleanups)
        cls.fixture = fixture
        cls.folder = Path(fixture.temp.name)/"r11-performance"
        cls.folder.mkdir(parents=True,exist_ok=True)
        cls.actual_rom_sha = hashlib.sha256(fixture.rom.read_bytes()).hexdigest()
        manifest = sidecar.load_manifest(fixture.manifest)
        if cls.actual_rom_sha != manifest.source_identity.sha256:
            raise AssertionError("R11 benchmark resource and ROM identity mismatch")
        if fixture.probe < 0x02000000 or fixture.probe >= 0x02040000:
            raise AssertionError("R11 FireRed probe address invalid")
        cls.samples={"enabled":[],"disabled":[]}
        cls.native_logs={}
        for number,mode in enumerate(RUN_ORDER):
            destination=cls.folder/f"{number+1:02d}-{mode}.json"
            result=launcher.launch(
                fixture.rom, fixture.manifest, "graphic.crystal",
                emulator=fixture.emulator, frames=1800,
                probe_address=fixture.probe,
                second_resource_id="graphic.magma",
                r11_perf=destination,
                disabled=mode=="disabled")
            if "PASS_R11_PALLET_NATIVE_PERF mode="+mode not in result.stdout:
                raise AssertionError("Native FireRed benchmark did not execute")
            if not destination.is_file():
                raise AssertionError("Native mGBA did not write real frame profile")
            metrics=json.loads(destination.read_text(encoding="utf-8"))
            if metrics["mode"] != mode or metrics["schema"] != 1:
                raise AssertionError("Native benchmark mode/protocol mismatch")
            cls.samples[mode].append(metrics)
            cls.native_logs[destination.name]=result.stdout.strip()

        def per_mode(mode,phase):
            return aggregate([s[phase] for s in cls.samples[mode]])

        cls.aggregate={
            "milestone":"R11_PALLET_TOWN_NATIVE_FRAME_BENCHMARK",
            "scope":"Actual FireRed Pallet Town, pinned native mGBA; unthrottled CPU frame processing ONLY. Not actual GUI/vsync/Android realtime FPS.",
            "upstream_firered":r10.r6.FIRERED_PIN,
            "upstream_mgba":r10.r6.MGBA_PIN,
            "identical_rom_sha256":cls.actual_rom_sha,
            "sidecar_sha256":hashlib.sha256(
                Path(manifest.data_path).read_bytes()).hexdigest(),
            "run_order":RUN_ORDER,
            "host": {
                "system":platform.system(),
                "machine":platform.machine(),
                "processor":platform.processor() or "unreported",
                "cpu_count":os.cpu_count(),
                "runner_name":os.environ.get("RUNNER_NAME","unknown"),
                "runner_arch":os.environ.get("RUNNER_ARCH","unknown")
            },
            "nominal_gba_frame_ms":NOMINAL_FRAME_MS,
            "warmup_frames_per_run":120,
            "measured_before_frames_per_run":360,
            "measured_after_frames_per_run":360,
            "select_frames_per_run":3,
            "disabled":{
                "before":per_mode("disabled","before"),
                "after":per_mode("disabled","after"),
            },
            "enabled":{
                "before":per_mode("enabled","before"),
                "after":per_mode("enabled","after"),
                "select_to_ready_wall_ms_median":round(statistics.median(
                    s["select_to_ready_wall_ms"] for s in cls.samples["enabled"]),6),
                "select_first_frame_ms_median":round(statistics.median(
                    s["select_first_frame_ms"] for s in cls.samples["enabled"]),6),
                "select_frames_to_ready":[
                    s["select_frames_until_external_ready"]
                    for s in cls.samples["enabled"]
                ],
            },
        }
        ratios={}
        for phase in ("before","after"):
            a=cls.aggregate["enabled"][phase]["median_mean_ms"]
            b=cls.aggregate["disabled"][phase]["median_mean_ms"]
            if a<=0 or b<=0:
                raise AssertionError("R11 measured invalid native frame times")
            ratios[phase]=round(a/b,5)
        cls.aggregate["enabled_to_disabled_frame_cost_ratio"]=ratios
        cls.aggregate["performance_interpretation"]={
            "important":(
                "R11 FPS is unthrottled native core PROCESSING THROUGHPUT "
                "on a shared GitHub-hosted Linux runner, not actual on-screen "
                "playback speed. Video playback timing is excluded."
            ),
            "thresholds":(
                "CI fails for >2x sustained regression plus >=2ms/frame "
                "overhead, or if enabled mean exceeds the 16.74ms budget "
                "while disabled mean stays within it. Actual results reported "
                "even when passing; this test cannot guarantee Android FPS."
            )
        }
        cls.aggregate["full_native_runs"]=cls.samples
        target=os.environ.get("XGBA_R11_PERF_DIR")
        if target:
            output=Path(target)
            output.mkdir(parents=True,exist_ok=True)
            for original in sorted(cls.folder.glob("*.json")):
                (output/original.name).write_bytes(original.read_bytes())
            (output/"r11-summary.json").write_text(json.dumps(
                cls.aggregate,indent=2,sort_keys=True)+"\n",encoding="utf-8")
            rows=["mode,run,phase,mean_ms,p50_ms,p95_ms,worst_ms,unthrottled_fps,frames_over_budget"]
            for mode in ("disabled","enabled"):
                for index,m in enumerate(cls.samples[mode],1):
                    for phase in ("before","after"):
                        x=m[phase]
                        rows.append(f"{mode},{index},{phase},{x['mean_ms']},"
                                    f"{x['median_ms']},{x['p95_ms']},"
                                    f"{x['worst_ms']},{x['unthrottled_fps']},"
                                    f"{x['frames_over_16_74ms']}")
            (output/"r11-frame-timings.csv").write_text(
                "\n".join(rows)+"\n",encoding="utf-8")
            (output/"README.txt").write_text(
                "XGBA R11: actual pinned FireRed Pallet Town and real patched "
                "mGBA-native execution, same ROM and sidecar in all six trials.\n"
                "The native emulator samples CLOCK_MONOTONIC around each "
                "mCore.runFrame call, including Select live swap input. "
                "120 warmup, 360 steady, 3 select, 360 steady frames/run; "
                "no image writing or GIF encoding during timing.\n"
                "The computed FPS is **UNCAPPED EMULATION PROCESSING** "
                "THROUGHPUT, NOT displayed FPS or emulator vsync. CI runner "
                "CPU scheduling and caching can affect measurements. "
                "Hardware/GUI/Android performance remains unverified.\n"
                "Source ROM hash, upstream pins, and raw six machine-produced "
                "JSON traces recorded in r11-summary.json.\n"
                ,encoding="utf-8")
        print("R11_COMPARATIVE_NATIVE_PERFORMANCE_REPORT "+
              json.dumps({
                  "enabled_before_fps":cls.aggregate["enabled"]["before"]["median_unthrottled_fps"],
                  "disabled_before_fps":cls.aggregate["disabled"]["before"]["median_unthrottled_fps"],
                  "enabled_after_fps":cls.aggregate["enabled"]["after"]["median_unthrottled_fps"],
                  "disabled_after_fps":cls.aggregate["disabled"]["after"]["median_unthrottled_fps"],
                  "enabled_to_disabled_mean_frame_ratio":ratios,
                  "select_to_ready_wall_ms":cls.aggregate["enabled"]["select_to_ready_wall_ms_median"],
                  "select_frames_to_ready":cls.aggregate["enabled"]["select_frames_to_ready"],
              },sort_keys=True))

    def test_all_runs_same_actual_firered_rom_and_native_mgba(self):
        self.assertEqual(len(self.samples["enabled"]),3)
        self.assertEqual(len(self.samples["disabled"]),3)
        self.assertEqual(self.actual_rom_sha,self.aggregate["identical_rom_sha256"])
        self.assertEqual(len(self.actual_rom_sha),64)
        for values in self.samples.values():
            for r in values:
                self.assertEqual(r["map"],"Pallet Town")
                self.assertEqual((r["game_map_group"],r["game_map_num"]),(3,0))
                self.assertEqual(r["steady_frames_before"],360)
                self.assertEqual(r["steady_frames_after"],360)
                self.assertEqual(r["select_frames"],3)
                self.assertGreaterEqual(r["game_overworld_ticks"],719)

    def test_enabled_select_event_fetches_second_asset_without_restarting(self):
        for m in self.samples["enabled"]:
            self.assertEqual(m["external_reads"],2)
            self.assertEqual(m["provider_lookups"],2)
            self.assertEqual(m["selected_pack_after"],1)
            self.assertGreater(m["select_to_ready_wall_ms"],0)
            self.assertIn(m["select_frames_until_external_ready"],(1,2,3))

    def test_disabled_fallback_performs_no_external_file_reads(self):
        for m in self.samples["disabled"]:
            self.assertEqual(m["external_reads"],0)
            self.assertEqual(m["provider_lookups"],0)
            self.assertEqual(m["selected_pack_after"],0)
            self.assertEqual(m["select_frames_until_external_ready"],0)
            self.assertEqual(m["select_to_ready_wall_ms"],0)

    def test_all_steady_frame_samples_are_measured_not_gif_timing(self):
        for mode in ("disabled","enabled"):
            for report in self.samples[mode]:
                self.assertEqual(report["host_clock"],"CLOCK_MONOTONIC")
                self.assertIn("no PNG or GIF",report["emulation_mode"])
                for phase in ("before","after"):
                    stats=report[phase]
                    self.assertGreater(stats["mean_ms"],0)
                    self.assertGreater(stats["median_ms"],0)
                    self.assertGreater(stats["p95_ms"],0)
                    self.assertGreater(stats["unthrottled_fps"],0)

    def test_no_severe_sustained_xgba_processing_regression(self):
        # Ratio-only checks would flag a harmless 0.05 -> 0.12 ms jitter,
        # so require BOTH a large relative hit and a meaningful absolute one.
        # Likewise, an already slow CI runner is NOT evidence XGBA caused it.
        for phase in ("before","after"):
            enabled=self.aggregate["enabled"][phase]["median_mean_ms"]
            disabled=self.aggregate["disabled"][phase]["median_mean_ms"]
            if enabled/disabled > 2.0 and enabled-disabled >= 2.0:
                self.fail(f"XGBA severe frame cost regression {phase}: "
                          f"enabled {enabled:.3f}ms vs disabled {disabled:.3f}ms")
            if enabled > NOMINAL_FRAME_MS and disabled <= NOMINAL_FRAME_MS:
                self.fail(f"XGBA crosses a native-core frame budget on CI "
                          f"when the same disabled ROM stays within it: "
                          f"enabled={enabled:.3f}ms, disabled={disabled:.3f}ms")


if __name__=="__main__":
    unittest.main()

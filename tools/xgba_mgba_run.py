#!/usr/bin/env python3
"""Developer launcher for the R7 native mGBA-with-XGBA headless executable.

Requires a legitimate, user-supplied GBA ROM and XGBA v1 sidecar manifest.
The ROM identity, resource bounds, and hashes are validated before launch;
the native extended mGBA build independently repeats the ROM identity check
and validates resource integrity as the *emulated game* requests each asset.

This does not rewrite ROMs, intercept stock mGBA, or ship game ROM binaries.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

import xgba_resource_sidecar as sidecar

MAX_ROM = 32 * 1024 * 1024
MAX_GUEST_RESOURCE = 16 * 1024


def launch(rom, manifest_path, resource_id, *, emulator, frames=600,
           probe_address=0, disabled=False, screenshot=None, scene_dir=None,
           second_resource_id=None, extra_resource_ids=(), r10_dir=None, r11_perf=None,
           r12_dir=None, r13_dir=None, r14_dir=None,
           r15_dir=None, r15_savefile=None, r15_phase=None, r15_save_probe=0,
           r16_emerald_dir=None, r17_emerald_map_dir=None,
           r18_dir=None, r18_savefile=None, r18_phase=None, r18_save_probe=0,
           r19_connected_dir=None, r19_route_offset=0, r19_route_length=0,
           r19_battle_dir=None, r19_battle_probe=0,
           r19_battle0_offset=0, r19_battle0_length=0,
           r19_battle1_offset=0, r19_battle1_length=0):
    rom = Path(rom).resolve(strict=True)
    if not rom.is_file() or rom.stat().st_size > MAX_ROM:
        raise ValueError("ROM must be a real GBA file of at most 32 MiB")
    digest = hashlib.sha256()
    with rom.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    manifest = sidecar.load_manifest(manifest_path)
    if digest.hexdigest() != manifest.source_identity.sha256:
        raise ValueError("Sidecar identity does not match this ROM")
    resource = manifest.get_resource(resource_id)
    if not 0 < resource.length <= MAX_GUEST_RESOURCE:
        raise ValueError("R7 guest resource must be 1..16384 bytes")
    if resource.offset <= MAX_ROM:
        raise ValueError("R7 milestone resource must begin beyond 32 MiB")
    executable = Path(emulator).resolve(strict=True)
    if not executable.is_file():
        raise ValueError("The XGBA mGBA executable is unavailable")
    if not 1 <= frames <= 36000 or not 0 <= probe_address <= 0xFFFFFFFF:
        raise ValueError("Invalid frame limit or proof address")
    cmd = [
        str(executable),
        str(rom),
        str(manifest.data_path),
        manifest.source_identity.id,
        manifest.source_identity.sha256,
        resource.id,
        str(resource.offset),
        str(resource.length),
        resource.sha256,
        str(frames),
        hex(probe_address),
    ]
    if screenshot is not None:
        cmd.extend(["--screenshot", str(Path(screenshot).resolve())])
    if scene_dir is not None:
        capture = Path(scene_dir).resolve()
        if not capture.is_dir():
            raise ValueError("R9 frame destination directory must already exist")
        cmd.extend(["--scene-dir", str(capture)])
    if second_resource_id is not None:
        second = manifest.get_resource(second_resource_id)
        if not 0 < second.length <= MAX_GUEST_RESOURCE:
            raise ValueError("R10 second asset exceeds bounded EWRAM")
        if second.offset <= MAX_ROM:
            raise ValueError("R10 second asset must begin after 32 MiB")
        cmd.extend(["--second-resource", second.id,
                    str(second.offset), str(second.length), second.sha256])
    # R19 resource manifest has any number of independently verified source
    # references. Preserve legacy two-resource CLI as-is for R7–R18.
    if not isinstance(extra_resource_ids,(tuple,list)) or len(extra_resource_ids)>16:
        raise ValueError("The bounded XGBA provider permits at most 16 additional assets")
    used={resource_id}
    if second_resource_id is not None:
        used.add(second_resource_id)
    for extra_id in extra_resource_ids:
        if extra_id in used:
            raise ValueError("Duplicate simultaneous XGBA resource ID")
        used.add(extra_id)
        extra=manifest.get_resource(extra_id)
        if not 0<extra.length<=MAX_GUEST_RESOURCE or extra.offset<=MAX_ROM:
            raise ValueError("Extra resource violates actual 16KiB guest boundary")
        cmd.extend(["--extra-resource",extra.id,str(extra.offset),
                    str(extra.length),extra.sha256])
    if r10_dir is not None:
        target = Path(r10_dir).resolve()
        if not target.is_dir():
            raise ValueError("R10 real-map frame directory must already exist")
        cmd.extend(["--r10-dir", str(target)])
    if r11_perf is not None:
        result_path = Path(r11_perf).resolve()
        if not result_path.parent.is_dir():
            raise ValueError("R11 benchmark output directory must exist")
        cmd.extend(["--r11-perf", str(result_path)])
    if r12_dir is not None:
        folder = Path(r12_dir).resolve()
        if not folder.is_dir() or second_resource_id is None:
            raise ValueError("R12 requires an existing directory and two resources")
        cmd.extend(["--r12-dir", str(folder)])
    if r13_dir is not None:
        folder = Path(r13_dir).resolve()
        if not folder.is_dir():
            raise ValueError("R13 requires an existing evidence directory")
        cmd.extend(["--r13-dir", str(folder)])
    if r14_dir is not None:
        folder = Path(r14_dir).resolve()
        if not folder.is_dir() or second_resource_id is None:
            raise ValueError("R14 requires an existing directory and two map/tileset packs")
        cmd.extend(["--r14-dir", str(folder)])
    if r15_dir is not None:
        folder=Path(r15_dir).resolve()
        if not folder.is_dir() or second_resource_id is None:
            raise ValueError("R15 requires existing evidence directory and two packs")
        if r15_phase not in ("write","continue","corrupt") or not r15_savefile or not (
                0x02000000<=r15_save_probe<0x02040000):
            raise ValueError("R15 requires valid phase, durable Flash path and guest probe")
        save_path=Path(r15_savefile).resolve()
        if not save_path.parent.is_dir():
            raise ValueError("R15 native Flash save parent missing")
        cmd.extend(["--r15-dir",str(folder),
                    "--r15-savefile",str(save_path),
                    "--r15-phase",r15_phase,
                    "--r15-save-probe",hex(r15_save_probe)])
    if r16_emerald_dir is not None:
        directory=Path(r16_emerald_dir).resolve()
        if not directory.is_dir():
            raise ValueError("R16 native evidence destination must exist")
        if r15_dir is not None:
            raise ValueError("R15 and R16 execution modes are exclusive")
        cmd.extend(["--r16-emerald-dir",str(directory)])
    if r17_emerald_map_dir is not None:
        destination=Path(r17_emerald_map_dir).resolve()
        if not destination.is_dir() or second_resource_id is None:
            raise ValueError("R17 needs existing native screenshots directory and second resource")
        if r16_emerald_dir is not None or r15_dir is not None:
            raise ValueError("R17 may not overlap earlier game proof modes")
        cmd.extend(["--r17-emerald-map-dir",str(destination)])
    if r18_dir is not None:
        directory=Path(r18_dir).resolve()
        if not directory.is_dir() or second_resource_id is None:
            raise ValueError("R18 requires actual LCD directory and both original Emerald resources")
        if r18_phase not in ("write","continue","corrupt") or not r18_savefile or not (
                0x02000000<=r18_save_probe<0x02040000):
            raise ValueError("R18 requires phase, genuine mGBA Flash file and native guest ELF proof")
        flash=Path(r18_savefile).resolve()
        if not flash.parent.is_dir():
            raise ValueError("R18 Flash save parent absent")
        if r15_dir is not None or r17_emerald_map_dir is not None:
            raise ValueError("R18 native emulator mode must be exclusive")
        cmd.extend(["--r18-dir",str(directory),
                    "--r18-savefile",str(flash),"--r18-phase",r18_phase,
                    "--r18-save-probe",hex(r18_save_probe)])
    if r19_connected_dir is not None:
        directory=Path(r19_connected_dir).resolve()
        if not directory.is_dir() or second_resource_id is None:
            raise ValueError("R19 requires native original LCD evidence directory and Route101 ID")
        if r19_route_offset<=32*1024*1024 or not 0<r19_route_length<=16384:
            raise ValueError("R19 requires exact external original Route101 source range")
        if r18_dir is not None or r17_emerald_map_dir is not None:
            raise ValueError("R19 is a distinct Emerald map integration mode")
        cmd.extend(["--r19-connected-dir",str(directory),
                    "--r19-route-offset",str(r19_route_offset),
                    "--r19-route-length",str(r19_route_length)])
    if r19_battle_dir is not None:
        dest=Path(r19_battle_dir).resolve()
        if not dest.is_dir() or not (0x02000000<=r19_battle_probe<0x02040000):
            raise ValueError("R19 actual Emerald battle proof or native LCD directory missing")
        if r19_connected_dir is not None:
            raise ValueError("R19 separate battle and overworld functional modes")
        if not 0<r19_route_length<=16384 or r19_route_offset<=MAX_ROM:
            raise ValueError("R19 battle requires previously validated two-map resource set")
        if (r19_battle0_offset<=MAX_ROM or r19_battle1_offset<=MAX_ROM or
            not 0<r19_battle0_length<=8192 or not 0<r19_battle1_length<=8192):
            raise ValueError("R19 source-backed Emerald battle sprites must fit native EWRAM slots")
        cmd.extend(["--r19-battle-dir",str(dest),
                    "--r19-battle-probe",hex(r19_battle_probe),
                    "--r19-route-offset",str(r19_route_offset),
                    "--r19-route-length",str(r19_route_length),
                    "--r19-battle0-offset",str(r19_battle0_offset),
                    "--r19-battle0-length",str(r19_battle0_length),
                    "--r19-battle1-offset",str(r19_battle1_offset),
                    "--r19-battle1-length",str(r19_battle1_length)])
    if disabled:
        cmd.append("--disabled")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(
            f"XGBA native emulator failed (exit {result.returncode}):\\n"
            f"{result.stdout[-4000:]}\\n{result.stderr[-4000:]}"
        )
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--resource-id", required=True)
    p.add_argument("--emulator", default="build/xgba-r7/xgba-mgba-headless")
    p.add_argument("--frames", type=int, default=600)
    p.add_argument("--probe-address", type=lambda s: int(s, 0), default=0)
    p.add_argument("--disabled", action="store_true")
    p.add_argument("--screenshot", help="Write an actual mGBA-rendered 240x160 PNG")
    p.add_argument("--scene-dir", help="Record 16 genuine emulator frames while injecting D-pad inputs")
    p.add_argument("--second-resource-id", help="Additional ID in same sidecar for in-session switching")
    p.add_argument("--extra-resource-id", action="append", default=[], help="Additional verified resources in same sidecar for simultaneous original game use")
    p.add_argument("--r10-dir", help="Record the actual FireRed map before/after Select in one session")
    p.add_argument("--r11-perf", help="Write native Pallet Town CPU performance metrics as JSON")
    p.add_argument("--r12-dir", help="Execute actual FireRed mGBA savestate recovery proof")
    p.add_argument("--r13-dir", help="Execute native external map transition proof")
    p.add_argument("--r14-dir", help="Execute physical door and connected external map/tileset proof")
    p.add_argument("--r15-dir", help="Store real FireRed Flash save/continue LCD evidence")
    p.add_argument("--r16-emerald-dir", help="Execute source-built Emerald MMIO proof and capture native LCD")
    p.add_argument("--r17-emerald-map-dir", help="Execute Emerald native external map/tileset and D-pad proof")
    p.add_argument("--r18-dir", help="Execute genuine Emerald Flash save/cold continuation")
    p.add_argument("--r18-savefile", help="Private native 128 KiB Emerald Flash save file")
    p.add_argument("--r18-phase", choices=["write","continue","corrupt"])
    p.add_argument("--r18-save-probe", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-connected-dir", help="Run original Emerald multi-map D-pad and native tileset proof")
    p.add_argument("--r19-route-offset", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-route-length", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-battle-dir", help="Actual Emerald double battle using local ROM and two external sprites")
    p.add_argument("--r19-battle-probe", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-battle0-offset", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-battle0-length", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-battle1-offset", type=lambda s:int(s,0), default=0)
    p.add_argument("--r19-battle1-length", type=lambda s:int(s,0), default=0)
    p.add_argument("--r15-savefile", help="Private real mGBA Flash file, never publish")
    p.add_argument("--r15-phase", choices=["write","continue","corrupt"])
    p.add_argument("--r15-save-probe", type=lambda s:int(s,0), default=0)
    args = p.parse_args()
    out = launch(args.rom, args.manifest, args.resource_id,
                 emulator=args.emulator, frames=args.frames,
                 probe_address=args.probe_address, disabled=args.disabled,
                 screenshot=args.screenshot, scene_dir=args.scene_dir,
                 second_resource_id=args.second_resource_id,
                 extra_resource_ids=args.extra_resource_id,
                 r10_dir=args.r10_dir, r11_perf=args.r11_perf,
                 r12_dir=args.r12_dir, r13_dir=args.r13_dir, r14_dir=args.r14_dir,
                 r15_dir=args.r15_dir, r15_savefile=args.r15_savefile,
                 r15_phase=args.r15_phase, r15_save_probe=args.r15_save_probe,
                 r16_emerald_dir=args.r16_emerald_dir,
                 r17_emerald_map_dir=args.r17_emerald_map_dir,
                 r18_dir=args.r18_dir, r18_savefile=args.r18_savefile,
                 r18_phase=args.r18_phase, r18_save_probe=args.r18_save_probe,
                 r19_connected_dir=args.r19_connected_dir,
                 r19_route_offset=args.r19_route_offset,
                 r19_route_length=args.r19_route_length,
                 r19_battle_dir=args.r19_battle_dir,
                 r19_battle_probe=args.r19_battle_probe,
                 r19_battle0_offset=args.r19_battle0_offset,
                 r19_battle0_length=args.r19_battle0_length,
                 r19_battle1_offset=args.r19_battle1_offset,
                 r19_battle1_length=args.r19_battle1_length)
    print(out.stdout, end="")
    if out.stderr:
        print(out.stderr, file=sys.stderr, end="")


if __name__ == "__main__":
    main()

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
           second_resource_id=None, r10_dir=None, r11_perf=None,
           r12_dir=None, r13_dir=None):
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
    p.add_argument("--r10-dir", help="Record the actual FireRed map before/after Select in one session")
    p.add_argument("--r11-perf", help="Write native Pallet Town CPU performance metrics as JSON")
    p.add_argument("--r12-dir", help="Execute actual FireRed mGBA savestate recovery proof")
    p.add_argument("--r13-dir", help="Execute native external map transition proof")
    args = p.parse_args()
    out = launch(args.rom, args.manifest, args.resource_id,
                 emulator=args.emulator, frames=args.frames,
                 probe_address=args.probe_address, disabled=args.disabled,
                 screenshot=args.screenshot, scene_dir=args.scene_dir,
                 second_resource_id=args.second_resource_id,
                 r10_dir=args.r10_dir, r11_perf=args.r11_perf,
                 r12_dir=args.r12_dir, r13_dir=args.r13_dir)
    print(out.stdout, end="")
    if out.stderr:
        print(out.stderr, file=sys.stderr, end="")


if __name__ == "__main__":
    main()

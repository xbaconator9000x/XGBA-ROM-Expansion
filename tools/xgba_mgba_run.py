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
           probe_address=0, disabled=False, screenshot=None):
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
    args = p.parse_args()
    out = launch(args.rom, args.manifest, args.resource_id,
                 emulator=args.emulator, frames=args.frames,
                 probe_address=args.probe_address, disabled=args.disabled,
                 screenshot=args.screenshot)
    print(out.stdout, end="")
    if out.stderr:
        print(out.stderr, file=sys.stderr, end="")


if __name__ == "__main__":
    main()

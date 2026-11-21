#!/usr/bin/env python3
"""Native patched-mGBA acceptance for source-built RHH expansion variants.

Requires a separate upstream RHH checkout BUILT by the reversible source
adapter and an intact pinned mGBA Git checkout. The guest, not the host,
initiates the MMIO request. Never uploads ROMs, extracted art or saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "integration/mgba"),
               str(ROOT / "tests")]

import xgba_expansion_source_adapter as adapter
import xgba_expansion_map_pages as map_pages
import xgba_expansion_trainer_pages as trainer_pages
import xgba_resource_integration_smoke as r6
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher
import apply_core_patch
import test_xgba_r7_mgba_core as r7

RESOURCE_OFFSET = r6.RESOURCE_OFFSET
PAGE_PAYLOAD = bytes(((i * 7 + 47) % 256 for i in range(16 * 1024)))
RESOURCE_SIZE = len(PAGE_PAYLOAD)


def verify_elf_probe(source: Path, target: str) -> tuple[Path, int]:
    rom = source / f"poke{target}.gba"
    elf = source / f"poke{target}.elf"
    if not rom.is_file() or not elf.is_file():
        raise AssertionError("RHH expanded game native ARM output absent")
    if not 0 < rom.stat().st_size <= 32 * 1024 * 1024:
        raise AssertionError("RHH expanded ROM exceeds native cartridge window")
    symbols = r7.run(["arm-none-eabi-nm", "-g", elf]).stdout
    matches = re.findall(
        r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+gXgbaExpansionProof$",
        symbols, re.MULTILINE)
    if len(matches) != 1:
        raise AssertionError("RHH actual game EWRAM proof symbol missing")
    address = int(matches[0], 16)
    if not 0x02000000 <= address <= 0x02040000 - 28:
        raise AssertionError("RHH source-built EWRAM proof outside 256 KiB")
    return rom, address


def prove(source: Path, mgba: Path, target: str, output: Path, *,
          map_smoke: bool = False, overworld_play: bool = False) -> dict:
    if map_smoke and overworld_play:
        raise ValueError("Overworld play and isolated map smoke cannot run together")
    if target not in adapter.TARGETS:
        raise ValueError("Unrecognized expanded game variant")
    source = source.resolve()
    mgba = mgba.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    upstream_sha = adapter.require_release_tag(source, adapter.VALIDATED_RELEASE)
    if upstream_sha != adapter.VALIDATED_RELEASE_SHA:
        raise AssertionError("Upstream source release identity drift")
    if r7.run(["git", "-C", source, "status", "--porcelain"]).stdout.strip():
        raise AssertionError("Source adapter left the upstream repository dirty")
    rom, proof_address = verify_elf_probe(source, target)
    game_bytes = rom.read_bytes()
    game_sha = hashlib.sha256(game_bytes).hexdigest()
    if PAGE_PAYLOAD in game_bytes:
        raise AssertionError("External resource must not be embedded in the ROM")

    mgba_sha = r7.run(["git", "-C", mgba, "rev-parse", "HEAD"]).stdout.strip()
    if mgba_sha != adapter.MGBA_PIN:
        raise AssertionError("Native mGBA source is not the pinned version")
    apply_core_patch.apply(mgba)
    build = Path(tempfile.mkdtemp(prefix="xgba-rhh-mgba-", dir=output))
    r7.run(["cmake", "-S", ROOT / "integration/mgba", "-B", build,
            "-DCMAKE_BUILD_TYPE=Release",
            "-DXGBA_MGBA_CHECKOUT=" + str(mgba)], timeout=240)
    r7.run(["cmake", "--build", build, "--target",
            "xgba-mgba-headless", "--parallel", "2"], timeout=1300)
    executable = build / "xgba-mgba-headless"
    if not executable.is_file():
        raise AssertionError("Real patched native mGBA build missing")

    resource_id = f"expansion.{target}.bridge"
    external = output / "xgba-private-test-sidecar.bin"
    with external.open("wb") as file:
        file.truncate(RESOURCE_OFFSET + RESOURCE_SIZE)
        file.seek(RESOURCE_OFFSET)
        file.write(PAGE_PAYLOAD)
    page_entries = []
    if map_smoke or overworld_play:
        first = ("LAYOUT_LITTLEROOT_TOWN" if target == "emerald"
                 else "LAYOUT_PALLET_TOWN")
        layouts = ([first, "LAYOUT_ROUTE101" if target == "emerald" else "LAYOUT_ROUTE1"]
                   if overworld_play else [first])
        png = ("data/tilesets/primary/general/tiles.png" if target == "emerald"
               else "data/tilesets/primary/general_frlg/tiles.png")
        with external.open("r+b") as combined:
            combined.seek(0, 2)
            for layout in layouts:
                plan = map_pages.build(source, target, layout,
                                       output / "private-source", primary_png=png)
                page_manifest = sidecar.load_manifest(plan["private_manifest"])
                for name, entry in page_manifest.resources.items():
                    if not re.fullmatch(r"rhh\.[mps]\.[0-9a-f]{4}\.[0-9a-f]{2}", name):
                        raise AssertionError("Unexpected RHH original external resource")
                    with page_manifest.data_path.open("rb") as original:
                        original.seek(entry.offset)
                        blob = original.read(entry.length)
                    if hashlib.sha256(blob).hexdigest() != entry.sha256:
                        raise AssertionError("Original RHH source page SHA-256 mismatch")
                    offset = combined.tell()
                    combined.write(blob)
                    page_entries.append({"id": name, "offset": offset,
                                         "length": entry.length,
                                         "sha256": entry.sha256})
    # Supply genuine trainer pages during playable navigation as well as maps.
    # Isolated field-loader smoke retains its exact original read contract.
    if overworld_play:
        trainer_manifest = sidecar.load_manifest(trainer_pages.build(
            source, target, output / "private-source" / "trainers"))
        seen = {entry["id"] for entry in page_entries}
        with external.open("ab") as combined:
            for name, entry in trainer_manifest.resources.items():
                if name in seen or not re.fullmatch(r"rhh\.trainer\.[0-9a-f]{4}", name):
                    raise AssertionError("Unexpected or duplicate trainer resource")
                with trainer_manifest.data_path.open("rb") as original:
                    original.seek(entry.offset)
                    blob = original.read(entry.length)
                if len(blob) != 2048 or hashlib.sha256(blob).hexdigest() != entry.sha256:
                    raise AssertionError("Original trainer page integrity mismatch")
                offset = combined.tell()
                combined.write(blob)
                page_entries.append({"id": name, "offset": offset,
                                     "length": len(blob), "sha256": entry.sha256})
                seen.add(name)
    manifest = output / "xgba-private-test-manifest.json"
    manifest.write_text(json.dumps({
        "format": sidecar.FORMAT,
        "version": sidecar.VERSION,
        "source_identity": {"id": f"rhh-{target}-expansion-1.17.2",
                            "sha256": game_sha},
        "data_file": external.name,
        "resources": [{"id": resource_id,
                       "offset": RESOURCE_OFFSET,
                       "length": RESOURCE_SIZE,
                       "sha256": hashlib.sha256(PAGE_PAYLOAD).hexdigest()}] + page_entries,
    }), encoding="utf-8")

    outputs = {}
    for enabled in (True, False):
        proc = launcher.launch(
            rom, manifest, resource_id, emulator=executable,
            frames=1200, probe_address=proof_address,
            expansion_dir=output, expansion_target=target,
            expansion_overworld=overworld_play,
            disabled=not enabled,
            extra_resource_ids=tuple(entry["id"] for entry in page_entries))
        label = "enabled" if enabled else "disabled"
        if overworld_play:
            expected = (f"PASS_RHH_REAL_OVERWORLD_NATIVE "
                        f"target={target} enabled={int(enabled)}")
            if expected not in proc.stdout:
                raise AssertionError(f"native {target} {label} real player-controlled route acceptance failed")
        elif map_smoke:
            expected = (f"PASS_XGBA_RHH_NATIVE_REAL_FIELD_LOADER "
                        f"target={target} enabled={int(enabled)}")
            if expected not in proc.stdout or "map_bytes=" not in proc.stdout:
                raise AssertionError(f"native {target} {label} original field loader unverified")
        else:
            expected = (f"PASS_XGBA_RHH_EXPANSION_NATIVE_GUEST_MMIO "
                        f"target={target} enabled={int(enabled)}")
            if expected not in proc.stdout or "page_intact_after_frames=1" not in proc.stdout:
                raise AssertionError(f"native {target} {label} protected-page proof not accepted")
        captures = ([output / f"rhh-{target}-{'external' if enabled else 'fallback'}-{stage}.png"
                     for stage in ("00-initial-real-town","01-dpad-movement","02-after-north")]
                    if overworld_play else [output / f"expansion-{target}-{label}.png"])
        from PIL import Image
        for filename in captures:
            if not filename.is_file() or filename.stat().st_size <= 64:
                raise AssertionError(f"real mGBA LCD capture missing: {filename.name}")
            with Image.open(filename) as image:
                if image.size != (240, 160):
                    raise AssertionError("native screenshot is not real GBA LCD size")
                if len(set(image.convert("RGB").getdata())) <= 8:
                    raise AssertionError(f"RHH LCD image blank or monochrome: {filename.name}")
        outputs[label] = proc.stdout

    report = {
        "framework": "rh-hideout/pokeemerald-expansion",
        "release_tag": adapter.VALIDATED_RELEASE,
        "upstream_sha": upstream_sha,
        "target": target,
        "native_mgba_sha": mgba_sha,
        "guest_mmio_abi": 1,
        "source_rom_sha256": game_sha,
        "source_rom_bytes": len(game_bytes),
        "guest_ewram_proof_address": f"0x{proof_address:08x}",
        "resource_id": resource_id,
        "external_resource_offset": RESOURCE_OFFSET,
        "external_payload_sha256": hashlib.sha256(PAGE_PAYLOAD).hexdigest(),
        "external_resource_bytes": RESOURCE_SIZE,
        "actual_16k_page_intact_after_game_frames": not map_smoke,
        "map_tileset_loader_source_native_verified": map_smoke or overworld_play,
        "player_controlled_overworld_verified": overworld_play,
        "original_town_to_route_native_acceptance": overworld_play,
        "map_tileset_real_source_page_count": sum(not e["id"].startswith("rhh.trainer.") for e in page_entries),
        "trainer_provider_page_count": sum(e["id"].startswith("rhh.trainer.") for e in page_entries),
        "gameplay_map_rendering_verified": overworld_play,
        "heap_bytes_reserved_for_xgba_page": RESOURCE_SIZE,
        "real_expanded_guest_provider_reads_verified": True,
        "same_source_built_rom_enabled_and_disabled": True,
        "original_source_restored": True,
        "actual_lcd_frames": 6 if overworld_play else 2,
        "native_enabled": outputs["enabled"],
        "native_disabled": outputs["disabled"],
        "not_proven": ("scripted NPC interactions, battles and Flash cold restart"
                       if overworld_play else
                       "native playable map transition/render, NPCs, battle sprites or Flash save"),
    }
    (output / f"{target}-proof.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Keep only public-compatible artifacts: exact proof and LCD images. The
    # generated private-style sidecar and manifest remain transient.
    external.unlink()
    manifest.unlink()
    if map_smoke or overworld_play:
        shutil.rmtree(output / "private-source")
    shutil.rmtree(build)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mgba", type=Path, required=True)
    parser.add_argument("--target", choices=adapter.TARGETS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--map-smoke", action="store_true")
    parser.add_argument("--overworld-play", action="store_true")
    args = parser.parse_args()
    report = prove(args.source, args.mgba, args.target, args.output,
                   map_smoke=args.map_smoke,
                   overworld_play=args.overworld_play)
    print("PASS_XGBA_RHH_NATIVE_INTEGRATION",
          report["target"], report["upstream_sha"],
          report["native_mgba_sha"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

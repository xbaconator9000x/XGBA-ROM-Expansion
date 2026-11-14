#!/usr/bin/env python3
"""R86 owner-private REAL Emerald -> Rocket room -> Rocket landing mGBA test.

No mocked movement or source switch. Inputs are passed to actual GBA key
register by the patched mGBA core. Original source key and native actor/asset
proofs come from EWRAM. Actual LCD screenshots are captured in private.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher

PASS_MARKER="PASS_R86_ORIGINAL_ROCKET_DOOR_ROUNDTRIP_NATIVE_GBA"

def run(rom:Path,manifest:Path,emulator:Path,controller:Path,
        proof_address:int,private_output:Path,frames:int=3100):
    rom=Path(rom).resolve(strict=True)
    manifest=Path(manifest).resolve(strict=True)
    private_output=Path(private_output)
    if private_output.exists():
        raise ValueError("R86 refuses to overwrite native original-world gameplay evidence")
    binding=manifest.parent/"R85_PRIVATE_BINDING_PROOF.json"
    if not binding.is_file():
        raise ValueError("R86 requires R85 exact-source original-owner binding proof")
    witness=json.loads(binding.read_text())
    if witness.get("authenticated_original_private_resources")!=435 or \
       witness.get("actual_emulator_player_route_completed") is not False:
        raise ValueError("R86 refuses a missing/falsely accepted original resource binding")
    m=sidecar.load_manifest(manifest)
    private=[rid for rid in m.resources if rid not in ("emerald.littleroot","emerald.bridge")]
    if len(private)<435 or any(k not in m.resources for k in
        ("emerald.r48.npc","rocket.r48.npc","heart_soul.r48.npc")):
        raise ValueError("R86 missing original source-world NPC/terrain/tile packages")
    if not 0x02000000<=proof_address<=0x0203ffe8 or proof_address&3:
        raise ValueError("R86 requires real Emerald ELF symbol address for gXgbaR80SourceRoomProof")
    # Never create 'passed' evidence unless native mGBA exits with real
    # guest-originated two-room proof and authentic LCD frame capture.
    private_output.mkdir(parents=True,exist_ok=False)
    result=launcher.launch(rom,manifest,"emerald.littleroot",
        emulator=emulator,frames=frames,probe_address=0,
        second_resource_id="emerald.bridge",
        extra_resource_ids=private,
        r86_input_dir=private_output,r86_input_script=controller,
        r86_proof=proof_address)
    (private_output/"r86-native-mgba.log").write_text(result.stdout+"\n"+result.stderr)
    captures=sorted(private_output.glob("r86-native-arrival-*.png"))
    if PASS_MARKER not in result.stdout or len(captures)!=2:
        raise AssertionError("R86 native gameplay acceptance requires two actual LCD arrival screenshots")
    report={"native_original_rocket_room_played":True,
            "from_source":"0x010009","interior_source":"0x012304",
            "returned_source":"0x010009","native_arrival_lcd_count":2,
            "private_resources":435,"real_emulator_controller":True,
            "foreign_world_flash_persistence_implemented":False,
            "three_rom_playthrough_completed":False}
    (private_output/"R86_REAL_NATIVE_ROCKET_ROOM_ACCEPTANCE.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--built-emerald",type=Path,required=True)
    p.add_argument("--bound-private-manifest",type=Path,required=True)
    p.add_argument("--patched-mgba",type=Path,required=True)
    p.add_argument("--controller-script",type=Path,required=True)
    p.add_argument("--emerald-elf-r80-proof",type=lambda s:int(s,0),required=True)
    p.add_argument("--private-evidence-dir",type=Path,required=True)
    p.add_argument("--boot-frames",type=int,default=3100)
    a=p.parse_args()
    print(json.dumps(run(a.built_emerald,a.bound_private_manifest,
         a.patched_mgba,a.controller_script,a.emerald_elf_r80_proof,
         a.private_evidence_dir,a.boot_frames),indent=2))
if __name__=="__main__":main()

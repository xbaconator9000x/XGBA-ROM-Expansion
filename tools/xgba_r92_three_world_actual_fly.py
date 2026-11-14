#!/usr/bin/env python3
"""R92. Actually PLAY 3 source-world Fly legs via GBA controller and mGBA.

Fails on partial/artificial door evidence. Original Heart & Soul world2
BG and NPC art are mandatory. No source ROM/sidecar/GameData in public CI.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import xgba_resource_sidecar as sidecar
import xgba_mgba_run as launcher

PASS="PASS_R92_NATIVE_THREE_WORLD_HM_FLY"
HNS_REQUIRED=(
  "r53.w2.v2.t00f8823c.meta","r53.w2.v2.t00f885e4.meta",
  "r56.w2.s0196.meta","r56.w2.s01e9.meta","r56.w2.s4010.meta"
)
def run(rom:Path,manifest:Path,emulator:Path,controller:Path,proofs:dict,
        output:Path):
    rom=Path(rom).resolve(strict=True)
    manifest=Path(manifest).resolve(strict=True)
    emulator=Path(emulator).resolve(strict=True)
    controller=Path(controller).resolve(strict=True)
    output=Path(output)
    if output.exists():raise ValueError("Never overwrite owner-private 3-World original Fly evidence")
    pack=sidecar.load_manifest(manifest)
    if hashlib.sha256(rom.read_bytes()).hexdigest()!=pack.source_identity.sha256:
        raise ValueError("R92 only runs with the exact native Emerald ROM associated with the sidecar")
    resources=pack.resources
    for resource in ("emerald.littleroot","emerald.bridge","rocket.r48.npc",
                     "heart_soul.r48.npc","emerald.r48.npc",*HNS_REQUIRED):
        if resource not in resources:raise ValueError("R92 missing original source graphics or NPC: "+resource)
    wanted=("r48","r54","r58")
    if set(proofs)!=set(wanted):
        raise ValueError("R92 requires all three exact native Emerald ELF symbol addresses")
    if any(type(v) is not int or v<0x02000000 or v>0x0203ffcc or v&3
           for v in proofs.values()):raise ValueError("R92 invalid native original ELF proof address")
    output.mkdir(parents=True)
    registered=[id for id in resources if id not in ("emerald.littleroot","emerald.bridge")]
    cmd=launcher.launch(rom,manifest,"emerald.littleroot",
        emulator=emulator,frames=3100,probe_address=0,
        second_resource_id="emerald.bridge",extra_resource_ids=registered,
        r92_fly_dir=output,r92_fly_script=controller,
        r92_r48=proofs["r48"],r92_r54=proofs["r54"],r92_r58=proofs["r58"])
    (output/"r92-native-mgba.log").write_text(cmd.stdout+"\n"+cmd.stderr)
    frames=sorted(output.glob("r92-real-fly-*.png"))
    if PASS not in cmd.stdout or len(frames)!=3:
        raise AssertionError("R92 actual original Emerald Fly animation and 3 postfade LCD landings NOT PROVEN")
    report={"genuine_game_hm_fly":True,"original_three_world_route":[0,1,2,0],
        "actual_fly_in_callbacks":3,"native_fly_menu_confirmations":3,
        "genuine_lcd_landings":3,"source_art_sha_verified":True,
        "foreign_world_flash_persistence_tested":False,"party_pc_bad_egg_tested":False}
    (output/"R92_THREE_WORLD_ACTUAL_FLY_ACCEPTANCE.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("built-emerald","bound-private-manifest","patched-mgba",
                "real-controller-script","private-evidence-dir"):
        p.add_argument("--"+arg,required=True,type=Path)
    for arg in ("r48","r54","r58"):
        p.add_argument("--native-elf-"+arg,required=True,type=lambda x:int(x,0))
    a=p.parse_args()
    print(json.dumps(run(a.built_emerald,a.bound_private_manifest,a.patched_mgba,
        a.real_controller_script,{"r48":a.native_elf_r48,
        "r54":a.native_elf_r54,"r58":a.native_elf_r58},
        a.private_evidence_dir),indent=2))
if __name__=="__main__":main()

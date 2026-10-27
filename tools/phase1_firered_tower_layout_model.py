#!/usr/bin/env python3
"""Pinned FireRed Trainer Tower layout: isolated host C ABI witness, NOT ARM runtime proof."""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path

PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
 "include/cereader_tool.h":"5cb5a9ebc32db23de07800ccce124bcb28d3ef15",
 "include/pokemon.h":"414dc41767295aed38f299e8495c5e2f8d25ddc9",
 "include/constants/global.h":"21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9",
 "include/constants/trainer_tower.h":"ea0039ea1408c06b8c968cfde8e2628213b2a0dc",
 "include/save.h":"87fb9b615b434b58823d15688056695acda9feab",
 "src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e",
 "src/save.c":"36b960f375c92711aa49b99bdfe9c6b3a99d6b1c"}
ANCHORS={
 "src/cereader_tool.c":["#define SEC30_SIZE  (offsetof(struct EReaderTrainerTowerSet, floors[4]))",
 "#define SEC31_SIZE  (sizeof(struct EReaderTrainerTowerSet) - SEC30_SIZE)",
 "memcpy(buffer, ttdata, SEC30_SIZE);","buffer[1] = GetTrainerHillUnkVal();",
 "memcpy(buffer, (u8 *)ttdata + SEC30_SIZE, SEC31_SIZE);",
 "memcpy(ttdata + 0x000, buffer, SEC30_SIZE);",
 "memcpy((u8 *)ttdata + SEC30_SIZE, buffer, SEC31_SIZE);",
 "if (!ValidateTrainerTowerData(ttdata))"],
 "src/save.c":["size = SECTOR_COUNTER_OFFSET - 1;","savData = &gSaveDataBuffer.data[4];",
 "for (; i <= size; i++)"],
 "include/cereader_tool.h":["struct TrainerTowerTrainer","struct TrainerTowerFloor",
 "struct EReaderTrainerTowerSet","struct BattleTowerPokemon mons[PARTY_SIZE];"],
 "include/pokemon.h":["struct BattleTowerPokemon","u32 hpIV:5;","u32 personality;"],
 "include/constants/global.h":["#define MAX_MON_MOVES 4","#define PARTY_SIZE 6",
 "#define POKEMON_NAME_LENGTH 10"],
 "include/constants/trainer_tower.h":["#define MAX_TRAINER_TOWER_FLOORS 8",
 "#define MAX_TRAINERS_PER_FLOOR  3"],
 "include/save.h":["#define SECTOR_DATA_SIZE 3968","#define SECTOR_FOOTER_SIZE 128",
 "u32 counter;"]}
def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def extract_struct(text,name):
    pattern=r"struct\s+"+re.escape(name)+r"\s*\{.*?\};"
    match=re.search(pattern,text,re.S)
    if not match:raise ValueError("Struct missing: "+name)
    return match.group(0)
def verify_anchors(sources):
    for path,terms in ANCHORS.items():
        for term in terms:
            if term not in sources[path]:raise ValueError(path+": missing source anchor "+term)
def load(root):
    if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
        raise ValueError("Pinned FireRed checkout changed")
    result={}
    for path,sha in BLOBS.items():
        tree=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD:"+path],text=True).strip()
        data=subprocess.check_output(["git","-C",str(root),"cat-file","blob",sha])
        if tree!=sha or blob(data)!=sha:raise ValueError("Pinned source mismatch "+path)
        result[path]=data.decode("utf-8")
    verify_anchors(result)
    for path,terms in ANCHORS.items():
        for term in terms:
            changed=dict(result);changed[path]=changed[path].replace(term,"",1)
            try:verify_anchors(changed)
            except ValueError:pass
            else:raise ValueError("Negative source mutation not rejected "+path+":"+term)
    return result
def build_model(sources,compiler):
    macros={}
    for name,path in (("MAX_MON_MOVES","include/constants/global.h"),
                      ("PARTY_SIZE","include/constants/global.h"),
                      ("POKEMON_NAME_LENGTH","include/constants/global.h"),
                      ("MAX_TRAINER_TOWER_FLOORS","include/constants/trainer_tower.h"),
                      ("MAX_TRAINERS_PER_FLOOR","include/constants/trainer_tower.h"),
                      ("SECTOR_DATA_SIZE","include/save.h"),
                      ("SECTOR_FOOTER_SIZE","include/save.h")):
        m=re.search(r"^#define\s+"+name+r"\s+(\d+)\s*$",sources[path],re.M)
        if not m:raise ValueError("Unresolved source macro "+name)
        macros[name]=int(m.group(1))
    definitions="\n".join(extract_struct(sources[path],name) for path,name in (
        ("include/pokemon.h","BattleTowerPokemon"),
        ("include/cereader_tool.h","TrainerTowerTrainer"),
        ("include/cereader_tool.h","TrainerTowerFloor"),
        ("include/cereader_tool.h","EReaderTrainerTowerSet"),
        ("include/save.h","SaveSector")))
    prelude="#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\ntypedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;\n"
    prelude+="".join(f"#define {k} {v}\n" for k,v in macros.items())
    main=r"""
int main(void) {
  printf("{\"battle_mon\":%zu,\"trainer\":%zu,\"floor\":%zu,\"set\":%zu,"
         "\"trainer_mons_offset\":%zu,\"floor_checksum_offset\":%zu,"
         "\"sec30\":%zu,\"sec31\":%zu,\"counter_offset\":%zu}\n",
         sizeof(struct BattleTowerPokemon),sizeof(struct TrainerTowerTrainer),
         sizeof(struct TrainerTowerFloor),sizeof(struct EReaderTrainerTowerSet),
         offsetof(struct TrainerTowerTrainer,mons),
         offsetof(struct TrainerTowerFloor,checksum),
         offsetof(struct EReaderTrainerTowerSet,floors[4]),
         sizeof(struct EReaderTrainerTowerSet)-offsetof(struct EReaderTrainerTowerSet,floors[4]),
         offsetof(struct SaveSector,counter));
  return 0;
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        src=Path(tmp)/"layout.c";exe=Path(tmp)/"layout"
        src.write_text(prelude+definitions+"\n"+main)
        subprocess.run([compiler,"-std=gnu11","-Wall","-Wextra","-Werror",str(src),"-o",str(exe)],check=True)
        output=subprocess.check_output([str(exe)],text=True)
    observed=json.loads(output)
    expected={"battle_mon":44,"trainer":328,"floor":992,"set":7944,
              "trainer_mons_offset":64,"floor_checksum_offset":988,
              "sec30":3976,"sec31":3968,"counter_offset":4092}
    if observed!=expected:raise ValueError(f"Host C model layout diverged: {observed}")
    return observed
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--compiler",default="cc")
    a=p.parse_args()
    sources=load(a.source)
    model=build_model(sources,a.compiler)
    result={"schema":"xgba-phase1-trainer-tower-host-model-v1","pinned_commit":PIN,
            "source_blobs":BLOBS,"host_c_layout":model,
            "payload_copy_count_per_special_sector":model["counter_offset"],
            "special_sector_capacity":model["counter_offset"],
            "remaining_zero_pad_first":model["counter_offset"]-model["sec30"],
            "remaining_zero_pad_second":model["counter_offset"]-model["sec31"],
            "source_anchor_mutation_controls":sum(map(len,ANCHORS.values())),
            "scope":"Host C ABI model of exact pinned struct declarations, not original agbcc, GBA binary or emulator execution",
            "independent_approvals":0,"phase1_gate":"FAIL_INCOMPLETE"}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()

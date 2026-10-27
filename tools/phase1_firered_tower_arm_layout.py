#!/usr/bin/env python3
"""Compile exact-pinned Trainer Tower structs for ARMv4T using Clang, not agbcc."""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from phase1_firered_tower_layout_model import PIN,BLOBS,load,extract_struct

MACROS={
 "MAX_MON_MOVES":("include/constants/global.h",4),
 "PARTY_SIZE":("include/constants/global.h",6),
 "POKEMON_NAME_LENGTH":("include/constants/global.h",10),
 "MAX_TRAINER_TOWER_FLOORS":("include/constants/trainer_tower.h",8),
 "MAX_TRAINERS_PER_FLOOR":("include/constants/trainer_tower.h",3),
 "SECTOR_DATA_SIZE":("include/save.h",3968),
 "SECTOR_FOOTER_SIZE":("include/save.h",128)}
SIZES={"BattleTowerPokemon":44,"TrainerTowerTrainer":328,"TrainerTowerFloor":992,
       "EReaderTrainerTowerSet":7944,"SaveSector":4096}
OFFSETS={
 "struct TrainerTowerTrainer,mons":64,
 "struct TrainerTowerFloor,checksum":988,
 "struct EReaderTrainerTowerSet,floors[4]":3976,
 "struct SaveSector,counter":4092}
def source(s):
    c="typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32;\n"
    for name,(path,value) in MACROS.items():
        match=re.search(r"^#define\s+"+name+r"\s+(\d+)\s*$",s[path],re.M)
        if not match or int(match.group(1))!=value:raise ValueError("Pinned macro changed: "+name)
        c+=f"#define {name} {value}\n"
    for path,name in (("include/pokemon.h","BattleTowerPokemon"),
                      ("include/cereader_tool.h","TrainerTowerTrainer"),
                      ("include/cereader_tool.h","TrainerTowerFloor"),
                      ("include/cereader_tool.h","EReaderTrainerTowerSet"),
                      ("include/save.h","SaveSector")):
        c+=extract_struct(s[path],name)+"\n"
    for name,size in SIZES.items():
        c+=f'_Static_assert(sizeof(struct {name}) == {size}, "size {name}");\n'
    for expression,offset in OFFSETS.items():
        c+=f'_Static_assert(__builtin_offsetof({expression}) == {offset}, "offset {expression}");\n'
    c+='_Static_assert(sizeof(struct EReaderTrainerTowerSet)-__builtin_offsetof(struct EReaderTrainerTowerSet,floors[4]) == 3968, "sec31");\n'
    c+='int xgba_trainer_tower_layout_witness(void) { return sizeof(struct EReaderTrainerTowerSet); }\n'
    return c
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--clang",default="clang")
    p.add_argument("--readelf",default="readelf")
    a=p.parse_args()
    pinned=load(a.source)
    c=source(pinned)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"tower.c";obj=Path(tmp)/"tower.o"
        path.write_text(c)
        cmd=[a.clang,"-target","armv4t-none-eabi","-ffreestanding","-std=gnu11",
             "-Wall","-Wextra","-Werror","-c",str(path),"-o",str(obj)]
        subprocess.run(cmd,check=True)
        header=subprocess.check_output([a.readelf,"-h",str(obj)],text=True)
        if not re.search(r"Machine:\s+ARM\b",header) or not re.search(r"Class:\s+ELF32\b",header):
            raise ValueError("Compiler did not produce 32-bit ARM ELF")
        object_sha=hashlib.sha256(obj.read_bytes()).hexdigest()
    result={"schema":"xgba-phase1-trainer-tower-armv4t-clang-layout-v1",
            "pinned_commit":PIN,"pinned_blobs":BLOBS,
            "compiler":subprocess.check_output([a.clang,"--version"],text=True).splitlines()[0],
            "target":"armv4t-none-eabi","elf_class":"ELF32","elf_machine":"ARM",
            "compiled_size_assertions":SIZES,"compiled_offset_assertions":OFFSETS,
            "sec31_size":3968,"static_assertions":len(SIZES)+len(OFFSETS)+1,
            "object_sha256":object_sha,
            "scope":"ARMv4T Clang object static layout proof; NOT original agbcc, linked game, mGBA execution or independent approval",
            "independent_approvals":0,"phase1_gate":"FAIL_INCOMPLETE"}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()

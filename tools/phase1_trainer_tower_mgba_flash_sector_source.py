#!/usr/bin/env python3
"""Pinned FireRed Trainer Tower sector IDs -> mGBA Flash bank source mapping."""
import argparse,json,subprocess
from pathlib import Path
FR="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MG="fd9dc5c2cbf234365068855851107e762fc6211b"
BLOBS={
"include/save.h":"87fb9b615b434b58823d15688056695acda9feab",
"src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e",
"src/gba/savedata.c":"fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
"include/mgba/internal/gba/savedata.h":"6227be25e8c9d2c1cc14c06ded34389b96138577"}
def need(x,msg):
    if not x:raise ValueError(msg)
def check(save,reader,flash,header):
    for k in ["#define SECTOR_ID_TRAINER_TOWER_1    30",
              "#define SECTOR_ID_TRAINER_TOWER_2    31",
              "#define SECTORS_COUNT                32"]:
        need(k in save,"FireRed physical sector ID drift: "+k)
    for k in ["TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",
              "TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",
              "TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",
              "TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)"]:
        need(k in reader,"Trainer Tower callsite drift: "+k)
    for k in ["if (address == 0 && value < 2)",
              "_flashSwitchBank(savedata, value);",
              "savedata->currentBank = &savedata->data[bank << 16];",
              "size_t size = 0x1000;",
              "sectorStart >> 12",
              "memset(&savedata->currentBank[sectorStart & ~(size - 1)], 0xFF, size);"]:
        need(k in flash,"mGBA Flash implementation drift: "+k)
    need(flash.count("case FLASH_COMMAND_SWITCH_BANK:")>=2,
         "Flash bank command dispatch drift")
    need(flash.count("savedata->currentBank = &savedata->data[bank << 16];")==2,
         "both mGBA currentBank restoration and bank switch mappings must match")
    need("FLASH_COMMAND_SWITCH_BANK = 0xB0" in header,"bank command opcode drift")
    need("FLASH_COMMAND_ERASE_SECTOR = 0x30" in header,"erase command opcode drift")
    return {"sector_30":{"bank":1,"bank_local_sector":14,"file_offset_hex":"0x1e000"},
            "sector_31":{"bank":1,"bank_local_sector":15,"file_offset_hex":"0x1f000"},
            "sector_size":4096,"evidence":"SOURCE_DERIVED_NOT_NATIVE",
            "power_loss_atomicity_proven":False}
def mutations(save,reader,flash,header):
    cases=[
      (0,"#define SECTOR_ID_TRAINER_TOWER_1    30",
       "#define SECTOR_ID_TRAINER_TOWER_1    29"),
      (0,"#define SECTOR_ID_TRAINER_TOWER_2    31",
       "#define SECTOR_ID_TRAINER_TOWER_2    30"),
      (0,"#define SECTORS_COUNT                32",
       "#define SECTORS_COUNT                30"),
      (1,"TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",
       "TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)"),
      (1,"TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",
       "TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)"),
      (2,"if (address == 0 && value < 2)",
       "if (address == 0 && value < 1)"),
      (2,"savedata->currentBank = &savedata->data[bank << 16];",
       "savedata->currentBank = &savedata->data[bank << 15];"),
      (2,"size_t size = 0x1000;","size_t size = 0x2000;"),
      (2,"sectorStart >> 12","sectorStart >> 13"),
      (3,"FLASH_COMMAND_SWITCH_BANK = 0xB0",
       "FLASH_COMMAND_SWITCH_BANK = 0xB1"),
      (3,"FLASH_COMMAND_ERASE_SECTOR = 0x30",
       "FLASH_COMMAND_ERASE_SECTOR = 0x31")]
    original=[save,reader,flash,header]
    for i,(which,old,new) in enumerate(cases):
        need(old in original[which],"negative target absent "+str(i))
        changed=list(original)
        changed[which]=changed[which].replace(old,new,1)
        try:check(*changed)
        except ValueError:continue
        raise AssertionError("escaped source mutation "+str(i))
    return len(cases)
def read(root,pin,paths):
    def git(*args):return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
    need(git("rev-parse","HEAD")==pin,"source revision drift")
    result={}
    for p in paths:
        need(git("hash-object",p)==BLOBS[p],"source blob drift "+p)
        result[p]=(root/p).read_text()
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firered",required=True,type=Path)
    p.add_argument("--mgba",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    fr=read(a.firered,FR,["include/save.h","src/cereader_tool.c"])
    mg=read(a.mgba,MG,["src/gba/savedata.c","include/mgba/internal/gba/savedata.h"])
    args=(fr["include/save.h"],fr["src/cereader_tool.c"],
          mg["src/gba/savedata.c"],mg["include/mgba/internal/gba/savedata.h"])
    result={"evidence":"PINNED_SOURCE_ONLY","firered":FR,"mgba":MG,"blobs":BLOBS,
            "mapping":check(*args),"negative_controls":mutations(*args),
            "native_mgba_execution":False,"phase1_gate":"FAIL_INCOMPLETE",
            "independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("PINNED_TOWER_MGBA_FLASH_SOURCE_PASS negatives=%d"%result["negative_controls"])
if __name__=="__main__":main()

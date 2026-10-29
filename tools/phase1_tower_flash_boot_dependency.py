#!/usr/bin/env python3
"""Fail-closed pinned FireRed special-sector ARM Flash initialization dependency closure.
Source only; does not claim runtime native Flash transactions.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
 "src/save.c":"36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
 "src/agb_flash.c":"08aeed1638e214a3cad8b28d103964ab24342fba",
 "src/agb_flash_1m.c":"e249fab9a350f3263e7df5f20ff301a6d008e3db",
 "src/load_save.c":"8b723dd044c6024b3671bb890b25b56a53f99ec5",
 "src/main.c":"542b0f5d16dd93107523d11163bfcb70a42b707a",
 "src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e",
}
CHECKS={
 ("src/save.c","u32 TryReadSpecialSaveSector(u8 sectorId, u8 *dst)"):(
  "SECTOR_ID_TRAINER_TOWER_1","SECTOR_ID_TRAINER_TOWER_2",
  "ReadFlash(sectorId, 0, (u8 *)&gSaveDataBuffer, SECTOR_SIZE);",
  "SPECIAL_SECTOR_SENTINEL","dst[i] = savData[i];"),
 ("src/save.c","u32 TryWriteSpecialSaveSector(u8 sector, u8 *src)"):(
  "SECTOR_ID_TRAINER_TOWER_1","SECTOR_ID_TRAINER_TOWER_2",
  "SPECIAL_SECTOR_SENTINEL","savData[i] = src[i];",
  "ProgramFlashSectorAndVerify(sector, savDataBuffer)"),
 ("src/agb_flash.c","void ReadFlash(u16 sectorNum, u32 offset, void *dest, u32 size)"):(
  "gFlash->romSize","SwitchFlashBank(sectorNum / SECTORS_PER_BANK);",
  "readFlash_Core_Buffer","readFlash_Core(src, dest, size);"),
 ("src/agb_flash.c","u32 VerifyFlashSector(u16 sectorNum, u8 *src)"):(
  "gFlash->romSize","SwitchFlashBank(sectorNum / SECTORS_PER_BANK);",
  "verifyFlashSector_Core_Buffer","gFlash->sector.size"),
 ("src/agb_flash.c","u32 ProgramFlashSectorAndVerify(u16 sectorNum, u8 *src)"):(
  "i < 3","ProgramFlashSector(sectorNum, src);",
  "VerifyFlashSector(sectorNum, src);"),
 ("src/agb_flash.c","void StartFlashTimer(u8 phase)"):(
  "gFlashMaxTime","sTimerReg","REG_IME"),
 ("src/agb_flash_1m.c","u16 IdentifyFlash(void)"):(
  "ReadFlashId();","ProgramFlashSector = (*setupInfo)->programFlashSector;",
  "WaitForFlashWrite = (*setupInfo)->WaitForFlashWrite;",
  "gFlashMaxTime = (*setupInfo)->maxTime;",
  "gFlash = &(*setupInfo)->type;"),
 ("src/load_save.c","void CheckForFlashMemory(void)"):(
  "IdentifyFlash()","gFlashMemoryPresent = TRUE;","InitFlashTimer();"),
 ("src/main.c","void InitFlashTimer(void)"):(
  "SetFlashTimerIntr(2, *func);",),
 ("src/cereader_tool.c","static bool32 CEReaderTool_SaveTrainerTower_r(struct EReaderTrainerTowerSet * ttdata, u8 * buffer)"):(
  "TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",
  "TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)"),
 ("src/cereader_tool.c","static bool32 CEReaderTool_LoadTrainerTower_r(struct EReaderTrainerTowerSet * ttdata, void *buffer)"):(
  "TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",
  "TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)"),
}
def need(x,msg):
    if not x:raise ValueError(msg)
def body(s,signature):
    need(s.count(signature)==1,"signature missing/duplicated: "+signature)
    start=s.index(signature)
    begin=s.index("{",start+len(signature))
    depth=0
    for i in range(begin,len(s)):
        if s[i]=="{":depth+=1
        elif s[i]=="}":
            depth-=1
            if depth==0:return s[start:i+1]
    raise ValueError("unclosed function "+signature)
def check(sources):
    for (path,signature),anchors in CHECKS.items():
        frag=body(sources[path],signature)
        for anchor in anchors:
            need(frag.count(anchor)==1,"function anchor drift "+signature+" :: "+anchor)
    read=body(sources["src/save.c"],"u32 TryReadSpecialSaveSector(u8 sectorId, u8 *dst)")
    write=body(sources["src/save.c"],"u32 TryWriteSpecialSaveSector(u8 sector, u8 *src)")
    init=body(sources["src/load_save.c"],"void CheckForFlashMemory(void)")
    need(read.index("SECTOR_ID_TRAINER_TOWER_1")<read.index("ReadFlash("),
         "read guard must precede Flash call")
    need(write.index("SECTOR_ID_TRAINER_TOWER_1")<write.index("ProgramFlashSectorAndVerify("),
         "write guard must precede Flash call")
    need(init.index("IdentifyFlash()")<init.index("InitFlashTimer()"),
         "Flash detection must precede timer initialization")
    return True
def negatives(sources):
    count=0
    for (path,signature),anchors in CHECKS.items():
        fragment=body(sources[path],signature)
        for anchor in anchors:
            changed=dict(sources)
            changed[path]=sources[path].replace(fragment,fragment.replace(anchor,"PHASE1_NEGATIVE",1),1)
            need(changed[path]!=sources[path],"ineffective mutation")
            try:check(changed)
            except ValueError:count+=1
            else:raise AssertionError("negative escaped: "+signature+" "+anchor)
    need(count==sum(len(v) for v in CHECKS.values()),"negative count drift")
    return count
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firered",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    def git(*xs):
        return subprocess.check_output(["git","-C",str(a.firered),*xs],text=True).strip()
    need(git("rev-parse","HEAD")==PIN,"pinned FireRed HEAD drift")
    for path,blob in BLOBS.items():
        need(git("hash-object",path)==blob,"pinned blob drift "+path)
    sources={path:(a.firered/path).read_text() for path in BLOBS}
    check(sources)
    count=negatives(sources)
    record={
      "evidence_class":"SOURCE_ONLY_PINNED_SPECIAL_SECTOR_FLASH_BOOT_DEPENDENCY",
      "firered_pin":PIN,"source_blobs":BLOBS,
      "partial_functions":{path+":"+signature:hashlib.sha256(body(sources[path],signature).encode()).hexdigest()
                           for path,signature in CHECKS},
      "source_mutations_rejected":count,
      "required_boot_precondition":"CheckForFlashMemory -> IdentifyFlash sets gFlash and ProgramFlashSector -> InitFlashTimer sets timer interrupt",
      "read_boundary":"TryReadSpecialSaveSector -> ReadFlash -> gFlash ROM size, bank switching and RAM-resident core",
      "write_boundary":"TryWriteSpecialSaveSector -> ProgramFlashSectorAndVerify -> function pointer + VerifyFlashSector + timer",
      "native_original_agbcc_sector_30_31_transaction_executed":False,
      "stock_gameplay_reachability":False,
      "physical_hardware":False,
      "phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
    print("PINNED_FLASH_BOOT_DEPENDENCY_SOURCE_PASS functions=%d negatives=%d gate=FAIL_INCOMPLETE approvals=0"%(len(CHECKS),count))
if __name__=="__main__":main()

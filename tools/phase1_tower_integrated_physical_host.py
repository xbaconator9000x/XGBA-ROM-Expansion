#!/usr/bin/env python3
"""Execute original FireRed CEReaderTool and special save functions together on host.
Do not misclassify this test-only fake Flash as agbcc/mGBA/native hardware.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={"src/save.c":"36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
       "src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e",
       "include/cereader_tool.h":"5cb5a9ebc32db23de07800ccce124bcb28d3ef15",
       "src/util.c":"b32799584937a120a03b08897886f08adc033fce"}
SAVE=("u32 TryReadSpecialSaveSector(u8 sectorId, u8 *dst)",
      "u32 TryWriteSpecialSaveSector(u8 sector, u8 *src)")
TOWER=("static u8 GetTrainerHillUnkVal(void)",
       "static bool32 ValidateTrainerTowerTrainer(struct TrainerTowerFloor * floor)",
       "bool32 ValidateTrainerTowerData(struct EReaderTrainerTowerSet * ttdata)",
       "static bool32 CEReaderTool_SaveTrainerTower_r(struct EReaderTrainerTowerSet * ttdata, u8 * buffer)",
       "bool32 CEReaderTool_SaveTrainerTower(struct EReaderTrainerTowerSet * ttdata)",
       "static bool32 CEReaderTool_LoadTrainerTower_r(struct EReaderTrainerTowerSet * ttdata, void *buffer)",
       "bool32 CEReaderTool_LoadTrainerTower(struct EReaderTrainerTowerSet * ttdata)",
       "bool32 ReadTrainerTowerAndValidate(void)")
EXPECTED=[
"INTEGRATED_PHYSICAL_ROUNDTRIP bytes=7944 sectors=30,31 sentinel=1",
"INTEGRATED_SECOND_WRITE_FAILURE first_updated=1 second_old=1 loader_rejects=1 destination_mutated=7944",
"INTEGRATED_RETRY bytes=7944",
"INTEGRATED_FIRST_SENTINEL_FAILURE destination_unchanged=7944",
"INTEGRATED_SECOND_SENTINEL_FAILURE first_copied=3976 second_preserved=3968",
"INTEGRATED_STOCK_STUB returns_false=1",
"PHASE1_DONE gate=FAIL_INCOMPLETE approvals=0"]

def require(v,msg):
    if not v: raise ValueError(msg)

def extract(src,signature):
    require(src.count(signature)==1,"missing/duplicate pinned function "+signature)
    start=src.index(signature); opening=src.find("{",start+len(signature))
    require(opening>start,"missing body "+signature)
    depth=0
    for i in range(opening,len(src)):
        depth+=(src[i]=="{")-(src[i]=="}")
        if depth==0: return src[start:i+1]
    raise ValueError("unterminated "+signature)

def contract(save,tower):
    checks=[("TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",tower),
            ("TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",tower),
            ("TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",tower),
            ("TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",tower),
            ("if (!ValidateTrainerTowerData(ttdata))",tower),
            ("return FALSE;",tower),
            ("return SAVE_STATUS_ERROR;",save),
            ("ProgramFlashSectorAndVerify(sector, savDataBuffer) != 0",save),
            ("if (*(u32 *)(&gSaveDataBuffer.data[0]) != SPECIAL_SECTOR_SENTINEL)",save),
            ("size = SECTOR_COUNTER_OFFSET - 1;",save)]
    for needle,body in checks:
        require(needle in body,"source contract drift "+needle)
    require(save.count("size = SECTOR_COUNTER_OFFSET - 1;")==2,
            "both special-sector copy extents must remain pinned")
    return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--harness",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--log",type=Path,required=True)
    a=ap.parse_args()
    def git(*args):
        return subprocess.check_output(["git","-C",str(a.source),*args],text=True).strip()
    require(git("rev-parse","HEAD")==PIN,"wrong FireRed pin")
    for p,blob in BLOBS.items():
        require(git("hash-object",p)==blob,"blob mismatch "+p)
    source_save=(a.source/"src/save.c").read_text()
    source_tower=(a.source/"src/cereader_tool.c").read_text()
    source_util=(a.source/"src/util.c").read_text()
    util=extract(source_util,"u32 CalcByteArraySum(const u8 * array, u32 size)")
    require("result += array[i];" in util,"original byte sum drift")
    save="\n\n".join(extract(source_save,s) for s in SAVE)
    tower="\n\n".join(extract(source_tower,s) for s in TOWER)
    contract(save,tower)
    edits=[(save.replace("SECTOR_COUNTER_OFFSET - 1","SECTOR_COUNTER_OFFSET - 2",1),tower),
           (save.replace("ProgramFlashSectorAndVerify(sector, savDataBuffer) != 0",
                         "ProgramFlashSectorAndVerify(sector, savDataBuffer) == 0",1),tower),
           (save.replace("SPECIAL_SECTOR_SENTINEL)","0xFFFFFFFF)",1),tower),
           (save,tower.replace("TryReadSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_2, buffer)",
                              "TryReadSpecialSaveSector(29, buffer)",1)),
           (save,tower.replace("TryWriteSpecialSaveSector(SECTOR_ID_TRAINER_TOWER_1, buffer)",
                              "TryWriteSpecialSaveSector(29, buffer)",1)),
           (save,tower.replace("if (!ValidateTrainerTowerData(ttdata))",
                              "if (ValidateTrainerTowerData(ttdata))",1))]
    for i,(s,t) in enumerate(edits):
        require((s,t)!=(save,tower),"ineffective source negative "+str(i))
        try: contract(s,t)
        except ValueError: continue
        raise ValueError("source negative escaped "+str(i))
    harness=a.harness.read_text()
    require(harness.count("PHASE1_PINNED_SPECIAL_SECTOR_FUNCTIONS")==1 and
            harness.count("PHASE1_PINNED_CEREADER_FUNCTIONS")==1,
            "test-only injection markers drift")
    require(harness.count("PHASE1_PINNED_ORIGINAL_BYTE_SUM_FUNCTION")==1,
            "byte-sum injection marker drift")
    require("PHASE1_DONE gate=" in harness,"test harness completion assertion missing")
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); src=root/"combined.c"; exe=root/"combined"
        src.write_text(harness.replace("PHASE1_PINNED_ORIGINAL_BYTE_SUM_FUNCTION",util)
                              .replace("PHASE1_PINNED_SPECIAL_SECTOR_FUNCTIONS",save)
                              .replace("PHASE1_PINNED_CEREADER_FUNCTIONS",tower))
        build=subprocess.run(["cc","-std=gnu11","-O0","-Wall","-Wextra","-Werror","-Wno-sign-compare",
                              str(src),"-o",str(exe)],capture_output=True,text=True)
        require(build.returncode==0,"compiled integration failed "+build.stderr[-5000:])
        run=subprocess.run([str(exe)],capture_output=True,text=True)
        a.log.parent.mkdir(parents=True,exist_ok=True)
        a.log.write_text(run.stdout+run.stderr)
        require(run.returncode==0,"integrated execution failed "+run.stderr[-5000:])
        lines=run.stdout.strip().splitlines()
    require(lines==EXPECTED,"transcript mismatch "+repr(lines))
    mutants=[lines[:-1],
             [s.replace("bytes=7944","bytes=7943") for s in lines],
             [s.replace("loader_rejects=1","loader_rejects=0") for s in lines],
             [s.replace("first_updated=1","first_updated=0") for s in lines],
             [s.replace("destination_unchanged=7944","destination_unchanged=0") for s in lines],
             [s.replace("first_copied=3976","first_copied=3975") for s in lines],
             [s.replace("gate=FAIL_INCOMPLETE","gate=PASS") for s in lines],
             [s.replace("approvals=0","approvals=1") for s in lines]]
    for i,m in enumerate(mutants):
        require(m!=lines and m!=EXPECTED,"evidence negative escaped "+str(i))
    evidence={"evidence_class":"ORIGINAL_FIRERED_CE_READER_PLUS_SPECIAL_SECTOR_HOST_C",
              "pin":PIN,"blobs":BLOBS,
              "extracted_save_sha256":hashlib.sha256(save.encode()).hexdigest(),
              "extracted_cereader_sha256":hashlib.sha256(tower.encode()).hexdigest(),
              "original_function_bodies_unmodified":True,
              "integrated_original_functions":len(SAVE)+len(TOWER)+1,
              "original_util_c_byte_sum_sha256":hashlib.sha256(util.encode()).hexdigest(),
              "test_only_fake_physical_flash":True,
              "original_agbcc_arm_executed":False,"mgba_executed":False,
              "stock_gameplay_reachability_proved":False,
              "source_mutations_rejected":len(edits),
              "transcript_mutations_rejected":len(mutants),
              "trace":lines,"phase1_gate":"FAIL_INCOMPLETE",
              "independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"result":"PASS_HOST_ONLY","source_negatives":len(edits),
                      "trace_negatives":len(mutants),"gate":"FAIL_INCOMPLETE"}))
if __name__=="__main__": main()

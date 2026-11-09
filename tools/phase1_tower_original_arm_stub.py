#!/usr/bin/env python3
"""Original-agbcc linked Trainer Tower stub executed in unchanged native mGBA."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from phase1_tower_compiled_stub import parse_stub, controls
FR="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MG="fd9dc5c2cbf234365068855851107e762fc6211b"
AG="da598c1d918402c42c0c0d7128ba14567f3175e9"
BLOBS={"src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e",
       "src/trainer_tower.c":"732b3f2ed31ed95d6476b9e111d53f759c448d81"}
def need(x,msg):
    if not x: raise ValueError(msg)
def git(path,*args):
    return subprocess.check_output(["git","-C",str(path),*args],text=True).strip()
def check(log):
    lines=[s for s in log.splitlines() if s.startswith("CASE ")]
    need(len(lines)==3,"three native cases required")
    parsed=[]
    for line,input_value in zip(lines,(0,0xffffffff,0x13579bdf)):
        m=re.fullmatch(r"CASE input=0x([0-9a-f]{8}) returned=(\d+) steps=(\d+) result=0x([0-9a-f]{8}) marker=(\w+)",line)
        need(m is not None,"native transcript format")
        inp,ret,steps,result,marker=m.groups()
        need(int(inp,16)==input_value,"native input ordering")
        need(int(ret)==1 and 0<int(steps)<=32,"native Thumb return")
        need(int(result,16)==0 and marker=="unchanged","native result or memory")
        parsed.append({"input":input_value,"steps":int(steps),"result":0})
    summary="SUMMARY native_mgba=true original_agbcc_arm=true linked_stub_false=true synthetic_direct_entry=true stock_gameplay=false flash_transaction=false physical_hardware=false phase1_gate=FAIL_INCOMPLETE approvals=0"
    need(log.count(summary)==1 and "FAIL " not in log,"native scope or assertion")
    return parsed
def negatives(log):
    cases=[
        log.replace("input=0x00000000","input=0x00000001",1),
        log.replace("input=0xffffffff","input=0xeeeeeeee",1),
        log.replace("input=0x13579bdf","input=0x13579bde",1),
        log.replace("returned=1","returned=0",1),
        log.replace("steps=","steps=999",1),
        log.replace("result=0x00000000","result=0x00000001",1),
        log.replace("marker=unchanged","marker=changed",1),
        log.replace("native_mgba=true","native_mgba=false",1),
        log.replace("original_agbcc_arm=true","original_agbcc_arm=false",1),
        log.replace("linked_stub_false=true","linked_stub_false=false",1),
        log.replace("synthetic_direct_entry=true","synthetic_direct_entry=false",1),
        log.replace("stock_gameplay=false","stock_gameplay=true",1),
        log.replace("flash_transaction=false","flash_transaction=true",1),
        log.replace("physical_hardware=false","physical_hardware=true",1),
        log.replace("phase1_gate=FAIL_INCOMPLETE","phase1_gate=PASS",1),
        log.replace("approvals=0","approvals=1",1),
    ]
    for i,changed in enumerate(cases):
        need(changed!=log,"ineffective mutation %d"%i)
        try:check(changed)
        except ValueError:pass
        else:raise AssertionError("negative mutation escaped %d"%i)
    return len(cases)
def main():
    p=argparse.ArgumentParser()
    for key in ("firered","mgba","agbcc","elf","rom","executable","log","output"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args()
    for path,pin in ((a.firered,FR),(a.mgba,MG),(a.agbcc,AG)):
        need(git(path,"rev-parse","HEAD")==pin,"pin drift")
    for path,blob in BLOBS.items():
        need(git(a.firered,"hash-object",path)==blob,"source blob drift "+path)
    nm=subprocess.check_output(["arm-none-eabi-nm",str(a.elf)],text=True)
    matches=re.findall(r"(?m)^([0-9a-fA-F]+)\s+[Tt]\s+ReadTrainerTowerAndValidate$",nm)
    need(len(matches)==1,"linked original stub missing/duplicate")
    address=int(matches[0],16)&~1
    need(0x08000000<=address<0x0A000000,"stub not in linked ROM")
    dis=subprocess.check_output(["arm-none-eabi-objdump","-d",
        "--disassemble=ReadTrainerTowerAndValidate",str(a.elf)],text=True)
    compiled=parse_stub(dis)
    dis_negatives=controls()
    run=subprocess.run([str(a.executable.resolve()),str(a.rom.resolve()),hex(address)],
        text=True,capture_output=True)
    a.log.parent.mkdir(parents=True,exist_ok=True)
    a.log.write_text(run.stdout+run.stderr)
    need(run.returncode==0,"native mGBA failure "+run.stderr[-1500:])
    cases=check(run.stdout)
    rejected=negatives(run.stdout)
    out={"evidence_class":"NATIVE_MGBA_ORIGINAL_AGBCC_STOCK_TOWER_STUB_SYNTHETIC_DIRECT_ENTRY",
         "source_pins":{"firered":FR,"mgba":MG,"agbcc":AG},
         "source_blobs":BLOBS,"compiled_stub":compiled,
         "linked_stub_address":hex(address),
         "elf_sha256":hashlib.sha256(a.elf.read_bytes()).hexdigest(),
         "rom_sha256":hashlib.sha256(a.rom.read_bytes()).hexdigest(),
         "cases":cases,"native_transcript_mutations_rejected":rejected,
         "existing_compiled_disassembly_mutations_rejected":dis_negatives,
         "stock_gameplay_reachability":False,"flash_transaction":False,
         "physical_hardware":False,"phase1_gate":"FAIL_INCOMPLETE",
         "independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PINNED_TOWER_ARM_STUB_NATIVE_PASS cases=3 negatives=%d gate=FAIL_INCOMPLETE approvals=0"%rejected)
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Fail-closed original-agbcc native mGBA map-script reader evidence."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
FR="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MG="fd9dc5c2cbf234365068855851107e762fc6211b"
PS="c32481161c767b25a3425fa9f1f8729927ff3d55"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def symbols(elf):
    nm=subprocess.check_output(["arm-none-eabi-nm",str(elf)],text=True)
    out=[]
    for name in ("MapHeaderGetScriptTable","gMapHeader"):
        matches=re.findall(r"(?m)^([0-9a-fA-F]+)\s+[A-Za-z]\s+"+name+r"$",nm)
        need(len(matches)==1,"missing/duplicate original ELF symbol "+name)
        out.append(int(matches[0],16)&~1)
    return out
def check(log):
    rows=[x for x in log.splitlines() if x.startswith("CASE ")]
    need(len(rows)==4,"native case count changed")
    tags=[(3,0),(2,0),(99,0),(99,1)]
    parsed=[]
    for line,(tag,bad) in zip(rows,tags):
        m=re.fullmatch(r"CASE tag=(\d+) malformed=(\d+) returned=(\d+) steps=(\d+) result=0x([0-9a-f]{8}) table=0x([0-9a-f]{8})",line)
        need(m is not None,"native case format")
        a,b,ret,steps,result,table=(int(m.group(i),16 if i in (5,6) else 10) for i in range(1,7))
        need((a,b)==(tag,bad),"native tag/order")
        need(0<steps<=500,"native step budget")
        if not bad:
            need(ret==1,"valid reader return missing")
            need(result==(table+29 if tag==3 else table+11 if tag==2 else 0),
                 "original reader pointer result")
        parsed.append({"tag":tag,"malformed":bool(bad),"returned":bool(ret),"steps":steps,"result":result,"table":table})
    summary="SUMMARY native_mgba=true original_agbcc_arm=true actual_poryscript_cli_table=true synthetic_direct_entry=true stock_reachability=false physical_flash=false phase1_gate=FAIL_INCOMPLETE approvals=0"
    need(log.count(summary)==1,"native scope changed")
    need("FAIL " not in log,"native assertion failure")
    return parsed
def negatives(log):
    cases=[
        log.replace("tag=3","tag=4",1),
        log.replace("returned=1","returned=0",1),
        log.replace("malformed=1","malformed=0",1),
        log.replace("steps=","steps=999",1),
        log.replace("native_mgba=true","native_mgba=false",1),
        log.replace("original_agbcc_arm=true","original_agbcc_arm=false",1),
        log.replace("actual_poryscript_cli_table=true","actual_poryscript_cli_table=false",1),
        log.replace("stock_reachability=false","stock_reachability=true",1),
        log.replace("phase1_gate=FAIL_INCOMPLETE","phase1_gate=PASS",1),
        log.replace("approvals=0","approvals=1",1),
    ]
    count=0
    for changed in cases:
        need(changed!=log,"ineffective mutation")
        try:check(changed)
        except ValueError:count+=1
        else:raise AssertionError("native transcript mutation escaped")
    need(count==len(cases),"negative count changed")
    return count
def main():
    p=argparse.ArgumentParser()
    for x in ("firered","mgba","poryscript","elf","rom","table","executable","log","output"):
        p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args()
    for root,pin in ((a.firered,FR),(a.mgba,MG),(a.poryscript,PS)):
        need(git(root,"rev-parse","HEAD")==pin,"immutable pin drift")
    need(git(a.firered,"hash-object","src/script.c")==
         "d0433bdda062b138e53d1a1d3184b4566ad7d9dc","reader blob drift")
    reader,header=symbols(a.elf)
    need(0x08000000<=reader<0x0A000000,"linked reader outside ROM")
    need(0x02000000<=header<0x03000000,"linked gMapHeader outside EWRAM")
    cmd=[str(a.executable.resolve()),str(a.rom.resolve()),str(a.table.resolve()),
         hex(reader),hex(header)]
    done=subprocess.run(cmd,text=True,capture_output=True)
    a.log.parent.mkdir(parents=True,exist_ok=True)
    a.log.write_text(done.stdout+done.stderr)
    need(done.returncode==0,"native executable failed "+done.stderr[-1500:])
    parsed=check(done.stdout)
    count=negatives(done.stdout)
    out={"evidence_class":"NATIVE_PINNED_MGBA_ORIGINAL_AGBCC_READER_SYNTHETIC_DIRECT_ENTRY",
         "source_pins":{"firered":FR,"mgba":MG,"poryscript":PS},
         "reader_address":hex(reader),"gMapHeader_address":hex(header),
         "elf_sha256":hashlib.sha256(a.elf.read_bytes()).hexdigest(),
         "rom_sha256":hashlib.sha256(a.rom.read_bytes()).hexdigest(),
         "generated_table_sha256":hashlib.sha256(a.table.read_bytes()).hexdigest(),
         "native_cases":parsed,"transcript_mutations_rejected":count,
         "native_mgba_execution":True,"original_agbcc_arm_execution":True,
         "stock_gameplay_reachability":False,"malformed_table_safe":None,
         "physical_hardware":False,"phase1_gate":"FAIL_INCOMPLETE",
         "independent_approvals":0}
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PINNED_NATIVE_READER_PASS cases=4 negatives=%d gate=FAIL_INCOMPLETE approvals=0"%count)
if __name__=="__main__":main()

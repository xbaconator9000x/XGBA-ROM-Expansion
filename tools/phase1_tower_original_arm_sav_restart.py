#!/usr/bin/env python3
"""Fail-closed test-only .sav disk restart; original mGBA and FireRed APIs only."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from phase1_tower_original_arm_flash import FR, AG, MG, BLOBS, SYMBOLS, git, need, verify
MG_BLOBS = {"src/gba/savedata.c":"fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
            "src/gba/core.c":"6bfc518bb8899205c07d1d0fc091a287cb42f874",
            "src/gba/gba.c":"c30bd943909dc00df0b5b9932e6d9ddb6e1c404e"}
LINES = ("PERSIST partial_sav_bytes=131072","PERSIST complete_sav_bytes=131072",
         "PERSIST fresh_partial_sector30=1 sector31=255",
         "PERSIST fresh_complete_sector30=1 sector31=1")
SCOPE = ("PERSIST_SCOPE original_mgba_clone=true fresh_core=true original_arm_reader=true "
         "synthetic_snapshot=true automatic_writeback=false power_loss=false "
         "physical_hardware=false stock_gameplay=false phase1_gate=FAIL_INCOMPLETE approvals=0")
def check_log(log):
    verify(log)
    need(tuple(x for x in log.splitlines() if x.startswith("PERSIST ")) == LINES,
         "save and restart stages")
    need(log.count(SCOPE)==1,"scope")
    calls=re.findall(r"^ARM (\w+) steps=(\d+) result=0x([0-9a-f]{8})$",log,re.M)[7:]
    need(tuple(x[0] for x in calls)==("FreshInitIntrHandlers","FreshCheckForFlashMemory",
         "FreshReadSector30","FreshReadSector31","FreshInitIntrHandlers",
         "FreshCheckForFlashMemory","FreshReadSector30","FreshReadSector31"),"original ARM restarts")
    need(all(0<int(x[1])<=12000000 for x in calls),"step bounds")
    need(tuple(int(calls[i][2],16) for i in (2,3,6,7))==(1,255,1,1),"reader statuses")
def matches(data,offset,sector):
    return (data[offset:offset+4]==b"\x9d\xb3\x00\x00" and
            data[offset+4:offset+4096]==bytes((sector*13+i*7)&255 for i in range(4092)))
def check_bytes(p,c):
    need(len(p)==len(c)==131072,"save lengths")
    need(matches(p,0x1e000,30) and matches(c,0x1e000,30),"sector30")
    need(p[0x1f000:]==b"\xff"*4096,"partial sector31 erased")
    need(matches(c,0x1f000,31),"complete sector31")
    need(p[:0x1f000]==c[:0x1f000],"unchanged lower sectors")
def main():
    ap=argparse.ArgumentParser()
    for name in ("firered","agbcc","mgba","elf","rom","executable","sav","log","output"):
        ap.add_argument("--"+name,required=True,type=Path)
    a=ap.parse_args()
    for root,sha in ((a.firered,FR),(a.agbcc,AG),(a.mgba,MG)):
        need(git(root,"rev-parse","HEAD")==sha,"pin drift")
    for path,sha in BLOBS.items():
        need(git(a.firered,"hash-object",path)==sha,"FireRed source drift")
    for path,sha in MG_BLOBS.items():
        need(git(a.mgba,"hash-object",path)==sha,"mGBA source drift")
    nm=subprocess.check_output(["arm-none-eabi-nm",str(a.elf)],text=True)
    addresses=[]
    for symbol in SYMBOLS:
        matches_=re.findall(r"(?m)^([0-9a-fA-F]+)\s+[a-zA-Z]\s+"+re.escape(symbol)+r"$",nm)
        need(len(matches_)==1,"linked symbol "+symbol)
        addresses.append(int(matches_[0],16))
    a.sav.parent.mkdir(parents=True,exist_ok=True)
    cmd=[str(a.executable.resolve()),str(a.rom.resolve())]+[hex(x) for x in addresses]+[str(a.sav.resolve())]
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=900)
    a.log.parent.mkdir(parents=True,exist_ok=True)
    a.log.write_text(proc.stdout+proc.stderr)
    need(proc.returncode==0,"native failed "+(proc.stdout+proc.stderr)[-1200:])
    check_log(proc.stdout)
    partial=Path(str(a.sav)+".partial")
    p,c=partial.read_bytes(),a.sav.read_bytes()
    check_bytes(p,c)
    mutations=[proc.stdout.replace("fresh_core=true","fresh_core=false",1),
      proc.stdout.replace("automatic_writeback=false","automatic_writeback=true",1),
      proc.stdout.replace("power_loss=false","power_loss=true",1),
      proc.stdout.replace("phase1_gate=FAIL_INCOMPLETE","phase1_gate=PASS",1),
      proc.stdout.replace("PERSIST fresh_partial_sector30=1 sector31=255",
                          "PERSIST fresh_partial_sector30=1 sector31=1",1),
      proc.stdout.replace("ARM FreshReadSector31","ARM WrongReader",1),
      proc.stdout.replace("PERSIST complete_sav_bytes=131072",
                          "PERSIST complete_sav_bytes=65536",1)]
    rejected=0
    for changed in mutations:
        need(changed!=proc.stdout,"ineffective transcript mutation")
        try: check_log(changed)
        except ValueError: rejected+=1
        else: raise AssertionError("transcript negative escaped")
    variants=[(p[:-1],c),(p,c[:-1]),(p[:0x1f000]+b"\x00"+p[0x1f001:],c),
              (p,c[:0x1f000]+b"\xff"+c[0x1f001:]),
              (p[:0x1e000]+b"\x00"+p[0x1e001:],c)]
    for x,y in variants:
        try: check_bytes(x,y)
        except ValueError: rejected+=1
        else: raise AssertionError("save byte negative escaped")
    out={"evidence_class":"EXPERIMENTAL_ORIGINAL_ARM_MGBA_DISK_SAV_RESTART",
      "pins":{"firered":FR,"agbcc":AG,"mgba":MG},"mgba_blobs":MG_BLOBS,
      "rom_sha256":hashlib.sha256(a.rom.read_bytes()).hexdigest(),
      "partial_sav_sha256":hashlib.sha256(p).hexdigest(),
      "complete_sav_sha256":hashlib.sha256(c).hexdigest(),
      "native_transcript_sha256":hashlib.sha256(proc.stdout.encode()).hexdigest(),
      "fresh_mgba_cores":2,"original_arm_restart_reads":4,
      "negative_controls_rejected":rejected,"synthetic_snapshot":True,
      "automatic_writeback":False,"power_loss":False,"stock_gameplay":False,
      "physical_hardware":False,"phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    partial.unlink();a.sav.unlink()
    print("ORIGINAL_ARM_SAV_RESTART_PASS restarts=2 negatives=%d gate=FAIL_INCOMPLETE approvals=0"%rejected)
if __name__=="__main__":main()

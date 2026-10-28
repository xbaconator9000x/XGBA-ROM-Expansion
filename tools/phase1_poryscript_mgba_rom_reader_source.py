#!/usr/bin/env python3
"""Pinned FireRed -> mGBA ROM data-read boundary. SOURCE ONLY."""
import argparse,json,re,subprocess
from pathlib import Path
FR="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MG="fd9dc5c2cbf234365068855851107e762fc6211b"
FILES={"src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
"src/gba/memory.c":"aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
"include/mgba/internal/gba/memory.h":"0aad912613e726560d06bbdbf6061986e69e5842"}
def need(x,s):
    if not x: raise ValueError(s)
def fn(s,n):
    matches=list(re.finditer(r"\b"+n+r"\s*\([^;{}]*\)\s*\{",s))
    need(len(matches)==1,"function drift "+n)
    start=matches[0].start(); depth=0
    for i in range(s.index("{",start),len(s)):
        depth+=(s[i]=="{")-(s[i]=="}")
        if depth==0: return s[start:i+1],start,i+1
    raise ValueError("unclosed "+n)
def verify(fr,mg,h):
    sections=[
      (fn(fr,"MapHeaderGetScriptTable")[0],
       ["mapScripts += 5;","if (*mapScripts == 0)","return T2_READ_PTR(mapScripts);"]),
      (fn(fr,"MapHeaderCheckScriptTable")[0],
       ["if (!varIndex1)","ptr += 4;","return T2_READ_PTR(ptr);"]),
      (fn(mg,"GBALoad8")[0],
       ["Out of bounds ROM Load8","value = ((address >> 1) >> ((address & 1) * 8)) & 0xFF;"]),
      (fn(mg,"GBALoad16")[0],
       ["Out of bounds ROM Load16","value = (address >> 1) & 0xFFFF;"]),
      (fn(mg,"GBALoad32")[0],["LOAD_CART;","return ROR(value, rotate);"]),
      (fn(mg,"GBASetActiveRegion")[0],["_deadbeef","coreCrashed"]),
      (mg.split("#define LOAD_CART",1)[1].split("#define LOAD_SRAM",1)[0],
       ["(GBA_SIZE_ROM0 - 4)","Out of bounds ROM Load32",
        "value |= (((address & ~3) + 2) >> 1) << 16;"]),
      (h,["GBA_SIZE_ROM0 = 0x02000000"])]
    for i,(s,keys) in enumerate(sections):
        for key in keys: need(key in s,"boundary drift %d: %s"%(i,key))
    need(fn(fr,"MapHeaderCheckScriptTable")[0].count("T1_READ_16(ptr)")==2,
         "conditional 16-bit count drift")
    need(fn(mg,"GBALoad16")[0].count("value = (address >> 1) & 0xFFFF;")==3,
         "three ROM16 out-of-range fallback branches drift")
def mutate(fr,mg,h):
    cases=[
      ("fr","MapHeaderGetScriptTable","mapScripts += 5;","mapScripts += 4;"),
      ("fr","MapHeaderGetScriptTable","if (*mapScripts == 0)","if (*mapScripts == 255)"),
      ("fr","MapHeaderCheckScriptTable","ptr += 4;","ptr += 2;"),
      ("fr","MapHeaderCheckScriptTable","if (!varIndex1)","if (varIndex1 == 65535)"),
      ("mg","GBALoad8","Out of bounds ROM Load8","Unchecked ROM Load8"),
      ("mg","GBALoad16","value = (address >> 1) & 0xFFFF;","value = 0;"),
      ("mg","GBALoad32","LOAD_CART;","LOAD_BAD;"),
      ("mg","GBASetActiveRegion","_deadbeef","memory->rom")]
    for i,(which,name,old,new) in enumerate(cases):
        s=fr if which=="fr" else mg
        b,a,z=fn(s,name);need(old in b,"negative target absent")
        changed=s[:a]+b.replace(old,new,1)+s[z:]
        try: verify(changed if which=="fr" else fr,changed if which=="mg" else mg,h)
        except ValueError: continue
        raise AssertionError("escaped mutation %d"%i)
    for i,(old,new) in enumerate([
      ("(GBA_SIZE_ROM0 - 4)","(GBA_SIZE_ROM0 - 8)"),
      ("Out of bounds ROM Load32","Unchecked ROM Load32"),
      ("value |= (((address & ~3) + 2) >> 1) << 16;","value |= 0xFFFF0000;")],8):
        need(old in mg,"macro negative target absent")
        try: verify(fr,mg.replace(old,new,1),h)
        except ValueError: continue
        raise AssertionError("escaped macro mutation %d"%i)
    try: verify(fr,mg,h.replace("GBA_SIZE_ROM0 = 0x02000000","GBA_SIZE_ROM0 = 0x04000000",1))
    except ValueError: pass
    else: raise AssertionError("escaped aperture mutation")
    return 12
def pinned(root,pin,paths):
    def git(*a):return subprocess.check_output(["git","-C",str(root),*a],text=True).strip()
    need(git("rev-parse","HEAD")==pin,"commit pin drift")
    result={}
    for path in paths:
        need(git("hash-object",path)==FILES[path],"blob drift "+path)
        result[path]=(root/path).read_text()
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--firered",required=True,type=Path)
    p.add_argument("--mgba",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    fr=pinned(a.firered,FR,["src/script.c"])["src/script.c"]
    mg=pinned(a.mgba,MG,["src/gba/memory.c","include/mgba/internal/gba/memory.h"])
    verify(fr,mg["src/gba/memory.c"],mg["include/mgba/internal/gba/memory.h"])
    n=mutate(fr,mg["src/gba/memory.c"],mg["include/mgba/internal/gba/memory.h"])
    out={"evidence":"SOURCE_ONLY","firered":FR,"mgba":MG,"blobs":FILES,
         "negative_controls":n,"native_mgba_execution":False,
         "phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PINNED_ROM_READER_SOURCE_PASS negatives=%d"%n)
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Architecture-level parsing of assembly, linker scripts, and build recipes.

Source-anchored assembly/linker/build syntax relations, not macro expansion or
machine-code execution. Unsupported generated targets are explicitly recorded.
"""
import collections,csv,gzip,hashlib,json,re,sys
from pathlib import Path
ROOT=Path("upstream");OUT=Path("audit-output")
EXT={".s": "GBA_OR_HOST_ASSEMBLY",".asm":"GBA_OR_HOST_ASSEMBLY",".inc":"ASM_OR_MACRO_INCLUDE",
 ".ld":"LINKER_SCRIPT",".mk":"MAKE_RECIPE",".cmake":"CMAKE_RECIPE",
 ".sh":"SHELL_SCRIPT",".pory":"PORYSCRIPT_INPUT",
 ".pro":"QT_PROJECT",".pri":"QT_PRI",
 ".def":"DEFINITION_LIST",".in":"BUILD_TEMPLATE"}
BASENAMES={"Makefile":"MAKE_RECIPE","makefile":"MAKE_RECIPE",
           "GNUmakefile":"MAKE_RECIPE","CMakeLists.txt":"CMAKE_RECIPE",
           "Dockerfile":"DOCKER_RECIPE"}
DIRECTIVE=re.compile(r"^\s*\.(macro|endm|section|include|incbin|global|globl|extern|align|balign|p2align|4byte|2byte|byte|word|long|set|equ|pool|ltorg|thumb|arm)\b",re.I)
LABEL=re.compile(r"^\s*([A-Za-z_.$][\w.$]*)(?:::|:)(?!\w)")
MAKE_VARIABLE=re.compile(r"^\s*([A-Za-z_][\w.-]*)\s*(?::=|\?=|\+=|=)\s*(.*)")
MAKE_TARGET=re.compile(r"^([A-Za-z_./%$(){}\-][^:=]*):\s*(.*)")
LD_MEMORY=re.compile(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*,\s*LENGTH\s*=\s*([0-9a-fA-FxXKMG]+)")
INCLUDE=re.compile(r'(?:^\s*(?:\.include|\.incbin|INCLUDE|include|-include)\s+|#include\s+)[<"]?([A-Za-z0-9_./\-$(){}]+)',re.I)
IMPORT_LIT=re.compile(r'\b(?:INCBIN_[A-Za-z0-9_]+|INCLUDE_[A-Za-z0-9_]+|incbin)\s*\(\s*"([^"]+)"\s*\)')
NUMADDR=re.compile(r'(?<!\w)0x0[89A-F][0-9A-Fa-f]{6}(?!\w)')
RECORD=["repo","path","blob_sha","language","line","kind","name","value","scope","resolution"]
def gitsha(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def main():
 with gzip.open(OUT/"tracked_file_manifest.csv.gz","rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 assert len(rows)==14834
 files=collections.defaultdict(set)
 for r in rows:files[r["repo"]].add(r["path"])
 count=collections.Counter();kind=collections.Counter();byscope=collections.Counter();symbols=set()
 with gzip.open(OUT/"asm_build_semantic_sites.csv.gz","wt",encoding="utf-8",newline="") as out, \
      gzip.open(OUT/"asm_build_file_coverage.csv.gz","wt",encoding="utf-8",newline="") as mf:
  w=csv.DictWriter(out,fieldnames=RECORD);w.writeheader()
  fw=csv.writer(mf);fw.writerow(["repo","path","blob_sha","category","language","site_count","semantic_status"])
  for n,r in enumerate(rows,1):
   repo,path,blob=r["repo"],r["path"],r["blob_sha"]
   typ=BASENAMES.get(Path(path).name,EXT.get(Path(path).suffix.lower()))
   if not typ:continue
   target=ROOT/repo.split("/")[-1]/path
   if target.is_symlink():
    fw.writerow([repo,path,blob,r["category"],typ,0,"SYMLINK_NOT_BUILD_PARSED"])
    count["symlink"]+=1
    continue
   b=target.read_bytes()
   if gitsha(b)!=blob:raise RuntimeError(f"Stale source for {repo}/{path}")
   if b"\0" in b:
    fw.writerow([repo,path,blob,r["category"],typ,0,"BINARY_CONTAINING_NOT_BUILD_PARSED"])
    count["binary_like"]+=1
    continue
   count[typ]+=1
   sites=0;macro_scope=""
   for i,line in enumerate(b.decode("utf-8","surrogateescape").splitlines(),1):
    entries=[]
    m=DIRECTIVE.match(line)
    if m:
     word=m.group(1).lower();arg=line[m.end():].strip()
     if word=="macro":macro_scope=arg.split()[0] if arg else ""
     if word=="endm":macro_scope=""
     entries.append(("directive",word,arg[:140],""))
     if word in ("global","globl","extern"):entries.append(("symbol_binding",word,arg[:140],""))
    ml=LABEL.match(line)
    if ml:
     key=ml.group(1);entries.append(("symbol_definition",key,"", ""))
     symbols.add((repo,path,key))
    v=MAKE_VARIABLE.match(line)
    if v and typ in ("MAKE_RECIPE","BUILD_TEMPLATE","QT_PRI","QT_PROJECT"):
     entries.append(("build_variable",v.group(1),v.group(2)[:140],""))
    t=MAKE_TARGET.match(line)
    if t and typ=="MAKE_RECIPE":
     entries.append(("make_target",t.group(1).strip(),t.group(2)[:140],"UNRESOLVED"))
    ld=LD_MEMORY.search(line)
    if ld:
     entries.append(("linker_memory_region",ld.group(1),
        "flags="+ld.group(2)+";ORIGIN="+ld.group(3)+";LENGTH="+ld.group(4),""))
    im=INCLUDE.search(line)
    if im:
     dep=im.group(1);poss=[dep,str(Path(path).parent/dep)]
     resolved=sorted(set(p for p in poss if p in files[repo]))
     entries.append(("include_or_binary_embed",dep,";".join(resolved),
       "PATH_CANDIDATE" if resolved else "UNRESOLVED_IN_SOURCE"))
    for inc in IMPORT_LIT.finditer(line):
     dep=inc.group(1)
     matches=[p for p in (dep,str(Path(path).parent/dep)) if p in files[repo]]
     entries.append(("source_asset_incbin",dep,";".join(sorted(set(matches))),
       "PATH_CANDIDATE" if matches else "UNRESOLVED_IN_SOURCE"))
    for addr in NUMADDR.findall(line):
     entries.append(("hardcoded_rom_window_address",addr,"",""))
    for tkind,name,value,resolution in entries:
     w.writerow({"repo":repo,"path":path,"blob_sha":blob,"language":typ,"line":i,
       "kind":tkind,"name":name,"value":value,
       "scope":macro_scope,"resolution":resolution})
     sites+=1;kind[tkind]+=1
   fw.writerow([repo,path,blob,r["category"],typ,sites,"SYNTACTIC_BUILD_ASM_INDEXED_UNREVIEWED"])
   if n%500==0:
    folder=OUT/"asm_checkpoints";folder.mkdir(exist_ok=True)
    (folder/f"tracked_{n:05d}.json").write_text(json.dumps({
      "manifest_processed":n,"build_semantic_signoffs":0})+"\n")
 result={"build_asm_files_indexed":sum(count[k] for k in EXT.values())+sum(count[k] for k in BASENAMES.values()),
  "file_types":dict(count),"sites_by_kind":dict(kind),"symbol_definition_candidates":len(symbols),
  "independent_semantic_reviews":0,"phase1_mapping_complete":False,
  "limitations":["Macros and CPP conditionals have not been expanded; identifiers are syntax candidates.",
    "Linker symbol order and unresolved build variable interpolation need actual build evaluation.",
    "ASM source bytecode references are not relocatable external resources without ABI review."]}
 (OUT/"asm_build_semantic_summary.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()

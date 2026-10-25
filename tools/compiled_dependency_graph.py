#!/usr/bin/env python3
"""Use REAL GCC preprocessing and GNU nm output for pinned mGBA dependencies.

Produces build-configuration-specific, compiler-confirmed header closures and
static-library object-symbol relationships. Distinguishes these from speculative
source-file name matching and from runtime indirect callback execution.
"""
from __future__ import annotations
import collections,csv,hashlib,json,os,re,shlex,subprocess
from pathlib import Path
ROOT=Path("upstream/mgba").resolve()
BUILD=Path("build-mgba").resolve()
OUT=Path("compiler-evidence")
SHA="fd9dc5c2cbf234365068855851107e762fc6211b"
HEADERS=("object_source","source_blob_sha","dependency_path","dependency_blob_sha",
         "dependency_kind","compiler_configuration","resolution")
RELOCS=("archive","consumer_object","consumer_source_candidate","referenced_symbol",
        "symbol_provider_object","provider_source_candidate","provider_kind",
        "provider_count","resolution")
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def tracked_tree():
 raw=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r","-z","HEAD"])
 result={}
 for e in raw.split(b"\0"):
  if not e:continue
  attrs,p=e.split(b"\t",1)
  mode,kind,sha=attrs.decode().split()
  if kind=="blob":result[p.decode("utf-8","surrogateescape")]=sha
 return result
def decode_make_deps(output):
 # GCC dependency -MM format: target: source headers \newline...
 text=output.replace("\\\n"," ").replace("\\\r\n"," ")
 if ":" not in text:raise RuntimeError("No GCC Make dependency target")
 return shlex.split(text.split(":",1)[1])
def extraction_arg(cmd):
 trimmed=[];i=0
 # Strip object-output and depfile-output options while keeping ALL actual -I
 # and -D features and target ABI flags from the real compilation unit.
 taking={"-o","-MF","-MT","-MQ"}
 skipping={"-c","-MD","-MMD","-MP"}
 while i<len(cmd):
  a=cmd[i]
  if a in taking:i+=2;continue
  if a in skipping:i+=1;continue
  if a.startswith(("-MF","-MT","-MQ")) and len(a)>3:
   i+=1;continue
  trimmed.append(a);i+=1
 return [trimmed[0],"-MM","-MT","XGBA_DEPENDENCY_TARGET"]+trimmed[1:]
def source_path(f):
 p=Path(f).resolve()
 if p.is_relative_to(ROOT):return p.relative_to(ROOT).as_posix()
 if p.is_relative_to(BUILD):return "GENERATED/"+p.relative_to(BUILD).as_posix()
 return "EXTERNAL/"+p.name
def parse_nm_line(line):
 # GNU nm --print-file-name archive.a:object.o:00000000 T symbol
 m=re.match(r"^(.+?\.a):([^:]+):\s*(?:[0-9A-Fa-f]+\s+)?([A-Za-z?])\s+(\S+)\s*$",line)
 if not m:return None
 return m.group(1),m.group(2),m.group(3),m.group(4)
def main():
 OUT.mkdir(exist_ok=True)
 assert subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()==SHA
 tracked=tracked_tree()
 comp=json.loads((BUILD/"compile_commands.json").read_text())
 if len(comp)<30:raise RuntimeError("Compilation database missing main GBA core")
 object_to_src=collections.defaultdict(set);settings=collections.Counter()
 pre_errors=[];deps_seen=0;compiler_units=set();unique_headers=set();generated=0
 with (OUT/"compiler_proven_include_closure.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader()
  for c in comp:
   src=source_path(c["file"])
   cmd=c.get("arguments") or shlex.split(c["command"])
   arg=extraction_arg(cmd)
   cwd=Path(c["directory"])
   obj=(cwd/c.get("output","")).resolve()
   object_to_src[obj.name].add(src)
   for token in cmd:
    if token.startswith(("-D","-std=")):settings[token]+=1
   cp=subprocess.run(arg,cwd=cwd,text=True,capture_output=True,timeout=40)
   if cp.returncode!=0:
    pre_errors.append({"source":src,"stderr":cp.stderr[-900:],"returncode":cp.returncode})
    continue
   compiler_units.add(src)
   for dep in decode_make_deps(cp.stdout):
    p=(cwd/dep).resolve()
    if p.is_relative_to(ROOT):
     relative=p.relative_to(ROOT).as_posix()
     sh=tracked.get(relative,"")
     if not sh:
      classification="UNTRACKED_GENERATED_IN_SOURCE_TREE"
     else:
      data=p.read_bytes()
      if gitsha(data)!=sh:
       raise RuntimeError("Compiler selected header differs from pinned blob "+relative)
      classification="COMPILER_SELECTED_TRACKED_HEADER"
      unique_headers.add(relative)
    elif p.is_relative_to(BUILD):
     relative="GENERATED/"+p.relative_to(BUILD).as_posix();sh=""
     classification="BUILD_GENERATED_HEADER";generated+=1
    else:
     relative="EXTERNAL/"+p.name;sh=""
     classification="THIRD_PARTY_OUTSIDE_SOURCE_TREE"
    if relative==src:continue
    deps_seen+=1
    w.writerow({"object_source":src,"source_blob_sha":tracked.get(src,""),
     "dependency_path":relative,"dependency_blob_sha":sh,
     "dependency_kind":classification,
     "compiler_configuration":"headless-pinned-mgba-debug-static",
     "resolution":"COMPILE_PREPROCESSOR_PROVEN_TRANSITIVE_HEADER"})
 if pre_errors:raise RuntimeError("GCC include closure failed for "+str(pre_errors[:5]))
 if len(compiler_units)!=len(comp):
  # CMake sometimes builds the same source twice under differing targets.
  if len(compiler_units)<int(len(comp)*0.7):
   raise RuntimeError("Compilation units were not adequately resolved")
 archives=list(BUILD.rglob("*.a"))
 defs=collections.defaultdict(list);undef=[]
 for lib in archives:
  for flags,mode in [(["-A","-g","--defined-only"],"definition"),
                     (["-A","-u"],"undefined")]:
   output=subprocess.check_output(["nm",*flags,str(lib)],text=True,stderr=subprocess.DEVNULL)
   for line in output.splitlines():
    z=parse_nm_line(line)
    if not z:continue
    archive,obj,kind,name=z
    if mode=="definition":defs[name].append((archive,obj,kind))
    else:undef.append((archive,obj,kind,name))
 summary=collections.Counter()
 with (OUT/"compiled_symbol_reference_edges.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=RELOCS);w.writeheader()
  for archive,obj,_,name in undef:
   providers=defs.get(name,[])
   if len(providers)>32:
    summary["symbol_multi_provider_overflow"]+=1
    continue
   for l,other,kind in providers:
    if (l,obj)==(archive,other):continue
    consumer_src=";".join(sorted(object_to_src[obj]))
    provider_src=";".join(sorted(object_to_src[other]))
    # Linking a symbol may refer to a function or global data; T/W represent
    # code and named functions and B/D/R/etc represent data.
    classification=("LINK_OBJECT_CODE_SYMBOL_CANDIDATE" if kind.upper() in ("T","W")
                    else "LINK_OBJECT_DATA_OR_OTHER")
    w.writerow({"archive":archive,"consumer_object":obj,
      "consumer_source_candidate":consumer_src,"referenced_symbol":name,
      "symbol_provider_object":other,"provider_source_candidate":provider_src,
      "provider_kind":kind,"provider_count":len(providers),
      "resolution":classification})
    summary[classification]+=1
 result={
  "pinned_commit":SHA,"compiler_inputs":len(comp),
  "compiler_source_units_succeeded":len(compiler_units),
  "pinned_headers_selected_by_preprocessor":len(unique_headers),
  "compiled_transitive_header_edges":deps_seen,
  "build_generated_header_edges":generated,
  "linked_symbol_edge_categories":dict(summary),
  "static_libraries_inspected":len(archives),
  "configuration":"headless-mGBA; Qt/SDL/scripting-disabled; standard GNU C/C++ flags",
  "compiler_errors":pre_errors,
  "semantic_signoffs":0,"phase1_mapping_complete":False,
  "important_limits":["-MM proves active transitive preprocessor inclusion, not direct source include.",
    "Object symbol references are compiler/linker-visible name connections but not definite runtime calls.",
    "CMake build covers only 173 configured units, not the whole mGBA repository.",
    "Static libraries might contain unresolved externs that are satisfied by the final frontend or platform.",
    "mGBA host compilation is not a runtime XGBA expansion test."]}
 (OUT/"compiled_dependency_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()

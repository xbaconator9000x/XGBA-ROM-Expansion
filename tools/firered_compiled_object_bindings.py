#!/usr/bin/env python3
"""Compiler-produced object-symbol binding graph for classic/modern pinned FireRed.

Uses ACTUAL arm-none-eabi-nm on all compiled .o files (not AST name matching).
A unique provider candidate does not prove linker selection where weak symbols,
archives or linker scripts apply. Source paths are Git-blob-pinned when recoverable.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered").resolve()
OUT=Path("firered-variant-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BUILDS={"original_agbcc":"build/firered","modern_gcc":"build/firered_modern"}
REFS=["gScriptCmdTable","gBattleScriptingCommandsTable","gSongTable",
      "gMonFrontPicTable","gMapGroups","gSaveBlock1Ptr"]
COLS=["variant","consumer_object","consumer_source_candidate",
      "consumer_source_blob_sha","undefined_symbol","provider_status",
      "provider_object","provider_source_candidate","provider_source_blob_sha",
      "provider_symbol_type","candidate_provider_count"]
def tree():
 p=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r","-z","HEAD"])
 tracked={}
 for row in p.split(b"\0"):
  if not row:continue
  desc,name=row.split(b"\t",1);mode,typ,sha=desc.decode().split()
  if typ=="blob":tracked[name.decode("utf-8","surrogateescape")]=sha
 return tracked
def nm(rows,defined):
 result=collections.defaultdict(list)
 if not rows:return result
 for i in range(0,len(rows),90):
  chunk=rows[i:i+90]
  cmd=["arm-none-eabi-nm","-A","--defined-only" if defined else "--undefined-only"]+[str(f) for f in chunk]
  raw=subprocess.check_output(cmd,text=True,errors="replace")
  for line in raw.splitlines():
   if ":" not in line:continue
   path,rest=line.split(":",1)
   m=re.match(r"^\s*(?:[0-9A-Fa-f]+\s+)?([a-zA-Z?])\s+(\S+)\s*$",rest)
   if not m:continue
   typ,symbol=m.groups()
   result[path].append((typ,symbol))
 return result
def source_from_obj(objroot,obj,tracked):
 path=obj.relative_to(objroot).with_suffix("")
 options=[str(path)+ext for ext in (".c",".s",".S",".cpp",".cc")]
 found=[p for p in options if p in tracked]
 if len(found)==1:return found[0],tracked[found[0]],"UNIQUE_STEM_SOURCE_CANDIDATE"
 if len(found)>1:return "","", "AMBIGUOUS_STEM_SOURCE_CANDIDATE"
 return "","", "GENERATED_OR_NONMATCHING_OBJECT_SOURCE"
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Wrong immutable FireRed commit")
 tracked=tree();counts=collections.Counter();report={}
 with gzip.open(OUT/"compiled_object_symbol_dependencies.csv.gz","wt",encoding="utf-8",newline="") as fh, \
      gzip.open(OUT/"compiled_object_source_provenance.csv.gz","wt",encoding="utf-8",newline="") as srcf:
  w=csv.DictWriter(fh,fieldnames=COLS);w.writeheader()
  p=csv.writer(srcf);p.writerow(["variant","object","source_candidate","source_blob_sha","source_resolution",
                                  "defined_global_symbols","undefined_symbols"])
  for variant,dirname in BUILDS.items():
   objroot=(ROOT/dirname).resolve()
   if not objroot.is_dir():raise RuntimeError("Build output absent: "+str(objroot))
   files=sorted(objroot.rglob("*.o"))
   if len(files)<100:raise RuntimeError("Too few compiled object files in "+dirname)
   defined=nm(files,True);undefined=nm(files,False)
   global_providers=collections.defaultdict(list)
   object_sources={}
   for obj in files:
    k=str(obj)
    src,sha,status=source_from_obj(objroot,obj,tracked)
    object_sources[k]=(src,sha,status)
    if src:
     raw=(ROOT/src).read_bytes()
     blob=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
     if blob!=sha:
      # CRLF palettes aren't source .c/.s; still fail if any transform observed.
      raise RuntimeError("Source object path changed from pinned Git blob: "+src)
    defs=defined.get(k,[])
    refs=undefined.get(k,[])
    for typ,symbol in defs:
     if typ.isupper() and typ.upper()!="A":global_providers[symbol].append((k,typ))
    p.writerow([variant,obj.relative_to(ROOT),src,sha,status,
                sum(t.isupper() for t,s in defs),len(refs)])
    counts[(variant,"objects")]+=1
    counts[(variant,"source_identified" if src else "source_generated_or_unknown")]+=1
   for obj in files:
    k=str(obj);src,sha,status=object_sources[k]
    for typ,symbol in undefined.get(k,[]):
     choices=[(n,t) for n,t in global_providers.get(symbol,[]) if n!=k]
     providers=len(choices)
     if providers==1:state="UNIQUE_COMPILED_GLOBAL_PROVIDER_CANDIDATE"
     elif providers>1:state="MULTIPLE_OR_WEAK_COMPILED_PROVIDER_CANDIDATES"
     else:state="LINKER_ARCHIVE_GENERATED_OR_EXTERNAL_UNRESOLVED"
     counts[(variant,state)]+=1
     # Keep one row even if no provider. Expand up to 20 ambiguous provider candidates.
     for target,ktype in (choices[:20] if choices else [("","")]):
      ps,psha,pstatus=object_sources.get(target,("","",""))
      w.writerow({"variant":variant,"consumer_object":obj.relative_to(ROOT),
        "consumer_source_candidate":src,"consumer_source_blob_sha":sha,
        "undefined_symbol":symbol,"provider_status":state,
        "provider_object":Path(target).relative_to(ROOT) if target else "",
        "provider_source_candidate":ps,"provider_source_blob_sha":psha,
        "provider_symbol_type":ktype,"candidate_provider_count":providers})
   report[variant]={"object_files":counts[(variant,"objects")],
     "source_matched_objects":counts[(variant,"source_identified")],
     "objects_without_unique_tracked_source":counts[(variant,"source_generated_or_unknown")],
     "unique_global_provider_symbols":sum(len(v)==1 for v in global_providers.values()),
     "ambiguous_global_provider_symbols":sum(len(v)>1 for v in global_providers.values()),
     "undefined_symbol_sites":sum(len(v) for v in undefined.values()),
     "unique_provider_reference_sites":counts[(variant,"UNIQUE_COMPILED_GLOBAL_PROVIDER_CANDIDATE")],
     "ambiguous_provider_reference_sites":counts[(variant,"MULTIPLE_OR_WEAK_COMPILED_PROVIDER_CANDIDATES")],
     "external_linker_archive_reference_sites":counts[(variant,"LINKER_ARCHIVE_GENERATED_OR_EXTERNAL_UNRESOLVED")]}
 if not all(v["object_files"]>100 for v in report.values()):
  raise RuntimeError("Insufficient built source coverage")
 result={"pinned_revision":PIN,"configurations":report,
   "source_reference_level":"ACTUAL_GNU_NM_DEFINED_AND_UNDEFINED_OBJECT_SYMBOLS",
   "source_hash_integrity_checked":True,
   "selected_linker_provider_proved":False,
   "runtime_dispatch_coverage":False,
   "whole_file_semantic_signoffs":0,"phase1_mapping_complete":False,
   "caveats":[
    "Undefined external symbols can be provided by linker scripts, hidden runtime archives or alias definitions.",
    "Unique object symbol-name matching is not definitive archive/member link selection.",
    "Indirect function pointers and relocation target addends are not recovered from nm symbol names.",
    "This is compiled classic/modern FireRed only, not arbitrary ROM forks.",
    "Unrecognized generated objects are explicitly separated from pinned source path proof."
   ]}
 OUT.mkdir(exist_ok=True)
 (OUT/"compiled_object_binding_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k!="caveats"},indent=2))
if __name__=="__main__":main()

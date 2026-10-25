#!/usr/bin/env python3
"""Refine candidate C/C++/Go/Python call graph using translation-unit linkage.

Does not pretend to be a compiler linker: keeps C++ overload, macros, indirect
calls, imported language symbols, and external references as unresolved unless
local scope and source evidence justify a narrower classification.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,re,os,subprocess
from pathlib import Path
ROOT=Path("upstream")
OUT=Path("audit-output")
LANG={".c":"c",".h":"c",".cpp":"cpp",".cc":"cpp",".cxx":"cpp",
      ".hpp":"cpp",".hh":"cpp",".hxx":"cpp",".go":"go",".py":"python"}
COLS=["repo","caller_file","caller_blob_sha","caller_scope","caller_line",
      "callee_name","candidate_count_original","candidate_count_linkage_filtered",
      "binding_class","target_file","target_blob_sha","target_line",
      "symbol_linkage","evidence_notes"]
def rows(file):
 with gzip.open(OUT/file,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def main():
 manifest={(r["repo"],r["path"]):r for r in rows("tracked_file_manifest.csv.gz")}
 files={};definitions=collections.defaultdict(list)
 for d in rows("semantic_function_definitions.csv.gz"):
  repo,path=d["repo"],d["path"]
  key=(repo,path)
  if key not in files:
   m=manifest.get(key)
   if not m:raise RuntimeError("Untracked AST source "+str(key))
   checkout=ROOT/repo.split("/")[-1]
   p=checkout/path
   data=p.read_bytes() if not p.is_symlink() else os.readlink(p).encode()
   if gitsha(data)!=m["blob_sha"]:
    data=subprocess.check_output(["git","-C",str(checkout),"cat-file","blob",m["blob_sha"]])
   if gitsha(data)!=m["blob_sha"]:raise RuntimeError("Changed AST source "+str(key))
   files[key]=data.decode("utf-8","surrogateescape").splitlines()
  lines=files[key]
  pos=int(d["start_line"]);end=int(d["end_line"])
  if not 1<=pos<=len(lines):raise RuntimeError("Bad AST definition line "+str(key))
  # Function declaration qualifiers may span several lines; stop at open brace
  # and at most 20 lines. Does NOT infer whether C++ methods are virtual.
  signature="\n".join(lines[pos-1:min(end,pos+19,len(lines))])
  before_body=signature.split("{",1)[0]
  static=bool(re.search(r"(?<!\w)static(?!\w)",before_body))
  inline=bool(re.search(r"(?<!\w)inline(?!\w)",before_body))
  extension=Path(path).suffix.lower()
  language=LANG.get(extension,"unknown")
  if repo=="huderlem/porymap" and extension==".h":language="cpp"
  location="HEADER" if extension in (".h",".hpp",".hh",".hxx") else "TU"
  declarations={"repo":repo,"path":path,"blob_sha":d["blob_sha"],
    "name":d["name"],"line":pos,"language":language,
    "linkage":"INTERNAL_STATIC" if static else ("HEADER_INLINE_CANDIDATE" if inline and location=="HEADER" else "EXTERNAL_OR_UNKNOWN"),
    "header":location=="HEADER"}
  definitions[(repo,d["name"])].append(declarations)
 counters=collections.Counter();byrepo=collections.defaultdict(collections.Counter)
 examples=collections.defaultdict(list)
 with gzip.open(OUT/"call_graph_linkage_filtered.csv.gz","wt",encoding="utf-8",newline="") as out:
  w=csv.DictWriter(out,fieldnames=COLS);w.writeheader()
  for site in rows("semantic_call_graph.csv.gz"):
   repo,caller,name=site["repo"],site["caller_file"],site["callee_name"]
   m=manifest.get((repo,caller))
   if not m:raise RuntimeError("Call origin absent from manifest")
   initial=definitions.get((repo,name),[])
   local=[x for x in initial if x["path"]==caller]
   caller_lang=LANG.get(Path(caller).suffix.lower(),"unknown")
   if repo=="huderlem/porymap" and caller.endswith(".h"):caller_lang="cpp"
   if site["resolution"]=="INDIRECT_OR_MEMBER_CALL_UNRESOLVED":
    eligible=[];klass="INDIRECT_OR_MEMBER_UNRESOLVED"
   elif caller_lang not in ("c","cpp"):
    eligible=[];klass="NON_C_LANGUAGE_BINDING_REQUIRES_IMPORTS"
   elif caller_lang=="cpp":
    # Within a C++ file, a matching identifier may be an overload, method,
    # ADL resolution, template or a namespace symbol. Never promote it.
    eligible=local if local else initial
    klass="CPP_OVERLOAD_OR_NAME_LOOKUP_UNRESOLVED"
   elif len(local)==1:
    eligible=local
    klass="SAME_C_FILE_DEFINITION_CANDIDATE"
   elif len(local)>1:
    eligible=local
    klass="AMBIGUOUS_SAME_C_FILE"
   else:
    # External translation units cannot resolve static C functions. Header
    # static-inline definitions are only candidates if truly included, which
    # this pass cannot prove for transitive macros.
    eligible=[x for x in initial if x["linkage"]!="INTERNAL_STATIC" or x["header"]]
    if len(eligible)==1:
     klass=("HEADER_INLINE_REQUIRES_INCLUDE_CHAIN" if eligible[0]["header"]
            else "EXTERNAL_C_LINKAGE_CANDIDATE")
    elif eligible:
     klass="AMBIGUOUS_EXTERNAL_C_SYMBOL"
    elif initial:
     klass="REJECTED_CROSS_FILE_STATIC_NAME_MATCH"
    else:
     klass="UNRESOLVED_EXTERNAL_MACRO_OR_FUNCTION"
   counters[klass]+=1;byrepo[repo][klass]+=1
   # Only one deterministic directly named definition from C gets a
   # candidate dependency edge. C++ and dynamic dispatch remain unresolved.
   target=eligible[0] if len(eligible)==1 and klass in (
     "SAME_C_FILE_DEFINITION_CANDIDATE","EXTERNAL_C_LINKAGE_CANDIDATE",
     "HEADER_INLINE_REQUIRES_INCLUDE_CHAIN") else None
   if len(examples[klass])<8 and (klass in ("REJECTED_CROSS_FILE_STATIC_NAME_MATCH",
                    "CPP_OVERLOAD_OR_NAME_LOOKUP_UNRESOLVED")):
    examples[klass].append({"repo":repo,"caller":caller,"line":int(site["caller_line"]),
                            "callee":name,"candidate_paths":[x["path"] for x in initial[:4]]})
   w.writerow({"repo":repo,"caller_file":caller,"caller_blob_sha":m["blob_sha"],
     "caller_scope":site["caller_scope"],"caller_line":site["caller_line"],
     "callee_name":name,"candidate_count_original":len(initial),
     "candidate_count_linkage_filtered":len(eligible),"binding_class":klass,
     "target_file":target["path"] if target else "",
     "target_blob_sha":target["blob_sha"] if target else "",
     "target_line":target["line"] if target else "",
     "symbol_linkage":target["linkage"] if target else "",
     "evidence_notes":"Static exclusion by pinned function signature; no compiler symbol resolution."})
 summary={"call_sites_examined":sum(counters.values()),
   "calls_by_linkage_class":dict(counters),
   "by_repo":{k:dict(v) for k,v in byrepo.items()},
   "examples":dict(examples),
   "candidate_bindings_after_linkage_filter":sum(counters[k] for k in (
      "SAME_C_FILE_DEFINITION_CANDIDATE","EXTERNAL_C_LINKAGE_CANDIDATE",
      "HEADER_INLINE_REQUIRES_INCLUDE_CHAIN")),
   "rejected_cross_file_static":counters["REJECTED_CROSS_FILE_STATIC_NAME_MATCH"],
   "cpp_overload_or_name_lookup_unresolved":counters["CPP_OVERLOAD_OR_NAME_LOOKUP_UNRESOLVED"],
   "approval_status":"LINKAGE_FILTERED_NAME_MATCH_NOT_COMPILER_VERIFIED",
   "phase1_mapping_complete":False,
   "limitations":["Static detection uses pinned source text immediately preceding function bodies.",
       "Macros can change linkage or produce additional definitions after preprocessing.",
       "Header candidates need transitive #include evidence.",
       "C++ overload, namespace, templates, methods, ADL and link-time symbols remain unbound.",
       "No runtime call reachability is claimed; some same-file matches may still be macro-conditional."]}
 (OUT/"call_graph_linkage_summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("examples","by_repo")},indent=2))
if __name__=="__main__":main()

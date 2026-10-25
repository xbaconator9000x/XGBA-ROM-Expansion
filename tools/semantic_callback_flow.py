#!/usr/bin/env python3
"""Connect source-pinned function-pointer assignments to indirect call sites.

Only syntactic member-slot correspondence is established. Runtime aliasing,
struct types, configuration and reassignment remain unverified and explicitly
flagged; no link is promoted to executable binding proof.
"""
from __future__ import annotations
import collections,csv,gzip,json,re
from pathlib import Path
OUT=Path("audit-output")
COLS=["repo","slot","caller_path","caller_blob_sha","caller_line","caller_scope",
      "assignment_path","assignment_blob_sha","assignment_line","assignment_scope",
      "assigned_function","target_definition_path","target_definition_blob_sha",
      "target_definition_line","classification","same_compilation_unit"]
NAME=re.compile(r"^\s*&?\s*([A-Za-z_]\w*)\s*$")
CHAIN=re.compile(r"(?:[A-Za-z_]\w*)(?:(?:->|\.)[A-Za-z_]\w*){2,}$")
def rows(name):
 with gzip.open(OUT/name,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def slotname(expr):
 if not expr:return None
 compact=re.sub(r"\s+","",expr)
 if not CHAIN.fullmatch(compact):return None
 parts=re.split(r"(?:->|\.)",compact)
 return parts[-2]+"."+parts[-1]
def main():
 manifest={(r["repo"],r["path"]):r["blob_sha"] for r in rows("tracked_file_manifest.csv.gz")}
 definitions=collections.defaultdict(list)
 for d in rows("semantic_function_definitions.csv.gz"):
  definitions[(d["repo"],d["name"])].append(d)
 assigns=collections.defaultdict(list);calls=[];counters=collections.Counter()
 with gzip.open(OUT/"semantic_ast_sites.jsonl.gz","rt",encoding="utf-8") as f:
  for line in f:
   r=json.loads(line);repo,path=r["repo"],r["path"]
   if manifest.get((repo,path))!=r["git_blob_sha"]:
    raise RuntimeError("AST origin hash mismatch "+repo+"/"+path)
   members=collections.defaultdict(list)
   for e in r["sites"]:
    if e["kind"]=="member":members[(e["line"],e.get("member"))].append(e.get("expression",""))
   for e in r["sites"]:
    if e["kind"]=="write":
     slot=slotname(e.get("target"))
     if not slot:continue
     value=e.get("value_sample") or ""
     m=NAME.match(value)
     if m:
      assigns[(repo,slot)].append({"repo":repo,"file":path,"blob_sha":r["git_blob_sha"],
       "line":e["line"],"scope":e.get("scope"),"name":m.group(1),
       "raw_target":e["target"]})
      counters["assignments_named_function_candidate"]+=1
     else:
      counters["assignments_non_name_or_reassignment"]+=1
    if e["kind"]=="call" and not e.get("direct_identifier"):
     candidate_fields=members.get((e["line"],e.get("callee")),[])
     slot_names=set(filter(None,(slotname(x) for x in candidate_fields)))
     if len(slot_names)!=1:
      counters["indirect_calls_no_unique_member_slot"]+=1;continue
     slot=next(iter(slot_names))
     calls.append({"repo":repo,"file":path,"blob_sha":r["git_blob_sha"],
       "line":e["line"],"scope":e.get("scope"),"slot":slot})
   counters["ast_files_reviewed"]+=1
 binding_rows=0;slotresolved=0;siteunresolved=0;ambig=0
 with gzip.open(OUT/"indirect_member_callback_candidates.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
  for c in calls:
   repo,slot=c["repo"],c["slot"]
   choices=assigns.get((repo,slot),[])
   if not choices:siteunresolved+=1;continue
   if len(choices)>24:ambig+=1;continue
   slotresolved+=1
   for a in choices:
    # A declaration in the assigning TU is preferred. Other definitions
    # remain name candidates, not compiler-resolved targets.
    defs=definitions.get((repo,a["name"]),[])
    same=[d for d in defs if d["path"]==a["file"]]
    viable=same or defs
    if len(viable)>8:continue
    for d in viable:
     if manifest.get((repo,d["path"]))!=d["blob_sha"]:
      raise RuntimeError("Callback definition SHA mismatch "+repo+"/"+d["path"])
     klass=("SAME_FILE_CALLBACK_VALUE_CANDIDATE" if d["path"]==a["file"]
             else "REPOSITORY_CALLBACK_NAME_CANDIDATE")
     w.writerow({"repo":repo,"slot":slot,"caller_path":c["file"],
       "caller_blob_sha":c["blob_sha"],"caller_line":c["line"],"caller_scope":c["scope"],
       "assignment_path":a["file"],"assignment_blob_sha":a["blob_sha"],
       "assignment_line":a["line"],"assignment_scope":a["scope"],
       "assigned_function":a["name"],"target_definition_path":d["path"],
       "target_definition_blob_sha":d["blob_sha"],"target_definition_line":d["start_line"],
       "classification":klass,"same_compilation_unit":str(d["path"]==a["file"])})
     binding_rows+=1
 summary={"ast_files_reviewed":counters["ast_files_reviewed"],
   "function_pointer_member_assignments":counters["assignments_named_function_candidate"],
   "non_name_member_assignments":counters["assignments_non_name_or_reassignment"],
   "indirect_calls_with_recognized_slot":len(calls),
   "caller_sites_with_at_least_one_assignment":slotresolved,
   "caller_sites_without_assignment":siteunresolved,
   "caller_sites_with_too_many_assignments":ambig,
   "candidate_callback_site_to_target_edges":binding_rows,
   "indirect_calls_no_unique_member_slot":counters["indirect_calls_no_unique_member_slot"],
   "semantic_signoffs":0,"phase1_mapping_complete":False,
   "limitations":["Struct member suffixes match names, not compiler-resolved types.",
    "Source assignment is not proof callback pointer has that value at runtime.",
    "Reassignments, aliases, casts and conditional builds may change the dispatch target.",
    "A shared slot name from unrelated types is an explicit candidate ambiguity.",
    "Only assignment of simple named functions and directly recognized member-call expression is indexed."]}
 (OUT/"indirect_member_callback_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":
 assert slotname("cpu->memory.load32")=="memory.load32"
 assert slotname("gba->memory.dmaEvent.callback")=="dmaEvent.callback"
 assert not slotname("gba->memory.load32[0]")
 main()

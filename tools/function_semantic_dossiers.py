#!/usr/bin/env python3
"""Build source-blob-anchored function-level semantic *review* dossiers.

This is a syntactic side-effect and call-flow surface for all parsed functions,
not a declaration that C semantics, aliasing, callbacks or conditional builds
are proven. Every function is explicitly marked unapproved. Files where
tree-sitter reported errors remain syntax-partial rather than silently passing.
"""
from __future__ import annotations
import collections,csv,gzip,json,re,sys
from pathlib import Path

OUT=Path("audit-output")
INDEX_FIELDS=("repo","path","pinned_revision","source_blob_sha","language",
    "priority","name","scope_id","start_line","end_line","body_bytes",
    "ast_file_status","semantic_status","calls","direct_calls","indirect_calls",
    "global_like_writes","pointer_writes","array_writes","local_like_writes",
    "control_flow_nodes","return_nodes","memory_reference_nodes","evidence_record_id")
GLOBAL=re.compile(r"^(?:g[A-Z]\w*|s[A-Z]\w*|(?:gba|cpu|memory|state|ctx|game)->)")
def manifest():
 with gzip.open(OUT/"tracked_file_manifest.csv.gz","rt",encoding="utf-8",newline="") as f:
  data={(r["repo"],r["path"]):(r["blob_sha"],r["revision"]) for r in csv.DictReader(f)}
 if len(data)!=14834:raise RuntimeError("File identity census missing or incomplete")
 return data
def classification(target):
 if not target:return "unknown_write_target"
 value=re.sub(r"\s+","",target)
 if value.startswith("*") or "->" in value or "." in value:return "pointer_or_struct_write"
 if "[" in value:return "indexed_array_write"
 if GLOBAL.match(value):return "global_like_write"
 return "local_or_alias_unknown"
def main():
 source=manifest();totals=collections.Counter();status=collections.Counter()
 danger=collections.Counter();files=collections.Counter();lang=collections.Counter()
 ast_untrusted=0;count=0
 idx=OUT/"function_semantic_index.csv.gz"
 evidence=OUT/"function_semantic_dossiers.jsonl.gz"
 with gzip.open(OUT/"semantic_ast_sites.jsonl.gz","rt",encoding="utf-8") as inp, \
      gzip.open(evidence,"wt",encoding="utf-8",newline="") as dossiers, \
      gzip.open(idx,"wt",encoding="utf-8",newline="") as fs:
  w=csv.DictWriter(fs,fieldnames=INDEX_FIELDS);w.writeheader()
  for line in inp:
   rec=json.loads(line)
   key=rec["repo"],rec["path"]
   if key not in source:raise RuntimeError("AST file not found in pinned source manifest: "+repr(key))
   if source[key]!=(rec["git_blob_sha"],rec["pinned_revision"]):
    raise RuntimeError("AST provenance does not match manifest "+repr(key))
   funcs=rec["functions"];site_by_scope=collections.defaultdict(list)
   for s in rec["sites"]:
    scope=s.get("scope")
    if scope:site_by_scope[scope].append(s)
    else:totals["sites_outside_functions"]+=1
   scopes={f["scope_id"] for f in funcs}
   if len(scopes)!=len(funcs):
    raise RuntimeError("Duplicate function scope identifiers "+repr(key))
   unbound_scopes=set(site_by_scope)-scopes
   totals["unbound_ast_scopes"]+=len(unbound_scopes)
   file_status=rec["status"]
   if file_status!="PARSED_AST":ast_untrusted+=len(funcs)
   for fun in funcs:
    count+=1
    if not (1<=int(fun["line"])<=int(fun["end_line"])):
     raise RuntimeError("Bad function line provenance "+fun["scope_id"])
    scope=fun["scope_id"]
    sites=site_by_scope[scope]
    writes=collections.Counter()
    targets=collections.defaultdict(collections.Counter)
    calls=[];control=collections.Counter();memory=[]
    for s in sites:
     kind=s["kind"]
     if kind=="write":
      cl=classification(s.get("target"))
      writes[cl]+=1
      if s.get("target"):targets[cl][s["target"]]+=1
     elif kind=="call":
      calls.append({"line":s["line"],"callee":s.get("callee"),
                    "direct_identifier_candidate":bool(s.get("direct_identifier")),
                    "argument_syntax_nodes":s.get("arg_count",0)})
     elif kind=="control":control[s["control"]]+=1
     elif kind=="memory_reference":
      memory.append({"line":s["line"],"token":s.get("token")})
    risks=[]
    if writes["pointer_or_struct_write"]:risks.append("POINTER_OR_STRUCT_WRITES_NEED_ALIAS_REVIEW")
    if writes["global_like_write"]:risks.append("GLOBAL_STATE_OR_GLOBAL_ALIAS_CANDIDATE")
    if any(not c["direct_identifier_candidate"] for c in calls):
     risks.append("INDIRECT_OR_MEMBER_CALL_TARGET_UNRESOLVED")
    if control["goto_statement"] or control["switch_statement"]:
     risks.append("CONTROL_FLOW_REQUIRES_PATH_REVIEW")
    if memory:risks.append("DIRECT_MEMORY_ADDRESS_OR_BUS_REFERENCE_CANDIDATE")
    if file_status!="PARSED_AST":risks.append("SOURCE_AST_CONTAINS_ERRORS")
    if not risks:risks.append("HELPER_SIDE_EFFECTS_AND_MACROS_STILL_UNKNOWN")
    certainty=("AST_SYNTAX_PARTIAL_NOT_SEMANTICALLY_REVIEWED" if file_status!="PARSED_AST"
               else "AST_SYNTAX_CAPTURED_NOT_SEMANTICALLY_REVIEWED")
    for r in risks:danger[r]+=1
    status[certainty]+=1;files[key]+=1;lang[rec["language"]]+=1
    doc={"source":{"repo":rec["repo"],"path":rec["path"],
          "pinned_revision":rec["pinned_revision"],"git_blob_sha":rec["git_blob_sha"],
          "language":rec["language"],"AST_file_status":file_status},
         "function":{"name":fun["name"],"scope_id":scope,
          "start_line":fun["line"],"end_line":fun["end_line"],
          "syntax_bytes":fun["body_bytes"]},
         "observed_ast":{"site_nodes":len(sites),"calls_total":len(calls),
          "direct_name_call_candidates":sum(bool(c["direct_identifier_candidate"]) for c in calls),
          "indirect_or_member_call_candidates":sum(not c["direct_identifier_candidate"] for c in calls),
          "call_site_samples":calls[:80],
          "write_kinds":dict(writes),
          "write_target_samples":{k:dict(v.most_common(40)) for k,v in targets.items()},
          "control_flow_kinds":dict(control),"memory_references":memory[:70]},
         "obligations":{"risk_flags":risks,"semantic_status":certainty,
          "independent_reviewer":None,"semantic_signoff":False,
          "source_conditions_preprocessed":False,
          "actual_call_targets_compiler_bound":False,
          "side_effects_path_complete":False,
          "review_note":"AST syntax is not compiler-verified data flow, runtime reachability, or whole-file signoff."}}
    doc_id="FN-"+str(count).zfill(6)
    doc["evidence_record_id"]=doc_id
    dossiers.write(json.dumps(doc,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n")
    w.writerow({"repo":rec["repo"],"path":rec["path"],"pinned_revision":rec["pinned_revision"],
       "source_blob_sha":rec["git_blob_sha"],"language":rec["language"],"priority":rec["priority"],
       "name":fun["name"],"scope_id":scope,"start_line":fun["line"],
       "end_line":fun["end_line"],"body_bytes":fun["body_bytes"],
       "ast_file_status":file_status,"semantic_status":certainty,
       "calls":len(calls),
       "direct_calls":sum(bool(c["direct_identifier_candidate"]) for c in calls),
       "indirect_calls":sum(not c["direct_identifier_candidate"] for c in calls),
       "global_like_writes":writes["global_like_write"],
       "pointer_writes":writes["pointer_or_struct_write"],
       "array_writes":writes["indexed_array_write"],
       "local_like_writes":writes["local_or_alias_unknown"],
       "control_flow_nodes":sum(control.values()),
       "return_nodes":control["return_statement"],
       "memory_reference_nodes":len(memory),"evidence_record_id":doc_id})
    if count%500==0:
     checkpoint=OUT/"function_checkpoints"
     checkpoint.mkdir(exist_ok=True)
     (checkpoint/f"function_{count:06d}.json").write_text(
        json.dumps({"functions_indexed":count,"semantic_signoffs":0,
                    "status":"UNAPPROVED_AST_FUNCTION_DOSSIERS"})+"\n")
 result={"source_anchored_function_dossiers":count,
  "function_containing_files":len(files),"ast_functions_from_error_files":ast_untrusted,
  "review_status":dict(status),"by_language":dict(lang),
  "risk_obligation_function_counts":dict(danger),
  "syntax_sites_outside_functions":totals["sites_outside_functions"],
  "unbound_ast_scope_names":totals["unbound_ast_scopes"],
  "function_semantic_signoffs":0,"file_semantic_signoffs":0,
  "phase1_mapping_complete":False,
  "limitations":["Nested AST functions/blocks are assigned scope using the existing parser; this is not control-flow graph proof.",
   "Global-looking names and pointer writes can be local aliases; no compiler-based points-to analysis.",
   "Macro expansion, cross-function data flow, callbacks, exception paths and generated source are not resolved.",
   "File AST syntax errors mean function ranges may be incomplete; never mark function approved from parse success."]}
 (OUT/"function_semantic_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result,indent=2))
 if count<30000:raise RuntimeError("Unexpectedly low function coverage")
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("FUNCTION DOSSIERS FAILED:",repr(e),file=sys.stderr)
  sys.exit(2)

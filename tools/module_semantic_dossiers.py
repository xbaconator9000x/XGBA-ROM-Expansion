#!/usr/bin/env python3
"""Phase 1 per-module source/asset coverage and semantic-review obligations.

This is a work allocation map, not automatic per-file review certification.
Every module lists exact pinned file hashes via the source census, all indexed
code/assembly boundaries, typed dependency candidates and unresolved grammar.
"""
import collections,csv,gzip,json,re
from pathlib import Path
OUT=Path("audit-output")
def rows(name):
 with gzip.open(OUT/name,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def module_name(repo,path):
 p=path.split("/")
 if repo=="pret/pokefirered":
  if p[0] in ("src","include","asm","data","graphics","sound","tools"):
   if len(p)>2 and p[0] in ("data","graphics","sound","tools"):return "/".join(p[:2])
   if p[0]=="src" and len(p)>2:return "src/"+p[1]
   return p[0]
 if repo=="mgba-emu/mgba":
  if p[0]=="src" and len(p)>2:return "src/"+p[1]+("/"+p[2] if p[1]=="gba" and p[2] in ("cart","cheats","sio","timer") else "")
  if p[0]=="include" and len(p)>3:return "include/"+p[1]+"/"+p[2]
 if repo=="huderlem/porymap":
  if p[0]=="src" and len(p)>2:return "src/"+p[1]
 if repo=="pret/agbcc":
  if len(p)>2 and p[0]=="gcc_arm" and p[1]=="config":return "gcc_arm/config/"+p[2]
  if len(p)>2 and p[0]=="gcc":return "gcc/"+p[1]
 return p[0] if len(p)>1 else "(root)"
def main():
 manifest=list(rows("tracked_file_manifest.csv.gz"))
 if len(manifest)!=14834:raise RuntimeError("14,834 original files required")
 files={(r["repo"],r["path"]):r for r in manifest}
 queues={(r["repo"],r["path"]):r for r in rows("semantic_review_queue.csv.gz")}
 ast={(r["repo"],r["path"]):r for r in rows("semantic_ast_file_manifest.csv.gz")}
 asm={(r["repo"],r["path"]):r for r in rows("asm_build_file_coverage.csv.gz")}
 grouped=collections.defaultdict(list)
 for r in manifest:grouped[(r["repo"],module_name(r["repo"],r["path"]))].append(r)
 modules={}
 for (repo,name),source in grouped.items():
  key=repo+"::"+name
  priority=collections.Counter(queues[(repo,r["path"])]["priority"] for r in source)
  cats=collections.Counter(r["category"] for r in source)
  aststates=collections.Counter(ast[(repo,r["path"])]["status"] for r in source if (repo,r["path"]) in ast)
  asmstates=collections.Counter(asm[(repo,r["path"])]["semantic_status"] for r in source if (repo,r["path"]) in asm)
  modules[key]={"repo":repo,"module":name,"tracked_file_count":len(source),
   "source_category":dict(cats),"risk_priority_heuristic":dict(priority),
   "ast_parse_status":dict(aststates),"assembly_build_parse_status":dict(asmstates),
   "function_definitions_indexed":sum(int(ast[(repo,r["path"])]["functions"]) for r in source if (repo,r["path"]) in ast),
   "ast_sites_indexed":sum(int(ast[(repo,r["path"])]["sites"]) for r in source if (repo,r["path"]) in ast),
   "source_hashes":[{"path":r["path"],"blob":r["blob_sha"]} for r in source],
   "observed_external_module_edges":collections.Counter(),
   "unresolved_include_references":0,
   "semantic_dispositions_approved":0,"review_status":"PENDING_INDEPENDENT_SEMANTIC_REVIEW"}
 for row in rows("unresolved_include_dispositions.csv.gz"):
  key=row["repo"]+"::"+module_name(row["repo"],row["from_path"])
  if key in modules:modules[key]["unresolved_include_references"]+=1
 cross=collections.Counter()
 for row in rows("unified_candidate_dependency_edges.csv.gz"):
  repo=row["repo"]
  s=module_name(repo,row["source_path"])
  t=module_name(repo,row["target_path"])
  if s==t:continue
  sk=repo+"::"+s
  tk=repo+"::"+t
  if sk not in modules or tk not in modules:raise RuntimeError("Unknown module endpoint")
  cross[(sk,tk,row["edge_type"])]+=int(row["site_count"])
 for (sk,tk,typ),count in cross.items():
  modules[sk]["observed_external_module_edges"][(tk,typ)]+=count
 total=0
 with gzip.open(OUT/"module_semantic_dossiers.jsonl.gz","wt",encoding="utf-8") as f:
  for key in sorted(modules):
   d=modules[key]
   d["observed_external_module_edges"]=[
     {"target_module":target,"edge_type":kind,"observed_sites":n}
     for (target,kind),n in sorted(d["observed_external_module_edges"].items())]
   total+=d["tracked_file_count"]
   f.write(json.dumps(d,sort_keys=True,separators=(",",":"))+"\n")
 assert total==14834
 stats=collections.Counter()
 for d in modules.values():
  if d["risk_priority_heuristic"].get("P0",0):stats["modules_containing_P0"]+=1
  if d["ast_parse_status"].get("PARSED_WITH_SYNTAX_ERRORS",0):stats["modules_with_AST_errors"]+=1
  if d["unresolved_include_references"]:stats["modules_with_unresolved_includes"]+=1
 summary={"tracked_files_assigned":total,"semantic_modules":len(modules),
  "cross_module_dependency_type_groups":len(cross),
  "cross_module_observed_reference_sites":sum(cross.values()),
  "module_coverage":dict(stats),"approved_module_semantics":0,
  "approved_whole_file_semantics":0,"phase1_mapping_complete":False,
  "warning":"A module summary is a reproducible semantic-review queue, not an assertion that the module has been understood.",
  "limitations":["Module partition is directory/role-based and can miss semantic submodules.",
   "Cross-module edges are syntactic candidates unless a dedicated compiled proof exists.",
   "Every file is inventoried and source-anchored, but most are not independently semantically reviewed."]}
 (OUT/"module_semantic_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

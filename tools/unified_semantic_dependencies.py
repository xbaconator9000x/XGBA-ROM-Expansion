#!/usr/bin/env python3
"""Unify source-backed candidate dependencies; compute conservative impact closures.

All edges carry provenance, type, and candidate status. No inferred target becomes
a compiler-verified binding or independent Phase 1 semantic signoff.
"""
import collections,csv,gzip,json,re,sys
from pathlib import Path
from collections import deque
OUT=Path("audit-output")
ROOTS=[
("mgba-emu/mgba","src/arm/arm.c"),
("mgba-emu/mgba","src/gba/memory.c"),
("mgba-emu/mgba","src/gba/dma.c"),
("mgba-emu/mgba","src/gba/serialize.c"),
("mgba-emu/mgba","src/gba/cart/matrix.c"),
("pret/pokefirered","src/script.c"),
("pret/pokefirered","src/scrcmd.c"),
("pret/pokefirered","src/load_save.c"),
("pret/pokefirered","src/fieldmap.c"),
("huderlem/porymap","src/project.cpp"),
("huderlem/porymap","src/core/maplayout.cpp"),
("huderlem/poryscript","emitter/emitter.go")]
def rows(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def main():
 manifest={(r["repo"],r["path"]):r for r in rows(OUT/"tracked_file_manifest.csv.gz")}
 assert len(manifest)==14834
 graph=collections.defaultdict(lambda:{"site_count":0,"source_lines":[]})
 anomalous=collections.Counter()
 def add(repo,src,dst,typ,line,status):
  if not src or not dst or src==dst:return
  a=(repo,src);b=(repo,dst)
  if a not in manifest or b not in manifest:
   anomalous["unknown_endpoint"]+=1;return
  key=(repo,src,dst,typ,status)
  p=graph[key];p["site_count"]+=1
  if len(p["source_lines"])<12:p["source_lines"].append(line)
 for e in rows(OUT/"resolved_include_edges.csv.gz"):
  if e["resolution"]=="UNRESOLVED":continue
  for dst in e["target_path"].split(";"):
   if dst:add(e["repo"],e["from_path"],dst,"preprocessor_include",e["line"],e["resolution"])
 for e in rows(OUT/"semantic_call_graph.csv.gz"):
  if e["resolution"]!="UNIQUE_REPO_SYMBOL_CANDIDATE":continue
  for spec in e["callee_paths"].split(";"):
   if ":" not in spec:continue
   path,line=spec.rsplit(":",1)
   add(e["repo"],e["caller_file"],path,"ast_direct_call",e["caller_line"],e["resolution"])
 for e in rows(OUT/"explicit_asset_references.csv.gz"):
  if e["resolution"]!="UNIQUE_EXPLICIT_PATH_CANDIDATE":continue
  for p in e["target_paths"].split(";"):
   if p:add(e["repo"],e["from_path"],p,"literal_asset_reference",e["line"],e["resolution"])
 for e in rows(OUT/"asm_build_semantic_sites.csv.gz"):
  if e["kind"] not in ("include_or_binary_embed","source_asset_incbin"):continue
  if e["resolution"]!="PATH_CANDIDATE":continue
  for p in e["value"].split(";"):
   if p:add(e["repo"],e["path"],p,"assembly_or_build_include",e["line"],e["resolution"])
 bykind=collections.Counter();incoming=collections.Counter();outgoing=collections.Counter()
 rev=collections.defaultdict(set)
 with gzip.open(OUT/"unified_candidate_dependency_edges.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.writer(f);w.writerow(["repo","source_path","source_blob_sha","target_path","target_blob_sha",
    "edge_type","resolution_status","site_count","sample_source_lines"])
  for key,value in sorted(graph.items()):
   repo,src,dst,kind,status=key;bykind[kind]+=1
   source=manifest[(repo,src)];target=manifest[(repo,dst)]
   w.writerow([repo,src,source["blob_sha"],dst,target["blob_sha"],kind,
               status,value["site_count"],";".join(str(x) for x in value["source_lines"])])
   incoming[(repo,dst)]+=value["site_count"]
   outgoing[(repo,src)]+=value["site_count"]
   rev[(repo,dst)].add((repo,src))
 def impact(root):
  if root not in manifest:return {"status":"ROOT_NOT_IN_MANIFEST","candidates":[]}
  seen={root};todo=deque([root])
  while todo:
   node=todo.popleft()
   for pred in rev[node]:
    if pred not in seen:
     seen.add(pred);todo.append(pred)
  results=sorted(seen-{root})
  return {"status":"CANDIDATE_DEPENDENCY_REACHABILITY_NOT_PROOF",
   "source_blob_sha":manifest[root]["blob_sha"],"transitive_candidate_files":len(results),
   "by_repository":dict(collections.Counter(a for a,b in results)),
   "sample_files":[a+"/"+b for a,b in results[:45]]}
 impacts={repo+"/"+path:impact((repo,path)) for repo,path in ROOTS}
 summary={"manifest_files":len(manifest),"unique_typed_file_dependency_edges":len(graph),
  "sites_aggregated":sum(x["site_count"] for x in graph.values()),
  "edge_types":dict(bykind),"source_files_with_outgoing_edges":len(outgoing),
  "target_files_with_incoming_edges":len(incoming),
  "unresolved_endpoint_candidates":dict(anomalous),
  "phase1_mapping_complete":False,"independent_semantic_signoffs":0,
  "limitations":["Source calls are syntactic and are not linker-resolved.",
    "Include files and literal asset paths are candidate uses; build flags and generated tables can change targets.",
    "Traversal follows candidate edges and does not prove runtime call reachability.",
    "Unresolved dynamic dispatch, opaque binary dependencies and conditional macros remain outside this graph."]}
 (OUT/"unified_candidate_dependency_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (OUT/"p0_semantic_impact_candidates.json").write_text(json.dumps(impacts,indent=2)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

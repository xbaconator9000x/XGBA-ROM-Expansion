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
 # Linkage-screened C candidates replace naive whole-repo name matching.
 # A C static name in another source unit does not establish a call edge.
 # C++/Python/Go name lookups require a compiler-aware binder.
 for e in rows(OUT/"call_graph_linkage_filtered.csv.gz"):
  if e["binding_class"] not in ("EXTERNAL_C_LINKAGE_CANDIDATE","HEADER_INLINE_REQUIRES_INCLUDE_CHAIN"):
   continue
  if not e["target_file"]:continue
  add(e["repo"],e["caller_file"],e["target_file"],"c_linkage_screened_call_candidate",
      e["caller_line"],e["binding_class"])
 for e in rows(OUT/"explicit_asset_references.csv.gz"):
  if e["resolution"]!="UNIQUE_EXPLICIT_PATH_CANDIDATE":continue
  for p in e["target_paths"].split(";"):
   if p:add(e["repo"],e["from_path"],p,"literal_asset_reference",e["line"],e["resolution"])
 for e in rows(OUT/"asm_build_semantic_sites.csv.gz"):
  if e["kind"] not in ("include_or_binary_embed","source_asset_incbin"):continue
  if e["resolution"]!="PATH_CANDIDATE":continue
  for p in e["value"].split(";"):
   if p:add(e["repo"],e["path"],p,"assembly_or_build_include",e["line"],e["resolution"])
 # Generated graphics are compiled from tracked PNG/PAL by Makefile suffix rules.
 # Consumer -> original source image is a candidate BUILD dependency, not a direct runtime pointer.
 gen=OUT/"generated_asset_provenance_edges.csv.gz"
 if gen.exists():
  for e in rows(gen):
   if e["resolution"]!="TRACKED_BUILD_SOURCE_CANDIDATE":continue
   if e["derived_primary"]:
    add(e["source_repo"],e["consumer"],e["derived_primary"],
      "generated_graphics_source_provenance",e["source_line"],e["resolution"])
 # An explicit Make concat target can consume many differently named source files.
 # Keep every component and its order in the separate evidence CSV; graph edges
 # are candidate consumer->tracked source dependencies only.
 comp=OUT/"composite_graphics_source_edges.csv.gz"
 if comp.exists():
  for e in rows(comp):
   if e["component_resolution"]!="EXPLICIT_MAKE_RULE_COMPONENT_SOURCE_CANDIDATE":continue
   add("pret/pokefirered",e["consumer_path"],e["component_checked_in_source"],
       "composite_graphics_source_provenance",
       e["consumer_source_line"],e["component_resolution"])
 # Function pointer dispatch: the interpreter calls a table indexed by bytecode.
 # Track interpreter -> opcode table and opcode table -> registered handler source.
 op=OUT/"bytecode_opcode_dispatch_semantic.csv.gz"
 if op.exists():
  seen_sites=set()
  for e in rows(op):
   repo=e["repo"]
   site=(repo,e["dispatch_site_path"],e["dispatch_table_path"],e["dispatch_table"])
   if site not in seen_sites:
    add(repo,e["dispatch_site_path"],e["dispatch_table_path"],
      "indirect_opcode_dispatch_to_table",e["table_line"],"SOURCE_BACKED_TABLE_LOOKUP")
    seen_sites.add(site)
   add(repo,e["dispatch_table_path"],e["handler_path"],
     "opcode_table_function_pointer",e["table_line"],"SOURCE_BACKED_HANDLER_DEFINITION")
 # Member-function callback assignments are candidate runtime edges: producer
 # wrote a named handler to a struct member and a consumer calls that member.
 # Alias analysis is not proved; keep the edge's evidence type explicit.
 callback=OUT/"indirect_member_callback_candidates.csv.gz"
 if callback.exists():
  for e in rows(callback):
   if e["classification"]!="SAME_FILE_CALLBACK_VALUE_CANDIDATE":continue
   add(e["repo"],e["caller_path"],e["target_definition_path"],
       "member_callback_assignment_to_indirect_call",
       e["caller_line"],"MEMBER_NAME_ALIAS_UNVERIFIED")
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
  "limitations":["Linkage-screened C cross-file calls are candidates and are not compiler/linker-resolved; C++/Go/Python unresolved by design.",
    "Include files and literal asset paths are candidate uses; build flags and generated tables can change targets.",
    "Traversal follows candidate edges and does not prove runtime call reachability.",
    "Named member callbacks are linked only by slot candidate without type/alias proof; opaque binary dependencies and conditional macros remain unresolved."]}
 (OUT/"unified_candidate_dependency_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (OUT/"p0_semantic_impact_candidates.json").write_text(json.dumps(impacts,indent=2)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

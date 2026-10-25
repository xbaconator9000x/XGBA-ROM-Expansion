#!/usr/bin/env python3
"""Phase 1 review dossiers for all pinned source files. Candidates only, never review signoff."""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, os, re, sys
from pathlib import Path

PINS={
 "pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
 "mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
 "huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
 "huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55",
 "pret/agbcc":"da598c1d918402c42c0c0d7128ba14567f3175e9"}
PRIORITY={
 "cpu_fetch":95,"rom_window":100,"cartridge_stream":100,"dma_save":95,
 "save_state":95,"map_layout":90,"script":90,"linker_build":80,
 "editor_format":80,"game_data":70,"graphics":65,"audio":65}
P0_PATH=re.compile(r"(?:^|/)(?:memory|dma|gba|serialize|savedata|script|scrcmd|map|fieldmap|load_save|link|agbcc|emitter|parser|rom|cart|makefile|ld_script|porymap)(?:[/._-]|$)",re.I)
FILE_FIELDS=("repo","path","blob_sha","category","priority","lexical_match_count",
 "direct_include_count","resolved_includes","ambiguous_includes",
 "unresolved_includes","incoming_includes","symbol_candidates","machine_review_status",
 "evidence_sha256")
INCLUDE_FIELDS=("repo","from_path","line","include","resolution","target_path","candidate_count")
def rows(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
  yield from csv.DictReader(fh)
def digest(data):return hashlib.sha256(data).hexdigest()
def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def resolve(repo,source,include,index):
 parts=Path(include).parts
 if ".." in parts or include.startswith("/"):return []
 root=Path(source).parent
 places=(root/include,Path(include),Path("include")/include,Path("src")/include,
         Path("tools")/include,Path("include")/"gba"/include)
 found=[]
 for item in places:
  norm=os.path.normpath(str(item)).replace("\\","/")
  if norm in index and norm not in found:found.append(norm)
 return found
def git_blob_sha(data):
 return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def verify_source(repo,entry,root):
 path=root/repo.split("/")[-1]/entry["path"]
 if path.is_symlink():content=os.readlink(path).encode()
 else:content=path.read_bytes()
 if git_blob_sha(content)!=entry["blob_sha"]:
  raise RuntimeError(f"Changed source bytes {repo}/{entry['path']}")
 return content
def self_test():
 d={"include/a.h","src/main.c","src/a.h"}
 assert resolve("r","src/main.c","a.h",d)==["src/a.h","include/a.h"]
 assert resolve("r","src/main.c","missing.h",d)==[]
 assert resolve("r","src/main.c","../secret",d)==[]
 assert git_blob_sha(b"abc")=="f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f"
 print("Self-test PASSED")
def main():
 a=argparse.ArgumentParser()
 a.add_argument("--census",type=Path,required=True)
 a.add_argument("--root",type=Path,required=True)
 a.add_argument("--out",type=Path,required=True)
 x=a.parse_args();x.out.mkdir(parents=True,exist_ok=True)
 summary=json.loads((x.census/"audit_summary.json").read_text())
 if not summary.get("census_complete") or not summary["conditions"].get("all_source_config_content_scanned"):
  raise RuntimeError("Full pinned source census must pass before evidence extraction")
 if {k:v["commit"] for k,v in summary["repositories"].items()}!=PINS:
  raise RuntimeError("Pinned Git commit map changed")
 manifest=list(rows(x.census/"tracked_file_manifest.csv.gz"))
 if len(manifest)!=14834:raise RuntimeError("Unexpected tracked file count")
 keyed={(r["repo"],r["path"]):r for r in manifest}
 if len(keyed)!=len(manifest):raise RuntimeError("Duplicate tracked paths")
 repo_files=collections.defaultdict(set)
 for r in manifest:repo_files[r["repo"]].add(r["path"])
 candidates=collections.defaultdict(list)
 for r in rows(x.census/"lexical_sites.csv.gz"):
  k=r["repo"],r["path"]
  if k not in keyed or r["blob_sha"]!=keyed[k]["blob_sha"]:raise RuntimeError(f"Stale lexical anchor {k}")
  candidates[k].append(r)
 symbols=collections.defaultdict(list)
 for r in rows(x.census/"symbol_candidates.csv.gz"):
  k=r["repo"],r["path"]
  if k not in keyed or r["blob_sha"]!=keyed[k]["blob_sha"]:raise RuntimeError(f"Stale symbol anchor {k}")
  symbols[k].append(r)
 dependencies=collections.defaultdict(list);incoming=collections.Counter()
 include_stats=collections.Counter()
 with gzip.open(x.out/"resolved_include_edges.csv.gz","wt",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=INCLUDE_FIELDS);w.writeheader()
  for inc in rows(x.census/"includes.csv.gz"):
   k=(inc["repo"],inc["path"])
   if k not in keyed or inc["blob_sha"]!=keyed[k]["blob_sha"]:raise RuntimeError(f"Stale include anchor {k}")
   found=resolve(inc["repo"],inc["path"],inc["include"],repo_files[inc["repo"]])
   kind="RESOLVED_CANDIDATE" if len(found)==1 else ("AMBIGUOUS" if found else "UNRESOLVED")
   include_stats[kind]+=1
   dependencies[k].append((int(inc["line"]),inc["include"],kind,found))
   for p in found:incoming[(inc["repo"],p)]+=1
   w.writerow({"repo":inc["repo"],"from_path":inc["path"],"line":inc["line"],
               "include":inc["include"],"resolution":kind,
               "target_path":";".join(found),"candidate_count":len(found)})
 files_by_priority=collections.Counter();status=collections.Counter()
 with gzip.open(x.out/"candidate_review_dossiers.jsonl.gz","wt",encoding="utf-8") as ev, \
      gzip.open(x.out/"semantic_review_queue.csv.gz","wt",encoding="utf-8",newline="") as q:
  qw=csv.DictWriter(q,fieldnames=FILE_FIELDS);qw.writeheader()
  for i,r in enumerate(manifest,1):
   key=r["repo"],r["path"];lex=candidates[key];inc=dependencies[key];syms=symbols[key]
   categories=collections.Counter(h["rule"] for h in lex)
   max_rule=max([PRIORITY.get(z,40) for z in categories],default=0)
   is_text=r["category"] in ("source","structured_or_text_config")
   is_doc=r["category"]=="documentation"
   base=30 if is_text else (10 if is_doc else 20)
   score=max(base,max_rule)+(5 if is_text and P0_PATH.search(r["path"]) else 0)
   if score>=90:p="P0"
   elif score>=70:p="P1"
   elif score>=40:p="P2"
   else:p="P3"
   files_by_priority[p]+=1
   bytes_sha=None
   if is_text:
    content=verify_source(r["repo"],r,x.root)
    bytes_sha=digest(content)
    source_excerpt=[]
    lines=content.decode("utf-8","surrogateescape").splitlines()
    for h in lex[:24]:
     n=int(h["line"])
     if n<1 or n>len(lines):raise RuntimeError(f"Unanchored lexical site {key}:{n}")
     source_excerpt.append({"line":n,"rule":h["rule"],"source":lines[n-1][:260]})
    machine="CANDIDATE_ONLY_SOURCE_HASH_VERIFIED"
   else:
    source_excerpt=[]
    machine="INVENTORIED_NOT_SEMANTICALLY_REVIEWED"
   status[machine]+=1
   evidence={
    "provenance":{"repository":r["repo"],"pinned_revision":r["revision"],
       "path":r["path"],"git_blob_sha":r["blob_sha"],"category":r["category"],
       "source_content_sha256":bytes_sha,"tracked_bytes":r["bytes"]},
    "machine_assessment":{"priority":p,"rule_counts":dict(categories),
       "lexical_sites_total":len(lex),"symbol_candidates_total":len(syms),
       "incoming_include_candidates":incoming[key],
       "outgoing_include_candidates":len(inc),
       "resolved_include_candidates":sum(a[2]=="RESOLVED_CANDIDATE" for a in inc),
       "ambiguous_include_candidates":sum(a[2]=="AMBIGUOUS" for a in inc),
       "unresolved_include_candidates":sum(a[2]=="UNRESOLVED" for a in inc),
       "snippet_samples":source_excerpt,
       "include_samples":[{"line":a[0],"name":a[1],"resolution":a[2],"candidate_paths":a[3]} for a in inc[:24]],
       "symbol_samples":[{"line":int(s["line"]),"name":s["symbol"]} for s in syms[:24]]},
    "review":{"status":machine,"reviewer":None,"semantic_signoff":False,
              "relocation_contracts_confirmed":False,
              "notes":"This evidence is an automated triage snapshot, not semantic approval. Regex matches and include paths may have false positives or missed generated edges."}}
   serialized=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=True)
   evidence_digest=digest(serialized.encode("utf-8"))
   ev.write(serialized+"\n")
   qw.writerow({"repo":r["repo"],"path":r["path"],"blob_sha":r["blob_sha"],
    "category":r["category"],"priority":p,"lexical_match_count":len(lex),
    "direct_include_count":len(inc),
    "resolved_includes":sum(z[2]=="RESOLVED_CANDIDATE" for z in inc),
    "ambiguous_includes":sum(z[2]=="AMBIGUOUS" for z in inc),
    "unresolved_includes":sum(z[2]=="UNRESOLVED" for z in inc),
    "incoming_includes":incoming[key],"symbol_candidates":len(syms),
    "machine_review_status":machine,"evidence_sha256":evidence_digest})
   if i%500==0:dump(x.out/"review_checkpoints"/f"files_{i:05d}.json",{
     "files_processed":i,"phase1_semantic_signoffs":0,
     "source_blobs_verified":status["CANDIDATE_ONLY_SOURCE_HASH_VERIFIED"],
     "status":"REVIEW_INCOMPLETE"})
 result={"tracked_files":len(manifest),"source_blobs_sha1_verified":status["CANDIDATE_ONLY_SOURCE_HASH_VERIFIED"],
  "source_candidates":sum(len(v) for v in candidates.values()),
  "lexical_sites":sum(map(len,candidates.values())),"include_edges":dict(include_stats),
  "symbol_candidates":sum(map(len,symbols.values())),
  "priority_distribution":dict(files_by_priority),
  "machine_review_status":dict(status),
  "phase1_semantic_mapping_complete":False,"semantic_signoff_count":0,
  "warning":"Machine-generated evidentiary dossiers with blob-pinned snippets do not constitute independent semantic review."}
 dump(x.out/"second_pass_summary.json",result)
 print(json.dumps(result,indent=2))
if __name__=="__main__":
 if "--self-test" in sys.argv:self_test()
 else:
  try:main()
  except Exception as e:
   print("SECOND PASS FAILED:",repr(e),file=sys.stderr)
   raise

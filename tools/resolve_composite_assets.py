#!/usr/bin/env python3
"""Resolve special composite graphics through pinned Makefile prerequisite rules."""
from __future__ import annotations
import csv,gzip,json,re,hashlib
from pathlib import Path
OUT=Path("audit-output");ROOT=Path("upstream/pokefirered")
REPO="pret/pokefirered"
EXPECTED="39b952cd45b6a34eb98318a76aa531fcafff134d"
FIELDS=["consumer_path","consumer_git_blob_sha","consumer_source_line",
"requested_generated_artifact","composite_rule_file","composite_rule_blob_sha",
"composite_rule_line","component_order","component_generated_artifact",
"component_checked_in_source","component_source_sha","component_resolution"]
VAR=re.compile(r"\$\(([A-Za-z_][A-Za-z_0-9]*)\)")
def blob(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def readrows(name):
 with gzip.open(OUT/name,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def logical(lines):
 i=0
 while i<len(lines):
  start=i+1;v=lines[i]
  while v.rstrip().endswith("\\") and i+1<len(lines):
   i+=1;v=v.rstrip()[:-1]+" "+lines[i].strip()
  yield start,v
  i+=1
def expand(s,variables,depth=0):
 if depth>10:raise RuntimeError("Too many nested graphics Make variables")
 new=VAR.sub(lambda x: variables.get(x.group(1),x.group()),s)
 return expand(new,variables,depth+1) if new!=s else new
def source_of(name,manifest):
 core=name
 while core.endswith((".lz",".rl")):core=core.rsplit(".",1)[0]
 for suffix in (".4bpp",".8bpp",".1bpp",".gbapal"):
  if core.endswith(suffix):
   stem=core[:-len(suffix)]
   for e in ((".pal",".png") if suffix==".gbapal" else (".png",)):
    p=stem+e
    if p in manifest:return p
 return None
def main():
 manifest={r["path"]:r for r in readrows("tracked_file_manifest.csv.gz") if r["repo"]==REPO}
 raw=(ROOT/"graphics_file_rules.mk").read_bytes()
 if blob(raw)!=EXPECTED:raise RuntimeError("Graphics rules SHA changed")
 ls=list(logical(raw.decode("utf-8","surrogateescape").splitlines()))
 vars={}
 for line,t in ls:
  m=re.match(r"^\s*([A-Z][A-Z_0-9]*)\s*:=\s*(.*)",t)
  if m:vars[m.group(1)]=m.group(2)
 rules={}
 for n,s in ls:
  s=expand(s,vars)
  if ":" not in s or s.lstrip().startswith(("#",".","\t")):continue
  left,right=s.split(":",1)
  target=left.strip()
  if not target or target.startswith("%") or " " in target or "$(" in target:continue
  prereqs=[p for p in right.split() if not p.startswith(("%",":"))]
  if prereqs:rules[target]=(n,prereqs)
 unresolved=[];composites=[]
 for rec in readrows("generated_asset_provenance_edges.csv.gz"):
  if rec["resolution"]!="GENERATED_TARGET_WITHOUT_DIRECT_SOURCE":continue
  target=rec["generated_path"];core=target
  while core.endswith((".lz",".rl")):core=core.rsplit(".",1)[0]
  rule=rules.get(core)
  if not rule:
   unresolved.append({"target":target,"consumer":rec["consumer"],"reason":"NO_EXPLICIT_COMPOSITE_RULE"})
   continue
  n,components=rule
  for pos,c in enumerate(components):
   src=source_of(c,manifest)
   if not src:unresolved.append({"target":target,"component":c,"reason":"COMPONENT_SOURCE_MISSING"})
   composites.append({"consumer_path":rec["consumer"],"consumer_git_blob_sha":rec["source_sha"],
    "consumer_source_line":rec["source_line"],"requested_generated_artifact":target,
    "composite_rule_file":"graphics_file_rules.mk","composite_rule_blob_sha":EXPECTED,
    "composite_rule_line":n,"component_order":pos,"component_generated_artifact":c,
    "component_checked_in_source":src or "",
    "component_source_sha":manifest[src]["blob_sha"] if src else "",
    "component_resolution":"EXPLICIT_MAKE_RULE_COMPONENT_SOURCE_CANDIDATE" if src else "UNRESOLVED_COMPOSITE_CONSTITUENT"})
 with gzip.open(OUT/"composite_graphics_source_edges.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(composites)
 summary={"previous_unresolved_generated_literals":17,
 "composite_targets_identified":len(set(x["requested_generated_artifact"] for x in composites)),
 "composite_component_edges":len(composites),
 "component_tracked_source_matches":sum(bool(x["component_checked_in_source"]) for x in composites),
 "unresolved_composite_component_count":len(unresolved),
 "unresolved_samples":unresolved[:50],
 "all_17_generated_literals_have_explicit_composite_rules":
   len(set(x["requested_generated_artifact"] for x in composites))==17,
 "rule_blob_sha_verified":EXPECTED,"phase1_mapping_complete":False,
 "limitations":["Expanded simple Make variables, not an evaluated make dependency graph.",
                "Component order follows the explicit rule but output binary concatenation is not executed.",
                "Final LZ compression and pointer tables are separate build stages."]}
 (OUT/"composite_graphics_source_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k!="unresolved_samples"},indent=2))
 if not summary["all_17_generated_literals_have_explicit_composite_rules"]:
  raise RuntimeError("Not all 17 unmatched composite graphics targets mapped")
 if unresolved:raise RuntimeError("Composite graphics constituents missing: "+str(unresolved[:5]))
if __name__=="__main__":main()

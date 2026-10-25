#!/usr/bin/env python3
"""FireRed generated graphics references: source -> build-rule -> consumed output.

Match literal paths to the pinned Makefile's suffix rules and to actual checked-in
PNG/PAL upstream files. The generated artifact itself may not exist in Git;
that's expected, NOT proof of missing asset or completed build.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("audit-output")
COMMIT="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
GEN_SUFFIXES=(".1bpp",".4bpp",".8bpp",".gbapal")
# Handles foo.4bpp, foo.4bpp.lz, foo.4bpp.rl, foo.gbapal.lz, etc.
GEN_QUOTED=re.compile(
 r'(?P<q>["\x27])(?P<path>(?:[A-Za-z0-9_.$/-]+/)?[A-Za-z0-9_.$/-]+'
 r'\.(?:1bpp|4bpp|8bpp|gbapal)(?:\.(?:lz|rl))?)(?P=q)',re.I)
FIELDS=("source_repo","source_path","source_sha","source_line","consumer",
  "generated_path","derived_primary","derived_primary_sha","alternate_source",
  "alternate_source_sha","build_rule","build_rule_path","build_rule_sha",
  "build_rule_line","resolution","transform_chain","scope")
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def canonical(path,sha):
 p=ROOT/path
 data=p.read_bytes() if not p.is_symlink() else os.readlink(p).encode()
 if gitsha(data)!=sha:
  data=subprocess.check_output(["git","-C",str(ROOT),"cat-file","blob",sha])
 if gitsha(data)!=sha:raise RuntimeError("Pinned blob changed "+path)
 return data
def main():
 manifest={}
 with gzip.open(OUT/"tracked_file_manifest.csv.gz","rt",encoding="utf-8",newline="") as f:
  for r in csv.DictReader(f):
   if r["repo"]=="pret/pokefirered":
    manifest[r["path"]]=r
 assert len(manifest)==9857
 rules=canonical("Makefile",manifest["Makefile"]["blob_sha"]).decode("utf-8","surrogateescape").splitlines()
 rulelines={}
 for n,line in enumerate(rules,1):
  m=re.search(r"^%\.((?:1|4|8)bpp|gbapal|lz|rl):\s*%\.?(png|pal)?\s*(?:;|$)",line.strip())
  if m:rulelines[(m.group(1),m.group(2) or "")]=n
 required=[("1bpp","png"),("4bpp","png"),("8bpp","png"),("gbapal","pal"),
           ("gbapal","png"),("lz",""),("rl","")]
 for k in required:
  if k not in rulelines:raise RuntimeError("Unexpected graphics Makefile rule changed "+str(k))
 assert "graphics_file_rules.mk" in "\n".join(rules)
 counts=collections.Counter();filemap=collections.defaultdict(int);distinct=set()
 with gzip.open(OUT/"generated_asset_provenance_edges.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
  for path,row in manifest.items():
   if row["category"] not in ("source","structured_or_text_config"):continue
   if Path(path).suffix.lower() not in {".c",".h",".cpp",".s",".asm",".inc",".mk",".txt",".sh",".py"} and Path(path).name not in {"Makefile","GNUmakefile"}:continue
   data=canonical(path,row["blob_sha"])
   if b"\0" in data:continue
   for lineno,line in enumerate(data.decode("utf-8","surrogateescape").splitlines(),1):
    for m in GEN_QUOTED.finditer(line):
     generated=m.group("path").lstrip("./")
     suffix=None;compressed=None;stem=None
     for e in (".lz",".rl"):
      if generated.lower().endswith(e):
       compressed=e[1:];generated_core=generated[:-len(e)];break
     else:generated_core=generated
     for e in GEN_SUFFIXES:
      if generated_core.lower().endswith(e):
       suffix=e[1:];stem=generated_core[:-len(e)];break
     if not suffix:continue
     primary_ext=".pal" if suffix=="gbapal" else ".png"
     primary=stem+primary_ext
     alt=stem+".png" if suffix=="gbapal" else ""
     primary_row=manifest.get(primary);alt_row=manifest.get(alt) if alt else None
     if primary_row:source=primary
     elif alt_row:source=alt
     else:source=None
     rule_ext="pal" if primary_row and suffix=="gbapal" else "png"
     buildrule=rulelines[(suffix,rule_ext)]
     if source:
      resolution="TRACKED_BUILD_SOURCE_CANDIDATE"
      counts["sources_matched"]+=1;distinct.add(source)
     else:
      resolution="GENERATED_TARGET_WITHOUT_DIRECT_SOURCE"
      counts["source_missing_or_composite"]+=1
     transform=suffix+(("+"+compressed) if compressed else "")
     if compressed:
      if (compressed,"") not in rulelines:raise RuntimeError("Unknown compression rule")
     w.writerow({"source_repo":"pret/pokefirered","source_path":path,
       "source_sha":row["blob_sha"],"source_line":lineno,
       "consumer":path,"generated_path":m.group("path"),"derived_primary":source or "",
       "derived_primary_sha":manifest[source]["blob_sha"] if source else "",
       "alternate_source":alt if alt_row and alt!=source else "",
       "alternate_source_sha":alt_row["blob_sha"] if alt_row and alt!=source else "",
       "build_rule":"graphics converter" if source else "graphics converter or custom composite",
       "build_rule_path":"Makefile","build_rule_sha":manifest["Makefile"]["blob_sha"],
       "build_rule_line":buildrule,"resolution":resolution,"transform_chain":transform,
       "scope":"PINNED_CONSUMER_LITERAL_AND_GENERAL_MAKE_RULE_NOT_BUILT"})
     counts["literal_generated_references"]+=1
     counts["suffix_"+suffix]+=1
     if compressed:counts["compressed_"+compressed]+=1
     filemap[path]+=1
     if (counts["literal_generated_references"]%500)==0:
      checkpoints=OUT/"generated_asset_checkpoints";checkpoints.mkdir(exist_ok=True)
      (checkpoints/f"refs_{counts['literal_generated_references']:05d}.json").write_text(
        json.dumps({"references_processed":counts["literal_generated_references"],
        "unique_matched_tracked_sources":len(distinct),
        "file_semantic_signoffs":0,"status":"GENERATED_GRAPHICS_CANDIDATES"})+"\n")
 summary={"observed_generated_resource_literals":counts["literal_generated_references"],
          "resolved_candidate_tracked_source":counts["sources_matched"],
          "composite_or_no_simple_source":counts["source_missing_or_composite"],
          "distinct_candidate_source_files":len(distinct),"consumer_files":len(filemap),
          "suffix_counts":{k:v for k,v in counts.items() if k.startswith(("suffix_","compressed_"))},
          "make_rules_sha":manifest["Makefile"]["blob_sha"],
          "build_rule_evidence":"Makefile lines 262-268; 'include graphics_file_rules.mk' line 245",
          "phase1_mapping_complete":False,"independent_semantic_signoffs":0,
          "limitations":["Suffix and stem correspondence does not prove which Make pattern or override executed.",
            "Special spritesheets can concatenate fragments in graphics_file_rules.mk; missing direct PNGs are queued.",
            "Generated .4bpp, .gbapal, .lz and .rl do not normally appear as tracked Git blobs.",
            "Full build output contents, palette order and sprite width semantics require tool execution."]}
 (OUT/"generated_asset_provenance_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Validate every mapping anchor against pinned Git bytes, not only file hashes."""
import csv,hashlib,io,json,re,sys,zipfile
from pathlib import Path
PINS={
"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
"huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
"huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55",
"pret/agbcc":"da598c1d918402c42c0c0d7128ba14567f3175e9"}
MAP="maps/XGBA_Mapping_Register_v1.5_With_Includes_29068.csv"
def verify(root,archive):
 cache={};bad=[];total=0;types={}
 with zipfile.ZipFile(archive) as z:
  with io.TextIOWrapper(z.open(MAP),encoding="utf-8",newline="") as stream:
   for row in csv.DictReader(stream):
    total+=1
    key=row["repo"],row["path"]
    if row["repo"] not in PINS or row["revision"]!=PINS[row["repo"]]:
     bad.append((row["record_id"],"wrong pinned revision"));continue
    if key not in cache:
     p=root/row["repo"].split("/")[-1]/row["path"]
     if not p.is_file():
      cache[key]=(None,None)
     else:
      data=p.read_bytes()
      sha=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
      cache[key]=(sha,data.decode("utf-8","surrogateescape").splitlines())
    sha,lines=cache[key]
    if sha!=row["source_blob_sha"]:
     bad.append((row["record_id"],"source blob mismatch"));continue
    try:line=int(row["line"])
    except ValueError:bad.append((row["record_id"],"invalid line"));continue
    if not lines or not 1<=line<=len(lines):
     bad.append((row["record_id"],"line outside pinned source"));continue
    typ=row["record_type"];types[typ]=types.get(typ,0)+1
    if typ=="include_dependency_candidate":
     src=lines[line-1]
     if not re.match(r'^\s*#\s*include\s*[<"]',src):
      bad.append((row["record_id"],"include record not anchored to include directive"))
 report={"rows_checked":total,"unique_source_files_checked":len(cache),
         "record_types":types,"bad_anchors":len(bad),"bad_anchor_samples":bad[:50],
         "status":"PASS" if not bad and total==29068 else "FAIL",
         "semantic_review_complete":False}
 p=Path("audit-output/map_anchor_validation.json");p.parent.mkdir(exist_ok=True)
 p.write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k!="bad_anchor_samples"},indent=2))
 if report["status"]!="PASS":sys.exit(2)
if __name__=="__main__":verify(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"),Path(sys.argv[2] if len(sys.argv)>2 else "imports/XGBA_Phase1_v1.5_Complete_Workpack.zip"))

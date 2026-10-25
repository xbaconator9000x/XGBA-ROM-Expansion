#!/usr/bin/env python3
"""Validate imported v1.5 source mapping workpack before accepting it as persisted."""
import csv,hashlib,io,json,sys,zipfile
from pathlib import Path
EXPECTED="XGBA_Phase1_v1.5_Complete_Workpack.zip"
MAPNAME="maps/XGBA_Mapping_Register_v1.5_With_Includes_29068.csv"
def fail(msg):raise SystemExit("IMPORT REJECTED: "+msg)
def run(path):
 if not path.is_file():fail("Missing archive at "+str(path))
 if path.name!=EXPECTED:fail("Wrong archive name")
 if path.stat().st_size>25*1024*1024:fail("Archive exceeds GitHub browser upload limit")
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  if len(names)!=len(set(names)):fail("Duplicate ZIP member path")
  if any(n.startswith("/") or ".." in Path(n).parts or "\\" in n for n in names):fail("Unsafe ZIP member path")
  if z.testzip():fail("Invalid member CRC")
  if "SHA256_MANIFEST_v15.json" not in names:fail("No file-integrity manifest")
  hashes=json.loads(z.read("SHA256_MANIFEST_v15.json"))
  if hashes["checked_file_count"]!=len(hashes["sha256"]):fail("Manifest count mismatch")
  if set(hashes["sha256"])!=set(names)-{"SHA256_MANIFEST_v15.json"}:fail("Manifest member list mismatch")
  for n,d in hashes["sha256"].items():
   if hashlib.sha256(z.read(n)).hexdigest()!=d:fail("SHA-256 mismatch on "+n)
  if MAPNAME not in names:fail("Complete mapping CSV missing")
  with z.open(MAPNAME) as fh:
   lines=io.TextIOWrapper(fh,encoding="utf-8",newline="")
   reader=csv.DictReader(lines)
   ids=set();old=0;linec=0;newsite=0;includes=0
   for row in reader:
    linec+=1
    rid=row["record_id"]
    if rid in ids:fail("Duplicate mapping record ID "+rid)
    ids.add(rid)
    if rid.startswith("XC15I-"):includes+=1
    elif rid.startswith("XC15-"):newsite+=1
    elif rid.startswith("XC-"):old+=1
    else:fail("Unknown record prefix "+rid)
    if not row["source_blob_sha"] or len(row["source_blob_sha"])!=40:fail("Missing blob SHA "+rid)
   if (linec,old,newsite,includes)!=(29068,11024,4315,13729):
    fail("Mapping record composition mismatches authoritative checksum manifest")
  with z.open("evidence/phase1_mapping_gate.json") as f:
   gate=json.load(f)
  if gate.get("decision")!="FAIL_INCOMPLETE":fail("Unverified mapping completion claim")
  report={"archive_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
    "archive_bytes":path.stat().st_size,"verified_contents":len(hashes["sha256"]),
    "mapping_records":linec,"original_preserved":old,"new_lexical":newsite,"include_candidates":includes,
    "semantic_review_complete":False,"import_integrity":"PASS"}
  Path("import_report.json").write_text(json.dumps(report,indent=2)+"\n")
  print(json.dumps(report,indent=2))
if __name__=="__main__":run(Path(sys.argv[1] if len(sys.argv)>1 else "imports/"+EXPECTED))

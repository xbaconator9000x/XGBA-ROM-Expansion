#!/usr/bin/env python3
"""Fail-closed Phase 1 mapping gate; never conflates source census with semantic signoff."""
import argparse,csv,gzip,hashlib,json,re,sys
from pathlib import Path
from phase1_review_attestations import load_trust, verify_attestation, self_test as review_attestation_self_test
GOOD={"mapped_dependencies","reviewed_not_relevant","excluded_with_evidence"}
SHA1=re.compile(r"^[0-9a-f]{40}$")
SHA256=re.compile(r"^[0-9a-f]{64}$")
def sha256(data):return hashlib.sha256(data).hexdigest()
def rows(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def disposition_problems(d,src,review):
 k=(d.get("repo"),d.get("path"));issues=[]
 if d.get("git_blob_sha")!=src["blob_sha"]:
  issues.append("Disposition SHA mismatch "+str(k))
 if d.get("evidence_sha256")!=review["evidence_sha256"]:
  issues.append("Disposition has stale evidence "+str(k))
 status=d.get("status")
 if status not in GOOD:issues.append("Unknown/non-approved disposition "+str(k))
 if len((d.get("reviewer") or "").strip())<3:
  issues.append("Missing independent reviewer "+str(k))
 if len((d.get("semantic_rationale") or "").strip())<40:
  issues.append("Missing substantial semantic rationale "+str(k))
 if status=="mapped_dependencies" and not (d.get("contract_ids") or "").strip():
  issues.append("Mapped code without contract IDs "+str(k))
 return issues
def gate(root,dispositions):
 issues=[];audit=json.loads((root/"audit_summary.json").read_text())
 second=json.loads((root/"second_pass_summary.json").read_text())
 if not audit["census_complete"]:issues.append("Pinned source census is incomplete")
 if second["source_blobs_sha1_verified"]!=4685:issues.append("Not all 4685 source/config blobs hash-verified")
 manifest=list(rows(root/"tracked_file_manifest.csv.gz"))
 queue=list(rows(root/"semantic_review_queue.csv.gz"))
 if len(manifest)!=14834 or len(queue)!=14834:issues.append("Wrong 14834-file manifest/queue size")
 index={(m["repo"],m["path"]):m for m in manifest}
 if len(index)!=14834:issues.append("Duplicate manifest paths")
 qindex={(m["repo"],m["path"]):m for m in queue}
 if set(index)!=set(qindex):issues.append("Queue and manifest disagree")
 source_verified=0
 for row in queue:
  src=index.get((row["repo"],row["path"]),{})
  if row["blob_sha"]!=src.get("blob_sha") or not SHA1.fullmatch(row["blob_sha"]):
   issues.append("Review queue source hash mismatch: "+str((row["repo"],row["path"])))
  if not SHA256.fullmatch(row["evidence_sha256"]):
   issues.append("Invalid dossier hash: "+str((row["repo"],row["path"])))
 # Dossier payload must be bound to the source map and its individual digest
 with gzip.open(root/"candidate_review_dossiers.jsonl.gz","rt",encoding="utf-8") as f:
  dossier_count=0
  for line in f:
   if dossier_count>=len(queue):issues.append("Extra review dossiers");break
   d=json.loads(line);row=queue[dossier_count]
   payload=json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
   if sha256(payload)!=row["evidence_sha256"]:issues.append("Dossier SHA mismatch at "+str(dossier_count))
   p=d["provenance"]
   if (p["repository"],p["path"],p["git_blob_sha"])!=(row["repo"],row["path"],row["blob_sha"]):
    issues.append("Dossier provenance mismatch at "+str(dossier_count))
   dossier_count+=1
  if dossier_count!=len(queue):issues.append("Missing review dossiers")
 if not dispositions.exists():
  issues.append("No completed, reviewed semantic dispositions supplied")
  dispositions_rows=[]
 else:
  with gzip.open(dispositions,"rt",encoding="utf-8",newline="") as f:
   dispositions_rows=list(csv.DictReader(f))
 # Trusted reviewer keys are provisioned separately; no CSV field is an attestation.
 trusted=load_trust()
 seen=set();approved_keys=set();by_status={}
 for d in dispositions_rows:
  k=d.get("repo"),d.get("path")
  duplicate=k in seen
  if duplicate:issues.append("Duplicate disposition "+str(k))
  seen.add(k);src=index.get(k)
  if not src:issues.append("Disposition for unknown source "+str(k));continue
  problems=disposition_problems(d,src,qindex[k])
  if not problems:
   verified,reason=verify_attestation(d,trusted)
   if not verified:problems.append("Unverified independent review "+str(k)+": "+reason)
  issues.extend(problems)
  if not duplicate and not problems:
   approved_keys.add(k)
   status=d["status"]
   by_status[status]=by_status.get(status,0)+1
 missing=set(index)-seen
 if missing:issues.append(f"{len(missing)} tracked files lack independent semantic dispositions")
 unapproved=set(index)-approved_keys
 if len(unapproved)>len(missing):
  issues.append(f"{len(unapproved)} tracked files lack valid independent semantic dispositions")
 approved=len(approved_keys)
 expected_reviews=sum(x["priority"]=="P0" for x in queue)
 result={"phase":"Phase 1 source mapping only","decision":"PASS_MAPPING_ONLY" if not issues else "FAIL_INCOMPLETE",
  "verified_source_manifest_entries":len(index),"source_blobs_verified":second["source_blobs_sha1_verified"],
  "machine_generated_dossiers":len(queue),"approved_semantic_dispositions":approved,
  "remaining_dispositions":len(unapproved),"p0_review_candidates":expected_reviews,
  "disposition_status_counts":by_status,
  "not_in_phase1":"Emulator modification, external resource runtime, ROM build and regression tests are Phase 2/release tasks.",
  "issues":issues[:200],"issues_truncated":len(issues)>200}
 (root/"phase1_mapping_gate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"decision":result["decision"],"remaining":len(unapproved),"issues":len(issues)},indent=2))
 return result["decision"]
def self_test():
 src={"blob_sha":"a"*40}
 review={"evidence_sha256":"b"*64}
 valid={"repo":"pret/pokefirered","path":"src/main.c",
        "git_blob_sha":src["blob_sha"],"evidence_sha256":review["evidence_sha256"],
        "status":"mapped_dependencies","reviewer":"independent-reviewer",
        "semantic_rationale":"Source-anchored review of the exact pinned file and its dependencies.",
        "contract_ids":"FIRERED_SCRIPT_NATIVE_CALLBACK"}
 assert not disposition_problems(valid,src,review)
 for field,bad in [
  ("git_blob_sha","c"*40),("evidence_sha256","d"*64),
  ("status","candidate_only"),("reviewer",""),("reviewer","  "),
  ("semantic_rationale","too short"),("contract_ids","  ")]:
  item={**valid,field:bad}
  assert disposition_problems(item,src,review),f"Fail-open disposition field: {field}"
 for status in ("reviewed_not_relevant","excluded_with_evidence"):
  item={**valid,"status":status,"contract_ids":""}
  assert not disposition_problems(item,src,review)
 # Structural validity is NOT review approval; the separate signature gate is mandatory.
 review_attestation_self_test()
 print("Phase 1 disposition structural and attestation fail-closed negative controls: PASS")
if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--root",type=Path,default=Path("audit-output"))
 a.add_argument("--dispositions",type=Path,default=Path("semantic_dispositions.csv.gz"))
 a.add_argument("--self-test",action="store_true")
 x=a.parse_args()
 if x.self_test:
  self_test()
  sys.exit(0)
 try:
  outcome=gate(x.root,x.dispositions)
  sys.exit(0 if outcome=="PASS_MAPPING_ONLY" else 2)
 except Exception as exc:
  x.root.mkdir(parents=True,exist_ok=True)
  (x.root/"phase1_mapping_gate.json").write_text(json.dumps({"decision":"FAIL_INCOMPLETE","error":repr(exc)},indent=2)+"\n")
  print("Mapping verification FAILED:",exc,file=sys.stderr)
  sys.exit(2)

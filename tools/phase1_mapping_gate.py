#!/usr/bin/env python3
"""Fail-closed Phase 1 mapping gate; never conflates source census with semantic signoff."""
import argparse,csv,gzip,hashlib,json,os,re,sys
from pathlib import Path
from phase1_copilot_receipts import github_get_json, load_receipts, validate_receipt
GOOD={"mapped_dependencies","reviewed_not_relevant","excluded_with_evidence"}
SHA1=re.compile(r"^[0-9a-f]{40}$")
SHA256=re.compile(r"^[0-9a-f]{64}$")
LEGACY_RECEIPT_MARKER="XGBA-Phase1-Legacy-Disposition-SHA256: "
DECISION_MARKER="XGBA-Phase1-Decision: APPROVED"
def sha256(data):return hashlib.sha256(data).hexdigest()
def rows(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def legacy_disposition_digest(d):
 payload={k:v for k,v in d.items() if k!="reviewer_provenance"}
 return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode())
def legacy_provenance(d):
 raw=d.get("reviewer_provenance")
 if isinstance(raw,str):
  try:raw=json.loads(raw)
  except json.JSONDecodeError:return None
 return raw if isinstance(raw,dict) else None
def disposition_problems(d,src,review):
 k=(d.get("repo"),d.get("path"));issues=[]
 if d.get("git_blob_sha")!=src["blob_sha"]:
  issues.append("Disposition SHA mismatch "+str(k))
 if d.get("evidence_sha256")!=review["evidence_sha256"]:
  issues.append("Disposition has stale evidence "+str(k))
 status=d.get("status")
 if status not in GOOD:issues.append("Unknown/non-approved disposition "+str(k))
 reviewer=(d.get("reviewer") or "").strip()
 if len(reviewer)<3:
  issues.append("Missing independent reviewer "+str(k))
 if "copilot" in reviewer.casefold():
  issues.append("Copilot dispositions require an attributable receipt "+str(k))
 provenance=legacy_provenance(d)
 if not isinstance(provenance,dict):
  issues.append("Legacy disposition lacks attributable GitHub reviewer provenance "+str(k))
 else:
  reviewer_login=provenance.get("reviewer_login")
  if (not isinstance(reviewer_login,str)
      or reviewer_login.casefold()!=reviewer.casefold()
      or not isinstance(provenance.get("repository"),str)
      or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",provenance.get("repository",""))
      or not isinstance(provenance.get("pull_number"),int) or provenance["pull_number"]<1
      or not isinstance(provenance.get("review_id"),int) or provenance["review_id"]<1
      or not isinstance(provenance.get("head_sha"),str) or not SHA1.fullmatch(provenance["head_sha"])
      or provenance.get("disposition_sha256")!=legacy_disposition_digest(d)):
   issues.append("Legacy disposition reviewer provenance is invalid or stale "+str(k))
 if len((d.get("semantic_rationale") or "").strip())<40:
  issues.append("Missing substantial semantic rationale "+str(k))
 if status=="mapped_dependencies" and not (d.get("contract_ids") or "").strip():
  issues.append("Mapped code without contract IDs "+str(k))
 return issues
def verify_legacy_provenance(d,repository,github_api=github_get_json):
 provenance=legacy_provenance(d)
 if not isinstance(provenance,dict):return ["Missing legacy GitHub reviewer provenance"]
 if provenance.get("repository")!=repository:
  return ["Legacy reviewer provenance belongs to another repository"]
 api_root=f"https://api.github.com/repos/{repository}"
 try:
  pull=github_api(f"{api_root}/pulls/{provenance['pull_number']}")
  reviews=github_api(f"{api_root}/pulls/{provenance['pull_number']}/reviews?per_page=100")
  if not isinstance(reviews,list) or len(reviews)>=100:
   return ["Legacy GitHub review list is missing or exceeds the fail-closed lookup limit"]
  reviewer=provenance["reviewer_login"]
  body_hash=provenance["disposition_sha256"]
  matching=[
   review for review in reviews
   if review.get("id")==provenance["review_id"]
   and review.get("user",{}).get("login","").casefold()==reviewer.casefold()
   and review.get("commit_id")==provenance["head_sha"]
   and review.get("state")=="COMMENTED"
   and review.get("submitted_at")
   and LEGACY_RECEIPT_MARKER+body_hash in (review.get("body") or "")
   and DECISION_MARKER in (review.get("body") or "")
  ]
  author=pull.get("user",{}).get("login","")
  if (not author or author.casefold()==reviewer.casefold()
      or len(matching)!=1):
   return ["Legacy GitHub review is missing, unattributed, or conflicts with PR author"]
 except (KeyError,AttributeError,TypeError,ValueError,OSError) as exc:
  return ["Unable to verify legacy GitHub reviewer provenance: "+str(exc)]
 return []
def gate(root,dispositions,copilot_receipts=None,source_root=None,expected_head=None,
        repository=None,github_api=github_get_json):
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
 dossiers={}
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
   dossiers[(row["repo"],row["path"])]=d
   dossier_count+=1
  if dossier_count!=len(queue):issues.append("Missing review dossiers")
 if not dispositions.exists():
  dispositions_rows=[]
 else:
  with gzip.open(dispositions,"rt",encoding="utf-8",newline="") as f:
   dispositions_rows=list(csv.DictReader(f))
 seen=set();approved_keys=set();by_status={}
 for d in dispositions_rows:
  k=d.get("repo"),d.get("path")
  duplicate=k in seen
  if duplicate:issues.append("Duplicate disposition "+str(k))
  seen.add(k);src=index.get(k)
  if not src:issues.append("Disposition for unknown source "+str(k));continue
  problems=disposition_problems(d,src,qindex[k])
  if not problems:
   problems=verify_legacy_provenance(d,repository,github_api) if repository else [
    "Legacy disposition cannot be attributed without repository context"]
  issues.extend(problems)
  if not duplicate and not problems:
   approved_keys.add(k)
   status=d["status"]
   by_status[status]=by_status.get(status,0)+1
 copilot_count=0
 copilot_keys=set()
 if copilot_receipts is not None and Path(copilot_receipts).exists():
  receipts,receipt_load_issues=load_receipts(copilot_receipts)
  issues.extend(receipt_load_issues)
  receipt_seen=set()
  for receipt in receipts:
   key,problems=validate_receipt(receipt,queue=qindex,dossiers=dossiers,
     source_root=source_root,expected_head=expected_head,repository=repository)
   if key in receipt_seen:
    issues.append("Duplicate Copilot review receipt "+str(key))
    continue
   receipt_seen.add(key)
   if problems:
    issues.extend("Invalid Copilot receipt "+str(key)+": "+problem for problem in problems)
    continue
   if key in seen:
    issues.append("Conflicting legacy and Copilot dispositions "+str(key))
    continue
   approved_keys.add(key)
   copilot_keys.add(key)
   by_status["copilot_reviewed"]=by_status.get("copilot_reviewed",0)+1
   copilot_count+=1
 if not dispositions.exists() and not copilot_count:
  issues.append("No completed, reviewed semantic dispositions supplied")
 missing=set(index)-seen-copilot_keys
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
  "disposition_status_counts":by_status,"copilot_receipts_accepted":copilot_count,
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
        "status":"mapped_dependencies","reviewer":"reviewer",
        "semantic_rationale":"Source-anchored review of the exact pinned file and its dependencies.",
        "contract_ids":"FIRERED_SCRIPT_NATIVE_CALLBACK"}
 valid["reviewer_provenance"]=json.dumps({
  "repository":"xbaconator9000x/XGBA-ROM-Expansion","pull_number":8,"review_id":1,
  "head_sha":"c"*40,"reviewer_login":"reviewer","disposition_sha256":""
 },sort_keys=True,separators=(",",":"))
 provenance=json.loads(valid["reviewer_provenance"])
 provenance["disposition_sha256"]=legacy_disposition_digest(valid)
 valid["reviewer_provenance"]=json.dumps(provenance,sort_keys=True,separators=(",",":"))
 assert not disposition_problems(valid,src,review)
 for field,bad in [
  ("git_blob_sha","c"*40),("evidence_sha256","d"*64),
  ("status","candidate_only"),("reviewer",""),("reviewer","  "),("reviewer","Copilot"),
  ("reviewer_provenance",""),
  ("semantic_rationale","too short"),("contract_ids","  ")]:
  item={**valid,field:bad}
  assert disposition_problems(item,src,review),f"Fail-open disposition field: {field}"
 for status in ("reviewed_not_relevant","excluded_with_evidence"):
  item={**valid,"status":status,"contract_ids":""}
  provenance=json.loads(item["reviewer_provenance"])
  provenance["disposition_sha256"]=legacy_disposition_digest(item)
  item["reviewer_provenance"]=json.dumps(provenance,sort_keys=True,separators=(",",":"))
  assert not disposition_problems(item,src,review)
 print("Phase 1 disposition fail-closed negative controls: PASS")
if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--root",type=Path,default=Path("audit-output"))
 a.add_argument("--dispositions",type=Path,default=Path("semantic_dispositions.csv.gz"))
 a.add_argument("--copilot-receipts",type=Path,default=Path("docs/phase1-review-readiness/copilot-semantic-review-receipts.jsonl"))
 a.add_argument("--source-root",type=Path)
 a.add_argument("--expected-head",default=None)
 a.add_argument("--repository",default=None)
 a.add_argument("--self-test",action="store_true")
 x=a.parse_args()
 if x.self_test:
  self_test()
  sys.exit(0)
 try:
  outcome=gate(x.root,x.dispositions,x.copilot_receipts,x.source_root,
    x.expected_head or os.environ.get("GITHUB_SHA"),
    x.repository or os.environ.get("GITHUB_REPOSITORY"))
  sys.exit(0 if outcome=="PASS_MAPPING_ONLY" else 2)
 except Exception as exc:
  x.root.mkdir(parents=True,exist_ok=True)
  (x.root/"phase1_mapping_gate.json").write_text(json.dumps({"decision":"FAIL_INCOMPLETE","error":repr(exc)},indent=2)+"\n")
  print("Mapping verification FAILED:",exc,file=sys.stderr)
  sys.exit(2)

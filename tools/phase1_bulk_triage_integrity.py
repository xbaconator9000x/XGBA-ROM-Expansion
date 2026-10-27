#!/usr/bin/env python3
"""Reconcile 2,000 exact-pinned machine records; never count as semantic reviews."""
import hashlib,json,re
from pathlib import Path
from phase1_bulk_triage import PINS,REG,read_queue,checked_dossiers,select

RANGES=((0,199),(200,499),(500,999),(1000,1499),(1500,1999))
def check_record(x,q):
    expected={"repository":q["repo"],"pinned_commit":PINS[q["repo"]],
              "path":q["path"],"git_blob_sha1":q["blob_sha"]}
    if x.get("identity")!=expected:raise ValueError("Wrong identity or deterministic queue order")
    e=x.get("evidence",{})
    if e.get("dossier_sha256")!=q["evidence_sha256"] or e.get("snapshot_provenance_verified") is not True or e.get("source_blob_reverified_this_run") is not True:
        raise ValueError("Unverified dossier/source blob")
    if x.get("priority")!=q["priority"] or x.get("state")!="MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW" or x.get("prepared_whole_file_candidate") is not False or x.get("independent_approval") is not False:
        raise ValueError("Priority, review state or approval corrupted")
    s=x.get("whole_file_structure") or {}
    for k in ("whole_blob_sha256","all_lines_sha256"):
        if not re.fullmatch("[0-9a-f]{64}",str(s.get(k,""))):raise ValueError("Missing full-file digest")
    if not isinstance(s.get("source_lines"),int) or s["source_lines"]<0 or not isinstance(s.get("includes"),list) or not isinstance(s.get("conditional_directive_lines"),list) or not s.get("limits") or not x.get("review_obligations"):
        raise ValueError("Incomplete structural evidence")
def check_shard(d,rows,start,end):
    required={"schema":"xgba-phase1-machine-triage-v1","snapshot_gate":"FAIL_INCOMPLETE",
              "inventory_total":14834,"prepared_register_baseline":113,
              "selected_count":end-start+1,"offset":start,"source_reverified":True}
    for k,v in required.items():
        if d.get(k)!=v:raise ValueError(f"Shard {start}-{end}: {k} mismatch")
    if not isinstance(d.get("records"),list) or len(d["records"])!=end-start+1:
        raise ValueError("Shard missing records")
    for x,q in zip(d["records"],rows):check_record(x,q)
def main():
    root=Path("docs/phase1-machine-triage")
    snap=Path("semantic-snapshots/current")
    gate=json.loads((snap/"phase1_mapping_gate.json").read_text())
    if gate.get("decision")!="FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions")!=0:
        raise ValueError("Gate changed; fail closed")
    queue=read_queue(snap)
    checked_dossiers(snap,queue)
    prepared={(m.group("repo"),m.group("path")) for m in REG.finditer(Path("docs/phase1-disposition-candidates/README.md").read_text())}
    if len(prepared)!=113:raise ValueError("Prepared register changed; reconcile before triage")
    selected=select(queue,prepared,2000,0)
    seen=set();shards=[]
    for start,end in RANGES:
        path=root/f"batch-{start:06d}-{end:06d}.json"
        raw=path.read_bytes();d=json.loads(raw)
        check_shard(d,selected[start:end+1],start,end)
        ids={(r["identity"]["repository"],r["identity"]["path"]) for r in d["records"]}
        if len(ids)!=end-start+1 or ids&seen or ids&prepared:raise ValueError("Duplicate/prepared identity")
        seen.update(ids)
        shards.append({"file":path.name,"count":len(ids),"sha256":hashlib.sha256(raw).hexdigest()})
    if len(seen)!=2000:raise ValueError("Missing source identities")
    result={"schema":"xgba-phase1-machine-triage-integrity-v1","unique_source_verified_machine_records":2000,
            "new_source_verified_machine_records":1000,"inventory":14834,
            "analyst_prepared_baseline":113,"independent_approvals":0,
            "phase1_gate":"FAIL_INCOMPLETE","shards":shards,
            "scope":"Structural/lexical evidence only, not semantic signoff or runtime certification"}
    (root/"integrity-000000-001999.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Fail-closed 3000-record reconciliation; machine triage is not semantic signoff."""
import hashlib,json
from pathlib import Path
from phase1_bulk_triage import REG,read_queue,checked_dossiers,select
from phase1_bulk_triage_integrity import check_shard

RANGES=((0,199),(200,499),(500,999),(1000,1499),(1500,1999),
        (2000,2249),(2250,2499),(2500,2749),(2750,2999))
def main():
    root=Path("docs/phase1-machine-triage")
    snapshot=Path("semantic-snapshots/current")
    gate=json.loads((snapshot/"phase1_mapping_gate.json").read_text())
    if gate.get("decision")!="FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions")!=0:
        raise ValueError("Authoritative Phase 1 gate changed")
    queue=read_queue(snapshot)
    checked_dossiers(snapshot,queue)
    prepared={(m.group("repo"),m.group("path")) for m in REG.finditer(Path("docs/phase1-disposition-candidates/README.md").read_text())}
    if len(prepared)!=113:raise ValueError("Analyst-prepared register baseline changed")
    expected=select(queue,prepared,3000,0)
    seen=set();shards=[]
    for start,end in RANGES:
        path=root/f"batch-{start:06d}-{end:06d}.json"
        raw=path.read_bytes();doc=json.loads(raw)
        check_shard(doc,expected[start:end+1],start,end)
        ids={(r["identity"]["repository"],r["identity"]["path"]) for r in doc["records"]}
        if len(ids)!=end-start+1 or ids&seen or ids&prepared:raise ValueError("Overlap, duplicate or already-prepared source")
        seen.update(ids)
        shards.append({"file":path.name,"count":len(ids),"sha256":hashlib.sha256(raw).hexdigest()})
    if len(seen)!=3000:raise ValueError("Expected 3000 distinct source identities")
    report={"schema":"xgba-phase1-machine-triage-integrity-v1","inventory":14834,
            "unique_source_verified_machine_records":3000,"new_source_verified_machine_records":1000,
            "analyst_prepared_baseline":113,"independent_approvals":0,"phase1_gate":"FAIL_INCOMPLETE",
            "shards":shards,"scope":"Exact-source structural/lexical processing only; not whole-file semantic approval"}
    (root/"integrity-000000-002999.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"verified":3000,"new":1000,"prepared":113,"approved":0,"gate":"FAIL_INCOMPLETE"},sort_keys=True))
if __name__=="__main__":main()

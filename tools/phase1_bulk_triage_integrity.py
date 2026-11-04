#!/usr/bin/env python3
"""Reconcile 2,000 exact-pinned machine records; never count as semantic reviews."""
import hashlib,json,re
from pathlib import Path
from phase1_bulk_triage import PINS,REG,read_queue,checked_dossiers,select

RANGES=((0,199),(200,499),(500,999),(1000,1499),(1500,1999))
def check_record(x,q,schema='xgba-phase1-machine-triage-v1'):
    expected={"repository":q["repo"],"pinned_commit":PINS[q["repo"]],
              "path":q["path"],"git_blob_sha1":q["blob_sha"]}
    if x.get("identity")!=expected:raise ValueError("Wrong identity or deterministic queue order")
    e=x.get("evidence",{})
    if e.get("dossier_sha256")!=q["evidence_sha256"] or e.get("snapshot_provenance_verified") is not True or e.get("source_blob_reverified_this_run") is not True:
        raise ValueError("Unverified dossier/source blob")
    if x.get("priority")!=q["priority"] or x.get("state")!="MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW" or x.get("prepared_whole_file_candidate") is not False or x.get("independent_approval") is not False:
        raise ValueError("Priority, review state or approval corrupted")
    s=x.get("whole_file_structure") or {}
    if not re.fullmatch("[0-9a-f]{64}",str(s.get("whole_blob_sha256",""))):
        raise ValueError("Missing full-byte digest")
    if not s.get("limits") or not x.get("review_obligations"):
        raise ValueError("Missing review obligations")
    if schema=='xgba-phase1-machine-triage-v1':
        if not re.fullmatch("[0-9a-f]{64}",str(s.get("all_lines_sha256",""))):
            raise ValueError("Legacy source-line digest missing")
        if not isinstance(s.get("source_lines"),int) or s["source_lines"]<0 or not isinstance(s.get("includes"),list) or not isinstance(s.get("conditional_directive_lines"),list):
            raise ValueError("Legacy structural evidence incomplete")
        return
    if schema!='xgba-phase1-machine-triage-v2' or s.get("structure_schema")!='xgba-phase1-typed-structure-v2':
        raise ValueError("Unknown typed triage schema")
    kind=s.get("file_kind")
    m=x.get("machine_triage",{})
    if kind in ("text_source","authored_text"):
        if m.get("lexical_evidence_applicable") is not True:
            raise ValueError("Text file lost lexical provenance")
        if not isinstance(s.get("source_lines"),int) or s["source_lines"]<0 or not isinstance(s.get("nonblank_lines"),int) or not 0<=s["nonblank_lines"]<=s["source_lines"]:
            raise ValueError("Text line counts invalid")
        if not re.fullmatch("[0-9a-f]{64}",str(s.get("all_lines_sha256",""))):
            raise ValueError("Text source-line digest missing")
        if not isinstance(s.get("includes"),list) or not isinstance(s.get("conditional_directive_lines"),list) or not isinstance(s.get("risk_flags_line_anchors"),dict):
            raise ValueError("Text anchor structure invalid")
        for line in s["conditional_directive_lines"]:
            if type(line)!=int or not 1<=line<=s["source_lines"]:raise ValueError("Conditional anchor out of range")
        for item in s["includes"]:
            if type(item)!=dict or type(item.get("line"))!=int or not 1<=item["line"]<=s["source_lines"] or not isinstance(item.get("include"),str):
                raise ValueError("Include anchor invalid")
        for hits in s["risk_flags_line_anchors"].values():
            if not isinstance(hits,list) or any(type(line)!=int or not 1<=line<=s["source_lines"] for line in hits):
                raise ValueError("Risk anchor out of range")
        return
    if kind not in ("opaque_binary","image_png","image_binary","compiled_rom","compiled_binary","audio_binary","archive_binary","unknown_binary"):
        raise ValueError("Unrecognized file kind")
    if type(s.get("byte_length"))!=int or s["byte_length"]<0 or not re.fullmatch("[0-9a-f]{0,32}",str(s.get("format_signature_hex",""))):
        raise ValueError("Binary byte evidence invalid")
    if any(s.get(k) is not None for k in ("source_lines","nonblank_lines","all_lines_sha256")):
        raise ValueError("Binary bytes presented as source lines")
    if any(s.get(k)!=[] for k in ("includes","conditional_directive_lines")) or s.get("risk_flags_line_anchors")!={}:
        raise ValueError("Binary lexical anchors leaked")
    if m.get("lexical_evidence_applicable") is not False or any(k in m for k in ("lexical_rule_counts","symbol_samples","include_samples")):
        raise ValueError("Binary dossier lexical hints leaked")
def check_shard(d,rows,start,end):
    schema=d.get("schema")
    if schema not in ("xgba-phase1-machine-triage-v1","xgba-phase1-machine-triage-v2"):
        raise ValueError("Unknown machine-triage shard schema")
    required={"snapshot_gate":"FAIL_INCOMPLETE",
              "inventory_total":14834,"prepared_register_baseline":113,
              "selected_count":end-start+1,"offset":start,"source_reverified":True}
    for k,v in required.items():
        if d.get(k)!=v:raise ValueError(f"Shard {start}-{end}: {k} mismatch")
    if not isinstance(d.get("records"),list) or len(d["records"])!=end-start+1:
        raise ValueError("Shard missing records")
    for x,q in zip(d["records"],rows):check_record(x,q,schema)
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

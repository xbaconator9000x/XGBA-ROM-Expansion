#!/usr/bin/env python3
"""Verify curated source-interpreted P0 candidate register against five Git pins.

Do NOT approve file dispositions. Curated roles and evidence links are review
tickets, not proof of dynamic alias analysis or independent reviewer consent.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

EXPECTED_PINS={
    "pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
    "huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
    "huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/agbcc":"da598c1d918402c42c0c0d7128ba14567f3175e9",
}
REGISTRY=Path("semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json")
OUT=Path("audit-output/curated_p0_source_semantic_review_coverage.json")

def git_blob_sha(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def validate(root,document):
    if document.get("schema")!="xgba.phase1.curated_cross_source_semantic_review_candidates.v1":
        raise RuntimeError("Unrecognized curated semantic candidate registry schema")
    if document.get("repository_pins")!=EXPECTED_PINS:
        raise RuntimeError("Curated registry repository pin changed")
    records=document.get("candidate_files")
    if not isinstance(records,list) or len(records)!=29 or document.get("candidate_file_count")!=29:
        raise RuntimeError("Expected 29 curated source interpretation candidates")
    if document.get("independent_review_approvals")!=0 or document.get("phase1_mapping_complete") is not False:
        raise RuntimeError("Curated source roles are NOT independent approvals")
    docs=document.get("source_documentation")
    if not isinstance(docs,list) or not docs or any(not isinstance(x,str) for x in docs) or len(docs)!=len(set(docs)):
        raise RuntimeError("Missing or malformed semantic source documentation")
    doc_hashes=document.get("source_documentation_git_blob_sha1")
    if not isinstance(doc_hashes,dict) or set(doc_hashes)!=set(docs) or any(
        type(sha) is not str or len(sha)!=40 or any(c not in "0123456789abcdef" for c in sha)
        for sha in doc_hashes.values()
    ):
        raise RuntimeError("Semantic source documentation hash pins incomplete or malformed")
    for doc in docs:
        file=Path(doc)
        if not doc.startswith("docs/") or ".." in file.parts or file.is_absolute() or file.suffix!=".md" or not file.is_file():
            raise RuntimeError("Unsafe or missing semantic source documentation path: "+doc)
        if git_blob_sha(file.read_bytes())!=doc_hashes[doc]:
            raise RuntimeError("Semantic source documentation content changed: "+doc)
    seen=set()
    counts=Counter()
    hashes=[]
    for entry in records:
        repo=entry["repository"]
        path=entry["source_path"]
        key=(repo,path)
        if key in seen:raise RuntimeError("Duplicate curated semantic file "+str(key))
        seen.add(key)
        pin=EXPECTED_PINS.get(repo)
        if not pin or entry.get("revision")!=pin:
            raise RuntimeError("Curated semantic file revision mismatch: "+str(key))
        if entry.get("evidence_class")!="SOURCE_PINNED_MANUAL_SEMANTIC_INTERPRETATION_WITH_SOME_COMPILED_AND_RUNTIME_SUPPORT":
            raise RuntimeError("Curated evidence class must remain source-interpreted and unsigned")
        if entry.get("independent_whole_file_signoff") is not False:
            raise RuntimeError("Unreviewed semantic candidate claimed as approved")
        if entry.get("path_complete_alias_lifetime_proof") is not False:
            raise RuntimeError("Unproved dynamic alias semantics claimed complete")
        if entry.get("status")!="CANDIDATE_AWAITING_INDEPENDENT_WHOLE_FILE_REVIEW":
            raise RuntimeError("Curated file signoff state must remain pending")
        roles=entry.get("interpreted_semantic_roles")
        if not isinstance(roles,list) or not roles or not all(
             isinstance(x,str) and x and x.replace("_","").isalnum() for x in roles):
            raise RuntimeError("Untyped or missing candidate semantic role: "+str(key))
        if ".." in Path(path).parts or path.startswith("/"):
            raise RuntimeError("Unsafe source path in curated registry")
        checkout=root/repo.split("/")[-1]
        commit=subprocess.check_output(
            ["git","-C",str(checkout),"rev-parse","HEAD"],text=True).strip()
        if commit!=pin:raise RuntimeError("Upstream source moved "+repo)
        blob=git_blob_sha((checkout/path).read_bytes())
        if blob!=entry["expected_git_blob_sha1"]:
            raise RuntimeError("Curated source content changed: "+repo+"/"+path)
        if entry.get("upstream_blob_url")!=f"https://github.com/{repo}/blob/{pin}/{path}":
            raise RuntimeError("Misleading source link "+str(key))
        counts[repo]+=1
        hashes.append(f"{repo}/{path}:{blob}")
    if set(counts)!=set(EXPECTED_PINS):
        raise RuntimeError("Five-repository candidate coverage incomplete")
    return {
        "schema":"xgba.phase1.curated_p0_review_source_identity.v1",
        "status":"PASS_SOURCE_IDENTITIES_ONLY_INDEPENDENT_SEMANTICS_NOT_SIGNED",
        "source_revisions":EXPECTED_PINS,
        "source_hashes_verified":len(hashes),
        "interpreted_candidate_files":len(records),
        "candidate_files_per_repository":dict(sorted(counts.items())),
        "curated_registry_sha256":hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        "reviewed_independently_and_approved":0,
        "path_complete_control_flow_or_alias_coverage":False,
        "phase1_mapping_complete":False,
        "limitations":[
            "Every source blob and registry role is pinned, but no independent reviewer signed off the whole file.",
            "Curated roles do not supersede the full 14,834 tracked-file inventory or 338 P0 priority queue.",
            "Static roles are not proof of timing, dynamic callback target, compiled inlining, runtime bank coherence or safe extension implementation."
        ]
    }

def self_test():
    document=json.loads(REGISTRY.read_text())
    if len(document["candidate_files"])!=29:
        raise RuntimeError("Curated manifest tampered")
    cases=[
        ("independent_whole_file_signoff",True,"Unreviewed semantic candidate claimed as approved"),
        ("revision","unverified","Curated semantic file revision mismatch"),
        ("interpreted_semantic_roles",[],"Untyped or missing candidate semantic role"),
        ("status","APPROVED","Curated file signoff state must remain pending"),
        ("path_complete_alias_lifetime_proof",True,"Unproved dynamic alias semantics claimed complete"),
        ("evidence_class","INDEPENDENT_APPROVED","Curated evidence class must remain source-interpreted and unsigned"),
    ]
    for field,value,expected in cases:
        bad=json.loads(json.dumps(document))
        bad["candidate_files"][0][field]=value
        try:
            validate(Path("__intentionally_missing_checkout__"),bad)
        except RuntimeError as ex:
            if expected not in str(ex):
                raise RuntimeError(f"Wrong rejection reason for {field}: {ex}")
        else:
            raise AssertionError("Fail-open curated semantic review guard: "+field)
    for value,expected in [
        ([],"Missing or malformed semantic source documentation"),
        (["docs/../tools/verify_curated_p0_semantic_registry.py"],"Unsafe or missing semantic source documentation path"),
    ]:
        bad=json.loads(json.dumps(document))
        bad["source_documentation"]=value
        try:
            validate(Path("__intentionally_missing_checkout__"),bad)
        except RuntimeError as ex:
            if expected not in str(ex):
                raise RuntimeError(f"Wrong source-documentation rejection reason: {ex}")
        else:
            raise AssertionError("Fail-open curated semantic documentation guard")
    for label,mutate,expected in [
        ("missing_documentation_pin",lambda d:d["source_documentation_git_blob_sha1"].pop(d["source_documentation"][0]),
         "Semantic source documentation hash pins incomplete or malformed"),
        ("altered_documentation_pin",lambda d:d["source_documentation_git_blob_sha1"].__setitem__(d["source_documentation"][0],"0"*40),
         "Semantic source documentation content changed"),
    ]:
        bad=json.loads(json.dumps(document))
        mutate(bad)
        try:
            validate(Path("__intentionally_missing_checkout__"),bad)
        except RuntimeError as ex:
            if expected not in str(ex):
                raise RuntimeError(f"Wrong documentation-hash rejection reason for {label}: {ex}")
        else:
            raise AssertionError("Fail-open curated documentation hash guard: "+label)
    print("Curated candidate registry: ten false-approval/identity/documentation negative guards PASS")

if __name__=="__main__":
    try:
        self_test()
        result=validate(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"),
                        json.loads(REGISTRY.read_text(encoding="utf-8")))
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("Curated Phase 1 cross-source semantic candidates: 29/29 exact Git blobs PASS; signoffs 0")
    except Exception as ex:
        print("Curated semantic review candidate identity ERROR:",ex,file=sys.stderr)
        sys.exit(2)

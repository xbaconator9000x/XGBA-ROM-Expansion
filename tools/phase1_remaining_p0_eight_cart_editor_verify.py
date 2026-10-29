#!/usr/bin/env python3
"""Eight disjoint pinned mGBA cart/ARM and Porymap connection analyst dossiers; NO approvals."""
import copy
import json
from pathlib import Path
import urllib.request
from phase1_remaining_p0_eight_verify import git_blob, verify, reject
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/phase1-review-readiness/remaining-p0-eight-cart-editor-20261029.json"
def main():
    p = json.loads(SPEC.read_text(encoding="utf-8"))
    assert p["gate"] == "FAIL_INCOMPLETE"
    assert p["independent_p0_approved"] == p["independent_total_approved"] == 0
    assert p["curated_29_source_inspected"] == 29
    assert p["remaining_p0_partial_total"] == 30
    assert p["partial_source_inspected"] == len(p["records"]) == 8
    assert p["new_partial_indices"] == [23,24,27,29,39,40,54,63]
    assert len(set(p["previous_partial_indices"])) == 22
    assert not set(p["new_partial_indices"]) & set(p["previous_partial_indices"])
    idx = json.loads((ROOT / "docs/phase1-review-readiness/remaining-p0-partial-handoff-index-20261029.json").read_text(encoding="utf-8"))
    assert idx["remaining_p0_partial_source_inspected"] == 30
    packet_bytes = (ROOT / p["source_packet"]).read_bytes()
    assert git_blob(packet_bytes) == p["source_packet_blob_sha1"]
    packets = json.loads(packet_bytes)["packets"]
    negatives = 0
    for rec in p["records"]:
        i = rec["packet_index"]
        assert i in p["new_partial_indices"]
        s = rec["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(s["repository"],s["revision"],s["path"])
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-cart-editor"}),timeout=45) as resp:
            raw = resp.read()
        verify(raw,rec,packets[i])
        assert rec["evidence_class"] == "PINNED_SOURCE_ONLY"
        assert len(rec["reviewer_questions"]) >= 3
        mutated = raw.replace(rec["line_anchors"][0]["text"].encode(),b"XGBA_SOURCE_NEGATIVE",1)
        assert mutated != raw
        reject(mutated,rec,packets[i]); negatives += 1
        for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha1","fabricated"),("machine_dossier_sha256_unverified","0"*64)):
            bad = copy.deepcopy(rec); bad[field] = value
            reject(raw,bad,packets[i]); negatives += 1
        for field,value in (("path","wrong.h"),("git_blob_sha1","0"*40)):
            bad = copy.deepcopy(rec); bad["source"][field] = value
            reject(raw,bad,packets[i]); negatives += 1
        bad=copy.deepcopy(rec); bad["line_anchors"][0]["line"]+=1
        reject(raw,bad,packets[i]); negatives += 1
        bad=copy.deepcopy(rec); bad["line_anchors"][0]["text"]="incorrect source"
        reject(raw,bad,packets[i]); negatives += 1
        print("P0_CART_EDITOR_SOURCE_OK",i,s["repository"],s["path"],s["git_blob_sha1"])
    assert negatives == 88
    print("P0_CART_EDITOR_PASS files=8 negatives=88 curated=29 remaining_p0_partial=30 approvals=0 gate=FAIL_INCOMPLETE")
if __name__ == "__main__":
    main()

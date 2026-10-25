#!/usr/bin/env python3
"""Secondary architecture-aware review ordering for XGBA Phase 1.

The original lexical P0/P1/P2/P3 source queue is immutable. This schedules
review, not semantic proof or any independent file-signoff.
"""
from __future__ import annotations
import collections
import csv
import gzip
import io
import json
import hashlib
import sys
from pathlib import Path

ROOT=Path("audit-output")
REGISTRY=Path("semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json")
SOURCE=ROOT/"semantic_review_queue.csv.gz"
TARGET=ROOT/"architecture_semantic_review_queue.csv.gz"
SUMMARY=ROOT/"architecture_semantic_review_priority_summary.json"
PRIORITIES={"P0","P1","P2","P3"}
FIELDS=("architecture_review_tier","architecture_review_reason","source_queue_priority_preserved",
        "source_queue_machine_review_status_preserved","curated_semantic_roles")
RANK={
    "A0_PINNED_CROSS_SOURCE_CONTRACT_OWNER":0,
    "A1_ARCHITECTURE_CRITICAL_P0":1,
    "A2_OTHER_P0":2,
    "A3_P0_GAMEPLAY_SCRIPT_FIXTURE":3,
    "A4_P1_QUEUE":4,
    "A5_P2_QUEUE":5,
    "A6_P3_QUEUE":6,
}

def tier(repo,path,priority,curated):
    if (repo,path) in curated:
        return ("A0_PINNED_CROSS_SOURCE_CONTRACT_OWNER",
                "Source-pin verified curated semantic role overrides lexical source priority",
                ",".join(curated[(repo,path)]))
    # Individual map scripts are still P0 per original queue, but source command
    # behavior is architecture-central before 163 content/script examples.
    if (priority=="P0" and repo=="pret/pokefirered"
        and path.startswith("data/maps/") and path.endswith("/scripts.inc")):
        return ("A3_P0_GAMEPLAY_SCRIPT_FIXTURE",
                "Typed map script scenario; preserve P0 obligation after generic interpreter/ABI review","")
    if priority=="P0":
        architecture=(
            (repo=="pret/pokefirered" and path.startswith(
                ("src/","include/","asm/macros/","tools/mapjson/","data/script_cmd_table.inc","map_data_rules.mk")))
            or (repo=="mgba-emu/mgba" and path.startswith(
                ("src/gba/","src/arm/","include/mgba/internal/gba/","include/mgba/internal/arm/","include/mgba/core/")))
            or (repo=="huderlem/porymap" and path.startswith(
                ("src/project.cpp","src/core/","src/config.cpp","include/core/","include/project.h")))
            or (repo=="huderlem/poryscript" and path.startswith(("emitter/","parser/")))
        )
        if architecture:
            return ("A1_ARCHITECTURE_CRITICAL_P0",
                    "Lexical P0 with architecture-relevant source path; requires semantic review, not auto-approved","")
        return ("A2_OTHER_P0",
                "Original P0 preserved; indirect/platform/editor relevance requires targeted review","")
    return ({"P1":"A4_P1_QUEUE","P2":"A5_P2_QUEUE","P3":"A6_P3_QUEUE"}[priority],
            "Original heuristic priority retained; not proof of irrelevance","")

def load():
    with gzip.open(SOURCE,"rt",encoding="utf-8",newline="") as f:
        items=list(csv.DictReader(f))
    document=json.loads(REGISTRY.read_text(encoding="utf-8"))
    if document.get("independent_review_approvals")!=0 or document.get("phase1_mapping_complete") is not False:
        raise RuntimeError("Curation registry falsely signed off Phase 1")
    curated={}
    for entry in document["candidate_files"]:
        key=(entry["repository"],entry["source_path"])
        if key in curated:raise RuntimeError("Duplicate curated file "+str(key))
        if entry.get("independent_whole_file_signoff") is not False:
            raise RuntimeError("Unapproved curated file marked reviewed")
        curated[key]=entry
    if len(curated)!=29 or len(items)!=14834:
        raise RuntimeError("Unexpected immutable source queue/curation count")
    if collections.Counter(x["priority"] for x in items)["P0"]!=338:
        raise RuntimeError("P0 lexical heuristic changed; review queue requires re-baseline")
    seen=set()
    for item in items:
        key=(item["repo"],item["path"])
        if key in seen:raise RuntimeError("Duplicate source review queue file "+str(key))
        seen.add(key)
        if item["priority"] not in PRIORITIES:raise RuntimeError("Unrecognized lexical source priority")
        if key in curated and item["blob_sha"]!=curated[key]["expected_git_blob_sha1"]:
            raise RuntimeError("Curated/source-queue Git blob mismatch "+str(key))
    if set(curated)-seen:raise RuntimeError("Curated semantic files absent from full review queue")
    return items,curated,document

def self_test():
    cur={("huderlem/porymap","src/core/block.cpp"):["configured_16bit_masks"]}
    assert tier("huderlem/porymap","src/core/block.cpp","P2",cur)[0].startswith("A0")
    assert tier("pret/pokefirered","data/maps/PalletTown/scripts.inc","P0",cur)[0].startswith("A3")
    assert tier("pret/pokefirered","src/fieldmap.c","P0",cur)[0].startswith("A1")
    assert tier("mgba-emu/mgba","src/gba/cart/gpio.c","P0",cur)[0].startswith("A1")
    assert tier("mgba-emu/mgba","src/gb/core.c","P0",cur)[0].startswith("A2")
    assert tier("pret/agbcc","gcc/Makefile","P3",cur)[0].startswith("A6")
    assert len(set(RANK.values()))==len(RANK)
    print("Architecture review tier classifier six positive and guard assertions PASS")

def main():
    self_test()
    items,curated,document=load()
    output=[]
    by_original=collections.Counter()
    tiers=collections.Counter()
    labels={key:entry["interpreted_semantic_roles"] for key,entry in curated.items()}
    for row in items:
        key=(row["repo"],row["path"])
        tag,reason,roles=tier(row["repo"],row["path"],row["priority"],labels)
        result=dict(row)
        result.update({
            "architecture_review_tier":tag,
            "architecture_review_reason":reason,
            "source_queue_priority_preserved":row["priority"],
            "source_queue_machine_review_status_preserved":row["machine_review_status"],
            "curated_semantic_roles":roles,
        })
        output.append(result)
        tiers[tag]+=1
        if key in curated:by_original[row["priority"]]+=1
    output.sort(key=lambda row:(RANK[row["architecture_review_tier"]],
                                row["repo"],row["path"]))
    if len(output)!=len(items) or sum(tiers.values())!=14834 or tiers["A0_PINNED_CROSS_SOURCE_CONTRACT_OWNER"]!=29:
        raise RuntimeError("Review priority tool dropped or duplicated a source file")
    # A large fraction of original FireRed P0s are individual content scripts.
    if tiers["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"]!=163:
        raise RuntimeError("Changed native map script P0 distribution; update architecture review assumptions")
    with TARGET.open("wb") as binary:
        with gzip.GzipFile(filename="",mode="wb",fileobj=binary,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as out:
                writer=csv.DictWriter(out,fieldnames=list(items[0])+list(FIELDS))
                writer.writeheader();writer.writerows(output)
    summary={
        "schema":"xgba.phase1.architecture_priority_additive.v1",
        "baseline_manifest_files":len(items),
        "baseline_lexical_P0_count":338,
        "curated_cross_source_interpreted_candidates":29,
        "curated_by_original_lexical_priority":dict(sorted(by_original.items())),
        "architecture_review_tier_counts":dict(sorted(tiers.items())),
        "P0_gameplay_script_files_retained":163,
        "original_files_or_priority_overwritten":0,
        "source_queue_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "curated_register_sha256":hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
        "architecture_queue_sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "priority_is_not_semantic_disposition":True,
        "independent_whole_file_approvals":0,
        "phase1_mapping_complete":False,
        "review_policy":"Prioritize exact source-pinned architecture contracts before heuristic P0 game-content scripts; preserve complete original review queue for remaining file reviews"
    }
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print("Architecture-aware review ordering: 14834/14834 tracked files retained, curated=29, map-script P0=163; no approvals")

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("Architecture priority queue FAILED:",ex,file=sys.stderr)
        sys.exit(2)

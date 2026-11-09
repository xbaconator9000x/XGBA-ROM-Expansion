#!/usr/bin/env python3
"""Cross-batch curated source analyst handoff integrity; never semantic approval."""
import copy
import json
import pathlib
import urllib.request
from phase1_curated_six_source_verify import blob_sha

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "docs/phase1-review-readiness/curated-partial-handoff-index-20261029.json"

def validate(index, intake, batches):
    assert index["phase1_gate"] == "FAIL_INCOMPLETE"
    assert index["whole_file_semantic_approved"] == index["independent_p0_approved"] == index["independent_total_approved"] == 0
    assert index["curated_source_inspected_partial"] == 29 and index["curated_registry_only_remaining"] == 0
    assert len(index["batches"]) == 5 and set(index["batches"]) == set(batches)
    assert intake["record_count"] == 29 and intake["partial_source_inspected_count"] == 5
    assert intake["independent_approved_count"] == 0 and intake["gate"] == "FAIL_INCOMPLETE"
    originals = {r["ordinal"]: r for r in intake["records"]}
    assert set(originals) == set(range(1,30))
    initial = set(index["original_partial_ordinals"])
    assert initial == {3,8,16,20,24}
    for n in initial:
        r = originals[n]
        assert r["analyst_preparation"] == "PARTIAL_PINNED_SOURCE_INSPECTION"
        assert r["independent_review_verdict"] == "NEEDS_REVIEW"
        assert r["independent_reviewer"] is None and r["machine_dossier_sha1"] is None
        assert r["whole_file_semantic_coverage"] is False
    seen = set(initial)
    batch_count = 0
    for path in index["batches"]:
        batch = batches[path]
        assert batch["gate"] == "FAIL_INCOMPLETE"
        assert batch["p0_independent_approved"] == batch["total_independent_approved"] == 0
        assert batch["source_blobs_inspected"] == len(batch["records"])
        for r in batch["records"]:
            n = r["ordinal"]
            assert n in originals and n not in seen, "duplicate or unknown ordinal"
            seen.add(n); batch_count += 1
            pinned = originals[n]["identity"]
            src = r["source"]
            for key in ("repository", "revision", "path", "git_blob_sha1"):
                assert src[key] == pinned[key], "source identity mismatch"
            assert r["independent_verdict"] == "NEEDS_REVIEW"
            assert r["independent_reviewer"] is None and r["machine_dossier_sha1"] is None
            assert r["analyst_status"] == "PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
            assert r.get("whole_file_semantic_coverage") is not True
            assert r["license_status"].startswith("PENDING_") or r["license_status"] == "MPL_2_0_SOURCE_NOTICE_PRESENT_REUSE_REVIEW_PENDING"
            assert r["unresolved"] and r["dependency_edges"]
    assert batch_count == 24 and seen == set(range(1,30))
    return True

def expect_reject(index, intake, batches):
    try:
        validate(index, intake, batches)
    except (AssertionError, KeyError, TypeError):
        return
    raise AssertionError("forged or incomplete curated handoff accepted")

def main():
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    i = index["intake"]
    url = "https://raw.githubusercontent.com/{}/{}/{}".format(i["repository"],i["commit"],i["path"])
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-curated-handoff"}), timeout=45) as response:
        raw = response.read()
    assert blob_sha(raw) == i["git_blob_sha1"], "intake Git blob mismatch"
    intake = json.loads(raw)
    batches = {p:json.loads((ROOT / p).read_text(encoding="utf-8")) for p in index["batches"]}
    validate(index, intake, batches)
    negatives = 0
    def bad_batch(change):
        nonlocal negatives
        b = copy.deepcopy(batches)
        path = index["batches"][-1]
        change(b[path]["records"])
        expect_reject(index, intake, b)
        negatives += 1
    bad_batch(lambda rows: rows.append(copy.deepcopy(rows[0])))
    bad_batch(lambda rows: rows.pop())
    bad_batch(lambda rows: rows[0]["source"].update(git_blob_sha1="0"*40))
    bad_batch(lambda rows: rows[0].update(independent_verdict="APPROVED"))
    bad_batch(lambda rows: rows[0].update(independent_reviewer="fake"))
    bad_batch(lambda rows: rows[0].update(machine_dossier_sha1="fake"))
    bad_batch(lambda rows: rows[0].update(license_status="CLEARED"))
    bad_batch(lambda rows: rows[0].update(whole_file_semantic_coverage=True))
    bad_batch(lambda rows: rows[0]["source"].update(path="wrong.c"))
    fake = copy.deepcopy(intake); fake["records"][2]["independent_review_verdict"] = "APPROVED"
    expect_reject(index, fake, batches); negatives += 1
    fake = copy.deepcopy(index); fake["curated_source_inspected_partial"] = 30
    expect_reject(fake, intake, batches); negatives += 1
    fake = copy.deepcopy(index); fake["batches"] = fake["batches"][:-1]
    expect_reject(fake, intake, batches); negatives += 1
    assert negatives == 12
    print("CURATED_HANDOFF_PASS source_partial=29/29 batch_records=24 prior_partial=5 negatives=12 independent_p0=0/338 independent_total=0/14834 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

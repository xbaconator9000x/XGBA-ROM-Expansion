#!/usr/bin/env python3
"""Four additional curated P0 source boundaries; reuses existing fail-closed verifier."""
import json
import pathlib
import urllib.request
from phase1_curated_six_source_verify import check

SPEC = pathlib.Path(__file__).resolve().parents[1] / "docs/phase1-review-readiness/curated-four-source-dossiers-20261029.json"

def main():
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["p0_independent_approved"] == payload["total_independent_approved"] == 0
    assert len(payload["records"]) == 4
    negative = 0
    for entry in payload["records"]:
        src = entry["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(src["repository"], src["revision"], src["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-source-verifier"}), timeout=40) as response:
            data = response.read()
        check(data, entry)
        altered = data.replace(entry["source_anchors"][0].encode(), b"XGBA_MUTATED_ANCHOR", 1)
        assert altered != data
        try:
            check(altered, entry)
        except AssertionError:
            negative += 1
        else:
            raise AssertionError("source mutation accepted")
        forged = dict(entry, independent_verdict="APPROVED")
        try:
            check(data, forged)
        except AssertionError:
            negative += 1
        else:
            raise AssertionError("self approval accepted")
        print("PINNED_SOURCE_OK", src["repository"], src["path"], src["git_blob_sha1"])
    assert negative == 8
    print("SOURCE_BATCH_PASS files=4 negatives=8 approvals=0 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

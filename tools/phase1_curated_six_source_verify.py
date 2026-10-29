#!/usr/bin/env python3
"""Phase 1 pinned six-file source evidence. No independent semantic approval."""
import hashlib
import json
import pathlib
import urllib.request

SPEC = pathlib.Path(__file__).resolve().parents[1] / "docs/phase1-review-readiness/curated-six-source-dossiers-20261029.json"

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def check(data, entry):
    if blob_sha(data) != entry["source"]["git_blob_sha1"]:
        raise AssertionError("pinned Git blob SHA mismatch: " + entry["source"]["path"])
    content = data.decode("utf-8")
    for anchor in entry["source_anchors"]:
        if anchor not in content:
            raise AssertionError("missing source anchor: " + anchor)
    if entry["independent_verdict"] != "NEEDS_REVIEW" or entry["independent_reviewer"] is not None:
        raise AssertionError("analyst evidence must not self-approve")
    if entry["machine_dossier_sha1"] is not None:
        raise AssertionError("unverified machine dossier SHA")
    return True

def main():
    payload = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["gate"] == "FAIL_INCOMPLETE"
    assert payload["p0_independent_approved"] == payload["total_independent_approved"] == 0
    assert len(payload["records"]) == 6
    negative = 0
    for entry in payload["records"]:
        src = entry["source"]
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(src["repository"], src["revision"], src["path"])
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"xgba-phase1-source-verifier"}), timeout=40) as response:
            data = response.read()
        check(data, entry)
        # Negative 1: semantic anchor removed; hash and anchor checks must reject.
        changed = data.replace(entry["source_anchors"][0].encode(), b"XGBA_MUTATED_ANCHOR", 1)
        assert changed != data
        try:
            check(changed, entry)
        except AssertionError:
            negative += 1
        else:
            raise AssertionError("source mutation accepted")
        # Negative 2: original bytes but forged reviewer verdict must be rejected.
        forged = dict(entry, independent_verdict="APPROVED")
        try:
            check(data, forged)
        except AssertionError:
            negative += 1
        else:
            raise AssertionError("self approval accepted")
        print("PINNED_SOURCE_OK", src["repository"], src["path"], src["git_blob_sha1"])
    assert negative == 12
    print("SOURCE_BATCH_PASS files=6 negatives=12 approvals=0 gate=FAIL_INCOMPLETE")

if __name__ == "__main__":
    main()

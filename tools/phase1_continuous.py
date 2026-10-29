#!/usr/bin/env python3
"""Fail-closed, resumable verification queue for pinned Phase 1 source dossiers.

Each completed unit is an independently rechecked EXISTING source-evidence
packet, never an independent semantic disposition or Phase 1 approval.
The queue is intentionally sequential; a failed unit blocks later units.
A separate GitHub branch stores a compare-and-swap checkpoint after every
transition, so interrupted jobs restart the first unfinished unit.
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "xbaconator9000x/XGBA-ROM-Expansion")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
API = "https://api.github.com/repos/" + REPO
STATE_BRANCH = "phase1-queue-state"
STATE_PATH = ".phase1-queue/verified-evidence-state.json"
WORKFLOW = "phase1-continuous.yml"
CHUNK = 500
MAX_ATTEMPTS = 3
PINS = {
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
    "huderlem/porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/agbcc": "da598c1d918402c42c0c0d7128ba14567f3175e9",
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def gz_csv(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class Snapshot:
    def __init__(self, directory):
        base = Path(directory)
        summary = json.loads((base / "audit_summary.json").read_text())
        second = json.loads((base / "second_pass_summary.json").read_text())
        if not summary.get("census_complete") or not summary.get("conditions", {}).get("all_source_config_content_scanned"):
            raise RuntimeError("Incomplete source census")
        if {k: v["commit"] for k, v in summary["repositories"].items()} != PINS:
            raise RuntimeError("Pinned source revisions changed")
        if second.get("source_blobs_sha1_verified") != 4685:
            raise RuntimeError("Incomplete source/config verification")
        self.manifest = gz_csv(base / "tracked_file_manifest.csv.gz")
        self.queue = gz_csv(base / "semantic_review_queue.csv.gz")
        if len(self.manifest) != 14834 or len(self.queue) != 14834:
            raise RuntimeError("Unexpected manifest/queue length")
        ids = set()
        for m, q in zip(self.manifest, self.queue):
            key = (m["repo"], m["path"])
            if key in ids:
                raise RuntimeError("Repeated tracked source file")
            ids.add(key)
            if (q["repo"], q["path"], q["blob_sha"]) != (m["repo"], m["path"], m["blob_sha"]):
                raise RuntimeError("Review queue differs from pinned source manifest")
            if len(q["evidence_sha256"]) != 64:
                raise RuntimeError("Missing dossier digest")
        self.fingerprint = digest(canonical([
            (x["repo"], x["path"], x["blob_sha"], x["evidence_sha256"])
            for x in self.queue
        ]))
        self.dossiers = []
        with gzip.open(base / "candidate_review_dossiers.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                self.dossiers.append(json.loads(line))
                if len(self.dossiers) > len(self.queue):
                    raise RuntimeError("Too many candidate dossiers")
        if len(self.dossiers) != len(self.queue):
            raise RuntimeError("Missing candidate dossiers")

    @property
    def total(self):
        return math.ceil(len(self.queue) / CHUNK)

    def packet(self, i):
        if not 0 <= i < self.total:
            raise ValueError("Chunk outside source manifest")
        start = i * CHUNK
        end = min(len(self.queue), start + CHUNK)
        items = []
        for pos in range(start, end):
            q, d = self.queue[pos], self.dossiers[pos]
            identity = d.get("provenance", {})
            if (identity.get("repository"), identity.get("path"), identity.get("git_blob_sha")) != (
                q["repo"], q["path"], q["blob_sha"]
            ):
                raise RuntimeError("Dossier provenance mismatch at file " + str(pos + 1))
            if digest(canonical(d)) != q["evidence_sha256"]:
                raise RuntimeError("Dossier SHA256 mismatch at file " + str(pos + 1))
            if d.get("review", {}).get("semantic_signoff") is not False:
                raise RuntimeError("Candidate evidence unexpectedly claims semantic approval")
            items.append((q["repo"], q["path"], q["blob_sha"], q["evidence_sha256"]))
        return {
            "unit": i + 1, "first_file": start + 1, "last_file": end,
            "verified_files": len(items), "input_fingerprint": self.fingerprint,
            "packet_sha256": digest(canonical(items)),
            "evidence_class": "REVERIFIED_CANDIDATE_DOSSIERS_ONLY",
            "independent_semantic_approvals": 0, "phase1_approved": False,
        }


def initial_state(snapshot):
    return {
        "schema": 1, "input_fingerprint": snapshot.fingerprint,
        "chunk_size": CHUNK, "total_files": len(snapshot.queue),
        "units": [
            {"status": "PENDING", "attempts": 0, "receipt": None, "error": None}
            for _ in range(snapshot.total)
        ],
        "approval_claim": False,
    }


def verify_state(snapshot, state):
    if (state.get("schema"), state.get("input_fingerprint"), state.get("chunk_size"),
        state.get("total_files")) != (1, snapshot.fingerprint, CHUNK, len(snapshot.queue)):
        raise RuntimeError("Checkpoint schema or pinned evidence changed; manual reconciliation required")
    entries = state.get("units")
    if not isinstance(entries, list) or len(entries) != snapshot.total:
        raise RuntimeError("Checkpoint unit count changed")
    if state.get("approval_claim") is not False:
        raise RuntimeError("Queue cannot claim independent semantic approval")
    found_gap = False
    for i, entry in enumerate(entries):
        status = entry.get("status")
        if status not in ("PENDING", "RUNNING", "RETRY", "BLOCKED", "VERIFIED"):
            raise RuntimeError("Invalid status at unit " + str(i + 1))
        if type(entry.get("attempts")) is not int or entry["attempts"] < 0:
            raise RuntimeError("Invalid attempt count at unit " + str(i + 1))
        if status == "VERIFIED":
            if found_gap:
                raise RuntimeError("Verified chunk appears after unfinished chunk")
            if entry.get("receipt") != snapshot.packet(i):
                raise RuntimeError("Missing, stale or altered verified receipt at unit " + str(i + 1))
        else:
            found_gap = True
            if entry.get("receipt") is not None:
                raise RuntimeError("Unverified chunk contains receipt")
    return True


def next_unit(state):
    return next((i for i, x in enumerate(state["units"]) if x["status"] != "VERIFIED"), None)


class ApiError(RuntimeError):
    def __init__(self, code, message):
        super().__init__("GitHub API HTTP " + str(code) + ": " + message[:500])
        self.code = code


class GitHubStore:
    def __init__(self):
        if not TOKEN:
            raise RuntimeError("Missing GitHub token")

    def call(self, method, suffix, payload=None):
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "XGBA-Phase1-Continuous-Queue",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(API + suffix, headers=headers, data=data, method=method)
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                content = response.read()
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as error:
            raise ApiError(error.code, error.read().decode("utf-8", "replace")) from error

    def ensure_branch(self):
        name = urllib.parse.quote(STATE_BRANCH, safe="")
        try:
            self.call("GET", "/git/ref/heads/" + name)
            return
        except ApiError as error:
            if error.code != 404:
                raise
        main = self.call("GET", "/git/ref/heads/main")["object"]["sha"]
        try:
            self.call("POST", "/git/refs", {"ref": "refs/heads/" + STATE_BRANCH, "sha": main})
        except ApiError as error:
            if error.code != 422:
                raise
            self.call("GET", "/git/ref/heads/" + name)

    def load(self, snapshot):
        self.ensure_branch()
        path = "/contents/" + STATE_PATH + "?ref=" + STATE_BRANCH
        try:
            response = self.call("GET", path)
            state = json.loads(base64.b64decode(response["content"]).decode("utf-8"))
            return state, response["sha"]
        except ApiError as error:
            if error.code != 404:
                raise
            state = initial_state(snapshot)
            new_sha = self.save(state, None)
            return state, new_sha

    def save(self, state, old_sha):
        body = {
            "message": "Checkpoint pinned Phase 1 evidence queue",
            "branch": STATE_BRANCH,
            "content": base64.b64encode((json.dumps(state, indent=2, sort_keys=True) + "\n").encode()).decode(),
        }
        if old_sha:
            body["sha"] = old_sha
        response = self.call("PUT", "/contents/" + STATE_PATH, body)
        return response["content"]["sha"]

    def continue_run(self):
        self.call("POST", "/actions/workflows/" + WORKFLOW + "/dispatches", {
            "ref": "main",
        })


def perform(snapshot, store, max_units, run_id):
    state, sha = store.load(snapshot)
    verify_state(snapshot, state)
    progress = 0
    while progress < max_units:
        index = next_unit(state)
        if index is None:
            return "COMPLETE", progress, state
        item = state["units"][index]
        if item["status"] == "BLOCKED" or item["attempts"] >= MAX_ATTEMPTS:
            if item["status"] != "BLOCKED":
                item["status"] = "BLOCKED"
                item["error"] = "Retry budget exhausted"
                sha = store.save(state, sha)
            return "BLOCKED", progress, state
        # A RUNNING entry from a prior serialized job is not a completion.
        item["status"] = "RUNNING"
        item["attempts"] += 1
        item["run_id"] = str(run_id)
        item["error"] = None
        sha = store.save(state, sha)  # lease committed before any work
        try:
            receipt = snapshot.packet(index)
            # Commit evidence and the VERIFIED transition atomically in one file.
            item["receipt"] = receipt
            item["status"] = "VERIFIED"
            sha = store.save(state, sha)
        except Exception as error:
            item["receipt"] = None
            item["status"] = "RETRY" if item["attempts"] < MAX_ATTEMPTS else "BLOCKED"
            item["error"] = (type(error).__name__ + ": " + str(error))[:500]
            sha = store.save(state, sha)
            return ("RETRY" if item["status"] == "RETRY" else "BLOCKED"), progress, state
        progress += 1
        print("Verified candidate evidence unit %d of %d (files %d-%d); no semantic signoff" %
              (index + 1, snapshot.total, receipt["first_file"], receipt["last_file"]), flush=True)
    return ("COMPLETE" if next_unit(state) is None else "CONTINUE"), progress, state


def write_report(out, verdict, processed, state):
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    verified = sum(x["status"] == "VERIFIED" for x in state["units"])
    report = {
        "verdict": verdict, "verified_evidence_units": verified, "total_units": len(state["units"]),
        "processed_this_run": processed, "next_unit": (
            next_unit(state) + 1 if next_unit(state) is not None else None
        ), "blocked": [i + 1 for i, x in enumerate(state["units"]) if x["status"] == "BLOCKED"],
        "independent_semantic_approvals": 0,
        "phase1_mapping_approved": False,
    }
    (output / "queue-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("### XGBA evidence checkpoint\n\n")
            stream.write("Verified source-evidence units: %d / %d. Next unit: %s. Status: %s.\n\n" %
                         (verified, len(state["units"]), report["next_unit"], verdict))
            stream.write("Independent semantic approvals: **0**. Phase 1 remains **FAIL_INCOMPLETE**.\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", default="audit-output")
    parser.add_argument("--max-units", type=int, default=5)
    parser.add_argument("--output", default="queue-output")
    args = parser.parse_args()
    if args.max_units < 1 or args.max_units > 100:
        raise RuntimeError("max-units must be 1..100")
    snapshot = Snapshot(args.audit)
    store = GitHubStore()
    verdict, processed, state = perform(snapshot, store, args.max_units, os.environ.get("GITHUB_RUN_ID", "local"))
    write_report(args.output, verdict, processed, state)
    if verdict in ("CONTINUE", "RETRY"):
        # If dispatch fails, the 15-minute schedule is an independent recovery route.
        store.continue_run()
        print("Dispatched next workflow execution", flush=True)
    if verdict == "BLOCKED":
        print("First unfinished unit is blocked; no later unit has been skipped.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as err:
        print("FAIL_CLOSED: " + repr(err), file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Verify the final pinned mGBA savedata source tranche; never an approval."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
RECORD = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "final-source-tranche-handoff.json"
)
BASE = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata-teardown/"
    "review.json"
)
FD_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "fd-stdio-error-propagation-handoff.json"
)
LIFECYCLE_HANDOFF = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/"
    "gba-lifecycle-error-contract-handoff.json"
)
SAVEDATA_REVIEW = Path(
    "semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json"
)
GATE = Path("semantic-snapshots/current/phase1_mapping_gate.json")
DOSSIER = Path("semantic-snapshots/current/candidate_review_dossiers.jsonl.gz")
WORKFLOW = Path(".github/workflows/copilot-mgba-savedata-review.yml")

RECORD_SHA256 = "61885348028f22e363aaf29880839eea5e16b76a99e608e72c1969280ac98535"
BASE_SHA256 = "b3bec6ce260d6184fc22a859b9c5bbc518348966cb0092a4fbe56f296667c475"
FD_HANDOFF_SHA256 = "e6333debeed736a58146bf1834b5960ca464cd1116216e67cf6edb5b8a765320"
LIFECYCLE_HANDOFF_SHA256 = "994e10c0cf611a9d247d23335972d9d3d0f300731274562d7d11b5ecd98e6b06"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"

FILES = {
    "src/util/vfs/vfs-mem.c": {
        "blob": "048194e2dd2d0b3b395a852d2092c694663c88a2",
        "sha256": "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b",
        "row": "3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce",
        "bytes": 7681,
        "lines": 331,
        "anchors": [
            "src/util/vfs/vfs-mem.c:34-119",
            "src/util/vfs/vfs-mem.c:121-152",
            "src/util/vfs/vfs-mem.c:154-234",
            "src/util/vfs/vfs-mem.c:237-288",
            "src/util/vfs/vfs-mem.c:290-331",
        ],
        "patterns": [
            "vfm->d.close = _vfmClose;",
            "vfm->d.close = _vfmCloseFree;",
            "vfm->d.sync = _vfmSync;",
            "return true;",
            "void _vfmUnmap(",
            "vfm->size = size;",
        ],
    },
    "src/util/vfs.c": {
        "blob": "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "sha256": "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "row": "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "bytes": 7598,
        "lines": 352,
        "anchors": [
            "src/util/vfs.c:21-123",
            "src/util/vfs.c:125-169",
            "src/util/vfs.c:287-352",
        ],
        "patterns": [
            "#ifdef ENABLE_VFS_FILE",
            "return VFileFOpen(path, chflags);",
            "return VFileOpenFD(path, flags);",
            "return vf->write(vf, &leword, 4);",
            "return r;",
        ],
    },
    "src/core/scripting.c": {
        "blob": "7ccb51e897685ce24b37dabc76beb27427331b4f",
        "sha256": "8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1",
        "row": "9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8",
        "bytes": 57714,
        "lines": 1540,
        "anchors": [
            "src/core/scripting.c:414-465",
            "src/core/scripting.c:535-674",
            "src/core/scripting.c:1028-1062",
            "src/core/scripting.c:1426-1540",
        ],
        "patterns": [
            "static int _mScriptCoreSaveStateFile(",
            "vf->close(vf);",
            "SAVESTATE_ALL & ~SAVESTATE_SAVEDATA",
            "DEFINE_CALLBACK(savedataUpdated)",
            ".savedataUpdated = mCoreCallback(savedataUpdated)",
            "core->removeCoreCallbacks(core, &callbacks);",
        ],
    },
    "src/script/stdlib.c": {
        "blob": "f84b62515315c119ec4ff5b9fb6df4de4517c738",
        "sha256": "52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99",
        "row": "db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1",
        "bytes": 13807,
        "lines": 307,
        "anchors": [
            "src/script/stdlib.c:20-103",
            "src/script/stdlib.c:199-307",
        ],
        "patterns": [
            "mScriptContextAddCallback(adapter->context, name->buffer, fn)",
            "`savedataUpdated`: The emulation has just finished modifying save data",
            "mSCRIPT_CONSTANT_PAIR(SAVESTATE, SAVEDATA)",
            "mSCRIPT_CONSTANT_PAIR(SAVESTATE, RTC)",
        ],
    },
    "include/mgba-util/common.h": {
        "blob": "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "sha256": "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "row": "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "bytes": 12589,
        "lines": 350,
        "anchors": [
            "include/mgba-util/common.h:19-90",
            "include/mgba-util/common.h:104-135",
            "include/mgba-util/common.h:146-263",
        ],
        "patterns": [
            "#include <mgba-util/dllexports.h>",
            "#define SSIZE_MAX",
            "#define LOAD_32LE",
            "#define STORE_32LE",
        ],
    },
    "include/mgba-util/dllexports.h": {
        "blob": "a44480df6ec26821b8616650b2575ba794848eca",
        "sha256": "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
        "row": "5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070",
        "bytes": 523,
        "lines": 19,
        "anchors": ["include/mgba-util/dllexports.h:6-19"],
        "patterns": [
            "#if defined(BUILD_STATIC)",
            "#define MGBA_EXPORT __declspec(dllexport)",
            "#define MGBA_EXPORT __declspec(dllimport)",
        ],
    },
    "include/mgba-util/vector.h": {
        "blob": "c837379e2102ca6535db2b292233bd4983c3532c",
        "sha256": "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
        "row": "6a1179a47870dc93b443eff57599611d1b8d43d87560de25863a9e5805d83eb7",
        "bytes": 4475,
        "lines": 128,
        "anchors": [
            "include/mgba-util/vector.h:17-35",
            "include/mgba-util/vector.h:37-112",
            "include/mgba-util/vector.h:114-128",
        ],
        "patterns": [
            "#define DEFINE_VECTOR(NAME, TYPE)",
            "vector->vector = calloc(capacity, sizeof(TYPE));",
            "vector->vector = realloc(vector->vector, vector->capacity * sizeof(TYPE));",
        ],
    },
    "include/mgba-util/memory.h": {
        "blob": "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "sha256": "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
        "row": "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
        "bytes": 443,
        "lines": 18,
        "anchors": ["include/mgba-util/memory.h:9-16"],
        "patterns": [
            "void* anonymousMemoryMap(size_t size);",
            "void mappedMemoryFree(void* memory, size_t size);",
        ],
    },
    "include/mgba-util/math.h": {
        "blob": "f7b3269c9d51967765379b951ba6f43d24c61865",
        "sha256": "04f5ee1686f4b30744d4e62caef4cf16f2f4b80682b88a87e7e18cf117fd421e",
        "row": "87d819c03b064e4665a27b5563f4a7261cfcdad051913229884d4f72cfd813f9",
        "bytes": 3996,
        "lines": 145,
        "anchors": [
            "include/mgba-util/math.h:13-101",
            "include/mgba-util/math.h:103-145",
        ],
        "patterns": [
            "static inline uint32_t toPow2(uint32_t bits)",
            "unsigned lz = clz32(bits - 1);",
            "return 1 << (32 - lz);",
        ],
    },
}

EXPECTED_PR13_CI = {
    "run_id": 41882603072,
    "head_sha": "d4a753a8909f364ed133eda4b4253a06a985b9ab",
    "event": "pull_request",
    "conclusion": "action_required",
    "job_count": 0,
}
EXPECTED_PR35_CI = {
    "pr35_run_id": 41951361703,
    "pr35_head_sha": "0bef6d4342340eff98aebd26bf73f9af09f8dffe",
    "event": "pull_request",
    "conclusion": "action_required",
    "job_count": 0,
    "pr13_run_id": 41882603072,
    "pr13_head_sha": "d4a753a8909f364ed133eda4b4253a06a985b9ab",
    "pr13_conclusion": "action_required",
    "pr13_job_count": 0,
    "push_event_run_count_for_pr35_branch": 0,
    "logs_result": "No failed jobs found; workflow run has zero jobs.",
}
EXPECTED_CONTROLS = [
    "record-identity",
    "request-attribution",
    "wrong-source-pin",
    "subset-missing",
    "prior-overlap",
    "whole-file-not-analyzed",
    "promote-file-verdict",
    "independent-approval-claim",
    "source-blob-change",
    "source-digest-change",
    "dossier-row-change",
    "source-byte-mutation",
    "line-count-mutation",
    "missing-objection",
    "erase-unresolved-gap",
    "license-overclaim",
    "actions-success-overclaim",
    "push-coverage-overclaim",
    "phase-gate-promotion",
    "approval-count-promotion",
    "native-gameplay-overclaim",
]


class Rejected(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def read_json(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return raw, value


def dossier_rows(path: Path) -> dict[str, tuple[str, str, str]]:
    raw = path.read_bytes()
    require(sha256(raw) == DOSSIER_SHA256, "machine dossier SHA-256 mismatch")
    require(blob_sha1(raw) == DOSSIER_BLOB, "machine dossier Git blob mismatch")
    rows = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path_value = provenance.get("path")
            if (
                provenance.get("repository") != "mgba-emu/mgba"
                or provenance.get("pinned_revision") != PIN
                or path_value not in FILES
            ):
                continue
            require(path_value not in rows, f"duplicate dossier row: {path_value}")
            rows[path_value] = (
                sha256(canonical(row)),
                provenance.get("git_blob_sha"),
                provenance.get("source_content_sha256"),
            )
    require(set(rows) == set(FILES), "selected dossier rows are incomplete")
    return rows


def validate(
    record: dict,
    sources: dict[str, bytes],
    base: dict,
    fd_handoff: dict,
    lifecycle_handoff: dict,
    savedata_review: dict,
    gate: dict,
    rows: dict[str, tuple[str, str, str]],
) -> None:
    require(
        record.get("schema")
        == "xgba.copilot.mgba_savedata_final_source_tranche_handoff.v1",
        "handoff schema mismatch",
    )
    reviewer = record.get("reviewer", {})
    require(
        reviewer.get("identity")
        == "GitHub Copilot Coding Agent (@copilot), reviewer-side PR #35 follow-up"
        and reviewer.get("source_packet_interpreter")
        == "xbaconator9000x, pinned mGBA Phase 1 source and PR #13 evidence packet"
        and reviewer.get("approval_eligible") is False
        and "not a distinct human reviewer" in reviewer.get("identity_limit", ""),
        "reviewer attribution or non-approval limit mismatch",
    )
    attribution = record.get("request_attribution", {})
    require(
        attribution.get("repository") == "xbaconator9000x/XGBA-ROM-Expansion"
        and attribution.get("pull_request") == 35
        and attribution.get("comment_id") == 6648209121
        and attribution.get("comment_author") == "xbaconator9000x"
        and attribution.get("expected_parent_head")
        == "0bef6d4342340eff98aebd26bf73f9af09f8dffe",
        "request attribution or expected-parent identity mismatch",
    )
    scope = record.get("scope", {})
    require(
        scope.get("repository") == "mgba-emu/mgba"
        and scope.get("source_revision") == PIN
        and set(scope.get("subset", [])) == set(FILES)
        and scope.get("whole_file_analysis_count") == len(FILES)
        and scope.get("whole_file_hash_only_count") == 0
        and scope.get("overall_file_verdict") == "NEEDS_EVIDENCE"
        and scope.get("semantic_approval") is False,
        "scope or disposition overclaim",
    )
    files = {item["path"]: item for item in base.get("source_files", [])}
    require(set(files) == set(FILES) | set(fd_handoff["scope"]["subset"]) | set(lifecycle_handoff["scope"]["subset"]),
            "the three handoffs do not partition the original 20-file inventory")
    require(
        not set(FILES).intersection(fd_handoff["scope"]["subset"])
        and not set(FILES).intersection(lifecycle_handoff["scope"]["subset"]),
        "final tranche overlaps a prior handoff",
    )
    require(
        not set(fd_handoff["scope"]["subset"]).intersection(
            lifecycle_handoff["scope"]["subset"]
        ),
        "prior handoffs overlap unexpectedly",
    )
    require(set(sources) == set(FILES), "source byte set differs from tranche")
    selected_records = record.get("selected_files", [])
    require(len(selected_records) == len(FILES), "selected file record count mismatch")
    require(
        {item.get("path") for item in selected_records} == set(FILES),
        "selected file paths mismatch",
    )
    for item in selected_records:
        path = item["path"]
        raw = sources[path]
        original = files[path]
        expected = FILES[path]
        require(item.get("whole_file_analysis") == "COMPLETE",
                f"file marked hash-only or partial: {path}")
        require(item.get("verdict") == "NEEDS_EVIDENCE",
                f"file verdict promoted: {path}")
        require(item.get("independent_approval") is False,
                f"independent approval claimed: {path}")
        require(item.get("analysis_type") and item.get("review_findings") and item.get("unresolved"),
                f"file-level semantic analysis missing: {path}")
        require(
            item.get("git_blob_sha1") == original.get("git_blob_sha1")
            == expected["blob"]
            and blob_sha1(raw) == expected["blob"],
            f"Git blob mismatch: {path}",
        )
        require(
            item.get("source_sha256") == original.get("source_sha256")
            == expected["sha256"]
            and sha256(raw) == expected["sha256"],
            f"source byte SHA-256 mismatch: {path}",
        )
        require(
            item.get("dossier_row_sha256") == original.get("dossier_row_sha256")
            == expected["row"]
            and rows.get(path)
            == (expected["row"], expected["blob"], expected["sha256"]),
            f"canonical dossier source row mismatch: {path}",
        )
        require(
            item.get("byte_length") == len(raw) == expected["bytes"]
            and item.get("line_count") == len(raw.decode("utf-8").splitlines())
            == expected["lines"],
            f"complete file size/line count mismatch: {path}",
        )
        require(item.get("source_anchors") == expected["anchors"],
                f"source anchor inventory mismatch: {path}")
        lines = raw.decode("utf-8").splitlines()
        for anchor in expected["anchors"]:
            anchor_path, separator, bounds = anchor.rpartition(":")
            match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", bounds)
            require(separator and anchor_path == path and match,
                    f"invalid source citation: {anchor}")
            start, end = map(int, match.groups())
            require(start <= end <= len(lines), f"citation outside file: {anchor}")
        text = raw.decode("utf-8")
        for pattern in expected["patterns"]:
            require(pattern in text, f"source behavior anchor missing: {path}: {pattern}")
        require(
            b"Mozilla Public" in raw[:800]
            and b"License, v. 2.0." in raw[:800]
            and b"mozilla.org/MPL/2.0/" in raw[:800],
            f"MPL-2.0 notice missing: {path}",
        )

    closure = record.get("caller_and_dependency_closure", {})
    require(
        len(closure.get("traced_source_edges", [])) >= 5
        and len(closure.get("dependency_gaps", [])) >= 4
        and closure.get("licensing", {}).get("notice") == "MPL-2.0"
        and closure.get("licensing", {}).get("all_nine_leading_notices_checked") is True
        and closure.get("licensing", {}).get("whole_file_byte_hashes_and_dossier_rows_bound") is True
        and closure.get("licensing", {}).get("combined_distribution_conclusion") is False,
        "caller/dependency/license closure is incomplete or overclaims",
    )
    prior_evidence = record.get("prior_pr13_evidence", {})
    require(
        prior_evidence.get("execution_policy")
        == "Do not repeat the original PR13 native tests in this tranche; inspect and cite prior evidence only."
        and prior_evidence.get("callback_fixture", {}).get("sha256")
        == "4963287bf10a7e2a3cd5e52788bc3aa518d70319fafb8e580c1a9b935059b6d4"
        and prior_evidence.get("callback_runner", {}).get("sha256")
        == "cc67ed3f5fd9b3a6a9e7f30076b38422dc19a43b3530a6576b97b4f1ed13bb53",
        "PR13 evidence provenance changed",
    )
    require(
        prior_evidence.get("observed_scope")
        == "Original POSIX fd VFile translation unit, extracted GBASavedataClean/GBAFrameEnded and callback registration were exercised; the memory backend, scripting translation unit, full RTC/serialization round trip, physical Flash, cold restart, and power-loss durability were not.",
        "PR13 host/native evidence scope overclaimed",
    )
    require(
        prior_evidence.get("current_exact_head_ci", {}).get("pr35_run_id")
        == EXPECTED_PR35_CI["pr35_run_id"]
        and prior_evidence.get("current_exact_head_ci", {}).get("pr35_head_sha")
        == EXPECTED_PR35_CI["pr35_head_sha"]
        and prior_evidence.get("current_exact_head_ci", {}).get("event")
        == "pull_request"
        and prior_evidence.get("current_exact_head_ci", {}).get("conclusion")
        == "action_required"
        and prior_evidence.get("current_exact_head_ci", {}).get("job_count") == 0
        and prior_evidence.get("current_exact_head_ci", {}).get("pr13_run_id")
        == EXPECTED_PR13_CI["run_id"]
        and prior_evidence.get("current_exact_head_ci", {}).get("push_event_run_count_for_pr35_branch")
        == 0,
        "blocked Actions snapshots or missing push coverage misrepresented",
    )
    phase = record.get("phase1_state", {})
    require(
        phase
        == {
            "decision": "FAIL_INCOMPLETE",
            "p0_approved_before": 0,
            "p0_approved_after": 0,
            "approved_before": 0,
            "approved_after": 0,
            "phase2_started": False,
            "shared_gate_or_register_edited": False,
        },
        "handoff Phase 1 invariants changed",
    )
    require(
        base.get("phase1_state", {}).get("decision") == "FAIL_INCOMPLETE"
        and base.get("phase1_state", {}).get("p0_approved_before") == 0
        and base.get("phase1_state", {}).get("p0_approved_after") == 0
        and base.get("phase1_state", {}).get("approved_before") == 0
        and base.get("phase1_state", {}).get("approved_after") == 0
        and savedata_review.get("phase1_gate") == "FAIL_INCOMPLETE"
        and savedata_review.get("approval_accounting", {}).get("approved_before") == 0
        and savedata_review.get("approval_accounting", {}).get("approved_after") == 0
        and gate.get("decision") == "FAIL_INCOMPLETE",
        "live/base Phase 1 gate or approval invariants changed",
    )
    require(
        len(record.get("unresolved_obligations", [])) >= 7,
        "unresolved obligations missing",
    )


def load_context(root: Path, source_root: Path):
    record_raw, record = read_json(root / RECORD)
    require(RECORD_SHA256 != "PENDING" and sha256(record_raw) == RECORD_SHA256,
            "final source-tranche record SHA-256 mismatch")
    base_raw, base = read_json(root / BASE)
    require(sha256(base_raw) == BASE_SHA256, "original 20-file review changed")
    fd_raw, fd_handoff = read_json(root / FD_HANDOFF)
    require(sha256(fd_raw) == FD_HANDOFF_SHA256, "fd/stdio handoff changed")
    life_raw, lifecycle_handoff = read_json(root / LIFECYCLE_HANDOFF)
    require(sha256(life_raw) == LIFECYCLE_HANDOFF_SHA256,
            "prior lifecycle handoff changed")
    _, savedata_review = read_json(root / SAVEDATA_REVIEW)
    _, gate = read_json(root / GATE)
    rows = dossier_rows(root / DOSSIER)
    sources = {}
    for path in FILES:
        raw = (source_root / path).read_bytes()
        require(raw, f"missing pinned source: {path}")
        sources[path] = raw
    return record_raw, record, base, fd_handoff, lifecycle_handoff, savedata_review, gate, rows, sources


def git(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args], text=True
    ).strip()


def verify_workflow(root: Path) -> None:
    text = (root / WORKFLOW).read_text(encoding="utf-8")
    events = text.split("workflow_dispatch:", 1)[0]
    require(
        "tools/copilot_mgba_final_source_tranche_verify.py" in events
        and "tools/copilot_mgba_final_source_tranche_verify.py" in text
        and "--checkout upstream/mgba" in text
        and "--self-test" in text,
        "existing scoped workflow does not select and execute the tranche verifier",
    )


def run_controls(context) -> int:
    _, record, base, fd_handoff, lifecycle_handoff, savedata_review, gate, rows, sources = context
    rejected = []

    def control(
        name: str,
        mutate_record=lambda candidate: None,
        mutate_sources=lambda candidate: None,
    ) -> None:
        candidate = copy.deepcopy(record)
        candidate_sources = dict(sources)
        mutate_record(candidate)
        mutate_sources(candidate_sources)
        try:
            validate(
                candidate,
                candidate_sources,
                base,
                fd_handoff,
                lifecycle_handoff,
                savedata_review,
                gate,
                rows,
            )
        except Rejected:
            rejected.append(name)
        else:
            raise Rejected(f"negative control accepted: {name}")

    control("record-identity", lambda d: d.update(schema="wrong"))
    control("request-attribution", lambda d: d["request_attribution"].update(comment_id=1))
    control("wrong-source-pin", lambda d: d["scope"].update(source_revision="0" * 40))
    control("subset-missing", lambda d: d["scope"].update(subset=d["scope"]["subset"][:-1]))
    control("prior-overlap", lambda d: d["scope"].update(subset=d["scope"]["subset"] + ["src/gba/core.c"]))
    control("whole-file-not-analyzed", lambda d: d["selected_files"][0].update(whole_file_analysis="HASH_ONLY"))
    control("promote-file-verdict", lambda d: d["selected_files"][0].update(verdict="COPILOT_REVIEWED/PASSED"))
    control("independent-approval-claim", lambda d: d["selected_files"][0].update(independent_approval=True))
    control("source-blob-change", lambda d: d["selected_files"][0].update(git_blob_sha1="0" * 40))
    control("source-digest-change", lambda d: d["selected_files"][0].update(source_sha256="0" * 64))
    control("dossier-row-change", lambda d: d["selected_files"][0].update(dossier_row_sha256="0" * 64))
    control(
        "source-byte-mutation",
        mutate_sources=lambda src: src.update(
            {"src/util/vfs/vfs-mem.c": src["src/util/vfs/vfs-mem.c"] + b"\n"}
        ),
    )
    control("line-count-mutation", lambda d: d["selected_files"][0].update(line_count=1))
    control("missing-objection", lambda d: d["selected_files"].pop())
    control("erase-unresolved-gap", lambda d: d.update(unresolved_obligations=[]))
    control(
        "license-overclaim",
        lambda d: d["caller_and_dependency_closure"]["licensing"].update(
            combined_distribution_conclusion=True
        ),
    )
    control(
        "actions-success-overclaim",
        lambda d: d["prior_pr13_evidence"]["current_exact_head_ci"].update(
            conclusion="success", job_count=1
        ),
    )
    control(
        "push-coverage-overclaim",
        lambda d: d["prior_pr13_evidence"]["current_exact_head_ci"].update(
            push_event_run_count_for_pr35_branch=1
        ),
    )
    control("phase-gate-promotion", lambda d: d["phase1_state"].update(decision="PASS"))
    control("approval-count-promotion", lambda d: d["phase1_state"].update(approved_after=1))
    control(
        "native-gameplay-overclaim",
        lambda d: d["prior_pr13_evidence"].update(
            observed_scope="stock gameplay and physical Flash tested"
        ),
    )
    require(rejected == EXPECTED_CONTROLS, "negative control inventory mismatch")
    return len(rejected)


def main() -> int:
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    source_root = (args.checkout or args.source_dir).resolve()
    if args.checkout:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "mGBA checkout does not match immutable revision")
    context = load_context(root, source_root)
    _, record, base, fd_handoff, lifecycle_handoff, savedata_review, gate, rows, sources = context
    validate(record, sources, base, fd_handoff, lifecycle_handoff, savedata_review, gate, rows)
    verify_workflow(root)
    controls = run_controls(context) if args.self_test else 0
    print(
        f"PASS final mGBA source tranche: {len(FILES)} complete files, "
        f"{len(rows)} dossier rows, all NEEDS_EVIDENCE"
        + (f", {controls} mutation controls rejected" if args.self_test else "")
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print(f"REJECTED: {error}", file=sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Verify pinned cross-file Porymap transaction evidence and its source matrix."""
import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

PORYMAP_PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PORYSCRIPT_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"

PORYMAP_FILES = {
    "src/project.cpp": ("d43b0949303433111d4478ad76117c2b3445dd13",
                        "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
                        "Reused writer anchor: collateral files, map JSON, map groups, Save All."),
    "include/project.h": ("50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354",
                          "7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51",
                          "Reused API declaration anchor for Project save methods."),
    "src/lib/orderedjson.cpp": ("4d3a460c652541371a01132116e508db8c4c872c",
                                "a6acaf57872aa3bfc2fc98b02b743e550bead19cc85cf298c642c50a5f3f75ae",
                                "Reused JSON serialization boundary."),
    "include/lib/orderedjson.h": ("cb5139d37d955f2469ebd2eaaf089668b82884fe",
                                  "06af4ab35f09263aa213673dbdca5640b840fddfb22f7e8fc35dc41ad91fdaa2",
                                  "Reused QFile-based serializer API boundary."),
    "src/core/map.cpp": ("47b279919bd4afcc76b88f9eeecd459b3452989f",
                         "c2406bb2dd5950ee226a4e7fc8e1d198c70915cb638fd706a814b87de22ab332",
                         "Script path selection, original script parser call, watcher invalidation/re-registration."),
    "src/core/mapheader.cpp": ("689a52dc16a5cc5eea96e7c94924fd1f95a5c5b5",
                               "75ac866909595164cb242e0b8a13149b218a85546a2ddd6ca8baf59f79b74806",
                               "Map-header setters used while Project reloads persisted JSON."),
    "src/core/events.cpp": ("194a7ab17096d754295990e649a0c5c3ab816c78",
                            "36a5fadf65a0cd0b70ce02acef717aae60ac77052cd9f6f2bdfb56ed17cab886",
                            "Event object producer/consumer used by cloned and reopened map JSON."),
    "src/core/parseutil.cpp": ("a1c3e69daed3f04d7ed64e1a34bd95db56137ae2",
                               "7c9e4028c74555c7b27b7fb6e3d255f406d8303277989887f69ddf8a44ece441",
                               "Original .inc/.pory script-label parser used on cold reopen."),
    "src/config.cpp": ("9264f99bb18e0a725ef023f514c00df529d1d28d",
                       "fe8b6e3e4780ae8a63321d157d6fea43f438af3ab7a7fc697a9f9a2b43d4419d",
                       "Default project paths, FireRed text-file mode and Poryscript selection."),
    "include/config.h": ("539c5f3d416d22d847020cd324726b33725e5437",
                         "2a7a2621675e70b007fbc71f004a3cb0c44914f0a9c366ab974570ca8e2053ad",
                         "ProjectFilePath keys joining config defaults to persisted project assets."),
    "LICENSE.md": ("65c5ca88a67c30becee01c5a8816d964b03862f9",
                   "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
                   "Pinned Porymap root license evidence."),
}
FIRERED_FILES = {
    "data/event_scripts.s": ("88d75946a7300ccf952f4a36c283966c6aebf5c0",
                             "3b1bd10d26c0a74fb3452ab42fc9d14dfca785f8b71389db06c71f5dfdd50a27",
                             "Shared append target for generated map script/text includes."),
    "data/maps/map_groups.json": ("8c382f504d208286161903244772c93138cd7662",
                                  "ce296c9b54c8bb85cc35870b30a533ab017e72107fd40cf471224a42127af79a",
                                  "Project::saveAll output required to reopen the new maps."),
    "data/maps/PalletTown/map.json": ("802d32dc6de7688fe2de8c833d4e040d9137f6c1",
                                      "2816338934241bac34f52dae8b101ac3add59e0ebdde3e3fb6575f3b525b01c3",
                                      "Pinned source map cloned as the native test fixture."),
    "data/maps/PalletTown/scripts.inc": ("1384b7d6c6bb5d2b93538ebaf5e92defde2d41e5",
                                         "ca9ae01d210ebfeda42895a152145940b7c444a03b6416b26353ceb0adac9190",
                                         "Pinned assembly-script consumer fixture."),
    "data/maps/PalletTown/text.inc": ("726aea8c67812ef2bc72e51b2d8ee38e21fd4863",
                                      "6fe28872b8f6ad72ad26dc64a6f6922258cf187f5efb40dfeddc9e2d1f2469b2",
                                      "Pinned text-script consumer fixture."),
}

NATIVE = {
    "native_original_project": True,
    "synthetic_new_maps": True,
    "case_c_event_enospc_write_attempted": True,
    "case_c_original_event_bytes_and_inode_preserved": True,
    "case_c_map_json_script_text_saved_without_include": True,
    "case_d_partial_append_observed": True,
    "case_d_partial_append_bytes": 8,
    "case_d_map_saved_clean_after_partial_append": True,
    "case_d_original_event_bytes_and_inode_restored": True,
    "save_all_published_persisted_maps": True,
    "text_file_branch_enabled": True,
    "poryscript_mode": False,
    "poryscript_runtime_exercised": False,
    "host_filesystem_only": True,
    "physical_durability_tested": False,
    "phase1_gate": "FAIL_INCOMPLETE",
    "independent_approvals": 0,
}
COLD = {
    "fresh_process": True,
    "original_project_reopened": True,
    "four_maps_reloaded": True,
    "script_failure_map_and_include_mixed_state": True,
    "map_json_failure_retry_duplicate_include": True,
    "event_enospc_map_saved_without_include": True,
    "partial_append_fixture_rollback_verified": True,
    "script_text_outputs_reloaded": True,
    "original_script_parser_reloaded": True,
    "qsavefile_permission_commit_rejected": True,
    "qsavefile_failed_commit_error_code": 8,
    "qsavefile_failed_commit_error_string": "Unknown error",
    "permission_control_errno": 13,
    "qsavefile_failed_old_bytes_preserved": True,
    "qsavefile_failed_old_inode_preserved": True,
    "qsavefile_atomic_replace_committed": True,
    "qsavefile_atomic_replace_new_inode": True,
    "script_watcher_invalidated_after_replace": True,
    "script_watcher_rearmed_after_read": True,
    "script_watcher_delivered_post_rearm_change": True,
    "qsavefile_is_test_only": True,
    "physical_durability_tested": False,
    "phase1_gate": "FAIL_INCOMPLETE",
    "independent_approvals": 0,
}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

def blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def verify_source_bytes(sources):
    require(set(sources) == set(PORYMAP_FILES) | set(FIRERED_FILES), "source matrix field set")
    for path, (blob, digest, _) in PORYMAP_FILES.items():
        data = sources[path]
        require(blob_sha1(data) == blob, "Porymap blob mismatch " + path)
        require(hashlib.sha256(data).hexdigest() == digest, "Porymap SHA-256 mismatch " + path)
    for path, (blob, digest, _) in FIRERED_FILES.items():
        data = sources[path]
        require(blob_sha1(data) == blob, "FireRed blob mismatch " + path)
        require(hashlib.sha256(data).hexdigest() == digest, "FireRed SHA-256 mismatch " + path)

def record(log, prefix, expected):
    rows = [line.split("=", 1)[1] for line in log.splitlines()
            if line.startswith(prefix + "=")]
    require(len(rows) == 1, "exactly one " + prefix + " record")
    data = json.loads(rows[0])
    require(set(data) == set(expected), prefix + " field set")
    require(data == expected, prefix + " assertions or scope changed")
    require("FAIL " not in log, prefix + " native failure marker")
    return data

def verify_trace(lines):
    require(len(lines) > 3, "missing strace evidence")
    markers = ("PHASE1_TXN_ENOSPC_STAGE", "PHASE1_TXN_PARTIAL_STAGE")
    positions = []
    pids = []
    for marker in markers:
        hits = [i for i, line in enumerate(lines) if marker in line]
        require(len(hits) == 1, "expected one trace marker " + marker)
        match = re.match(r"\s*(\d+)\s+write\(", lines[hits[0]])
        require(match, "trace marker lacks process identity")
        positions.append(hits[0])
        pids.append(match.group(1))
    require(positions[0] < positions[1], "ENOSPC/partial stage order")

    enospc = re.compile(
        r'(?P<pid>\d+)\s+write\(\d+</dev/full(?:<[^>\n]+>)?(?: \(deleted\))?>, .*?, '
        r'(?P<requested>\d+)\)\s+= -1 ENOSPC\b'
    )
    enospc_rows = [line for line in lines[positions[0] + 1:positions[1]]
                   if (m := enospc.search(line))
                   and m.group("pid") == pids[0]
                   and int(m.group("requested")) > 1]
    require(enospc_rows, "no original event append ENOSPC write after its stage")

    partial = re.compile(
        r'(?P<pid>\d+)\s+write\(\d+<[^>\n]*event_scripts\.s[^>\n]*>, .*?, '
        r'(?P<requested>\d+)\)\s+= (?P<written>\d+)$'
    )
    partial_rows = []
    for line in lines[positions[1] + 1:]:
        match = partial.search(line)
        if (match and match.group("pid") == pids[1]
                and int(match.group("requested")) > 8
                and int(match.group("written")) == 8):
            partial_rows.append(line)
    require(partial_rows, "no traced partial write of exactly eight bytes to event_scripts.s")
    return {"enospc_write": enospc_rows[0][:350],
            "partial_write": partial_rows[0][:350],
            "native_pid": pids[0], "partial_pid": pids[1]}

def trace_negatives(lines):
    checks = [
        [line for line in lines if "PHASE1_TXN_ENOSPC_STAGE" not in line],
        [line.replace("ENOSPC", "EIO") for line in lines],
        [line.replace("event_scripts.s", "other-file.s") for line in lines],
        [line.replace("= 8", "= 7") for line in lines],
    ]
    for index, changed in enumerate(checks):
        try:
            verify_trace(changed)
        except ValueError:
            continue
        raise AssertionError("trace mutation escaped " + str(index))
    return len(checks)

def record_negatives(data, expected):
    count = 0
    for key, value in expected.items():
        changed = copy.deepcopy(data)
        changed[key] = (not value if isinstance(value, bool) else
                        value + 1 if isinstance(value, int) else
                        "PASS" if key == "phase1_gate" else 1)
        try:
            require(set(changed) == set(expected) and changed == expected,
                    "mutated evidence rejected")
        except ValueError:
            count += 1
        else:
            raise AssertionError("evidence mutation escaped " + key)
    return count

def source_negatives(sources):
    count = 0
    for path, data in sources.items():
        changed = dict(sources)
        changed[path] = bytes([data[0] ^ 1]) + data[1:]
        try:
            verify_source_bytes(changed)
        except ValueError:
            count += 1
        else:
            raise AssertionError("source mutation escaped " + path)
    return count

def main():
    parser = argparse.ArgumentParser()
    for arg in ("porymap", "firered", "log", "cold-log", "trace", "dossier", "output"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    require(git(args.porymap, "rev-parse", "HEAD") == PORYMAP_PIN, "Porymap pin")
    require(git(args.firered, "rev-parse", "HEAD") == FIRERED_PIN, "FireRed pin")
    sources = {}
    matrix = []
    for repo, root, entries in (
        ("huderlem/porymap", args.porymap, PORYMAP_FILES),
        ("pret/pokefirered", args.firered, FIRERED_FILES),
    ):
        for path, (blob, digest, role) in entries.items():
            data = (root / path).read_bytes()
            sources[path] = data
            if repo == "pret/pokefirered":
                review_status = "pinned_fixture_asset_not_source_review"
            elif path == "LICENSE.md":
                review_status = "license_metadata_only"
            elif path in {"src/project.cpp", "include/project.h",
                          "src/lib/orderedjson.cpp", "include/lib/orderedjson.h",
                          "src/core/map.cpp"}:
                review_status = "prior_partial_evidence"
            else:
                review_status = "new_dependency_not_whole_file_review"
            matrix.append({"repository": repo, "path": path, "git_blob": blob,
                           "sha256": digest, "producer_consumer_edge": role,
                           "review_status": review_status})
    verify_source_bytes(sources)
    root_names = git(args.firered, "ls-tree", "--name-only", "HEAD").splitlines()
    require(not any(name in root_names for name in
                    ("LICENSE", "LICENSE.md", "COPYING", "COPYING.md")),
            "FireRed root license inventory changed; re-evaluate licensing")

    native_log = args.log.read_text(errors="replace")
    cold_log = args.cold_log.read_text(errors="replace")
    native = record(native_log, "PHASE1_TRANSACTION_NATIVE", NATIVE)
    cold = record(cold_log, "PHASE1_TRANSACTION_COLD", COLD)
    trace_lines = args.trace.read_text(errors="replace").splitlines()
    trace = verify_trace(trace_lines)
    source_rejected = source_negatives(sources)
    native_rejected = record_negatives(native, NATIVE)
    cold_rejected = record_negatives(cold, COLD)
    trace_rejected = trace_negatives(trace_lines)

    poryscript = {
        "repository": "huderlem/poryscript",
        "pin": PORYSCRIPT_PIN,
        "path": "README.md",
        "git_blob": "c77e022eb86e74a41b184daac5953d14c72cacc3",
        "sha256": "d7aa099a6bcdd43745e746527589907d3cd4cd4b3db109319ccf8c609dec36f3",
        "runtime_exercised": False,
        "reason": "Pinned FireRed mode is .inc/raw assembly for this run; generated .pory-to-.inc integration remains separate prior evidence.",
    }
    out = {
        "evidence_class": "NATIVE_PINNED_PORYMAP_PROJECT_CROSS_FILE_TRANSACTION",
        "review_status": "NEEDS_EVIDENCE",
        "porymap_pin": PORYMAP_PIN,
        "firered_pin": FIRERED_PIN,
        "poryscript_boundary": poryscript,
        "source_matrix": matrix,
        "source_dependency_count": len(matrix),
        "new_dependency_count": sum(row["review_status"] == "new_dependency_not_whole_file_review"
                                    for row in matrix),
        "pinned_fixture_asset_count": sum(row["review_status"] ==
                                          "pinned_fixture_asset_not_source_review"
                                          for row in matrix),
        "source_mutations_rejected": source_rejected,
        "native_transcript_sha256": hashlib.sha256(native_log.encode()).hexdigest(),
        "cold_transcript_sha256": hashlib.sha256(cold_log.encode()).hexdigest(),
        "strace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(),
        "transaction_test_sha256": hashlib.sha256(
            Path("tests/porymap_qt_new_map_collateral.cpp").read_bytes()).hexdigest(),
        "workflow_sha256": hashlib.sha256(
            Path(".github/workflows/phase1-porymap-new-map-native-qt.yml").read_bytes()
        ).hexdigest(),
        "dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "native_assertions": native,
        "native_mutations_rejected": native_rejected,
        "cold_assertions": cold,
        "cold_mutations_rejected": cold_rejected,
        "trace_attribution": trace,
        "trace_mutations_rejected": trace_rejected,
        "licenses": {
            "porymap": "Pinned root LICENSE.md is LGPL-3.0 text; bundled OrderedJson source/header have separate MIT/Dropbox notices.",
            "firered": "No root LICENSE/LICENSE.md/COPYING file at pinned tree; no license or redistribution conclusion is made.",
            "qt": "Host-installed Qt6 system libraries; no Qt binaries or project/game assets uploaded.",
        },
        "evidence_limits": [
            "Synthetic new maps and test-only filesystem fault injection on a host filesystem.",
            "QSaveFile is exercised by the test harness, not claimed as Porymap's writer.",
            "Harness truncation restores the partial event append; this is not application rollback.",
            "No fsync, power-loss, physical-media durability, stock ROM runtime, or Poryscript execution.",
            "Native Project entrypoint is not a human GUI interaction.",
            "No complete-file semantic dispositions or independent approvals are claimed.",
        ],
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
    }
    require(source_rejected == len(sources), "source mutation count")
    require(native_rejected == len(NATIVE) and cold_rejected == len(COLD),
            "transcript mutation count")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("PORYMAP_TRANSACTION_NATIVE_PASS sources=%d source_negatives=%d "
          "native_negatives=%d cold_negatives=%d trace_negatives=%d "
          "gate=FAIL_INCOMPLETE approvals=0" %
          (len(sources), source_rejected, native_rejected, cold_rejected, trace_rejected))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify pinned RegionMap save/dirty-state behavior with bounded native Qt evidence."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
FILES = {
    "src/core/regionmap.cpp": (
        "94f686426e5ea8a84294dd1ac35617700c54e73f",
        "a6b6717820ae1fbd04424283cf1cb4c057ec34eaff6935c5a3dc8f36f90ad44c",
        "RegionMap asset serializers, save ordering, and undo-history clean transition",
    ),
    "include/core/regionmap.h": (
        "c8afb1b2dd44b80ebfbf14d3793866b7764629ed",
        "b723542988188a4bc4c1c7b02849baf10d8604199781c6fe21ca49f848451a84",
        "RegionMap state, paths, layout formats, and QUndoStack ownership",
    ),
    "src/core/regionmapeditcommands.cpp": (
        "f21f1d720ae22d4911ef71b984435ff66c0566f9",
        "28950c048b96df25fb7525d84298e50c3d302105edf7cc6aff285572e6c92f13",
        "Undo/redo commands that mutate RegionMap state",
    ),
    "include/core/regionmapeditcommands.h": (
        "e47fdb7b9ed59ff523d9e5a91975c98bca68efb1",
        "1645066c8a13ef544589516e76c5dc202f2605151bf0dc381270879b5137096e",
        "Undo command interfaces and state snapshots",
    ),
    "src/ui/regionmapeditor.cpp": (
        "a96de606cc18469b558b1acfc7c787432b8dcfb4",
        "43f433c1754cd25d4691491567e7be9ff48e47e89c485eb917a5b26e2e1eb4e2",
        "Save wrappers, project section-entry save, and UI close/reconfigure paths",
    ),
    "include/ui/regionmapeditor.h": (
        "432eaab62cd897146d8f64fe9f9555ae3ce4c265",
        "8ebab02239b042894fe0dcc7a644be8611316f2c505788544708271b0344753c",
        "RegionMapEditor save interfaces and undo-group ownership",
    ),
}
LICENSE_BLOB = "65c5ca88a67c30becee01c5a8816d964b03862f9"
LICENSE_SHA256 = "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-full-qt-project-roundtrip-20261028.md":
        "b143b4f44d879851b724deb21c567426ebf2355cd6ef2ea22dec521c8910d680",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "e00c5431a19b9d9e5a66d70b8dd3a817e5ea25a0307de7be8618e1cf2226af87",
    "docs/phase1-review-readiness/porymap-five-json-writers-native-20261029.md":
        "98f03e91e58e2f18a3e68dc464a2ca476058d22be8b390f5867899d6887af526",
}
FUNCTIONS = (
    ("src/core/regionmap.cpp", "void RegionMap::save()"),
    ("src/core/regionmap.cpp", "void RegionMap::saveTilemap()"),
    ("src/core/regionmap.cpp", "void RegionMap::saveLayout()"),
    ("src/core/regionmapeditcommands.cpp", "EditTilemap::EditTilemap("),
    ("src/core/regionmapeditcommands.cpp", "void EditTilemap::redo()"),
    ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::saveRegionMap("),
    ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::saveRegionMapEntries()"),
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def extract(source, anchor):
    require(source.count(anchor) == 1, "pinned source anchor missing/duplicated: " + anchor)
    start = source.index(anchor)
    end = source.find("\n}\n", start)
    require(end > start, "pinned source function unterminated: " + anchor)
    return source[start:end + 2]


def verify_sources(root):
    require(git(root, "rev-parse", "HEAD") == PIN, "Porymap commit pin changed")
    sources = {}
    rows = []
    for path, (blob, digest, role) in FILES.items():
        data = (root / path).read_bytes()
        require(git(root, "hash-object", path) == blob, "Porymap Git blob mismatch: " + path)
        require(hashlib.sha256(data).hexdigest() == digest, "Porymap byte hash mismatch: " + path)
        sources[path] = data.decode("utf-8")
        row = {
            "repository": "huderlem/porymap",
            "path": path,
            "pinned_commit": PIN,
            "git_blob_sha1": blob,
            "source_sha256": digest,
            "bytes": len(data),
            "lines": len(data.splitlines()),
            "role": role,
            "license": "Porymap root LICENSE.md, LGPL-3.0 text; not a redistribution determination",
            "original_dossier_row_sha256": None,
            "original_dossier_archive_sha256": None,
            "original_dossier_status": "NEEDS_EVIDENCE: no earlier per-file row/archive was found",
            "disposition": "NEEDS_EVIDENCE",
        }
        row["new_dossier_row_sha256"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        rows.append(row)
    license_path = root / "LICENSE.md"
    license_bytes = license_path.read_bytes()
    require(git(root, "hash-object", "LICENSE.md") == LICENSE_BLOB,
            "Porymap license blob mismatch")
    require(hashlib.sha256(license_bytes).hexdigest() == LICENSE_SHA256,
            "Porymap license byte hash mismatch")
    return sources, rows


def verify_no_prior_inventory_overlap(repository_root):
    new_tool = Path(__file__).resolve()
    new_dossier = (repository_root
                   / "docs/phase1-review-readiness/porymap-regionmap-persistence-boundary-20261105.md").resolve()
    # Later packets cite these sources as context; they are not prior inventory records.
    later_context_packet = {
        (repository_root / "tools/phase1_porymap_regionmap_project_caller.py").resolve(),
        (repository_root
         / "docs/phase1-review-readiness/porymap-regionmap-project-caller-20261105.md").resolve(),
        (repository_root / "tools/phase1_porymap_regionmap_project_save.py").resolve(),
        (repository_root
         / "docs/phase1-review-readiness/porymap-regionmap-project-save-failure-closure-20261106.md").resolve(),
    }
    files = []
    for folder in (repository_root / "tools",
                   repository_root / "docs/phase1-review-readiness"):
        files.extend(path for path in folder.rglob("*")
                     if path.is_file() and path.suffix in {".py", ".md"}
                     and path.resolve() not in {new_tool, new_dossier, *later_context_packet})
    for source_path in FILES:
        matches = [str(path) for path in files if source_path in path.read_text(errors="replace")]
        require(not matches, "selected source already appears in prior inventory: "
                + source_path + ": " + ", ".join(matches[:3]))
    return {
        "scanned_tools_and_readiness_dossiers": len(files),
        "prior_inventory_path_matches": 0,
        "paths": sorted(FILES),
    }


def verify_prior_dossiers(repository_root):
    actual = {}
    for path, digest in PRIOR_DOSSIERS.items():
        file_path = repository_root / path
        require(file_path.is_file(), "prior context dossier missing: " + path)
        actual[path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        require(actual[path] == digest, "prior context dossier hash drift: " + path)
    return actual


def verify_source_contract(sources):
    region = sources["src/core/regionmap.cpp"]
    region_header = sources["include/core/regionmap.h"]
    editor = sources["src/ui/regionmapeditor.cpp"]
    editor_header = sources["include/ui/regionmapeditor.h"]
    commands = sources["src/core/regionmapeditcommands.cpp"]
    commands_header = sources["include/core/regionmapeditcommands.h"]
    save = extract(region, "void RegionMap::save()")
    tilemap = extract(region, "void RegionMap::saveTilemap()")
    layout = extract(region, "void RegionMap::saveLayout()")
    wrapper = extract(editor, "bool RegionMapEditor::saveRegionMap(")
    entries = extract(editor, "bool RegionMapEditor::saveRegionMapEntries()")
    modified = extract(editor, "bool RegionMapEditor::modified()")
    save_config = extract(editor, "void RegionMapEditor::saveConfig()")
    close_event = extract(editor, "void RegionMapEditor::closeEvent(QCloseEvent *event)")
    save_action = extract(editor, "void RegionMapEditor::on_action_RegionMap_Save_triggered()")
    save_all_action = extract(editor, "void RegionMapEditor::on_actionSave_All_triggered()")
    redo = extract(commands, "void EditTilemap::redo()")
    require(save.index("saveTilemap();") < save.index("saveLayout();")
            < save.index("editHistory.setClean();"), "RegionMap save ordering changed")
    require("if (!tilemapFile.open(QIODevice::WriteOnly))" in tilemap
            and tilemap.count("tilemapFile.write(this->getTilemap());") == 1
            and "tilemapFile.error()" not in tilemap
            and "tilemapFile.close();" in tilemap,
            "tilemap write/error boundary changed")
    binary_layout = layout[layout.index("case LayoutFormat::Binary"):]
    require("if (!bfile.open(QIODevice::WriteOnly))" in binary_layout
            and binary_layout.index("logError(") < binary_layout.index("bfile.write(data);")
            and "return" not in binary_layout[:binary_layout.index("bfile.write(data);")],
            "binary layout failure handling changed")
    require("map->save();" in wrapper and wrapper.count("return true;") == 1,
            "RegionMapEditor save wrapper changed")
    require("this->project->setRegionMapEntries(this->region_map_entries);" in entries
            and "this->project->saveRegionMapSections();" in entries
            and entries.count("return true;") == 1,
            "RegionMapEditor section-save propagation changed")
    require("!this->history.isClean()" in modified and "!this->configSaved" in modified,
            "RegionMapEditor dirty predicate changed")
    require("if (this->modified())" in close_event
            and "this->on_action_RegionMap_Save_triggered();" in close_event
            and close_event.index("this->on_action_RegionMap_Save_triggered();")
            < close_event.index("event->accept();")
            and "event->accept();" in close_event,
            "RegionMapEditor close/save path changed")
    require("if (!file.open(QIODevice::WriteOnly))" in save_config
            and "jsonDoc.dump(&file);" in save_config
            and "file.close();" in save_config
            and save_config.index("file.close();") < save_config.index("this->configSaved = true;")
            and "file.error()" not in save_config,
            "RegionMapEditor config-write state transition changed")
    require(save_action.index("saveRegionMap(this->region_map);")
            < save_action.index("saveRegionMapEntries();")
            < save_action.index("saveConfig();")
            and "if (!" not in save_action,
            "RegionMapEditor save action result handling changed")
    require("for (auto it : this->region_maps)" in save_all_action
            and "saveRegionMap(it.second);" in save_all_action
            and "saveRegionMapEntries();" in save_all_action
            and "saveConfig();" in save_all_action,
            "RegionMapEditor save-all path changed")
    require("map->setTilemap(this->newTilemap);" in redo,
            "pinned edit command no longer mutates tilemap")
    require("QUndoStack editHistory;" in region_header
            and "void save();" in region_header
            and "void saveTilemap();" in region_header
            and "void saveLayout();" in region_header
            and "enum class LayoutFormat" in region_header,
            "RegionMap state interface changed")
    require("bool saveRegionMap(RegionMap *map);" in editor_header
            and "bool saveRegionMapEntries();" in editor_header
            and "QUndoGroup history;" in editor_header,
            "RegionMapEditor save/history interface changed")
    require("class EditTilemap" in commands_header
            and "void redo() override;" in commands_header
            and "RMCommandId::ID_EditTilemap;" in commands_header,
            "EditTilemap command interface changed")
    return {
        "save_tilemap_before_layout": True,
        "undo_history_cleaned_after_void_helpers": True,
        "binary_layout_open_failure_logs_then_attempts_write": True,
        "save_region_map_wrapper_returns_true_after_void_save": True,
        "region_map_entries_wrapper_ignores_project_save_result": True,
        "dirty_predicate_uses_undo_group_and_config_state": True,
        "close_yes_path_accepts_after_save_handler": True,
        "config_saved_after_unchecked_dump_and_close": True,
        "save_actions_do_not_check_wrapper_results": True,
        "edit_command_redo_mutates_tilemap": True,
    }


def verify_transcript(stdout):
    require("PHASE1_REGIONMAP_FATAL" not in stdout, "native test fatal marker")
    require(stdout.count("PHASE1_REGIONMAP_STAGE positive_save\n") == 1,
            "positive native stage missing")
    require(stdout.count("PHASE1_REGIONMAP_STAGE mixed_save_failure\n") == 1,
            "mixed failure stage missing")
    require(stdout.count("PHASE1_REGIONMAP_COLD_READ_PASS") == 2,
            "fresh-process file readback missing")
    require(stdout.count("PHASE1_REGIONMAP_COLD_NEGATIVE_PASS") == 1,
            "fresh-process mutation control missing")
    rows = re.findall(r"^PHASE1_REGIONMAP_RESULT (\{.*\})$", stdout, re.M)
    require(len(rows) == 1, "native result record missing/duplicated")
    record = json.loads(rows[0])
    expected = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "pinned_original_methods": True,
        "test_only_object_model": True,
        "qt_filesystem_and_undo_stack": True,
        "mixed_save_wrapper_reported_success": True,
        "tilemap_written_before_layout_failure": True,
        "failed_layout_bytes_and_inode_preserved": True,
        "undo_history_cleared_after_failure": True,
        "project_entries_wrapper_reported_success_on_injected_false": True,
        "permission_control_errno": 13,
        "fresh_process_file_readback": True,
        "fresh_process_wrong_bytes_rejected": True,
        "full_project_reopen_tested": False,
        "gui_interaction_tested": False,
        "application_rollback_observed": False,
        "hardware_durability_tested": False,
    }
    require(all(record.get(key) == value for key, value in expected.items()),
            "native evidence fields differ")
    require(isinstance(record.get("permission_control_qt_error_code"), int)
            and record["permission_control_qt_error_code"] > 0
            and record.get("permission_control_text") == "Permission denied",
            "native permission error witness differs")
    require(set(record) == set(expected) | {
        "permission_control_qt_error_code", "permission_control_text"
    }, "native evidence field set differs")
    return record


def source_negatives(sources):
    probes = [
        ("src/core/regionmap.cpp", "editHistory.setClean();", "editHistory.setCleanMutated();"),
        ("include/core/regionmap.h", "QUndoStack editHistory;", "QUndoStack changedHistory;"),
        ("src/core/regionmapeditcommands.cpp",
            "map->setTilemap(this->newTilemap);", "map->setTilemap(this->oldTilemap);"
        ),
        ("include/core/regionmapeditcommands.h",
            "RMCommandId::ID_EditTilemap;", "RMCommandId::ID_EditTilemapMutated;"
        ),
        ("src/ui/regionmapeditor.cpp", "map->save();", "map->saveMutated();"),
        ("src/ui/regionmapeditor.cpp",
            "if (this->modified()) {\n        QMessageBox::StandardButton result",
            "if (this->modifiedMutated()) {\n        QMessageBox::StandardButton result"),
        ("include/ui/regionmapeditor.h",
            "bool saveRegionMap(RegionMap *map);", "bool saveRegionMapMutated(RegionMap *map);"
        ),
    ]
    rejected = 0
    for path, original, mutated in probes:
        source = sources[path]
        require(original in source, "source mutation probe missing: " + path)
        changed = dict(sources)
        changed[path] = source.replace(original, mutated, 1)
        try:
            verify_source_contract(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + path)
    return rejected


def evidence_negatives(record):
    changes = {
        "phase1_gate": "PASS",
        "independent_approvals": 1,
        "pinned_original_methods": False,
        "test_only_object_model": False,
        "mixed_save_wrapper_reported_success": False,
        "failed_layout_bytes_and_inode_preserved": False,
        "undo_history_cleared_after_failure": False,
        "project_entries_wrapper_reported_success_on_injected_false": False,
        "fresh_process_file_readback": False,
        "fresh_process_wrong_bytes_rejected": False,
        "permission_control_errno": 0,
        "permission_control_qt_error_code": 0,
        "permission_control_text": "Unknown error",
        "full_project_reopen_tested": True,
        "application_rollback_observed": True,
        "hardware_durability_tested": True,
    }
    for key, value in changes.items():
        mutated = {**record, key: value}
        try:
            verify_record(mutated)
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped: " + key)
    return len(changes)


def verify_record(record):
    require(record["phase1_gate"] == "FAIL_INCOMPLETE"
            and record["independent_approvals"] == 0, "gate/approval overclaim")
    require(record["pinned_original_methods"] and record["test_only_object_model"],
            "source/execution provenance changed")
    require(record["qt_filesystem_and_undo_stack"]
            and record["mixed_save_wrapper_reported_success"]
            and record["failed_layout_bytes_and_inode_preserved"]
            and record["undo_history_cleared_after_failure"]
            and record["project_entries_wrapper_reported_success_on_injected_false"]
            and record["permission_control_errno"] == 13
            and record["permission_control_qt_error_code"] > 0
            and record["permission_control_text"] == "Permission denied"
            and record["fresh_process_file_readback"]
            and record["fresh_process_wrong_bytes_rejected"],
            "required native witness absent")
    require(not record["full_project_reopen_tested"]
            and not record["gui_interaction_tested"]
            and not record["application_rollback_observed"]
            and not record["hardware_durability_tested"],
            "unsupported behavior claim")


def verify_package_record(evidence):
    require(evidence["porymap_commit"] == PIN
            and evidence["phase1_gate"] == "FAIL_INCOMPLETE"
            and evidence["independent_approvals"] == 0,
            "package pin/gate/approval changed")
    rows = evidence["source_files"]
    require(len(rows) == len(FILES), "source row count changed")
    require({row["path"] for row in rows} == set(FILES), "source path set/overlap changed")
    for row in rows:
        blob, digest, _ = FILES[row["path"]]
        require(row["repository"] == "huderlem/porymap"
                and row["pinned_commit"] == PIN
                and row["git_blob_sha1"] == blob
                and row["source_sha256"] == digest,
                "source identity changed: " + row["path"])
        require("LGPL-3.0" in row["license"]
                and row["original_dossier_row_sha256"] is None
                and row["original_dossier_archive_sha256"] is None
                and row["original_dossier_status"].startswith("NEEDS_EVIDENCE")
                and row["disposition"] == "NEEDS_EVIDENCE",
                "license or unresolved prior-dossier status changed: " + row["path"])
        row_body = {key: value for key, value in row.items()
                    if key != "new_dossier_row_sha256"}
        expected_row_sha = hashlib.sha256(
            json.dumps(row_body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        require(row["new_dossier_row_sha256"] == expected_row_sha,
                "dossier row hash changed: " + row["path"])
    license_row = evidence["root_license"]
    require(license_row["pinned_git_blob_sha1"] == LICENSE_BLOB
            and license_row["source_sha256"] == LICENSE_SHA256
            and license_row["text"] == "LGPL-3.0",
            "root license evidence missing or changed")
    require(evidence["overlap_check"]["prior_inventory_path_matches"] == 0
            and set(evidence["overlap_check"]["paths"]) == set(FILES),
            "source overlap evidence changed")
    verify_record(evidence["native_result"])
    require(evidence["source_mutations_rejected"] == len(FILES) + 1
            and evidence["evidence_mutations_rejected"] >= 16,
            "negative-control evidence missing")
    require(evidence["evidence_labels"]["gameplay"] == "not tested"
            and evidence["native_result"]["full_project_reopen_tested"] is False
            and evidence["native_result"]["gui_interaction_tested"] is False,
            "execution label overclaim")


def package_negatives(evidence):
    mutations = []
    bad_license = json.loads(json.dumps(evidence))
    bad_license["source_files"][0]["license"] = ""
    mutations.append(("license", bad_license))
    bad_source = json.loads(json.dumps(evidence))
    bad_source["source_files"][0]["source_sha256"] = "0" * 64
    mutations.append(("source-hash", bad_source))
    bad_row = json.loads(json.dumps(evidence))
    bad_row["source_files"][0]["new_dossier_row_sha256"] = "0" * 64
    mutations.append(("dossier-row-hash", bad_row))
    overlap = json.loads(json.dumps(evidence))
    overlap["source_files"][1]["path"] = overlap["source_files"][0]["path"]
    mutations.append(("duplicate-overlap", overlap))
    promoted = json.loads(json.dumps(evidence))
    promoted["source_files"][0]["disposition"] = "COPILOT_REVIEWED/PASSED"
    mutations.append(("fabricated-review", promoted))
    approval = json.loads(json.dumps(evidence))
    approval["independent_approvals"] = 1
    mutations.append(("approval", approval))
    false_scope = json.loads(json.dumps(evidence))
    false_scope["native_result"]["full_project_reopen_tested"] = True
    mutations.append(("false-native-scope", false_scope))
    for label, changed in mutations:
        try:
            verify_package_record(changed)
        except (ValueError, KeyError):
            continue
        raise ValueError("package evidence mutation escaped: " + label)
    return len(mutations)


def deterministic_archive(dossier, archive):
    payload = dossier.read_bytes()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                info = tarfile.TarInfo(dossier.name)
                info.size = len(payload)
                info.mtime = 0
                info.mode = 0o644
                tar.addfile(info, __import__("io").BytesIO(payload))
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[1]
    sources, rows = verify_sources(args.porymap)
    source_observations = verify_source_contract(sources)
    require(source_negatives(sources) == len(FILES) + 1, "source mutation count drift")
    overlap_check = verify_no_prior_inventory_overlap(repository_root)
    prior_dossiers = verify_prior_dossiers(repository_root)
    harness = args.harness.read_text()
    require(harness.count("PHASE1_INSERT_PINNED_FUNCTIONS") == 1,
            "native insertion anchor changed")
    functions = [extract(sources[path], anchor) for path, anchor in FUNCTIONS]
    with tempfile.TemporaryDirectory() as directory:
        src = Path(directory) / "native_regionmap.cpp"
        exe = Path(directory) / "native_regionmap"
        src.write_text(harness.replace("PHASE1_INSERT_PINNED_FUNCTIONS",
                                       "\n\n".join(functions)))
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Widgets"], text=True
        ).split()
        command = ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
                   str(src), "-o", str(exe), *flags]
        built = subprocess.run(command, capture_output=True, text=True)
        require(built.returncode == 0,
                "native Qt compile failed: " + built.stderr[-5000:])
        run = subprocess.run([str(exe)], capture_output=True, text=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(run.stdout + run.stderr)
    require(run.returncode == 0, "native Qt test failed: " + run.stderr[-3000:])
    record = verify_transcript(run.stdout)
    verify_record(record)
    negatives = evidence_negatives(record)
    require(negatives == 16, "evidence mutation count drift")
    archive_sha = deterministic_archive(args.dossier, args.archive)

    evidence = {
        "class": "PINNED_PORYMAP_REGIONMAP_SAVE_DIRTY_STATE_NATIVE_QT",
        "porymap_commit": PIN,
        "source_files": rows,
        "root_license": {
            "pinned_git_blob_sha1": LICENSE_BLOB,
            "source_sha256": LICENSE_SHA256,
            "text": "LGPL-3.0",
            "scope_note": "Not a redistribution determination",
        },
        "prior_context_dossier_sha256": prior_dossiers,
        "overlap_check": overlap_check,
        "source_observations": source_observations,
        "native_result": record,
        "source_mutations_rejected": len(FILES) + 1,
        "evidence_mutations_rejected": negatives,
        "new_dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "new_dossier_archive_sha256": archive_sha,
        "evidence_labels": {
            "native": "unchanged pinned method bodies with real Qt6 QFile, QUndoStack, and a fresh child process",
            "test_only": "RegionMap/Project object shells; no original Project constructor or UI",
            "host": "Linux file permissions, bytes, and inode",
            "gameplay": "not tested",
        },
        "sqlite_or_qt_translation_sources": "not in selected source set",
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    package_mutations = package_negatives(evidence)
    evidence["package_mutations_rejected"] = package_mutations
    evidence["evidence_mutations_rejected"] = negatives + package_mutations
    verify_package_record(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify the pinned RegionMap multi-map save and Project-writer boundary."""
import argparse
import gzip
import hashlib
import importlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

caller = importlib.import_module("phase1_porymap_regionmap_project_caller")
PIN = caller.PIN


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def pinned_function(sources, path, anchor):
    return caller.extract(sources[path], anchor)


def verify_source_contract(sources):
    editor_header = sources["include/ui/regionmapeditor.h"]

    region_save = pinned_function(sources, "src/core/regionmap.cpp", "void RegionMap::save()")
    tilemap_save = pinned_function(sources, "src/core/regionmap.cpp", "void RegionMap::saveTilemap()")
    layout_save = pinned_function(sources, "src/core/regionmap.cpp", "void RegionMap::saveLayout()")
    setup = pinned_function(sources, "src/ui/regionmapeditor.cpp", "bool RegionMapEditor::setup()")
    set_region_map = pinned_function(sources, "src/ui/regionmapeditor.cpp",
                                     "void RegionMapEditor::setRegionMap(")
    save_region = pinned_function(sources, "src/ui/regionmapeditor.cpp",
                                  "bool RegionMapEditor::saveRegionMap(")
    save_entries = pinned_function(sources, "src/ui/regionmapeditor.cpp",
                                   "bool RegionMapEditor::saveRegionMapEntries()")
    save_config = pinned_function(sources, "src/ui/regionmapeditor.cpp",
                                  "void RegionMapEditor::saveConfig()")
    save_all = pinned_function(sources, "src/ui/regionmapeditor.cpp",
                               "void RegionMapEditor::on_actionSave_All_triggered()")
    set_entries = pinned_function(sources, "src/project.cpp",
                                  "void Project::setRegionMapEntries(")
    save_sections = pinned_function(sources, "src/project.cpp",
                                    "bool Project::saveRegionMapSections()")
    undo = pinned_function(sources, "src/core/regionmapeditcommands.cpp",
                           "void EditEntry::undo()")

    require(region_save.index("saveTilemap();") < region_save.index("saveLayout();")
            < region_save.index("this->editHistory.setClean();"),
            "RegionMap save/write/clean ordering changed")
    require("tilemapFile.write(this->getTilemap());" in tilemap_save
            and "tilemapFile.error()" not in tilemap_save,
            "RegionMap tilemap write error boundary changed")
    binary_layout = layout_save[layout_save.index("case LayoutFormat::Binary"):]
    require("bfile.write(data);" in binary_layout
            and "bfile.error()" not in binary_layout,
            "RegionMap binary layout write error boundary changed")
    require("newMap->setEntries(&this->region_map_entries);" in setup
            and "this->history.addStack(&(newMap->editHistory));" in setup,
            "RegionMap shared entry or undo-group ownership changed")
    require("this->region_map->editHistory.setActive();" in set_region_map,
            "active RegionMap undo-stack selection changed")
    require("map->save();" in save_region and save_region.count("return true;") == 1,
            "RegionMap save wrapper propagation changed")
    require("this->project->setRegionMapEntries(this->region_map_entries);" in save_entries
            and "this->project->saveRegionMapSections();" in save_entries
            and "if (!" not in save_entries and save_entries.count("return true;") == 1,
            "Project save result propagation through entries wrapper changed")
    require(save_all.index("for (auto it : this->region_maps)")
            < save_all.index("saveRegionMap(it.second);")
            < save_all.index("saveRegionMapEntries();")
            < save_all.index("saveConfig();")
            and "if (!" not in save_all,
            "RegionMap Save All write order/error propagation changed")
    require("this->locationData[*it].map = entries.value(*it);" in set_entries,
            "Project section-entry update mapping changed")
    require("if (!file.open(QIODevice::WriteOnly))" in save_sections
            and "return false;" in save_sections
            and "jsonDoc.dump(&file);" in save_sections
            and "file.close();" in save_sections
            and save_sections.index("file.close();") < save_sections.rindex("return true;")
            and "file.error()" not in save_sections
            and "file.flush()" not in save_sections,
            "Project RegionMap JSON writer result boundary changed")
    require("this->locationData" in save_sections
            and "mapSectionArray.append(mapSectionObj);" in save_sections,
            "Project RegionMap section serialization data path changed")
    require("jsonDoc.dump(&file);" in save_config
            and "file.close();" in save_config
            and save_config.index("file.close();") < save_config.index("this->configSaved = true;")
            and "file.error()" not in save_config,
            "RegionMap config clean-state/write-error boundary changed")
    require("map->setEntry(section, oldEntry);" in undo,
            "EditEntry undo no longer restores shared entry state")
    require("QUndoGroup history;" in editor_header
            and "QHash<QString, MapSectionEntry> region_map_entries;" in editor_header,
            "RegionMapEditor shared-hash/undo-group owner changed")

    return {
        "pinned_saveall_order": ["all_region_maps", "project_region_map_sections", "editor_config"],
        "regionmap_undo_stacks_share_project_entry_hash": True,
        "actual_project_writer_body_extracted": True,
        "unchecked_project_json_write_and_close": True,
        "application_rollback_not_proven_by_source": True,
        "new_original_source_files": 0,
    }


def source_negatives(sources):
    probes = [
        ("src/core/regionmap.cpp", "void RegionMap::save()",
         "saveTilemap();\n    saveLayout();", "saveLayout();\n    saveTilemap();"),
        ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::setup()",
         "this->history.addStack(&(newMap->editHistory));", "this->history.clear();"),
        ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::setRegionMap(",
         "this->region_map->editHistory.setActive();", "this->history.clear();"),
        ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::saveRegionMapEntries()",
         "this->project->saveRegionMapSections();",
         "if (!this->project->saveRegionMapSections()) return false;"),
        ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::on_actionSave_All_triggered()",
         "for (auto it : this->region_maps)", "if (false)"),
        ("src/project.cpp", "void Project::setRegionMapEntries(",
         "this->locationData[*it].map = entries.value(*it);",
         "this->locationData[*it].map = MapSectionEntry();"),
        ("src/project.cpp", "bool Project::saveRegionMapSections()",
         "jsonDoc.dump(&file);", "file.flush();"),
        ("src/core/regionmapeditcommands.cpp", "void EditEntry::undo()",
         "map->setEntry(section, oldEntry);", "map->setEntry(section, newEntry);"),
    ]
    rejected = 0
    for path, anchor, original, mutated in probes:
        original_function = pinned_function(sources, path, anchor)
        require(original in original_function, "source mutation probe missing: " + anchor)
        mutated_function = original_function.replace(original, mutated, 1)
        altered = dict(sources)
        altered[path] = sources[path].replace(original_function, mutated_function, 1)
        try:
            verify_source_contract(altered)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + anchor)
    return rejected


def verify_record(record):
    expected_true = (
        "pinned_original_method_bodies", "native_qt_file_io",
        "test_only_project_and_serializer_shells", "original_regionmap_save_all_called",
        "original_regionmap_asset_writers_called", "original_project_setter_and_writer_called",
        "original_entry_save_wrapper_called", "cross_map_undo_group_stacks_exercised",
        "cross_map_undo_shared_state_fingerprint_observed", "positive_multi_file_save_observed",
        "project_open_failure_wrapper_reports_success",
        "project_save_wrapper_reports_success_after_enospc",
        "map_assets_persist_after_project_json_failure", "test_fixture_restoration_used",
        "fresh_process_byte_readback",
    )
    expected_false = (
        "application_rollback_observed", "cold_project_load_tested", "gui_interaction_tested",
        "orderedjson_implementation_tested", "short_write_tested",
        "hardware_durability_tested", "gameplay_tested",
    )
    require(record["phase1_gate"] == "FAIL_INCOMPLETE"
            and record["independent_approvals"] == 0,
            "gate or approval overclaim")
    require(all(record.get(key) is True for key in expected_true),
            "required native result missing")
    require(all(record.get(key) is False for key in expected_false),
            "evidence scope overclaim")
    require(record["enospc_control_errno"] == 28
            and record["project_writer_errno"] == 28
            and isinstance(record["project_writer_write_result"], int)
            and record["project_writer_flush_failed"] is True
            and record["project_writer_error"] > 0,
            "native ENOSPC failure fingerprint changed")
    require(set(record) == {
        "phase1_gate", "independent_approvals", "pinned_original_method_bodies",
        "native_qt_file_io", "test_only_project_and_serializer_shells",
        "original_regionmap_save_all_called", "original_regionmap_asset_writers_called",
        "original_project_setter_and_writer_called", "original_entry_save_wrapper_called",
        "cross_map_undo_group_stacks_exercised",
        "cross_map_undo_shared_state_fingerprint_observed",
        "positive_multi_file_save_observed", "project_open_failure_wrapper_reports_success",
        "enospc_control_errno", "project_writer_flush_failed",
        "project_writer_write_result", "project_writer_errno", "project_writer_error",
        "project_save_wrapper_reports_success_after_enospc",
        "map_assets_persist_after_project_json_failure", "test_fixture_restoration_used",
        "application_rollback_observed", "fresh_process_byte_readback",
        "cold_project_load_tested", "gui_interaction_tested",
        "orderedjson_implementation_tested", "short_write_tested",
        "hardware_durability_tested", "gameplay_tested",
    }, "native result fields changed")
    return record


def evidence_negatives(record):
    mutations = (
        ("phase1_gate", "PASS"),
        ("independent_approvals", 1),
        ("test_only_project_and_serializer_shells", False),
        ("application_rollback_observed", True),
        ("fresh_process_byte_readback", False),
        ("cold_project_load_tested", True),
        ("orderedjson_implementation_tested", True),
        ("project_open_failure_wrapper_reports_success", False),
        ("project_writer_errno", 5),
        ("project_writer_write_result", "not-an-integer"),
        ("project_writer_flush_failed", False),
        ("project_save_wrapper_reports_success_after_enospc", False),
    )
    rejected = 0
    for key, value in mutations:
        changed = dict(record)
        changed[key] = value
        try:
            verify_record(changed)
        except (ValueError, KeyError):
            rejected += 1
        else:
            raise ValueError("evidence mutation escaped: " + key)
    return rejected


def run_native(harness, sources, log_path):
    functions = (
        ("src/ui/selectablepixmapitem.cpp", "QPoint SelectablePixmapItem::getCellPos("),
        ("src/ui/regionmapentriespixmapitem.cpp",
         "void RegionMapEntriesPixmapItem::mousePressEvent("),
        ("src/ui/regionmapentriespixmapitem.cpp",
         "void RegionMapEntriesPixmapItem::mouseMoveEvent("),
        ("src/ui/regionmapentriespixmapitem.cpp",
         "void RegionMapEntriesPixmapItem::mouseReleaseEvent("),
        ("src/core/regionmap.cpp", "MapSectionEntry RegionMap::getEntry("),
        ("src/core/regionmap.cpp", "void RegionMap::setEntry("),
        ("src/core/regionmap.cpp", "void RegionMap::save()"),
        ("src/core/regionmap.cpp", "void RegionMap::saveTilemap()"),
        ("src/core/regionmap.cpp", "void RegionMap::saveLayout()"),
        ("src/core/regionmapeditcommands.cpp", "EditEntry::EditEntry("),
        ("src/core/regionmapeditcommands.cpp", "void EditEntry::redo()"),
        ("src/core/regionmapeditcommands.cpp", "void EditEntry::undo()"),
        ("src/core/regionmapeditcommands.cpp", "bool EditEntry::mergeWith("),
        ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::onRegionMapEntryDragged("),
        ("src/ui/regionmapeditor.cpp",
         "void RegionMapEditor::on_spinBox_RM_Entry_x_valueChanged("),
        ("src/ui/regionmapeditor.cpp",
         "void RegionMapEditor::on_spinBox_RM_Entry_y_valueChanged("),
        ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::saveRegionMap("),
        ("src/ui/regionmapeditor.cpp", "bool RegionMapEditor::saveRegionMapEntries()"),
        ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::saveConfig()"),
        ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::on_actionSave_All_triggered()"),
        ("src/project.cpp", "void Project::setRegionMapEntries("),
        ("src/project.cpp", "bool Project::saveRegionMapSections()"),
    )
    bodies = "\n\n".join(pinned_function(sources, path, anchor)
                         for path, anchor in functions)
    generated = harness.read_text(encoding="utf-8")
    require(generated.count("PINNED_REGIONMAP_PROJECT_SAVE_METHODS") == 1,
            "native method placeholder missing/duplicated")
    generated = generated.replace("PINNED_REGIONMAP_PROJECT_SAVE_METHODS", bodies)

    with tempfile.TemporaryDirectory(prefix="phase1-regionmap-project-save-") as directory:
        directory = Path(directory)
        source = directory / harness.name
        source.write_text(generated, encoding="utf-8")
        moc = shutil.which("moc") or "/usr/lib/qt6/libexec/moc"
        moc_output = directory / "moc_regionmap_project_save.cpp"
        subprocess.run([moc, str(source), "-o", str(moc_output)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        executable = directory / "regionmap-project-save"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Widgets"], text=True
        ).split()
        build = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-Wall", "-Wextra",
             str(source), "-o", str(executable), *flags],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if build.returncode:
            log_path.write_text(build.stdout, encoding="utf-8")
            raise ValueError("native Qt compile failed; see " + str(log_path))
        import os
        environment = dict(os.environ)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run([str(executable)], env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=45)
        log_path.write_text(build.stdout + result.stdout, encoding="utf-8")
        require(result.returncode == 0, "native Project save test failed; see " + str(log_path))
        rows = re.findall(
            r"^PHASE1_REGIONMAP_PROJECT_SAVE_RESULT (\{.*\})$", result.stdout, re.M
        )
        require(len(rows) == 1, "native Project save result missing/duplicated")
        return verify_record(json.loads(rows[0]))


def make_archive(dossier, archive):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as tar:
        data = dossier.read_bytes()
        info = tarfile.TarInfo(dossier.name)
        info.size = len(data)
        info.mtime = 0
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0) as compressed:
            compressed.write(payload.getvalue())


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
    sources, rows = caller.verify_sources(args.porymap)
    reused_paths = set(caller.CONTEXT_FILES)
    reused_rows = [row for row in rows if row["path"] in reused_paths]
    require(len(reused_rows) == len(reused_paths)
            and all(row["disposition"] == "NEEDS_EVIDENCE" for row in reused_rows),
            "reused source disposition or identity rows changed")
    prior_dossier_hashes = caller.verify_prior_dossiers(repository_root)
    source_contract = verify_source_contract(sources)
    source_rejections = source_negatives(sources)
    native_result = run_native(args.harness, sources, args.log)
    evidence_rejections = evidence_negatives(native_result)
    make_archive(args.dossier, args.archive)

    previous_dossier = repository_root / (
        "docs/phase1-review-readiness/porymap-regionmap-project-caller-20261105.md"
    )
    result = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "porymap_pin": PIN,
        "firered_pin_unchanged_not_exercised":
            "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
        "poryscript_pin_unchanged_not_exercised":
            "c32481161c767b25a3425fa9f1f8729927ff3d55",
        "new_original_source_files": [],
        "reused_source_rows": reused_rows,
        "prior_regionmap_dossier_sha256": prior_dossier_hashes,
        "source_contract": source_contract,
        "previous_caller_dossier_sha256": hashlib.sha256(
            previous_dossier.read_bytes()
        ).hexdigest(),
        "native_result": native_result,
        "source_mutations_rejected": source_rejections,
        "evidence_mutations_rejected": evidence_rejections,
        "dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "archive_contents": [args.dossier.name],
        "archive_excludes_upstream_source": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PORYMAP_REGIONMAP_PROJECT_SAVE_PASS "
          f"new_sources=0 source_mutations={source_rejections} "
          f"evidence_mutations={evidence_rejections} gate=FAIL_INCOMPLETE approvals=0")
    print(json.dumps({
        "dossier_sha256": result["dossier_sha256"],
        "archive_sha256": result["archive_sha256"],
        "archive": result["archive_contents"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

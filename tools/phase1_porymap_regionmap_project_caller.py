#!/usr/bin/env python3
"""Verify the pinned RegionMap entry-drag to undo-stack caller boundary."""
import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
NEW_FILES = {
    "src/ui/selectablepixmapitem.cpp": (
        "267fbd1fc63f08efef4b2ddb3f1ad4845816fc78",
        "2fc424561b9958d71d8e097fb691756c67c1871e8402651c69ed79d0a0816cba",
        "Whole-file selection base; exact pixel-to-cell mapping used by entry dragging",
    ),
    "include/ui/selectablepixmapitem.h": (
        "a267291efbc6c3a4811e757b64a9def9f67b8d3d",
        "51dc65ebd2669dc42f5201f3f6ff089dfc6b7401f77f10f208db9bba36c5b07b",
        "Whole-file selection base interface and QGraphicsPixmapItem inheritance",
    ),
    "src/ui/regionmapentriespixmapitem.cpp": (
        "5bf9a08f6f5588577e57e729ee54f535b324ea81",
        "54cf0eaced29720b0c5e030f9003f6830dcfa59e8c769b778078f7a83f24adaf",
        "Whole-file RegionMap entry rendering, selection, and bounded drag signal",
    ),
    "include/ui/regionmapentriespixmapitem.h": (
        "12808c330b7ee6a778d6b8eaf9bccba72b2f7a0e",
        "48f009492b826709cc0c8ba02db61f8b315fbf63746f9d0f9b311370fc866c3a",
        "Whole-file entry item state, callbacks, and event-handler interface",
    ),
}
CONTEXT_FILES = {
    "src/ui/regionmapeditor.cpp": (
        "a96de606cc18469b558b1acfc7c787432b8dcfb4",
        "43f433c1754cd25d4691491567e7be9ff48e47e89c485eb917a5b26e2e1eb4e2",
        "Reused: item signal connection, edit slots, shared entry setup, and Project save wrapper",
    ),
    "src/core/regionmap.cpp": (
        "94f686426e5ea8a84294dd1ac35617700c54e73f",
        "a6b6717820ae1fbd04424283cf1cb4c057ec34eaff6935c5a3dc8f36f90ad44c",
        "Reused: entry getters/setters backed by the editor-owned shared hash",
    ),
    "src/core/regionmapeditcommands.cpp": (
        "f21f1d720ae22d4911ef71b984435ff66c0566f9",
        "28950c048b96df25fb7525d84298e50c3d302105edf7cc6aff285572e6c92f13",
        "Reused: EditEntry redo/undo and same-entry command merge",
    ),
    "include/core/regionmapeditcommands.h": (
        "e47fdb7b9ed59ff523d9e5a91975c98bca68efb1",
        "1645066c8a13ef544589516e76c5dc202f2605151bf0dc381270879b5137096e",
        "Reused: EditEntry command identity and merge interface",
    ),
    "include/core/regionmap.h": (
        "c8afb1b2dd44b80ebfbf14d3793866b7764629ed",
        "b723542988188a4bc4c1c7b02849baf10d8604199781c6fe21ca49f848451a84",
        "Reused: RegionMap shared-entry and undo-stack interface",
    ),
    "src/project.cpp": (
        "d43b0949303433111d4478ad76117c2b3445dd13",
        "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
        "Reused: Project::saveRegionMapSections consumer; not executed here",
    ),
}
PREVIOUS_REGIONMAP_FILES = {
    "src/core/regionmap.cpp",
    "include/core/regionmap.h",
    "src/core/regionmapeditcommands.cpp",
    "include/core/regionmapeditcommands.h",
    "src/ui/regionmapeditor.cpp",
    "include/ui/regionmapeditor.h",
}
LICENSE_BLOB = "65c5ca88a67c30becee01c5a8816d964b03862f9"
LICENSE_SHA256 = "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-regionmap-persistence-boundary-20261105.md":
        "cd111060bc16f62556ff09e1939b035b15c64a0ab03827716998e434283286f1",
    "docs/phase1-review-readiness/porymap-five-json-writers-native-20261029.md":
        "98f03e91e58e2f18a3e68dc464a2ca476058d22be8b390f5867899d6887af526",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "e00c5431a19b9d9e5a66d70b8dd3a817e5ea25a0307de7be8618e1cf2226af87",
}


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
    for path, (blob, digest, role) in {**NEW_FILES, **CONTEXT_FILES}.items():
        data = (root / path).read_bytes()
        require(git(root, "hash-object", path) == blob, "Porymap Git blob mismatch: " + path)
        require(hashlib.sha256(data).hexdigest() == digest, "Porymap byte hash mismatch: " + path)
        sources[path] = data.decode("utf-8")
        is_new = path in NEW_FILES
        row = {
            "repository": "huderlem/porymap",
            "path": path,
            "pinned_commit": PIN,
            "git_blob_sha1": blob,
            "source_sha256": digest,
            "bytes": len(data),
            "lines": len(data.splitlines()),
            "role": role,
            "row_kind": "new_complete_source" if is_new else "reused_context",
            "license": "Porymap root LICENSE.md, LGPL-3.0 text; not a redistribution determination",
            "original_dossier_row_sha256": None,
            "original_dossier_archive_sha256": None,
            "original_dossier_status": "NEEDS_EVIDENCE: original per-file row/archive not independently available",
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
                   / "docs/phase1-review-readiness/porymap-regionmap-project-caller-20261105.md").resolve()
    # Later packets cite these sources as context; they are not prior inventory records.
    later_context_packet = {
        (repository_root / "tools/phase1_porymap_regionmap_project_save.py").resolve(),
        (repository_root
         / "docs/phase1-review-readiness/porymap-regionmap-project-save-failure-closure-20261106.md").resolve(),
    }
    require(not set(NEW_FILES).intersection(PREVIOUS_REGIONMAP_FILES),
            "new complete-file inventory overlaps the prior RegionMap inventory")
    candidates = []
    for folder in (repository_root / "tools",
                   repository_root / "docs/phase1-review-readiness"):
        candidates.extend(path for path in folder.rglob("*")
                          if path.is_file() and path.suffix in {".py", ".md"}
                          and path.resolve() not in {new_tool, new_dossier, *later_context_packet})
    for path in NEW_FILES:
        matches = [str(candidate) for candidate in candidates
                   if path in candidate.read_text(errors="replace")]
        require(not matches, "selected source already appears in prior inventory: "
                + path + ": " + ", ".join(matches[:3]))
    return {
        "scanned_tools_and_readiness_dossiers": len(candidates),
        "prior_inventory_path_matches": 0,
        "new_complete_files": sorted(NEW_FILES),
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
    selectable = sources["src/ui/selectablepixmapitem.cpp"]
    selectable_header = sources["include/ui/selectablepixmapitem.h"]
    entries = sources["src/ui/regionmapentriespixmapitem.cpp"]
    entries_header = sources["include/ui/regionmapentriespixmapitem.h"]
    editor = sources["src/ui/regionmapeditor.cpp"]
    region = sources["src/core/regionmap.cpp"]
    commands = sources["src/core/regionmapeditcommands.cpp"]
    region_header = sources["include/core/regionmap.h"]
    commands_header = sources["include/core/regionmapeditcommands.h"]
    project = sources["src/project.cpp"]

    cell_pos = extract(selectable, "QPoint SelectablePixmapItem::getCellPos(")
    entry_methods = {
        anchor: extract(entries, anchor)
        for anchor in (
            "void RegionMapEntriesPixmapItem::draw()",
            "void RegionMapEntriesPixmapItem::select(int x, int y)",
            "void RegionMapEntriesPixmapItem::select(int index)",
            "void RegionMapEntriesPixmapItem::mousePressEvent(",
            "void RegionMapEntriesPixmapItem::mouseMoveEvent(",
            "void RegionMapEntriesPixmapItem::mouseReleaseEvent(",
            "void RegionMapEntriesPixmapItem::hoverMoveEvent(",
            "void RegionMapEntriesPixmapItem::hoverLeaveEvent(",
            "void RegionMapEntriesPixmapItem::updateSelectedTile()",
        )
    }
    setup = extract(editor, "bool RegionMapEditor::setup()")
    display = extract(editor, "void RegionMapEditor::displayRegionMapEntriesImage()")
    drag_slot = extract(editor, "void RegionMapEditor::onRegionMapEntryDragged(")
    x_slot = extract(editor, "void RegionMapEditor::on_spinBox_RM_Entry_x_valueChanged(")
    y_slot = extract(editor, "void RegionMapEditor::on_spinBox_RM_Entry_y_valueChanged(")
    get_entry = extract(region, "MapSectionEntry RegionMap::getEntry(")
    set_entry = extract(region, "void RegionMap::setEntry(")
    edit_ctor = extract(commands, "EditEntry::EditEntry(")
    edit_redo = extract(commands, "void EditEntry::redo()")
    edit_undo = extract(commands, "void EditEntry::undo()")
    edit_merge = extract(commands, "bool EditEntry::mergeWith(")
    save_entries = extract(editor, "bool RegionMapEditor::saveRegionMapEntries()")
    save_sections = extract(project, "bool Project::saveRegionMapSections()")

    require("static_cast<int>(itemPos.x())" in cell_pos
            and "static_cast<int>(itemPos.y())" in cell_pos
            and "x / this->cellWidth" in cell_pos
            and "y / this->cellHeight" in cell_pos,
            "pixel-to-cell mapping changed")
    require("void entryPositionChanged(int, int);" in entries_header
            and "emit entryPositionChanged(new_x, new_y);" in entry_methods[
                "void RegionMapEntriesPixmapItem::mouseMoveEvent("],
            "entry movement signal changed")
    move = entry_methods["void RegionMapEntriesPixmapItem::mouseMoveEvent("]
    require("if (!draggingEntry)" in move
            and "new_x + entry.width > this->region_map->tilemapWidth() - this->region_map->padLeft()"
            in move
            and "new_y + entry.height > this->region_map->tilemapHeight() - this->region_map->padTop()"
            in move
            and "new_x < 0 || new_y < 0" in move
            and "new_x != entry.x || new_y != entry.y" in move,
            "entry drag conditions changed")
    require("connect(this->region_map_entries_item, &RegionMapEntriesPixmapItem::entryPositionChanged,"
            in display and "&RegionMapEditor::onRegionMapEntryDragged);" in display,
            "entry signal caller connection changed")
    require("newMap->setEntries(&this->region_map_entries);" in setup,
            "RegionMap no longer uses the editor-owned entry hash")
    require("void setEntries(QHash<QString, MapSectionEntry> *entries)"
            in region_header
            and "QHash<QString, MapSectionEntry> *region_map_entries = nullptr;"
            in region_header,
            "RegionMap shared-entry pointer interface changed")
    require("on_spinBox_RM_Entry_x_valueChanged(new_x);" in drag_slot
            and "on_spinBox_RM_Entry_y_valueChanged(new_y);" in drag_slot,
            "entry drag editor slot changed")
    for slot in (x_slot, y_slot):
        require("this->region_map_entries[activeEntry]" in slot
                and "new EditEntry(this->region_map, activeEntry, oldEntry, newEntry)" in slot
                and "this->region_map->editHistory.push(commit);" in slot,
                "entry coordinate slot no longer pushes the original undo command")
    require("this->region_map_entries->value(section, MapSectionEntry())" in get_entry
            and "this->region_map_entries->insert(section, entry);" in set_entry
            and "map->setEntry(section, newEntry);" in edit_redo
            and "map->setEntry(section, oldEntry);" in edit_undo
            and "this->map != other->map" in edit_merge
            and "this->section != other->section" in edit_merge
            and "this->newEntry = other->newEntry;" in edit_merge,
            "shared entry undo/redo/merge contract changed")
    require("ID_EditEntry," in commands_header
            and "int id() const override { return RMCommandId::ID_EditEntry; }"
            in commands_header,
            "EditEntry QUndoStack merge identity changed")
    require("this->project->setRegionMapEntries(this->region_map_entries);" in save_entries
            and "this->project->saveRegionMapSections();" in save_entries
            and "return true;" in save_entries
            and "saveRegionMapSections" in save_sections,
            "Project consumer linkage changed")
    require("QPoint getCellPos(const QPointF &itemPos);" in selectable_header
            and "class RegionMapEntriesPixmapItem : public SelectablePixmapItem" in entries_header,
            "selected source headers changed")

    return {
        "new_complete_files": len(NEW_FILES),
        "new_complete_file_function_anchors": len(entry_methods) + 1,
        "reused_caller_function_anchors": 13,
        "entry_drag_signal_to_editor_slot": True,
        "region_map_shares_editor_project_entry_hash": True,
        "entry_undo_restores_shared_hash_by_source": True,
        "Project_writer_is_downstream_but_not_executed": True,
        "whole_file_disposition": "NEEDS_EVIDENCE",
    }


def source_negatives(sources):
    probes = [
        ("src/ui/selectablepixmapitem.cpp",
         "return QPoint(x / this->cellWidth, y / this->cellHeight);",
         "return QPoint(y / this->cellWidth, x / this->cellHeight);"),
        ("include/ui/selectablepixmapitem.h",
         "QPoint getCellPos(const QPointF &itemPos);",
         "QPoint getCellPosMutated(const QPointF &itemPos);"),
        ("src/ui/regionmapentriespixmapitem.cpp",
         "emit entryPositionChanged(new_x, new_y);",
         "emit entryPositionChanged(new_y, new_x);"),
        ("include/ui/regionmapentriespixmapitem.h",
         "void entryPositionChanged(int, int);",
         "void entryPositionChanged(int);"),
    ]
    rejected = 0
    for path, original, mutated in probes:
        require(original in sources[path], "source mutation probe missing: " + path)
        changed = dict(sources)
        changed[path] = sources[path].replace(original, mutated, 1)
        try:
            verify_source_contract(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + path)
    return rejected


def verify_record(record):
    expected = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "pinned_original_method_bodies": True,
        "native_qt_signal_dispatch": True,
        "test_only_object_model": True,
        "entry_drag_reaches_editor_undo_stack": True,
        "undo_restores_shared_entry_state": True,
        "redo_restores_moved_entry_state": True,
        "out_of_bounds_move_rejected": True,
        "move_after_release_rejected": True,
        "project_file_write_tested": False,
        "project_save_tested": False,
        "stale_disk_bytes_checked": False,
        "full_project_load_tested": False,
        "cold_project_reopen_tested": False,
        "application_failure_rollback_observed": False,
        "hardware_durability_tested": False,
        "gameplay_tested": False,
        "full_original_application_tested": False,
    }
    require(record == expected, "native caller evidence record differs")
    return expected


def evidence_negatives(record):
    mutations = {
        "phase1_gate": "PASS",
        "independent_approvals": 1,
        "native_qt_signal_dispatch": False,
        "test_only_object_model": False,
        "entry_drag_reaches_editor_undo_stack": False,
        "undo_restores_shared_entry_state": False,
        "project_file_write_tested": True,
        "project_save_tested": True,
        "stale_disk_bytes_checked": True,
        "full_project_load_tested": True,
        "cold_project_reopen_tested": True,
        "application_failure_rollback_observed": True,
        "hardware_durability_tested": True,
        "gameplay_tested": True,
        "full_original_application_tested": True,
    }
    rejected = 0
    for key, value in mutations.items():
        changed = dict(record)
        changed[key] = value
        try:
            verify_record(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("evidence mutation escaped: " + key)
    return rejected


def run_native(harness, sources, log_path):
    with tempfile.TemporaryDirectory(prefix="phase1-regionmap-caller-") as directory:
        directory = Path(directory)
        generated = harness.read_text(encoding="utf-8")
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
            ("src/core/regionmapeditcommands.cpp", "EditEntry::EditEntry("),
            ("src/core/regionmapeditcommands.cpp", "void EditEntry::redo()"),
            ("src/core/regionmapeditcommands.cpp", "void EditEntry::undo()"),
            ("src/core/regionmapeditcommands.cpp", "bool EditEntry::mergeWith("),
            ("src/ui/regionmapeditor.cpp", "void RegionMapEditor::onRegionMapEntryDragged("),
            ("src/ui/regionmapeditor.cpp",
             "void RegionMapEditor::on_spinBox_RM_Entry_x_valueChanged("),
            ("src/ui/regionmapeditor.cpp",
             "void RegionMapEditor::on_spinBox_RM_Entry_y_valueChanged("),
        )
        bodies = "\n\n".join(extract(sources[path], anchor) for path, anchor in functions)
        require(generated.count("PINNED_REGIONMAP_ENTRY_METHODS") == 1,
                "native method placeholder missing/duplicated")
        generated = generated.replace("PINNED_REGIONMAP_ENTRY_METHODS", bodies)
        source = directory / harness.name
        source.write_text(generated, encoding="utf-8")
        moc = shutil.which("moc") or "/usr/lib/qt6/libexec/moc"
        moc_output = directory / "moc_regionmap_caller.cpp"
        subprocess.run([moc, str(source), "-o", str(moc_output)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        with source.open("a", encoding="utf-8") as file:
            file.write('\n#include "moc_regionmap_caller.cpp"\n')
        executable = directory / "regionmap-caller"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Widgets"], text=True
        ).split()
        compile_result = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-Wall", "-Wextra",
             str(source), "-o", str(executable), *flags],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        output = compile_result.stdout
        if compile_result.returncode:
            Path(log_path).write_text(output, encoding="utf-8")
            raise ValueError("native Qt compile failed; see " + str(log_path))
        environment = dict(__import__("os").environ)
        environment["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run([str(executable)], check=False, env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=30)
        output += result.stdout
        Path(log_path).write_text(output, encoding="utf-8")
        require(result.returncode == 0, "native Qt caller test failed; see " + str(log_path))
        return output


def verify_transcript(stdout):
    require("PHASE1_REGIONMAP_PROJECT_CALLER_FATAL" not in stdout,
            "native caller test fatal marker")
    lines = re.findall(r"^PHASE1_REGIONMAP_PROJECT_CALLER_RESULT (\{.*\})$", stdout, re.M)
    require(len(lines) == 1, "native caller result missing/duplicated")
    return verify_record(json.loads(lines[0]))


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
    sources, rows = verify_sources(args.porymap)
    no_overlap = verify_no_prior_inventory_overlap(repository_root)
    prior_hashes = verify_prior_dossiers(repository_root)
    source_contract = verify_source_contract(sources)
    source_rejections = source_negatives(sources)
    stdout = run_native(args.harness, sources, args.log)
    record = verify_transcript(stdout)
    evidence_rejections = evidence_negatives(record)
    make_archive(args.dossier, args.archive)

    result = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "porymap_pin": PIN,
        "fire_red_pin_unchanged_not_exercised":
            "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
        "poryscript_pin_unchanged_not_exercised":
            "c32481161c767b25a3425fa9f1f8729927ff3d55",
        "new_file_rows": rows[:len(NEW_FILES)],
        "reused_context_rows": rows[len(NEW_FILES):],
        "source_contract": source_contract,
        "overlap_check": no_overlap,
        "prior_dossier_sha256": prior_hashes,
        "native_result": record,
        "source_mutations_rejected": source_rejections,
        "evidence_mutations_rejected": evidence_rejections,
        "new_dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "dossier_archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "archive_contents": [args.dossier.name],
        "archive_excludes_upstream_source": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PORYMAP_REGIONMAP_PROJECT_CALLER_PASS "
          f"new_files={len(NEW_FILES)} source_negatives={source_rejections} "
          f"evidence_negatives={evidence_rejections} gate=FAIL_INCOMPLETE approvals=0")
    print(json.dumps({
        "dossier_sha256": result["new_dossier_sha256"],
        "archive_sha256": result["dossier_archive_sha256"],
        "archive": result["archive_contents"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()

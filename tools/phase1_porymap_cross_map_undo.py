#!/usr/bin/env python3
"""Verify pinned Porymap cross-map connection undo and dirty-state boundaries."""
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

NEW_FILES = {
    "include/core/editcommands.h": (
        "5dc4bf0cd2092251ed705daa95cde369815aa4f8",
        "bc164f827a58b5ef2230a28591e85439ac0f6ff2e500734a7394604b4f6e3898",
        "Whole-file command identifiers, merge contracts, and connection command state",
    ),
    "src/ui/connectionpixmapitem.cpp": (
        "db05ffabdf817a376b78da1bb02b4ad037ae4e02",
        "3893fe1719300fa1e3ef2c1c112dd2859081ce19eb95927378f32c4c0b33d029",
        "Whole-file map-canvas producer, offset grid snapping, and drag action grouping",
    ),
    "include/ui/connectionpixmapitem.h": (
        "5106ba8fa0fdf91f8f1f1a45e06cf549da45bd31",
        "192e15752b7bb2630a93beec13ec838c131c9f845a1a27b3ffa4b1af240586fb",
        "Whole-file canvas item state, QPointer connection identity, and event interface",
    ),
    "src/ui/connectionslistitem.cpp": (
        "b773f752f678454fbde055884d30a14310fc32f4",
        "202695abe78881be8592d8d6e5aa2157592e7d07963388e77c91180327e6ec72",
        "Whole-file list-editor producers, validation, UI synchronization, and action IDs",
    ),
    "include/ui/connectionslistitem.h": (
        "1b9713cf45ef6643928e228327ee95af83937147",
        "cc93d862ac0a8ca8d72f609bf8b4d543c4252732ee60d08b4d6f8efdad0438b7",
        "Whole-file list item state, shared connection pointer, and command slots",
    ),
}
NEW_FILE_DETAILS = {
    "include/core/editcommands.h": {
        "caller_edges": ["src/ui/connectionpixmapitem.cpp", "src/ui/connectionslistitem.cpp"],
        "consumer_edges": ["src/core/editcommands.cpp", "src/core/map.cpp"],
        "objections": ["direction-masked command IDs are not matched by Map::pruneEditHistory base IDs"],
        "untraced_dependencies": ["full Editor QUndoGroup switching", "Qt command destruction across project close"],
    },
    "src/ui/connectionpixmapitem.cpp": {
        "caller_edges": ["Editor connection display/selection path (reused src/editor.cpp)"],
        "consumer_edges": ["Map::commit", "MapConnectionMove", "MapConnection offsetChanged"],
        "objections": ["drag commits to the connection's parent-map stack; actual GUI delivery was not tested"],
        "untraced_dependencies": ["QGraphicsScene drag event ordering", "render/cache behavior"],
    },
    "include/ui/connectionpixmapitem.h": {
        "caller_edges": ["Editor connection item creation (reused src/editor.cpp)"],
        "consumer_edges": ["src/ui/connectionpixmapitem.cpp", "MapConnection signals"],
        "objections": ["raw command pointer safety relies on Map ownership and history lifetime"],
        "untraced_dependencies": ["full graphics-scene teardown ordering"],
    },
    "src/ui/connectionslistitem.cpp": {
        "caller_edges": ["Editor connections panel construction (reused src/editor.cpp)"],
        "consumer_edges": ["Map::commit", "MapConnectionChangeDirection", "MapConnectionChangeMap",
                           "MapConnectionMove", "MapConnectionRemove"],
        "objections": ["map-name membership and edit-finish action grouping are source-checked, not interacted with in GUI"],
        "untraced_dependencies": ["generated Ui::ConnectionsListItem widget behavior", "signal timing during map switching"],
    },
    "include/ui/connectionslistitem.h": {
        "caller_edges": ["Editor connections panel construction (reused src/editor.cpp)"],
        "consumer_edges": ["src/ui/connectionslistitem.cpp", "MapConnection QPointer"],
        "objections": ["connection lifetime is guarded by QPointer but parent Map remains a raw pointer"],
        "untraced_dependencies": ["widget destruction and asynchronous signal delivery"],
    },
}
FILE_LICENSE_NOTICE = re.compile(
    r"(?im)^\s*(?://|/\*|\*|#)\s*(?:SPDX-License-Identifier:|Copyright\b|Licensed under\b)"
)

CONTEXT_FILES = {
    "src/core/editcommands.cpp": (
        "684d98c7ea8b2c600a5fb8888831b95723e741f3",
        "9d1485666ee84ab2890e911321e1136aff78b703e905d465880c782c16e68de3",
        "Reused context: hash/mirror preference appeared in prior mapgroups source inventory; command bodies are the new focused dependency",
    ),
    "src/core/mapconnection.cpp": (
        "d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4",
        "ce81c7c747e5403a2b2988cb64ffae6834c2389c7a27fa004cb2e54e4eb0fa03",
        "Reused context: mirror matching, setters, and modified-signal emission; referenced by earlier packet",
    ),
    "include/core/mapconnection.h": (
        "40713d3a26157fce7a36465858e8273c78dc12f6",
        "0e00c9b0ba5319838ba1457ceef3f60fd718e9b0a68f152710173b94998a1a03",
        "Reused context: model API appeared in prior mapgroups and connection-fill inventories",
    ),
    "src/core/map.cpp": (
        "47b279919bd4afcc76b88f9eeecd459b3452989f",
        "c2406bb2dd5950ee226a4e7fc8e1d198c70915cb638fd706a814b87de22ab332",
        "Reused context: connection ownership, dirty-state, and edit-history pruning",
    ),
    "include/core/map.h": (
        "47d52b08e4a403e88c80c0d436f563460721e65d",
        "560599fe48fcf3873af116d133b7c5160a19cd9a3196d6e5ce796172c2bef23b",
        "Reused context: Map dirty flags, QUndoStack, connection, and pruning interfaces",
    ),
    "src/project.cpp": (
        "d43b0949303433111d4478ad76117c2b3445dd13",
        "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
        "Reused context: load notification, map JSON save boundary, and project dirty aggregation",
    ),
    "include/project.h": (
        "50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354",
        "7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51",
        "Reused context: Project map-loaded signal, map registry, and save interfaces",
    ),
    "src/editor.cpp": (
        "34112f6355b13d9381de7188624c36e5efeba151",
        "a505ba77243efdcaa2da8cce448e97ce80aa355145fb567290cb6d549bead270",
        "Reused context: current-map save routing, active stack ownership, and map-switch pruning call",
    ),
    "include/editor.h": (
        "3842743d5a671633a494ce1a364a1f0677e6bb94",
        "a93a68d6739526da2be0806c9caf97667414a8e3244704be90938bb0525f652e",
        "Reused context: Editor map, project, layout, and QUndoGroup interfaces",
    ),
    "src/mainwindow.cpp": (
        "08ce1a7a599ef825967717b69626984cdc6d772b",
        "b1b7d6738bfa9a3c574ddfcdd774187783fa81cfc86889e1aa4b80cad93525d1",
        "Reused context: mapLoaded wiring and modified-signal propagation to unsaved map state",
    ),
}

LICENSE_BLOB = "65c5ca88a67c30becee01c5a8816d964b03862f9"
LICENSE_SHA256 = "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"
PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-full-qt-project-roundtrip-20261028.md":
        "b143b4f44d879851b724deb21c567426ebf2355cd6ef2ea22dec521c8910d680",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "e00c5431a19b9d9e5a66d70b8dd3a817e5ea25a0307de7be8618e1cf2226af87",
    "docs/phase1-review-readiness/porymap-regionmap-project-caller-20261105.md":
        "23028d438e707ea2a12a5dfaf19843ac44b06e13fcb22053a9f908ee6c918764",
    "docs/phase1-review-readiness/porymap-regionmap-project-save-failure-closure-20261106.md":
        "4ab40ca799cb25453d19f2c5004c3cc3dbe0a29d383a151196a10727bec2a32c",
}
PRIOR_INVENTORY_TOOLS = {
    "tools/phase1_porymap_mapgroups_roundtrip.py":
        "0e91d2fe15d83accbf53b6ff583fe7d130d9af79412f20d49301c19d92296500",
    "tools/verify_firered_connection_fill_geometry.py":
        "9d0ce4b23a44e22c568817c69c3cd6b342dc8b87d8d66f3a590bf843e2631761",
}

PR36_CHANGED_FILES = {
    ".github/workflows/copilot-poryscript-abi-review.yml",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/closure-review.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/file-inspection-followup.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/fire-red-script-dispatch-followup.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/map-header-review-followup.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/poryscript-firered-abi-followup.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/review.json",
    "semantic-snapshots/independent-reviews/copilot-poryscript-abi/review.md",
    "tests/test_copilot_poryscript_abi_review.py",
    "tools/copilot_poryscript_abi_review.py",
    "tools/copilot_poryscript_abi_review_probes.py",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def extract(source, anchor):
    return caller.extract(source, anchor)


def extract_class(source, anchor):
    require(source.count(anchor) == 1, "pinned class anchor missing/duplicated: " + anchor)
    start = source.index(anchor)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                end = source.find(";", index)
                require(end >= 0, "pinned class declaration unterminated: " + anchor)
                return source[start:end + 1]
    raise ValueError("pinned class declaration unterminated: " + anchor)


def extract_statement(source, anchor):
    require(source.count(anchor) == 1, "pinned statement missing/duplicated: " + anchor)
    start = source.index(anchor)
    end = source.index(";", start)
    return source[start:end + 1]


def git_blob_sha1(data):
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def verify_source_identity_bytes(path, data, expected_blob, expected_sha256):
    require(git_blob_sha1(data) == expected_blob,
            "Porymap Git blob mismatch: " + path)
    require(hashlib.sha256(data).hexdigest() == expected_sha256,
            "Porymap byte hash mismatch: " + path)


def verify_sources(root):
    require(git(root, "rev-parse", "HEAD") == PIN, "Porymap commit pin changed")
    sources = {}
    rows = []
    for path, (blob, digest, role) in {**NEW_FILES, **CONTEXT_FILES}.items():
        data = (root / path).read_bytes()
        verify_source_identity_bytes(path, data, blob, digest)
        require(git(root, "hash-object", path) == blob,
                "Porymap worktree Git blob mismatch: " + path)
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
            "whole_file_source_read": is_new,
            "semantic_scope": ("complete pinned file selected; subsystem obligations remain NEEDS_EVIDENCE"
                               if is_new else "reused dependency context; not counted as a new whole-file review"),
            "caller_edges": NEW_FILE_DETAILS[path]["caller_edges"] if is_new else [],
            "consumer_edges": NEW_FILE_DETAILS[path]["consumer_edges"] if is_new else [],
            "objections": NEW_FILE_DETAILS[path]["objections"] if is_new else [],
            "untraced_dependencies":
                NEW_FILE_DETAILS[path]["untraced_dependencies"] if is_new else [],
            "full_semantic_disposition": "NEEDS_EVIDENCE",
            "license": "Porymap root LICENSE.md, LGPL-3.0 text; not a redistribution determination",
            "file_specific_license_notice": bool(FILE_LICENSE_NOTICE.search(sources[path])),
            "original_dossier_row_sha256": None,
            "original_dossier_archive_sha256": None,
            "original_dossier_status":
                "NEEDS_EVIDENCE: no prior per-file dossier row/archive was available",
            "disposition": "NEEDS_EVIDENCE",
        }
        row["new_dossier_row_sha256"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        rows.append(row)

    notice_files = [path for path, source in sources.items()
                    if path in NEW_FILES and FILE_LICENSE_NOTICE.search(source)]
    require(not notice_files, "unexpected file-specific license notice: " + ", ".join(notice_files))
    license_bytes = (root / "LICENSE.md").read_bytes()
    require(git(root, "hash-object", "LICENSE.md") == LICENSE_BLOB,
            "Porymap license blob mismatch")
    require(hashlib.sha256(license_bytes).hexdigest() == LICENSE_SHA256,
            "Porymap license byte hash mismatch")
    return sources, rows


def source_identity_negatives(sources):
    rejected = 0
    for path, (blob, digest, _) in NEW_FILES.items():
        changed = sources[path].encode("utf-8") + b"\n"
        changed_blob = git_blob_sha1(changed)
        changed_digest = hashlib.sha256(changed).hexdigest()
        for expected_blob, expected_digest in (
            (blob, changed_digest),
            (changed_blob, digest),
        ):
            try:
                verify_source_identity_bytes(path, changed, expected_blob, expected_digest)
            except ValueError:
                rejected += 1
            else:
                raise ValueError("stale source identity escaped: " + path)
    return rejected


def verify_inventory_rows(rows, license_evidence):
    expected = set(NEW_FILES) | set(CONTEXT_FILES)
    require(len(rows) == len(expected)
            and {row["path"] for row in rows} == expected,
            "per-file inventory path/count mismatch")
    for row in rows:
        require(row["pinned_commit"] == PIN
                and row["disposition"] == "NEEDS_EVIDENCE"
                and row["full_semantic_disposition"] == "NEEDS_EVIDENCE"
                and row["license"]
                and not row["file_specific_license_notice"]
                and row["original_dossier_row_sha256"] is None
                and row["original_dossier_archive_sha256"] is None,
                "per-file pin/license/approval/receipt omission: " + row["path"])
        if row["row_kind"] == "new_complete_source":
            require(row["whole_file_source_read"]
                    and row["caller_edges"] and row["consumer_edges"]
                    and row["objections"] and row["untraced_dependencies"],
                    "per-file closure/objection record incomplete: " + row["path"])
        row_without_digest = dict(row)
        digest = row_without_digest.pop("new_dossier_row_sha256")
        require(hashlib.sha256(json.dumps(
            row_without_digest, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest() == digest,
                "new dossier row hash mismatch: " + row["path"])
    require(license_evidence["git_blob_sha1"] == LICENSE_BLOB
            and license_evidence["source_sha256"] == LICENSE_SHA256
            and "LGPL-3.0" in license_evidence["finding"],
            "pinned license evidence missing or changed")


def inventory_negatives(rows, license_evidence):
    rejected = 0
    mutations = (
        ("license", ""),
        ("disposition", "PASSED"),
        ("full_semantic_disposition", "COPILOT_REVIEWED"),
        ("git_blob_sha1", "0" * 40),
        ("original_dossier_archive_sha256", "0" * 64),
        ("objections", []),
        ("caller_edges", []),
    )
    for key, value in mutations:
        changed = [dict(row) for row in rows]
        changed[0][key] = value
        try:
            verify_inventory_rows(changed, license_evidence)
        except (ValueError, KeyError):
            rejected += 1
        else:
            raise ValueError("inventory mutation escaped: " + key)
    return rejected


def verify_prior_inventory_overlap(repository_root):
    tool = Path(__file__).resolve()
    dossier = (repository_root
               / "docs/phase1-review-readiness/porymap-cross-map-undo-boundary-20261106.md").resolve()
    candidates = []
    for folder in (repository_root / "tools",
                   repository_root / "docs/phase1-review-readiness"):
        candidates.extend(path for path in folder.rglob("*")
                          if path.is_file() and path.suffix in {".py", ".md"}
                          and path.resolve() not in {tool, dossier})
    for path in NEW_FILES:
        matches = [str(candidate) for candidate in candidates
                   if path in candidate.read_text(errors="replace")]
        require(not matches, "new source path already appears in a prior inventory: "
                + path + ": " + ", ".join(matches[:3]))
    require(not set(NEW_FILES).intersection(PR36_CHANGED_FILES),
            "new source overlaps PR #36 changed-file inventory")
    return {
        "scanned_tools_and_readiness_dossiers": len(candidates),
        "prior_inventory_path_matches": 0,
        "pr36_changed_file_matches": 0,
        "new_complete_files": sorted(NEW_FILES),
        "reused_context_source_paths_previously_referenced": [
            "src/core/editcommands.cpp",
            "src/core/mapconnection.cpp",
            "include/core/mapconnection.h",
        ],
    }


def verify_prior_dossiers(repository_root):
    actual = {}
    for path, digest in PRIOR_DOSSIERS.items():
        file_path = repository_root / path
        require(file_path.is_file(), "prior context dossier missing: " + path)
        actual[path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        require(actual[path] == digest, "prior context dossier hash drift: " + path)
    return actual


def verify_prior_inventory_tools(repository_root):
    actual = {}
    for path, digest in PRIOR_INVENTORY_TOOLS.items():
        file_path = repository_root / path
        require(file_path.is_file(), "prior inventory tool missing: " + path)
        actual[path] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        require(actual[path] == digest, "prior inventory tool hash drift: " + path)
    return actual


def verify_source_contract(sources):
    commands = sources["src/core/editcommands.cpp"]
    command_header = sources["include/core/editcommands.h"]
    connection_header = sources["include/core/mapconnection.h"]
    pixmap = sources["src/ui/connectionpixmapitem.cpp"]
    list_item = sources["src/ui/connectionslistitem.cpp"]
    map_source = sources["src/core/map.cpp"]
    map_header = sources["include/core/map.h"]
    project = sources["src/project.cpp"]
    editor = sources["src/editor.cpp"]
    mainwindow = sources["src/mainwindow.cpp"]
    connection_source = sources["src/core/mapconnection.cpp"]

    move_id = extract(commands, "int MapConnectionMove::id() const")
    direction_id = extract(commands, "int MapConnectionChangeDirection::id() const")
    change_map_id = extract(commands, "int MapConnectionChangeMap::id() const")
    add_id = extract(commands, "int MapConnectionAdd::id() const")
    remove_id = extract(commands, "int MapConnectionRemove::id() const")
    prune = extract(map_source, "void Map::pruneEditHistory()")
    modify = extract(map_source, "void Map::modify()")
    has_unsaved = extract(map_source, "bool Map::hasUnsavedChanges() const")
    map_clean = extract(map_source, "void Map::setClean()")
    map_commit = extract(map_source, "void Map::commit(")
    set_offset = extract(connection_source, "void MapConnection::setOffset(")
    set_direction = extract(connection_source, "void MapConnection::setDirection(")
    set_target = extract(connection_source, "void MapConnection::setTargetMapName(")
    parent_map = extract(connection_source, "void MapConnection::setParentMap(")
    are_mirrored = extract(connection_source, "bool MapConnection::areMirrored(")
    find_mirror = extract(connection_source, "MapConnection* MapConnection::findMirror()")
    add = extract(commands, "MapConnectionAdd::MapConnectionAdd(")
    add_redo = extract(commands, "void MapConnectionAdd::redo()")
    add_undo = extract(commands, "void MapConnectionAdd::undo()")
    remove = extract(commands, "MapConnectionRemove::MapConnectionRemove(")
    remove_redo = extract(commands, "void MapConnectionRemove::redo()")
    remove_undo = extract(commands, "void MapConnectionRemove::undo()")
    move_redo = extract(commands, "void MapConnectionMove::redo()")
    move_undo = extract(commands, "void MapConnectionMove::undo()")
    move_merge = extract(commands, "bool MapConnectionMove::mergeWith(")
    direction_redo = extract(commands, "void MapConnectionChangeDirection::redo()")
    direction_undo = extract(commands, "void MapConnectionChangeDirection::undo()")
    map_redo = extract(commands, "void MapConnectionChangeMap::redo()")
    map_undo = extract(commands, "void MapConnectionChangeMap::undo()")

    require(all("getConnectionDirectionMask" in body for body in
                (move_id, direction_id, change_map_id, add_id, remove_id)),
            "connection command IDs no longer include direction masks")
    require("mapConnectionIds.contains(command->id())" in prune
            and "getConnectionDirectionMask" not in prune
            and "command->id() &" not in prune,
            "observed direction-mask/pruning mismatch changed")
    require(all(f"ID_MapConnection{name}" in prune for name in
                ("Move", "ChangeDirection", "ChangeMap", "Add", "Remove")),
            "Map prune target list changed")
    require("this->connection->setOffset(this->newOffset, this->mirrored);" in move_redo
            and "this->connection->setOffset(this->oldOffset, this->mirrored);" in move_undo,
            "move command mirror undo/redo changed")
    require("this->actionId != other->actionId" in move_merge
            and "this->connection != other->connection" in move_merge,
            "move command merge identity changed")
    require("this->connection->setDirection(this->newDirection, this->mirrored);" in direction_redo
            and "this->connection->setOffset(this->newOffset, this->mirrored);" in direction_redo
            and "this->connection->setDirection(this->oldDirection, this->mirrored);" in direction_undo,
            "direction command cross-map undo/redo changed")
    require("setTargetMapName(this->newMapName, this->mirrored)" in map_redo
            and "setTargetMapName(this->oldMapName, this->mirrored)" in map_undo,
            "target-map command cross-map undo/redo changed")
    require("this->connection->setParentMap(this->map, false);" in add
            and "this->connection->createMirror()" in add
            and "this->mirrorMap->addConnection(this->mirror);" in add_redo
            and "this->mirrorMap->removeConnection(this->mirror);" in add_undo,
            "add command mirror lifecycle changed")
    require("findMirror()" in remove and "this->mirrorMap->removeConnection(this->mirror);" in remove_redo
            and "this->mirrorMap->addConnection(this->mirror);" in remove_undo,
            "remove command mirror lifecycle changed")
    require("connection->setOffset(-offset, false);" in set_offset
            and "markMapEdited();" in set_offset
            and "connection->setDirection(oppositeDirection(direction), false);" in set_direction
            and "connection->setParentMap(getMap(targetMapName), false);" in set_target,
            "MapConnection mirror setters changed")
    require("a->parentMapName() == b->m_targetMapName" in are_mirrored
            and "a->m_offset == -b->m_offset" in are_mirrored
            and "auto map = targetMap();" in find_mirror
            and "areMirrored(this, connection)" in find_mirror,
            "mirror matching identity changed")
    require("emit modified();" in modify
            and "map->setHasUnsavedDataChanges(true);" in
            extract(mainwindow, "void MainWindow::markMapEdited(")
            and "&Map::modified" in extract(mainwindow, "void MainWindow::onMapLoaded("),
            "modified-signal to unsaved-map propagation changed")
    require("m_hasUnsavedDataChanges" in has_unsaved
            and "m_editHistory->isClean()" in has_unsaved
            and "m_editHistory->setClean();" in map_clean
            and "m_hasUnsavedDataChanges = false;" in map_clean
            and "m_editHistory->push(cmd);" in map_commit,
            "Map dirty state or QUndoStack ownership changed")
    require("this->map->pruneEditHistory();" in extract(editor, "void Editor::unsetMap()")
            and "editGroup.setActiveStack(map->editHistory());" in extract(editor, "bool Editor::setMap("),
            "per-map undo stack switch/prune wiring changed")
    require("connect(project, &Project::mapLoaded, this, &MainWindow::onMapLoaded);" in mainwindow
            and "emit mapLoaded(map);" in extract(project, "Map* Project::loadMap("),
            "loaded-map modified-signal hookup changed")
    current_save = extract(editor, "bool Editor::save(bool currentOnly)")
    project_save = extract(project, "bool Project::saveMap(")
    save_all = extract(project, "bool Project::saveAll()")
    require("this->project->saveMap(this->map)" in current_save
            and "this->project->saveAll()" in current_save,
            "Editor current/all save routing changed")
    require("map->getConnections()" in project_save
            and 'mapObj["connections"] = connectionsArr;' in project_save
            and "map->setClean();" in project_save,
            "Project per-map connection serialization/clean ordering changed")
    require("for (auto map : this->maps)" in save_all
            and "saveMap(map, true)" in save_all,
            "Project Save All map iteration changed")
    require("this->connection->parentMap()->commit(new MapConnectionMove" in extract(
                pixmap, "QVariant ConnectionPixmapItem::itemChange(")
            and "newOffset != this->connection->offset()" in extract(
                pixmap, "QVariant ConnectionPixmapItem::itemChange("),
            "canvas drag producer changed")
    require("this->map->commit(new MapConnectionChangeDirection" in extract(
                list_item, "void ConnectionsListItem::commitDirection()")
            and "this->map->commit(new MapConnectionChangeMap" in extract(
                list_item, "void ConnectionsListItem::commitMap(")
            and "this->map->commit(new MapConnectionMove" in extract(
                list_item, "void ConnectionsListItem::commitMove(")
            and "this->map->commit(new MapConnectionRemove" in extract(
                list_item, "void ConnectionsListItem::commitRemove("),
            "list-editor command producers changed")
    require("QPointer<MapConnection> connection;" in command_header
            and "MapConnection *connection;" in command_header
            and "void setOffset(int offset, bool mirror = true);" in connection_header,
            "command/model pointer ownership interface changed")

    return {
        "direction_masked_connection_command_ids": True,
        "prune_compares_masked_ids_to_unmasked_bases": True,
        "mirror_modified_signal_marks_target_unsaved": True,
        "current_save_routes_to_active_map_only": True,
        "save_all_routes_through_all_loaded_maps": True,
        "pinned_project_connection_serialization_source_checked": True,
        "full_gui_and_disk_save_not_claimed": True,
        "new_complete_source_files": len(NEW_FILES),
    }


def source_negatives(sources):
    probes = [
        ("src/core/map.cpp", "void Map::pruneEditHistory()",
         "mapConnectionIds.contains(command->id())",
         "mapConnectionIds.contains(command->id() & 0xFF)"),
        ("src/core/editcommands.cpp", "int MapConnectionMove::id() const",
         "return CommandId::ID_MapConnectionMove | getConnectionDirectionMask({this->connection->direction()});",
         "return CommandId::ID_MapConnectionMove;"),
        ("src/core/editcommands.cpp", "void MapConnectionMove::redo()",
         "setOffset(this->newOffset, this->mirrored)", "setOffset(this->newOffset, false)"),
        ("src/core/editcommands.cpp", "bool MapConnectionMove::mergeWith(",
         "this->actionId != other->actionId", "this->actionId == other->actionId"),
        ("src/core/editcommands.cpp", "void MapConnectionChangeDirection::redo()",
         "setDirection(this->newDirection, this->mirrored)",
         "setDirection(this->newDirection, false)"),
        ("src/core/editcommands.cpp", "void MapConnectionChangeMap::redo()",
         "setTargetMapName(this->newMapName, this->mirrored)",
         "setTargetMapName(this->newMapName, false)"),
        ("src/core/editcommands.cpp", "void MapConnectionAdd::redo()",
         "this->mirrorMap->addConnection(this->mirror);",
         "this->mirrorMap->removeConnection(this->mirror);"),
        ("src/core/editcommands.cpp", "void MapConnectionRemove::undo()",
         "this->mirrorMap->addConnection(this->mirror);",
         "this->mirrorMap->removeConnection(this->mirror);"),
        ("src/core/mapconnection.cpp", "void MapConnection::setOffset(",
         "connection->setOffset(-offset, false);", "connection->setOffset(offset, false);"),
        ("src/mainwindow.cpp", "void MainWindow::markMapEdited(",
         "map->setHasUnsavedDataChanges(true);", "map->setHasUnsavedDataChanges(false);"),
        ("src/editor.cpp", "void Editor::unsetMap()",
         "this->map->pruneEditHistory();", "this->map->setClean();"),
        ("src/editor.cpp", "bool Editor::save(bool currentOnly)",
         "this->project->saveMap(this->map);", "this->project->saveAll();"),
        ("src/project.cpp", "bool Project::saveAll()",
         "for (auto map : this->maps)", "for (auto map : this->mapLayouts)"),
    ]
    rejected = 0
    for path, anchor, original, mutated in probes:
        body = extract(sources[path], anchor)
        require(original in body, "source mutation probe missing: " + anchor)
        altered = dict(sources)
        altered[path] = sources[path].replace(body, body.replace(original, mutated, 1), 1)
        try:
            verify_source_contract(altered)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + anchor)
    return rejected


def verify_record(record):
    expected_true = (
        "pinned_original_method_bodies", "native_qt_qundo_stack",
        "test_only_project_and_ui_shells", "original_mainwindow_dirty_handlers_called",
        "mirrored_dirty_state_observed_on_both_maps",
        "original_editor_current_save_routing_called", "current_save_left_mirror_map_dirty",
        "masked_command_remained_nonobsolete", "stale_stack_undo_overwrote_cross_map_edit",
        "second_stack_undo_restored_recorded_value", "direction_and_map_change_undo_redo",
        "add_remove_mirror_lifecycle_undo_redo",
    )
    expected_false = (
        "actual_project_map_json_write_tested", "actual_project_save_all_tested",
        "actual_gui_interaction_tested", "cold_project_reopen_tested",
        "stock_gameplay_tested", "hardware_durability_tested",
    )
    require(record["phase1_gate"] == "FAIL_INCOMPLETE"
            and record["independent_approvals"] == 0,
            "gate or approval overclaim")
    require(all(record.get(key) is True for key in expected_true),
            "required native result missing")
    require(all(record.get(key) is False for key in expected_false),
            "evidence scope overclaim")
    require(record["map_a_modified_signal_count"] > 0
            and record["map_b_modified_signal_count"] > 0,
            "cross-map modified signal was not observed")
    require(set(record) == {
        "phase1_gate", "independent_approvals", "pinned_original_method_bodies",
        "native_qt_qundo_stack", "test_only_project_and_ui_shells",
        "original_mainwindow_dirty_handlers_called",
        "mirrored_dirty_state_observed_on_both_maps",
        "original_editor_current_save_routing_called",
        "current_save_left_mirror_map_dirty",
        "masked_command_remained_nonobsolete",
        "stale_stack_undo_overwrote_cross_map_edit",
        "second_stack_undo_restored_recorded_value",
        "direction_and_map_change_undo_redo",
        "add_remove_mirror_lifecycle_undo_redo",
        "map_a_modified_signal_count", "map_b_modified_signal_count",
        "actual_project_map_json_write_tested", "actual_project_save_all_tested",
        "actual_gui_interaction_tested", "cold_project_reopen_tested",
        "stock_gameplay_tested", "hardware_durability_tested",
    }, "native result fields changed")
    return record


def evidence_negatives(record):
    mutations = (
        ("phase1_gate", "PASS"),
        ("independent_approvals", 1),
        ("native_qt_qundo_stack", False),
        ("test_only_project_and_ui_shells", False),
        ("masked_command_remained_nonobsolete", False),
        ("stale_stack_undo_overwrote_cross_map_edit", False),
        ("current_save_left_mirror_map_dirty", False),
        ("actual_project_map_json_write_tested", True),
        ("actual_project_save_all_tested", True),
        ("original_mainwindow_dirty_handlers_called", False),
        ("actual_gui_interaction_tested", True),
        ("cold_project_reopen_tested", True),
        ("stock_gameplay_tested", True),
        ("map_b_modified_signal_count", 0),
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


def pinned_functions(sources):
    map_connection = sources["src/core/mapconnection.cpp"]
    commands = sources["src/core/editcommands.cpp"]
    map_source = sources["src/core/map.cpp"]
    mainwindow = sources["src/mainwindow.cpp"]
    editor = sources["src/editor.cpp"]
    project = sources["src/project.cpp"]

    connection_methods = [
        extract_statement(map_connection, "QPointer<Project> MapConnection::project"),
        extract_statement(map_connection, "const QMap<QString, QString> MapConnection::oppositeDirections"),
        extract_statement(map_connection, "const QStringList MapConnection::cardinalDirections"),
    ]
    connection_methods.extend(extract(map_connection, anchor) for anchor in (
        "MapConnection::MapConnection(",
        "bool MapConnection::areMirrored(",
        "MapConnection* MapConnection::findMirror()",
        "MapConnection * MapConnection::createMirror()",
        "void MapConnection::markMapEdited()",
        "Map* MapConnection::getMap(",
        "Map* MapConnection::targetMap()",
        "void MapConnection::setParentMap(",
        "QString MapConnection::parentMapName()",
        "void MapConnection::setTargetMapName(",
        "void MapConnection::setDirection(",
        "void MapConnection::setOffset(",
        "bool MapConnection::isCardinal(",
        "bool MapConnection::isHorizontal(",
        "bool MapConnection::isVertical(",
        "bool MapConnection::isDiving(",
    ))
    map_methods = [extract(map_source, anchor) for anchor in (
        "void Map::addConnection(",
        "void Map::loadConnection(",
        "void Map::trackConnection(",
        "void Map::removeConnection(",
        "void Map::commit(",
        "void Map::modify()",
        "void Map::setClean()",
        "bool Map::hasUnsavedChanges() const",
        "void Map::pruneEditHistory()",
    )]
    edit_methods = [
        extract(commands, "int getConnectionDirectionMask("),
    ]
    edit_methods.extend(extract(commands, anchor) for anchor in (
        "MapConnectionMove::MapConnectionMove(",
        "void MapConnectionMove::redo()",
        "void MapConnectionMove::undo()",
        "bool MapConnectionMove::mergeWith(",
        "int MapConnectionMove::id() const",
        "MapConnectionChangeDirection::MapConnectionChangeDirection(",
        "void MapConnectionChangeDirection::redo()",
        "void MapConnectionChangeDirection::undo()",
        "int MapConnectionChangeDirection::id() const",
        "MapConnectionChangeMap::MapConnectionChangeMap(",
        "void MapConnectionChangeMap::redo()",
        "void MapConnectionChangeMap::undo()",
        "int MapConnectionChangeMap::id() const",
        "MapConnectionAdd::MapConnectionAdd(",
        "void MapConnectionAdd::redo()",
        "void MapConnectionAdd::undo()",
        "int MapConnectionAdd::id() const",
        "MapConnectionRemove::MapConnectionRemove(",
        "void MapConnectionRemove::redo()",
        "void MapConnectionRemove::undo()",
        "int MapConnectionRemove::id() const",
    ))
    mainwindow_methods = [
        extract(mainwindow, "void MainWindow::markMapEdited("),
        extract(mainwindow, "void MainWindow::onMapLoaded("),
    ]
    return {
        "PROJECT_LOAD_MAP_TEST_STUB": (
            "Map *Project::loadMap(const QString &name) { "
            "Map *map = maps.value(name, nullptr); "
            "if (map && !loadedMaps.contains(name)) { "
            "loadedMaps.insert(name); emit mapLoaded(map); } return map; }"
        ),
        "PINNED_PROJECT_HAS_UNSAVED_CHANGES_METHOD":
            extract(project, "bool Project::hasUnsavedChanges()"),
        "PROJECT_SAVE_ROUTING_TEST_STUB": (
            "bool Project::saveMap(Map *map) { "
            "if (!map) return false; savedMaps.append(map); map->setClean(); return true; }"
        ),
        "PINNED_MAP_CONNECTION_METHODS": "\n\n".join(connection_methods),
        "PINNED_MAP_METHODS": "\n\n".join(map_methods),
        "PINNED_EDIT_COMMAND_METHODS": "\n\n".join(edit_methods),
        "PINNED_MAINWINDOW_METHODS": "\n\n".join(mainwindow_methods),
        "PINNED_EDITOR_SAVE_METHOD": extract(editor, "bool Editor::save(bool currentOnly)"),
    }


def command_header(source):
    start = source.index("enum CommandId {")
    end = source.index("/// Implements a command to commit metatile paint actions", start)
    identifiers = source[start:end]
    classes = "\n\n".join(extract_class(source, "class " + name + " : public QUndoCommand")
                            for name in (
        "MapConnectionMove", "MapConnectionChangeDirection", "MapConnectionChangeMap",
        "MapConnectionAdd", "MapConnectionRemove",
    ))
    return (
        "#pragma once\n#include <QPointer>\n#include <QUndoCommand>\n"
        "#include \"mapconnection.h\"\nclass Map;\n\n"
        + identifiers + classes + "\n"
    )


def run_native(harness, sources, log_path):
    generated = harness.read_text(encoding="utf-8")
    for token, value in pinned_functions(sources).items():
        require(generated.count(token) == 1, "native source placeholder missing/duplicated: " + token)
        generated = generated.replace(token, value)
    require(generated.count("PROJECT_SAVE_ROUTING_TEST_STUB") == 0
            and generated.count("PROJECT_LOAD_MAP_TEST_STUB") == 0,
            "project save test shell placeholder not replaced")
    with tempfile.TemporaryDirectory(prefix="phase1-cross-map-undo-") as directory_name:
        directory = Path(directory_name)
        source = directory / harness.name
        source.write_text(generated, encoding="utf-8")
        (directory / "mapconnection.h").write_text(
            "#include <QImage>\n#include <QPixmap>\n#include <QPoint>\n"
            "#include <QPointer>\n#include <QStringList>\n"
            + sources["include/core/mapconnection.h"],
            encoding="utf-8",
        )
        (directory / "editcommands.h").write_text(
            command_header(sources["include/core/editcommands.h"]), encoding="utf-8"
        )
        moc = shutil.which("moc") or "/usr/lib/qt6/libexec/moc"
        mapconnection_moc = directory / "moc_mapconnection.cpp"
        harness_moc = directory / "moc_cross_map_undo.cpp"
        subprocess.run([moc, str(directory / "mapconnection.h"), "-o", str(mapconnection_moc)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        subprocess.run([moc, str(source), "-o", str(harness_moc)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        executable = directory / "cross-map-undo"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Widgets"], text=True
        ).split()
        build = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-Wall", "-Wextra", "-I", str(directory),
             str(source), "-o", str(executable), *flags],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        if build.returncode:
            log_path.write_text(build.stdout, encoding="utf-8")
            raise ValueError("native Qt compile failed; see " + str(log_path))
        import os
        environment = dict(os.environ)
        result = subprocess.run([str(executable)], env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=45)
        log_path.write_text(build.stdout + result.stdout, encoding="utf-8")
        require(result.returncode == 0, "native cross-map undo test failed; see " + str(log_path))
        rows = re.findall(r"^PHASE1_CROSS_MAP_UNDO_RESULT (\{.*\})$", result.stdout, re.M)
        require(len(rows) == 1, "native cross-map result missing/duplicated")
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
    sources, rows = verify_sources(args.porymap)
    overlap = verify_prior_inventory_overlap(repository_root)
    prior_dossiers = verify_prior_dossiers(repository_root)
    prior_inventory_tools = verify_prior_inventory_tools(repository_root)
    license_evidence = {
        "path": "LICENSE.md",
        "git_blob_sha1": LICENSE_BLOB,
        "source_sha256": LICENSE_SHA256,
        "finding": "LGPL-3.0 text; not a redistribution determination",
        "file_specific_notices_found": False,
        "Qt_translations_exercised": False,
        "SQLite_exercised": False,
    }
    verify_inventory_rows(rows, license_evidence)
    identity_rejections = source_identity_negatives(sources)
    inventory_rejections = inventory_negatives(rows, license_evidence)
    source_contract = verify_source_contract(sources)
    source_rejections = source_negatives(sources)
    native_result = run_native(args.harness, sources, args.log)
    evidence_rejections = evidence_negatives(native_result)
    make_archive(args.dossier, args.archive)

    result = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "porymap_pin": PIN,
        "firered_pin_unchanged_not_exercised":
            "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
        "poryscript_pin_unchanged_not_exercised":
            "c32481161c767b25a3425fa9f1f8729927ff3d55",
        "license_evidence": license_evidence,
        "per_file_rows": rows,
        "prior_dossier_sha256": prior_dossiers,
        "prior_inventory_tool_sha256": prior_inventory_tools,
        "inventory_reconciliation": overlap,
        "source_contract": source_contract,
        "source_mutations_rejected": source_rejections,
        "source_identity_mutations_rejected": identity_rejections,
        "inventory_mutations_rejected": inventory_rejections,
        "native_result": native_result,
        "evidence_mutations_rejected": evidence_rejections,
        "dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "archive_contents": [args.dossier.name],
        "archive_excludes_upstream_source": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PORYMAP_CROSS_MAP_UNDO_PASS "
          f"new_sources={len(NEW_FILES)} source_mutations={source_rejections} "
          f"evidence_mutations={evidence_rejections} gate=FAIL_INCOMPLETE approvals=0")
    print(json.dumps({
        "dossier_sha256": result["dossier_sha256"],
        "archive_sha256": result["archive_sha256"],
        "archive": result["archive_contents"],
        "native_result": native_result,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

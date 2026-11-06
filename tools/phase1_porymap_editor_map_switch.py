#!/usr/bin/env python3
"""Verify pinned Porymap map-switch pruning through the native Qt undo group."""
import argparse
import hashlib
import importlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

base = importlib.import_module("phase1_porymap_cross_map_undo")
PIN = base.PIN

NEW_FILES = {
    "src/ui/newmapconnectiondialog.cpp": (
        "b9938f3e8af71b10935e27ab7be1687f17283b91",
        "51c96d5717ca5ca4ef1d9f92fd149977342257543d5a6cb81f47a9582f3f237b",
        "Whole dialog implementation: map/direction defaults, validation, replace routing, and add-signal producer",
    ),
    "include/ui/newmapconnectiondialog.h": (
        "db9eee49ff3fb976be7dc4454cdaac5b3cd7bd8f",
        "f7bdeca282eaf9956fc5cc43df819fffb3f08dc293537d9dda47c9e35b9c6d46",
        "Whole dialog interface: map pointer, accept override, and add/replace signals",
    ),
}
FILE_DETAILS = {
    "src/ui/newmapconnectiondialog.cpp": {
        "caller_edges": [
            "MainWindow::on_pushButton_AddConnection_clicked (reused src/mainwindow.cpp)",
            "NewMapConnectionDialog::accept emits newConnectionedAdded",
        ],
        "consumer_edges": [
            "Editor::addNewConnection (reused src/editor.cpp)",
            "Map::commit -> MapConnectionAdd::id -> Map::pruneEditHistory",
        ],
        "objections": [
            "custom direction text enters the command producer without native dialog interaction",
            "dialog acceptance does not itself persist the project",
        ],
        "untraced_dependencies": [
            "forms/newmapconnectiondialog.ui generated widget behavior",
            "actual GUI signal timing and validation interaction",
            "Project map loading and JSON serialization",
        ],
    },
    "include/ui/newmapconnectiondialog.h": {
        "caller_edges": ["MainWindow constructs NewMapConnectionDialog"],
        "consumer_edges": [
            "src/ui/newmapconnectiondialog.cpp",
            "MainWindow signal connections to Editor add/replace slots",
        ],
        "objections": [
            "m_map is a non-owning raw pointer whose lifetime depends on dialog ownership and map switching",
            "signals describe command requests, not successful persistence",
        ],
        "untraced_dependencies": [
            "actual dialog destruction during map changes",
            "generated Ui::NewMapConnectionDialog lifetime",
        ],
    },
}

LICENSE_BLOB = base.LICENSE_BLOB
LICENSE_SHA256 = base.LICENSE_SHA256
PRIOR_DOSSIER_SHA256 = "9ec765b5c6dbf22868987ec95a797525b905c8e3e97e4d7152bbfc48d56f1432"
PRIOR_ARCHIVE_SHA256 = "f05a398aeca729476c6ff4c7b1120f2672ab1c520982ab250ca4b4cd4d50f17f"
PRIOR_NATIVE_TOOL_SHA256 = "7d5825ef42caa5bb0cec86fb82db394c4cb1486054f018af9c3e1e08ef614d15"
PRIOR_NATIVE_HARNESS_SHA256 = "8d6e4e0febed139ec50d9bd2e807552c71a292385f24d2d3bf029914d9f7890e"
PRIOR_PACKET_TOOL = Path("tools/phase1_porymap_cross_map_undo.py")
PRIOR_PACKET_DOSSIER = Path(
    "docs/phase1-review-readiness/porymap-cross-map-undo-boundary-20261106.md"
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_new_sources(porymap):
    require(base.git(porymap, "rev-parse", "HEAD") == PIN,
            "Porymap commit pin changed")
    sources = {}
    rows = []
    for path, (blob, digest, role) in NEW_FILES.items():
        data = (porymap / path).read_bytes()
        base.verify_source_identity_bytes(path, data, blob, digest)
        require(base.git(porymap, "hash-object", path) == blob,
                "Porymap worktree blob mismatch: " + path)
        text = data.decode("utf-8")
        sources[path] = text
        row = {
            "repository": "huderlem/porymap",
            "path": path,
            "pinned_commit": PIN,
            "git_blob_sha1": blob,
            "source_sha256": digest,
            "bytes": len(data),
            "lines": len(data.splitlines()),
            "role": role,
            "row_kind": "new_complete_source",
            "whole_file_source_read": True,
            "semantic_scope": "complete pinned file selected; subsystem obligations remain NEEDS_EVIDENCE",
            "caller_edges": FILE_DETAILS[path]["caller_edges"],
            "consumer_edges": FILE_DETAILS[path]["consumer_edges"],
            "objections": FILE_DETAILS[path]["objections"],
            "untraced_dependencies": FILE_DETAILS[path]["untraced_dependencies"],
            "full_semantic_disposition": "NEEDS_EVIDENCE",
            "license": "Porymap root LICENSE.md, LGPL-3.0 text; not a redistribution determination",
            "file_specific_license_notice": bool(base.FILE_LICENSE_NOTICE.search(text)),
            "original_dossier_row_sha256": None,
            "original_dossier_archive_sha256": None,
            "original_dossier_status":
                "NEEDS_EVIDENCE: no prior per-file row/archive exists for this path",
            "disposition": "NEEDS_EVIDENCE",
        }
        row["new_dossier_row_sha256"] = hashlib.sha256(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        rows.append(row)
    require(not any(base.FILE_LICENSE_NOTICE.search(text) for text in sources.values()),
            "unexpected file-specific license notice")
    return sources, rows


def verify_inventory_rows(rows):
    require(len(rows) == len(NEW_FILES)
            and {row["path"] for row in rows} == set(NEW_FILES),
            "new source inventory path/count mismatch")
    for row in rows:
        expected_blob, expected_sha256, _ = NEW_FILES[row["path"]]
        require(row["pinned_commit"] == PIN
                and row["git_blob_sha1"] == expected_blob
                and row["source_sha256"] == expected_sha256
                and row["whole_file_source_read"]
                and row["disposition"] == "NEEDS_EVIDENCE"
                and row["full_semantic_disposition"] == "NEEDS_EVIDENCE"
                and "LGPL-3.0" in row["license"]
                and not row["file_specific_license_notice"]
                and row["original_dossier_row_sha256"] is None
                and row["original_dossier_archive_sha256"] is None
                and row["caller_edges"] and row["consumer_edges"]
                and row["objections"] and row["untraced_dependencies"],
                "per-file evidence/disposition missing: " + row["path"])
        unsigned = dict(row)
        row_digest = unsigned.pop("new_dossier_row_sha256")
        require(hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest() == row_digest,
                "per-file row digest mismatch: " + row["path"])


def inventory_negatives(rows):
    mutations = (
        ("license", ""),
        ("disposition", "PASSED"),
        ("full_semantic_disposition", "COPILOT_REVIEWED"),
        ("git_blob_sha1", "0" * 40),
        ("source_sha256", "0" * 64),
        ("path", "src/editor.cpp"),
        ("original_dossier_archive_sha256", "0" * 64),
        ("caller_edges", []),
    )
    rejected = 0
    for key, value in mutations:
        changed = [dict(row) for row in rows]
        changed[0][key] = value
        unsigned = dict(changed[0])
        unsigned.pop("new_dossier_row_sha256")
        changed[0]["new_dossier_row_sha256"] = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        try:
            verify_inventory_rows(changed)
        except (ValueError, KeyError):
            rejected += 1
        else:
            raise ValueError("inventory mutation accepted: " + key)
    return rejected


def verify_inventory_overlap(repository_root):
    tool = Path(__file__).resolve()
    dossier = (repository_root
               / "docs/phase1-review-readiness/porymap-editor-map-switch-20261106.md").resolve()
    candidates = []
    for folder in (repository_root / "tools",
                   repository_root / "docs/phase1-review-readiness"):
        candidates.extend(path for path in folder.rglob("*")
                          if path.is_file() and path.suffix in {".py", ".md"}
                          and path.resolve() not in {tool, dossier})
    for source_path in NEW_FILES:
        matches = [str(candidate) for candidate in candidates
                   if source_path in candidate.read_text(errors="replace")]
        require(not matches, "new source path overlaps an earlier inventory: "
                + source_path + ": " + ", ".join(matches[:3]))
    require(not set(NEW_FILES).intersection(base.PR36_CHANGED_FILES),
            "new source overlaps PR #36 changed-file paths")
    return {
        "scanned_prior_tools_and_dossiers": len(candidates),
        "prior_inventory_path_matches": 0,
        "pr36_changed_file_matches": 0,
        "new_complete_files": sorted(NEW_FILES),
        "reused_source_context": [
            "src/editor.cpp",
            "src/core/map.cpp",
            "src/core/editcommands.cpp",
        ],
    }


def identity_negatives(sources):
    rejected = 0
    for path, (blob, digest, _) in NEW_FILES.items():
        changed = sources[path].encode() + b"\n"
        for expected_blob, expected_digest in (
            (blob, hashlib.sha256(changed).hexdigest()),
            (base.git_blob_sha1(changed), digest),
        ):
            try:
                base.verify_source_identity_bytes(
                    path, changed, expected_blob, expected_digest
                )
            except ValueError:
                rejected += 1
            else:
                raise ValueError("stale source identity accepted: " + path)
    return rejected


def source_contract(sources):
    editor = sources["src/editor.cpp"]
    map_source = sources["src/core/map.cpp"]
    commands = sources["src/core/editcommands.cpp"]
    mainwindow = sources["src/mainwindow.cpp"]
    dialog = sources["src/ui/newmapconnectiondialog.cpp"]
    dialog_header = sources["include/ui/newmapconnectiondialog.h"]

    move_id = base.extract(commands, "int MapConnectionMove::id() const")
    mask_function = base.extract(commands, "int getConnectionDirectionMask(")
    prune = base.extract(map_source, "void Map::pruneEditHistory()")
    unset_map = base.extract(editor, "void Editor::unsetMap()")
    set_map = base.extract(editor, "bool Editor::setMap(")
    add_connection = base.extract(editor, "void Editor::addNewConnection(")
    dialog_accept = base.extract(dialog, "void NewMapConnectionDialog::accept()")
    mainwindow_add = base.extract(
        mainwindow, "void MainWindow::on_pushButton_AddConnection_clicked()"
    )

    require("getConnectionDirectionMask" in move_id
            and "ID_MapConnectionMove |" in move_id,
            "original move command no longer masks its ID")
    require("mapConnectionIds.contains(command->id())" in prune
            and "getConnectionDirectionMask" not in prune
            and "command->id() &" not in prune,
            "original prune comparator no longer exhibits the exact-ID mismatch")
    require("this->map->pruneEditHistory();" in unset_map,
            "Editor::unsetMap no longer invokes map history pruning")
    require("editGroup.addStack(map->editHistory());" in set_map
            and "editGroup.setActiveStack(map->editHistory());" in set_map,
            "Editor::setMap no longer adds and activates the map-owned stack")
    require("emit newConnectionedAdded(targetMapName, direction);" in dialog_accept
            and "newConnectionedAdded" in dialog_header,
            "dialog add signal no longer carries the selected map/direction")
    require("&NewMapConnectionDialog::newConnectionedAdded" in mainwindow_add
            and "&Editor::addNewConnection" in mainwindow_add,
            "MainWindow dialog-to-Editor connection changed")
    require("this->map->commit(new MapConnectionAdd" in add_connection,
            "Editor add caller no longer pushes a MapConnectionAdd")
    require(all(token in mask_function for token in (
        "IDMask_ConnectionDirection_Up", "IDMask_ConnectionDirection_Down",
        "IDMask_ConnectionDirection_Left", "IDMask_ConnectionDirection_Right",
    )), "direction mask helper changed")
    return {
        "dialog_add_call_chain": [
            "MainWindow::on_pushButton_AddConnection_clicked",
            "NewMapConnectionDialog::accept",
            "Editor::addNewConnection",
            "Map::commit",
            "MapConnectionAdd::id",
            "Editor::unsetMap",
            "Map::pruneEditHistory",
            "Editor::setMap",
            "QUndoGroup::setActiveStack",
        ],
        "exact_id_comparison": "masked MapConnectionMove ID versus unmasked QSet entries",
        "editor_map_switch": "unsetMap prunes previous map, setMap activates loaded map stack",
        "source_only_ui_claim": "dialog signals and slot wiring are source-checked, not interacted with",
    }


def source_negatives(sources):
    probes = (
        ("src/core/editcommands.cpp", "int MapConnectionMove::id() const",
         "ID_MapConnectionMove |", "ID_MapConnectionMove"),
        ("src/core/map.cpp", "void Map::pruneEditHistory()",
         "mapConnectionIds.contains(command->id())",
         "mapConnectionIds.contains(command->id() & ~IDMask_ConnectionDirection_Up)"),
        ("src/editor.cpp", "void Editor::unsetMap()",
         "this->map->pruneEditHistory();", "this->map->invalidateScripts();"),
        ("src/editor.cpp", "bool Editor::setMap(",
         "editGroup.setActiveStack(map->editHistory());", "updateEvents();"),
        ("src/ui/newmapconnectiondialog.cpp", "void NewMapConnectionDialog::accept()",
         "emit newConnectionedAdded(targetMapName, direction);", "QDialog::accept();"),
        ("src/mainwindow.cpp", "void MainWindow::on_pushButton_AddConnection_clicked()",
         "&NewMapConnectionDialog::newConnectionedAdded",
         "&NewMapConnectionDialog::connectionReplaced"),
        ("src/editor.cpp", "void Editor::addNewConnection(",
         "this->map->commit(new MapConnectionAdd", "this->map->commit(new MapConnectionRemove"),
    )
    rejected = 0
    for path, anchor, old, replacement in probes:
        body = base.extract(sources[path], anchor)
        require(old in body, "source probe anchor missing: " + anchor)
        changed = dict(sources)
        changed[path] = sources[path].replace(
            body, body.replace(old, replacement, 1), 1
        )
        try:
            source_contract(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation accepted: " + anchor)
    return rejected


def source_definitions(sources):
    header = sources["include/core/editcommands.h"]
    enum_start = header.index("enum CommandId {")
    enum_end = header.index("};", enum_start) + 2
    definitions = [header[enum_start:enum_end]]
    for name in (
        "IDMask_ConnectionDirection_Up",
        "IDMask_ConnectionDirection_Down",
        "IDMask_ConnectionDirection_Left",
        "IDMask_ConnectionDirection_Right",
        "IDMask_ConnectionDirection_Dive",
        "IDMask_ConnectionDirection_Emerge",
    ):
        match = re.search(rf"(?m)^#define\s+{name}\s+.*$", header)
        require(match, "pinned direction mask definition missing: " + name)
        definitions.append(match.group(0))

    commands = sources["src/core/editcommands.cpp"]
    editor = sources["src/editor.cpp"]
    map_source = sources["src/core/map.cpp"]
    return {
        "PINNED_COMMAND_ENUM_AND_MASKS": "\n".join(definitions),
        "PINNED_DIRECTION_MASK_METHOD":
            base.extract(commands, "int getConnectionDirectionMask("),
        "PINNED_CONNECTION_MOVE_ID_METHOD":
            base.extract(commands, "int MapConnectionMove::id() const"),
        "PINNED_MAP_PRUNE_METHOD":
            base.extract(map_source, "void Map::pruneEditHistory()"),
        "PINNED_EDITOR_MAP_METHODS": "\n\n".join((
            base.extract(editor, "void Editor::unsetMap()"),
            base.extract(editor, "bool Editor::setMap("),
        )),
    }


def verify_native_record(record):
    require(record["phase1_gate"] == "FAIL_INCOMPLETE"
            and record["independent_approvals"] == 0,
            "gate or approval status was promoted")
    required_true = (
        "native_qt_qundo_group",
        "pinned_editor_set_unset_map_bodies",
        "pinned_map_prune_body",
        "pinned_connection_move_id_body",
        "masked_history_survives_switch",
        "unmasked_control_pruned",
        "inactive_stack_not_routed",
        "stale_history_reactivated",
        "undo_overwrite_observed",
        "redo_overwrite_observed",
    )
    require(all(record.get(field) is True for field in required_true),
            "native map-switch evidence incomplete")
    require(all(record.get(field) is False for field in (
        "full_gui", "project_json_persistence", "cold_reopen", "gameplay",
    )), "synthetic method test mislabeled as GUI/persistence/gameplay proof")


def evidence_negatives(record):
    mutations = (
        ("phase1_gate", "PASS"),
        ("independent_approvals", 1),
        ("native_qt_qundo_group", False),
        ("pinned_editor_set_unset_map_bodies", False),
        ("masked_history_survives_switch", False),
        ("unmasked_control_pruned", False),
        ("undo_overwrite_observed", False),
        ("project_json_persistence", True),
        ("cold_reopen", True),
        ("gameplay", True),
    )
    rejected = 0
    for key, value in mutations:
        changed = dict(record)
        changed[key] = value
        try:
            verify_native_record(changed)
        except (ValueError, KeyError):
            rejected += 1
        else:
            raise ValueError("evidence mutation accepted: " + key)
    return rejected


def run_native(harness, sources, log_path):
    generated = harness.read_text(encoding="utf-8")
    for token, value in source_definitions(sources).items():
        require(generated.count(token) == 1,
                "pinned method placeholder missing/duplicated: " + token)
        generated = generated.replace(token, value)
    require(not re.search(r"PINNED_[A-Z_]+", generated),
            "unreplaced pinned-source placeholder")

    with tempfile.TemporaryDirectory(prefix="phase1-editor-map-switch-") as temp:
        directory = Path(temp)
        source = directory / harness.name
        source.write_text(generated, encoding="utf-8")
        moc = shutil.which("moc") or "/usr/lib/qt6/libexec/moc"
        moc_source = directory / "moc_editor_map_switch.cpp"
        subprocess.run(
            [moc, str(source), "-o", str(moc_source)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        executable = directory / "editor-map-switch"
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
        result = subprocess.run(
            [str(executable)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=45,
        )
        log_path.write_text(build.stdout + result.stdout, encoding="utf-8")
        require(result.returncode == 0,
                "native editor map-switch test failed; see " + str(log_path))
        matches = re.findall(
            r"^PHASE1_EDITOR_MAP_SWITCH_RESULT (\{.*\})$", result.stdout, re.M
        )
        require(len(matches) == 1, "native map-switch result missing/duplicated")
        record = json.loads(matches[0])
        verify_native_record(record)
        return record


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
    context_sources, _ = base.verify_sources(args.porymap)
    new_sources, rows = verify_new_sources(args.porymap)
    sources = {**context_sources, **new_sources}
    previous_dossier = repository_root / PRIOR_PACKET_DOSSIER
    require(hashlib.sha256(previous_dossier.read_bytes()).hexdigest()
            == PRIOR_DOSSIER_SHA256,
            "prior packet dossier digest changed")
    previous_harness = repository_root / "tests/phase1_porymap_cross_map_undo.cpp"
    require(hashlib.sha256(previous_harness.read_bytes()).hexdigest()
            == PRIOR_NATIVE_HARNESS_SHA256,
            "prior packet native witness digest changed")

    verify_inventory_rows(rows)
    inventory_overlap = verify_inventory_overlap(repository_root)
    contract = source_contract(sources)
    identity_rejections = identity_negatives(new_sources)
    inventory_rejections = inventory_negatives(rows)
    source_rejections = source_negatives(sources)
    native_record = run_native(args.harness, sources, args.log)
    evidence_rejections = evidence_negatives(native_record)
    license_bytes = (args.porymap / "LICENSE.md").read_bytes()
    require(base.git(args.porymap, "hash-object", "LICENSE.md") == LICENSE_BLOB
            and hashlib.sha256(license_bytes).hexdigest() == LICENSE_SHA256,
            "pinned Porymap license evidence changed")
    base.make_archive(args.dossier, args.archive)

    result = {
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "porymap_pin": PIN,
        "firered_pin_unchanged_not_exercised":
            "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
        "poryscript_pin_unchanged_not_exercised":
            "c32481161c767b25a3425fa9f1f8729927ff3d55",
        "license": {
            "path": "LICENSE.md",
            "git_blob_sha1": LICENSE_BLOB,
            "source_sha256": LICENSE_SHA256,
            "finding": "LGPL-3.0 text; not a redistribution determination",
            "file_specific_notices_found": False,
            "qt_translations_exercised": False,
            "sqlite_exercised": False,
        },
        "per_file_rows": rows,
        "original_dossier_row_and_archive_status":
            "NEEDS_EVIDENCE for both new dialog files; no earlier per-file receipts existed",
        "prior_packet": {
            "dossier_sha256": PRIOR_DOSSIER_SHA256,
            "deterministic_archive_sha256": PRIOR_ARCHIVE_SHA256,
            "tool_path": PRIOR_PACKET_TOOL.as_posix(),
            "prior_tool_sha256": PRIOR_NATIVE_TOOL_SHA256,
            "prior_harness_sha256": PRIOR_NATIVE_HARNESS_SHA256,
        },
        "inventory_overlap": inventory_overlap,
        "source_contract": contract,
        "source_identity_mutations_rejected": identity_rejections,
        "inventory_mutations_rejected": inventory_rejections,
        "source_mutations_rejected": source_rejections,
        "native_result": native_record,
        "evidence_mutations_rejected": evidence_rejections,
        "evidence_classification": {
            "source": "immutable pinned source bodies and callers; source assertions only",
            "native": "Qt 6 QUndoGroup/QUndoStack plus unchanged extracted pinned methods and test-only model/command shells",
            "host": "Linux build host",
            "full_gui": False,
            "project_file_write_or_readback": False,
            "cold_reopen": False,
            "gameplay": False,
            "hardware_durability": False,
        },
        "dossier_sha256": hashlib.sha256(args.dossier.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "archive_contents": [args.dossier.name],
        "archive_excludes_upstream_source": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("PORYMAP_EDITOR_MAP_SWITCH_PASS "
          f"new_sources={len(NEW_FILES)} source_mutations={source_rejections} "
          f"evidence_mutations={evidence_rejections} "
          "gate=FAIL_INCOMPLETE approvals=0")
    print(json.dumps({
        "dossier_sha256": result["dossier_sha256"],
        "archive_sha256": result["archive_sha256"],
        "native_result": native_record,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Inventory the pinned Porymap event-script dropdown and open-in-editor path."""
import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"

NEW_FILES = {
    "include/editor.h": (
        "Porymap Editor interface for opening map and project scripts",
        ("bool openScript(const QString &scriptLabel) const;",
         "bool openScriptInFile(const QString &scriptLabel, const QString &filepath) const;"),
    ),
    "src/editor.cpp": (
        "Connects map script requests and locates a script definition in text files",
        ("connect(map, &Map::openScriptRequested, this, &Editor::openScript);",
         "bool Editor::openScript(const QString &scriptLabel) const {",
         "openScriptInFile(scriptLabel, map->getScriptsFilepath())",
         "project->getAllEventScriptsFilepaths()",
         "int lineNum = ParseUtil::getScriptLineNumber(filepath, scriptLabel);",
         "if (lineNum == 0)",
         "openInTextEditor(filepath, lineNum);"),
    ),
    "include/ui/eventframes.h": (
        "Event editor frame declarations for script dropdowns and source navigation",
        ("void populateScriptDropdown(NoScrollComboBox * combo, Project * project);",
         "NoScrollComboBox *combo_script;",
         "QToolButton *button_script;"),
    ),
    "src/ui/eventframes.cpp": (
        "Builds script dropdowns, autocomplete, and the script-definition button action",
        ("void EventFrame::populateScriptDropdown(NoScrollComboBox * combo, Project * project) {",
         "map->getScriptLabels(this->event->getEventGroup())",
         "project->insertGlobalScriptLabels(scripts);",
         "completer->setCaseSensitivity(Qt::CaseInsensitive);",
         "completer->setFilterMode(Qt::MatchContains);",
         "this->object->getMap()->openScript(this->combo_script->currentText());"),
    ),
    "include/ui/noscrollcombobox.h": (
        "Editable event dropdown interface and its editing-finished signal",
        ("class NoScrollComboBox : public QComboBox",
         "void setTextItem(const QString &text);",
         "void editingFinished();"),
    ),
    "src/ui/noscrollcombobox.cpp": (
        "Maps combo activation and line-edit completion to the shared signal",
        ("connect(this, QOverload<int>::of(&QComboBox::activated), this, &NoScrollComboBox::editingFinished);",
         "connect(this->lineEdit(), &QLineEdit::editingFinished, this, &NoScrollComboBox::editingFinished);",
         "void NoScrollComboBox::setTextItem(const QString &text)",
         "this->setItem(this->findText(text), text);"),
    ),
}

REUSED_FILES = {
    "include/core/map.h": (
        "Previously inventoried map script cache and request interface",
        ("QStringList getScriptLabels(Event::Group group = Event::Group::None);",
         "void openScriptRequested(const QString &label);"),
    ),
    "src/core/map.cpp": (
        "Previously inventoried script-file selection, labels, and watcher invalidation",
        ("QStringList Map::getScriptLabels(Event::Group group) {",
         "ParseUtil::getGlobalScriptLabels(scriptsFilepath, &error)",
         "scriptLabels.append(event->getScripts());",
         'scriptLabels.removeAll("0x0");',
         "QString Map::getScriptsFilepath() const {",
         "usePoryScript && !QFile::exists(path + extension)",
         "extension = Project::getScriptFileExtension(false)",
         "emit openScriptRequested(label);"),
    ),
    "include/core/parseutil.h": (
        "Previously inventoried parser API and not-found line-number contract",
        ("static int getScriptLineNumber(const QString &filePath, const QString &scriptLabel);",
         "Returns 0 if a definition for scriptLabel cannot be found.",
         "static QStringList getGlobalScriptLabels(const QString &filePath, QString *error = nullptr);"),
    ),
    "src/core/parseutil.cpp": (
        "Previously inventoried raw-assembly and Poryscript label/line parsing",
        ("int ParseUtil::getScriptLineNumber(",
         'filepath.endsWith(".inc") || filepath.endsWith(".s")',
         'filepath.endsWith(".pory")',
         "QStringList ParseUtil::getGlobalScriptLabels(",
         "QStringList ParseUtil::getGlobalRawScriptLabels(",
         "QStringList ParseUtil::getGlobalPoryScriptLabels("),
    ),
    "include/project.h": (
        "Previously inventoried project-wide event-script label collection interface",
        ("QStringList globalScriptLabels;",
         "void insertGlobalScriptLabels(QStringList &scriptLabels) const;"),
    ),
    "src/project.cpp": (
        "Previously inventoried global label collection from project script files",
        ("void Project::insertGlobalScriptLabels(QStringList &scriptLabels) const {",
         "scriptLabels.append(this->globalScriptLabels);",
         "this->globalScriptLabels << ParseUtil::getGlobalScriptLabels(path);",
         "this->globalScriptLabels.removeDuplicates();"),
    ),
}

ALL_FILES = {**NEW_FILES, **REUSED_FILES}
PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "Prior partial ParseUtil and project-write context; reused, not new coverage",
    "docs/phase1-review-readiness/porymap-poryscript-generated-inc-20261029.md":
        "Prior Porymap generated-script setup; adjacent context, not this UI consumer",
    "docs/phase1-review-readiness/poryscript-compiler-source-closure-20261105.md":
        "Separate compiler inventory; not repeated as consumer evidence",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    require(result.returncode == 0, "git command failed: " + " ".join(args))
    return result.stdout.strip()


def git_blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def pinned_file(root, path):
    expected = git(root, "rev-parse", PIN + ":" + path)
    data = (root / path).read_bytes()
    actual = git_blob(data)
    require(actual == expected, "working-tree source differs from pinned blob: " + path)
    return {
        "repository": "porymap",
        "commit": PIN,
        "path": path,
        "git_blob": actual,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }, data.decode("utf-8", "surrogateescape")


def verify_contracts(sources):
    for path, (_, anchors) in ALL_FILES.items():
        for anchor in anchors:
            require(anchor in sources[path], "source contract changed: " + path + ": " + anchor)
    # Keep the caller-to-parser route explicit rather than inferring it from names alone.
    require(
        sources["src/ui/eventframes.cpp"].index("map->getScriptLabels(")
        < sources["src/ui/eventframes.cpp"].index("project->insertGlobalScriptLabels(scripts);"),
        "event dropdown source ordering changed",
    )
    require(
        sources["src/editor.cpp"].index("openScriptInFile(scriptLabel, map->getScriptsFilepath())")
        < sources["src/editor.cpp"].index("project->getAllEventScriptsFilepaths()"),
        "editor no longer checks the current map script file first",
    )


def source_negatives(sources):
    rejected = 0
    for path, (_, anchors) in ALL_FILES.items():
        anchor = anchors[0]
        changed = dict(sources)
        mutated_anchor = anchor.replace(anchor[0], anchor[0] + "_MUTATED_", 1)
        changed[path] = sources[path].replace(anchor, mutated_anchor, 1)
        try:
            verify_contracts(changed)
        except ValueError:
            rejected += 1
            continue
        raise ValueError("source mutation escaped: " + path)
    return rejected


def validate_evidence(evidence):
    require(evidence["upstream_pin"] == PIN, "upstream pin changed")
    require(evidence["new_source_file_count"] == len(NEW_FILES), "new source count changed")
    require(evidence["reused_file_count"] == len(REUSED_FILES), "reused source count changed")
    require(len(evidence["files"]) == len(ALL_FILES), "source matrix row count changed")
    require(
        len({row["path"] for row in evidence["files"]}) == len(ALL_FILES),
        "duplicate source matrix row",
    )
    require(evidence["source_mutations_rejected"] == len(ALL_FILES),
            "source mutation controls missing")
    require(evidence["evidence_status"] == "NEEDS_EVIDENCE", "evidence status overclaimed")
    require(evidence["independent_approvals"] == 0, "approval count overclaimed")
    require(evidence["phase1_gate"] == "FAIL_INCOMPLETE", "gate overclaimed")
    require(evidence["native_ui_runtime"] is False, "GUI runtime overclaimed")
    require(evidence["complete_file_independent_review"] is False,
            "independent review overclaimed")
    for row in evidence["files"]:
        require(len(row["sha256"]) == 64, "invalid source SHA-256")
        expected = "new_inventory" if row["path"] in NEW_FILES else "reused_prior_context"
        require(row["coverage"] == expected, "source coverage classification changed")
        require(row["disposition"] == "NEEDS_EVIDENCE", "file disposition overclaimed")
    require(len(evidence["dossier_sha256"]) == 64, "invalid dossier SHA-256")
    require(len(evidence["prior_dossiers"]) == len(PRIOR_DOSSIERS),
            "prior dossier inventory changed")


def evidence_negatives(evidence):
    mutations = (
        {"upstream_pin": "0" * 40},
        {"new_source_file_count": 0},
        {"reused_file_count": 0},
        {"source_mutations_rejected": 0},
        {"evidence_status": "PASSED"},
        {"independent_approvals": 1},
        {"phase1_gate": "PASS"},
        {"native_ui_runtime": True},
        {"complete_file_independent_review": True},
        {"dossier_sha256": ""},
        {"prior_dossiers": []},
    )
    for index, mutation in enumerate(mutations):
        try:
            validate_evidence({**evidence, **mutation})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped " + str(index))
    return len(mutations)


def make_archive(dossier, evidence, destination):
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w") as archive:
        for path, name in ((dossier, "porymap-script-consumer-source-closure.md"),
                           (evidence, "porymap-script-consumer-source-closure.json")):
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    with destination.open("wb") as target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
            compressed.write(raw_tar.getvalue())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", required=True, type=Path)
    parser.add_argument("--dossier", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    root = args.porymap.resolve()
    require(git(root, "rev-parse", "HEAD") == PIN, "pinned Porymap commit drift")

    rows = []
    sources = {}
    for path, (role, _) in ALL_FILES.items():
        row, sources[path] = pinned_file(root, path)
        row.update({
            "role": role,
            "coverage": "new_inventory" if path in NEW_FILES else "reused_prior_context",
            "disposition": "NEEDS_EVIDENCE",
        })
        rows.append(row)

    verify_contracts(sources)
    source_mutation_count = source_negatives(sources)
    license_row, license_text = pinned_file(root, "LICENSE.md")
    require("GNU LESSER GENERAL PUBLIC LICENSE" in license_text,
            "pinned Porymap license notice changed")

    prior_dossiers = []
    for path, role in PRIOR_DOSSIERS.items():
        data = Path(path).read_bytes()
        prior_dossiers.append({
            "path": path,
            "role": role,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "lines": len(data.splitlines()),
        })

    dossier_sha = hashlib.sha256(args.dossier.read_bytes()).hexdigest()
    evidence = {
        "class": "PINNED_PORYMAP_EVENT_SCRIPT_CONSUMER_CLOSURE",
        "upstream_pin": PIN,
        "files": rows,
        "new_source_file_count": len(NEW_FILES),
        "reused_file_count": len(REUSED_FILES),
        "source_mutations_rejected": source_mutation_count,
        "evidence_mutations_rejected": 11,
        "consumer_path": [
            "EventFrame populates map labels and optional project-wide autocomplete.",
            "The script button sends the selected text through Map::openScriptRequested.",
            "Editor tries the current map script file first, then project event-script files.",
            "ParseUtil maps the label to a raw .inc/.s or Poryscript .pory line; zero means not found.",
        ],
        "prior_dossiers": prior_dossiers,
        "license_evidence": {
            "path": "LICENSE.md",
            **license_row,
            "license_text_observed": "GNU LESSER GENERAL PUBLIC LICENSE",
        },
        "dossier_sha256": dossier_sha,
        "archive_format": "deterministic gzip-compressed tar containing this dossier and evidence JSON",
        "evidence_status": "NEEDS_EVIDENCE",
        "complete_file_independent_review": False,
        "native_ui_runtime": False,
        "upstream_modified": False,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    validate_evidence(evidence)
    evidence["evidence_mutations_rejected"] = evidence_negatives(evidence)
    validate_evidence(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    make_archive(args.dossier, args.output, args.archive)
    archive_sha = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    args.archive.with_suffix(args.archive.suffix + ".sha256").write_text(
        archive_sha + "  " + args.archive.name + "\n")
    print(json.dumps({**evidence, "archive_sha256": archive_sha}, sort_keys=True))


if __name__ == "__main__":
    main()

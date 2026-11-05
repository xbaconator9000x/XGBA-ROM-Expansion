#!/usr/bin/env python3
"""Inventory the pinned Porymap external-editor preference and persistence boundary."""
import argparse
import copy
import gzip
import hashlib
import io
import json
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"

NEW_FILES = {
    "include/ui/preferenceeditor.h": (
        "PreferenceEditor public signals and private field-save interface",
        ("void preferencesSaved();", "void saveFields();"),
    ),
    "src/ui/preferenceeditor.cpp": (
        "Preference editor field load/save and accept/apply/cancel behavior",
        (
            "ui->lineEdit_TextEditorGotoLine->setText(porymapConfig.textEditorGotoLine);",
            "porymapConfig.textEditorGotoLine = ui->lineEdit_TextEditorGotoLine->text();",
            "porymapConfig.save();",
            "emit preferencesSaved();",
            "if (buttonRole == QDialogButtonBox::AcceptRole)",
            "saveFields();\n        close();",
            "} else if (buttonRole == QDialogButtonBox::ApplyRole)",
            "} else if (buttonRole == QDialogButtonBox::RejectRole)",
        ),
    ),
    "forms/preferenceeditor.ui": (
        "Preferences UI labels and configured external-editor command guidance",
        (
            'name="lineEdit_TextEditorGotoLine"',
            "Goto Line Command",
            "%F",
            "%L",
            "must&lt;/span&gt; be given if",
            "current map's scripts file is opened",
            'name="lineEdit_TextEditorOpenFolder"',
            "Open Project in Text Editor",
        ),
    ),
}

REUSED_FILES = {
    "include/editor.h": (
        "Previously inventoried Editor open-script and external-editor interface",
        ("bool openScript(const QString &scriptLabel) const;", "openInTextEditor"),
    ),
    "src/editor.cpp": (
        "Previously inventoried script lookup and configured editor process handoff",
        (
            "int lineNum = ParseUtil::getScriptLineNumber(filepath, scriptLabel);",
            "porymapConfig.textEditorGotoLine",
            "Editor::startDetachedProcess(command);",
            "bool Editor::startDetachedProcess(",
            "startDetachedProcess(command);",
            "QDesktopServices::openUrl(QUrl::fromLocalFile(path));",
        ),
    ),
    "include/config.h": (
        "Previously inventoried Porymap configuration interface",
        ("QString textEditorGotoLine;", "bool save();"),
    ),
    "src/config.cpp": (
        "Previously inventoried key/value configuration writer, compiled unchanged below",
        (
            "bool KeyValueConfigBase::save() {",
            "if (!file.open(QIODevice::WriteOnly))",
            "file.write(text.toUtf8());",
            "file.close();\n    return true;",
        ),
    ),
    "src/core/parseutil.cpp": (
        "Previously inventoried script-label to source-line lookup",
        ("int ParseUtil::getScriptLineNumber(",),
    ),
}

ALL_FILES = {**NEW_FILES, **REUSED_FILES}
EVIDENCE_MUTATION_COUNT = 16
PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-event-script-consumer-closure-20261105.md":
        "Prior dropdown and external-editor caller context; reused, not repeated",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "Prior transaction/config writer context; reused, not repeated",
    "docs/phase1-review-readiness/porymap-poryscript-generated-inc-20261029.md":
        "Prior generated-include context; adjacent, not script-buffer evidence",
    "docs/phase1-review-readiness/poryscript-compiler-source-closure-20261105.md":
        "Prior compiler/FireRed ABI work; distinct scope",
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
    text = data.decode("utf-8", "surrogateescape")
    return {
        "repository": "huderlem/porymap",
        "commit": PIN,
        "path": path,
        "git_blob": actual,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }, text


def verify_contracts(sources):
    for path, (_, anchors) in ALL_FILES.items():
        for anchor in anchors:
            require(anchor in sources[path],
                    "source contract changed: " + path + ": " + anchor)

    preferences = sources["src/ui/preferenceeditor.cpp"]
    save_at = preferences.index("porymapConfig.save();")
    saved_signal_at = preferences.index("emit preferencesSaved();", save_at)
    require(save_at < saved_signal_at,
            "preference save/signal ordering changed")
    require(
        "if (porymapConfig.save())" not in preferences
        and "if (!porymapConfig.save())" not in preferences,
        "preference save failure handling changed; reassess claims",
    )
    editor = sources["src/editor.cpp"]
    require(
        editor.index("startDetachedProcess(command);")
        > editor.index("porymapConfig.textEditorGotoLine"),
        "configured editor command no longer reaches detached process launch",
    )


def source_negatives(sources):
    rejected = 0
    for path, (_, anchors) in ALL_FILES.items():
        anchor = anchors[0]
        changed = dict(sources)
        changed[path] = sources[path].replace(anchor, anchor + "_MUTATED", 1)
        try:
            verify_contracts(changed)
        except ValueError:
            rejected += 1
            continue
        raise ValueError("source mutation escaped: " + path)
    return rejected


def extract_cpp_function(source, signature):
    start = source.find(signature)
    require(start >= 0, "pinned C++ function signature not found: " + signature)
    brace = source.find("{", start)
    require(brace >= 0, "pinned C++ function body not found: " + signature)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("unbalanced C++ function body: " + signature)


def compile_original_config_writer(config_source, temp_root):
    body = extract_cpp_function(config_source, "bool KeyValueConfigBase::save()")
    harness = r'''#include <QCoreApplication>
#include <cstdio>
#include <QDir>
#include <QFile>
#include <QFileDevice>
#include <QByteArray>
#include <QMap>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>

void logError(const QString &) {}

class KeyValueConfigBase {
public:
    bool save();
    QString filepath() const { return path; }
    QMap<QString, QString> getKeyValueMap() { return values; }
    QString path;
    QMap<QString, QString> values;
};

ORIGINAL_SOURCE_FUNCTION

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const QString blockedDirectory = QString::fromLocal8Bit(argv[1]);
    const QString successfulFilePath = QString::fromLocal8Bit(argv[2]);
    if (!QDir().mkpath(blockedDirectory))
        return 2;

    KeyValueConfigBase successfulSave;
    successfulSave.path = successfulFilePath;
    successfulSave.values.insert("editor", "configured");
    const bool successfulSaveResult = successfulSave.save();
    QFile savedFile(successfulFilePath);
    const bool savedBytesMatch = successfulSaveResult
        && savedFile.open(QIODevice::ReadOnly)
        && savedFile.readAll() == QByteArray("editor=configured\n");

    KeyValueConfigBase openFailure;
    openFailure.path = blockedDirectory;
    openFailure.values.insert("editor", "configured");
    const bool openFailureResult = openFailure.save();

    KeyValueConfigBase fullDevice;
    fullDevice.path = "/dev/full";
    fullDevice.values.insert("editor", "configured");
    const bool fullDeviceSaveResult = fullDevice.save();

    QFile control("/dev/full");
    const bool controlOpened = control.open(QIODevice::WriteOnly);
    const qint64 controlWrite = controlOpened ? control.write("editor=configured\n") : -2;
    const bool controlFlushed = controlOpened && control.flush();
    const bool controlWriteError = controlOpened
        && (controlWrite < 0 || !controlFlushed
            || control.error() != QFileDevice::NoError);
    const int controlError = static_cast<int>(control.error());
    control.close();

    QJsonObject result;
    result.insert("successful_save_bytes_match_expected", savedBytesMatch);
    result.insert("blocked_directory_save_returned_false", !openFailureResult);
    result.insert("full_device_save_returned_true", fullDeviceSaveResult);
    result.insert("direct_full_device_control_observed_write_error", controlWriteError);
    result.insert("direct_full_device_control_write_result",
                  static_cast<qint64>(controlWrite));
    result.insert("direct_full_device_control_error",
                  controlError);
    result.insert("full_device_exists", QFile::exists("/dev/full"));
    const QByteArray output = QJsonDocument(result).toJson(QJsonDocument::Compact);
    std::fwrite(output.constData(), 1, static_cast<size_t>(output.size()), stdout);
    std::fputc('\n', stdout);
    return 0;
}
'''.replace("ORIGINAL_SOURCE_FUNCTION", body)

    source_path = temp_root / "original_config_writer.cpp"
    binary_path = temp_root / "original_config_writer"
    source_path.write_text(harness)
    pkg = subprocess.run(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(pkg.returncode == 0, "Qt6Core pkg-config metadata unavailable: " + pkg.stderr)
    qt_version = subprocess.run(
        ["pkg-config", "--modversion", "Qt6Core"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(qt_version.returncode == 0, "Qt6Core version unavailable: " + qt_version.stderr)
    command = [
        "g++", "-std=c++17", "-fPIC", str(source_path), "-o", str(binary_path),
        *shlex.split(pkg.stdout),
    ]
    built = subprocess.run(command, capture_output=True, text=True, check=False)
    require(built.returncode == 0,
            "original config writer compile failed: " + built.stdout + built.stderr)
    blocked_directory = temp_root / "blocked-config-path"
    successful_file = temp_root / "successful-config"
    completed = subprocess.run(
        [str(binary_path), str(blocked_directory), str(successful_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    require(completed.returncode == 0,
            "original config writer execution failed: " + completed.stdout + completed.stderr)
    result = json.loads(completed.stdout)
    require(result["full_device_exists"], "Linux /dev/full failure fixture unavailable")
    require(result["successful_save_bytes_match_expected"],
            "original config writer failed the successful byte control")
    require(result["blocked_directory_save_returned_false"],
            "original config writer did not reject open failure")
    require(result["direct_full_device_control_observed_write_error"],
            "direct QFile /dev/full control did not observe a write error")
    require(result["full_device_save_returned_true"],
            "original writer no longer returns true after the controlled write failure")
    normalized_command = [
        argument.replace(str(temp_root), "<TEMP>") for argument in command
    ]
    return {
        **result,
        "original_function_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "compile_command": normalized_command,
        "compile_stdout": built.stdout.replace(str(temp_root), "<TEMP>"),
        "compile_stderr": built.stderr.replace(str(temp_root), "<TEMP>"),
        "execution_stdout": completed.stdout.strip(),
        "execution_stderr": completed.stderr,
        "qt6core_version": qt_version.stdout.strip(),
        "scope": "unchanged pinned KeyValueConfigBase::save body, Qt6 Core, test-only class/logError stubs",
    }


def validate_evidence(
    evidence, expected_rows, expected_license, expected_dossier_sha, expected_prior,
):
    require(evidence["upstream_pin"] == PIN, "upstream pin changed")
    require(evidence["new_source_file_count"] == len(NEW_FILES), "new source count changed")
    require(evidence["reused_file_count"] == len(REUSED_FILES), "reused source count changed")
    require(len(evidence["files"]) == len(ALL_FILES), "source matrix row count changed")
    require(
        {row["path"] for row in evidence["files"]}
        == {row["path"] for row in expected_rows},
        "source matrix file identity changed",
    )
    require(evidence["source_mutations_rejected"] == len(ALL_FILES),
            "source mutation controls missing")
    require(evidence["evidence_mutations_rejected"] == EVIDENCE_MUTATION_COUNT,
            "evidence mutation controls missing")
    require(evidence["evidence_status"] == "NEEDS_EVIDENCE",
            "evidence status overclaimed")
    require(evidence["independent_approvals"] == 0, "approval count overclaimed")
    require(evidence["phase1_gate"] == "FAIL_INCOMPLETE", "gate overclaimed")
    require(evidence["complete_file_independent_review"] is False,
            "independent review overclaimed")
    for row, expected in zip(evidence["files"], expected_rows):
        require(row["path"] == expected["path"], "source row order/identity changed")
        require(row == expected,
                "pinned source evidence changed: " + row["path"])
    require(evidence["license_evidence"] == expected_license, "license evidence changed")
    require(evidence["prior_dossiers"] == expected_prior, "prior dossier evidence changed")
    require(evidence["dossier_sha256"] == expected_dossier_sha,
            "dossier hash changed")
    require(evidence["native_original_config_writer"]["blocked_directory_save_returned_false"],
            "open-failure negative missing")
    require(evidence["native_original_config_writer"]["successful_save_bytes_match_expected"],
            "successful config-write control missing")
    require(evidence["native_original_config_writer"]["direct_full_device_control_observed_write_error"],
            "Qt /dev/full write-error control missing")
    require(evidence["native_original_config_writer"]["full_device_save_returned_true"],
            "original writer's failed-write return observation changed")
    require(evidence["native_original_config_writer"]["script_contents_tested"] is False,
            "script-content persistence overclaimed")
    require(evidence["external_editor_process_tested"] is False,
            "external editor launch overclaimed")
    require(evidence["porymap_script_buffer_tested"] is False,
            "Porymap-owned script buffer overclaimed")
    require(evidence["script_content_save_or_reopen_tested"] is False,
            "script-content persistence overclaimed")
    require(evidence["full_gui_runtime_tested"] is False, "GUI runtime overclaimed")
    require(evidence["fsync_durability_tested"] is False,
            "filesystem durability overclaimed")
    require(evidence["upstream_modified"] is False, "upstream modification claim changed")
    require(len(evidence["prior_dossiers"]) == len(PRIOR_DOSSIERS),
            "prior dossier inventory changed")


def evidence_negatives(
    evidence, expected_rows, expected_license, dossier_sha, expected_prior,
):
    mutations = []
    changed_row = copy.deepcopy(evidence["files"])
    changed_row[0]["path"] = "src/editor.cpp"
    mutations.append({"files": changed_row})
    for field in ("git_blob", "sha256"):
        changed_row = copy.deepcopy(evidence["files"])
        current = changed_row[0][field]
        replacement = "0" if current[0] != "0" else "f"
        changed_row[0][field] = replacement * len(current)
        mutations.append({"files": changed_row})
    changed_row = copy.deepcopy(evidence["files"])
    changed_row[0]["source_anchors"][0]["line"] = 0
    mutations.append({"files": changed_row})
    mutations.extend((
        {"license_evidence": {}},
        {"evidence_status": "PASSED"},
        {"independent_approvals": 1},
        {"phase1_gate": "PASS"},
        {"dossier_sha256": ""},
        {"external_editor_process_tested": True},
        {"porymap_script_buffer_tested": True},
        {"script_content_save_or_reopen_tested": True},
        {"full_gui_runtime_tested": True},
        {"fsync_durability_tested": True},
        {"upstream_modified": True},
    ))
    changed_writer = copy.deepcopy(evidence["native_original_config_writer"])
    changed_writer["full_device_save_returned_true"] = False
    mutations.append({"native_original_config_writer": changed_writer})
    for index, mutation in enumerate(mutations):
        try:
            validate_evidence(
                {**evidence, **mutation}, expected_rows, expected_license, dossier_sha,
                expected_prior,
            )
        except (ValueError, KeyError, TypeError):
            continue
        raise ValueError("evidence mutation escaped " + str(index))
    return len(mutations)


def make_archive(dossier, evidence, destination):
    raw_tar = io.BytesIO()
    with tarfile.open(fileobj=raw_tar, mode="w") as archive:
        for path, name in ((dossier, "porymap-external-editor-boundary.md"),
                           (evidence, "porymap-external-editor-boundary.json")):
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
    pending_rows = []
    for path, (role, anchors) in ALL_FILES.items():
        row, sources[path] = pinned_file(root, path)
        pending_rows.append((path, row, role, anchors))

    verify_contracts(sources)
    source_mutation_count = source_negatives(sources)
    for path, row, role, anchors in pending_rows:
        row.update({
            "role": role,
            "coverage": "new_inventory" if path in NEW_FILES else "reused_prior_context",
            "disposition": "NEEDS_EVIDENCE",
            "source_anchors": [
                {
                    "text": anchor,
                    "line": sources[path].count("\n", 0, sources[path].index(anchor)) + 1,
                }
                for anchor in anchors
            ],
        })
        rows.append(row)

    license_row, license_text = pinned_file(root, "LICENSE.md")
    require("GNU LESSER GENERAL PUBLIC LICENSE" in license_text,
            "pinned Porymap license notice changed")
    license_evidence = {
        **license_row,
        "observed_notice": "GNU LESSER GENERAL PUBLIC LICENSE",
    }

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
    with tempfile.TemporaryDirectory(prefix="phase1-porymap-external-editor-") as temp:
        native_writer = compile_original_config_writer(
            sources["src/config.cpp"], Path(temp),
        )

    expected_prior = prior_dossiers
    evidence = {
        "class": "PINNED_PORYMAP_EXTERNAL_EDITOR_PREFERENCE_BOUNDARY",
        "upstream_pin": PIN,
        "files": rows,
        "new_source_file_count": len(NEW_FILES),
        "reused_file_count": len(REUSED_FILES),
        "source_mutations_rejected": source_mutation_count,
        "evidence_mutations_rejected": EVIDENCE_MUTATION_COUNT,
        "source_path_summary": [
            "PreferenceEditor loads and saves the configured goto-line command.",
            "The original Editor resolves a script label and hands the path/line to a configured external process or desktop opener.",
            "The external-process launch result is discarded by this call site.",
            "The original configuration writer reports an open failure but ignores the QFile::write result.",
            "The native Qt test compiles only the unchanged configuration-writer method with test-only class/logging stubs.",
        ],
        "native_original_config_writer": {
            **native_writer,
            "script_contents_tested": False,
        },
        "prior_dossiers": prior_dossiers,
        "license_evidence": license_evidence,
        "dependency_scope": {
            "Qt6Core": "system build/test dependency; not vendored in the inventoried source rows",
            "SQLite": "not present in this bounded source closure",
            "Qt translations": "not present in this bounded source closure",
        },
        "dossier_sha256": dossier_sha,
        "archive_format": "deterministic gzip-compressed tar containing this dossier and evidence JSON",
        "evidence_status": "NEEDS_EVIDENCE",
        "complete_file_independent_review": False,
        "external_editor_process_tested": False,
        "porymap_script_buffer_tested": False,
        "script_content_save_or_reopen_tested": False,
        "full_gui_runtime_tested": False,
        "fsync_durability_tested": False,
        "upstream_modified": False,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    validate_evidence(
        evidence, rows, license_evidence, dossier_sha, expected_prior,
    )
    evidence["evidence_mutations_rejected"] = evidence_negatives(
        evidence, rows, license_evidence, dossier_sha, expected_prior,
    )
    validate_evidence(
        evidence, rows, license_evidence, dossier_sha, expected_prior,
    )

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

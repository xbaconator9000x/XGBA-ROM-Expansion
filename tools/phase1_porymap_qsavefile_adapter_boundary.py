#!/usr/bin/env python3
"""Phase 1: pinned Porymap Qt save-device adapter boundary; no upstream patch."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "include/lib/orderedjson.h": "cb5139d37d955f2469ebd2eaaf089668b82884fe",
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "LICENSE.md": "65c5ca88a67c30becee01c5a8816d964b03862f9",
}
EXPECTED = [
    "PHASE1_QSAVEFILE_TYPE QFile=0 QIODevice=1",
    "PHASE1_QSAVEFILE_COMMIT positive=1 bytes=12",
    "PHASE1_QSAVEFILE_CANCEL preserved=1",
    "PHASE1_QFILE_DEVFULL write_error=1",
    "PHASE1_QSAVEFILE_BOUNDARY PASS gate=FAIL_INCOMPLETE approvals=0",
]

def require(ok, message):
    if not ok:
        raise ValueError(message)

def body(source, name):
    start = source.find("bool Project::" + name + "(")
    require(start >= 0 and source.count("bool Project::" + name + "(") == 1,
            "missing/duplicate " + name)
    end = source.find("\n}\n", start)
    require(end > start, "unclosed " + name)
    return source[start:end+2]

def check(header, project, license_text):
    # Exact existing ABI: QSaveFile is a QIODevice but not a QFile. An unchanged
    # OrderedJsonDoc::dump(QFile*) cannot accept it directly.
    require(header.count("void dump(QFile *file)") == 1, "serializer signature changed")
    require("QTextStream fileStream(file);" in header, "serializer device changed")
    require("fileStream << m_obj->dump(&m_indent);" in header, "serializer output changed")
    require("fileStream << \"\\n\";" in header, "serializer newline changed")
    doc = header.split("class JsonDoc", 1)[1].split("private:", 1)[0]
    require("fileStream.status()" not in doc and "fileStream.flush()" not in doc,
            "serializer stream error handling changed")
    # The existing file watcher already explicitly repairs dropped watches
    # after replacement; an atomic rename still requires an actual Qt test.
    watch = body(project, "watchFile")
    require("QFileSystemWatcher(this)" in watch and "addPath(filepath)" in watch,
            "watcher setup changed")
    record_start = project.find("void Project::recordFileChange(")
    require(record_start >= 0, "watcher callback missing")
    record = project[record_start:project.find("\n}\n", record_start)+2]
    require("!this->fileWatcher->files().contains(filepath)" in record
            and "this->fileWatcher->addPath(filepath);" in record,
            "watcher replacement recovery changed")
    for name in ("saveTextFile", "appendTextFile"):
        b = body(project, name)
        require("file.write(text.toUtf8());" in b and "return true;" in b,
                "text write path changed: " + name)
        require("file.error()" not in b and "file.flush()" not in b,
                "text writer error handling changed: " + name)
    require("GNU LESSER GENERAL PUBLIC LICENSE" in license_text
            and "Version 3, 29 June 2007" in license_text,
            "pinned root LGPL-3.0 notice changed")
    require("Copyright (c) 2013 Dropbox, Inc." in header
            and "The above copyright notice and this permission notice" in header,
            "bundled json11 permissive notice changed")
    return True

def source_controls(header, project, license_text):
    variants = [
        (header.replace("void dump(QFile *file)", "void dump(QIODevice *file)", 1), project, license_text),
        (header.replace("QTextStream fileStream(file);", "QTextStream fileStream(nullptr);", 1), project, license_text),
        (header.replace("fileStream << m_obj->dump(&m_indent);", "fileStream << QString();", 1), project, license_text),
        (header.replace('fileStream << "\\n";', 'fileStream << " ";', 1), project, license_text),
        (header, project.replace("QFileSystemWatcher(this)", "QObject(this)", 1), license_text),
        (header, project.replace("this->fileWatcher->addPath(filepath);", "this->fileWatcher->removePath(filepath);", 1), license_text),
        (header, project.replace("file.write(text.toUtf8());", "file.flush();", 1), license_text),
        (header, project, license_text.replace("GNU LESSER GENERAL PUBLIC LICENSE", "UNKNOWN LICENSE", 1)),
        (header.replace("Copyright (c) 2013 Dropbox, Inc.", "Copyright unknown", 1), project, license_text),
    ]
    for i, variant in enumerate(variants):
        require(variant != (header, project, license_text), "ineffective source mutation")
        try:
            check(*variant)
        except ValueError:
            continue
        raise ValueError("source mutation escaped " + str(i))
    return len(variants)

def inspect(lines):
    require(lines == EXPECTED, "compiled Qt device evidence changed")
    return True

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--porymap", type=Path, required=True)
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(a.porymap), *args], text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "wrong pinned Porymap revision")
    contents = {}
    for path, sha in BLOBS.items():
        require(git("hash-object", path) == sha, "pinned blob mismatch " + path)
        contents[path] = (a.porymap / path).read_text()
    header, project, license_text = (contents[p] for p in BLOBS)
    check(header, project, license_text)
    source_negatives = source_controls(header, project, license_text)
    lines = a.trace.read_text().splitlines()
    inspect(lines)
    changes = [
        EXPECTED[:-1], EXPECTED[1:], EXPECTED[:2] + EXPECTED[3:],
        [x.replace("QFile=0", "QFile=1") for x in EXPECTED],
        [x.replace("QIODevice=1", "QIODevice=0") for x in EXPECTED],
        [x.replace("positive=1", "positive=0") for x in EXPECTED],
        [x.replace("preserved=1", "preserved=0") for x in EXPECTED],
        [x.replace("write_error=1", "write_error=0") for x in EXPECTED],
        [x.replace("FAIL_INCOMPLETE", "PASS") for x in EXPECTED],
        [x.replace("approvals=0", "approvals=1") for x in EXPECTED],
    ]
    for i, variant in enumerate(changes):
        try:
            inspect(variant)
        except ValueError:
            continue
        raise ValueError("compiled evidence mutation escaped " + str(i))
    evidence = {
        "class": "PINNED_PORYMAP_QSAVEFILE_QIODEVICE_ADAPTER_BOUNDARY",
        "upstream_pin": PIN, "source_git_blobs": BLOBS,
        "source_sha256": {p: hashlib.sha256(s.encode()).hexdigest() for p,s in contents.items()},
        "source_mutations_rejected": source_negatives,
        "compiled_evidence_mutations_rejected": len(changes),
        "qsavefile_drop_in_compatible_with_existing_dump_QFile_pointer": False,
        "qsavefile_is_qiodevice": True,
        "existing_file_watcher_readds_missing_path_after_replacement": True,
        "two_additional_unchecked_text_writer_paths_source_only": True,
        "qsavefile_actual_porymap_writer_runtime_tested": False,
        "qsavefile_commit_failure_on_actual_porymap_writer_tested": False,
        "qt_runtime": lines, "license": "pinned root LGPL-3.0 text; bundled json11 permissive notice; distribution needs separate review",
        "recommendation": "reuse Qt QSaveFile, adapt JsonDoc device signature and verify QTextStream status plus commit; test watcher and all callers; do not rebuild serializer",
        "independent_approvals": 0, "gate": "FAIL_INCOMPLETE",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()

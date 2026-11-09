#!/usr/bin/env python3
"""Verify and execute the pinned Qt savestate restore caller with Qt6Core."""

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-qt-restore-caller-20261109.json"
)
HARNESS = "tests/phase1_mgba_qt_restore_caller.cpp"
HARNESS_SHA256 = None

SOURCES = {
    "src/core/serialize.c": (
        "ff8a9a86747336bd792bf9c964c53f232a702a08",
        "45fb69d5da0c0c4c135efb2641c7d1c6140d575b1819f60a45985ebfa0081f3c",
        "e9ad34d5514e106adc1f56111abf530b72118d1780d8593ae490ee63772ab9b5",
        "PARTIAL_CORE_RESULT_AND_ERROR_CHANNEL_TRACE",
        "SOURCE_TRACED_MCORE_LOAD_RESULT; NOT EXECUTED BY THIS QT HOST WITNESS",
    ),
    "src/platform/qt/CoreController.cpp": (
        "183cea418a70963bd5332ef66bdff54a0dcccd46",
        "8ca7ca7b26fa030ef76322085a6f634b5e3ca4fd40a4e6549b6a12abace260b2",
        "1cbedd6e36f387b7c579bcea8c77bed82e9c3e8b18954974847c647dcf8b0f28",
        "PARTIAL_QT_RESTORE_CALLER_AND_BACKUP_RECOVERY",
        "COMPILED_EXTRACTED_QIODEVICE_AND_FILENAME_LOADSTATE_PLUS_LOADBACKUPSTATE",
    ),
    "src/platform/qt/CoreController.h": (
        "3b7d8bafb7202b66e326221890e2c68655d1be72",
        "3618b5e08c89274b89fa03683840ac79c8aeadc9e7f8ab87a20c65ac58a215a4",
        "2276f54d6a154f7e2ac2973b5f7ffe229e776caaf94aca15cf2ff49d814596e0",
        "PARTIAL_QT_PUBLIC_LOAD_AND_SUCCESS_SIGNAL_CONTRACT",
        "SOURCE_TRACED_DECLARATIONS; FRONTEND CLASS NOT COMPILED",
    ),
    "src/platform/qt/LoadSaveState.cpp": (
        "115d598925d4a85d68630f9909c065256f031ff4",
        "3b0c955cd33dfd3d0732ce2268aaf2747b9abcd62ee818f5cd38beda2702cbf0",
        "fb08e234dad5bcbf91bc59596ad6a916a3a0a3ad431bd64556ba9fe716f1585f",
        "PARTIAL_SLOT_UI_ENTRY_TRACE",
        "SOURCE_TRACED_SLOT_DISPATCH; WIDGET NOT EXECUTED",
    ),
    "src/platform/qt/LogController.cpp": (
        "526cdb9a4054698a0047379613c63fa64efad47d",
        "cb9e77b62ae0752495badb6942f3aec846b2fc0b1db6c33be96a8235d4d16299",
        "96796da1768502b3567e311199957f5890452d635f1d4e0bc6d0ff27391ea100",
        "PARTIAL_LOG_FILTER_AND_UI_ERROR_ROUTE_TRACE",
        "SOURCE_TRACED_LOG_FILTER_AND_QT_ERROR_DIALOG; NOT EXECUTED",
    ),
    "src/platform/qt/VFileDevice.cpp": (
        "337c4462228809477717c659397d037b47d1141b",
        "dc54f83ec81f59ced56a0285643c4520f28830cd999f53814866de8b3cfe0b8a",
        "9bef3ff9694cfdfcb5e3f5bf9382c8cb22a67621c17400afb5572bb67e7df9a5",
        "PARTIAL_QIODEVICE_TO_VFILE_WRAPPER",
        "COMPILED_EXTRACTED_OPEN_WRAP_AND_ABSTRACT_WRAPPER_METHODS",
    ),
    "src/platform/qt/VFileDevice.h": (
        "15f79bbcbdfe3a08bf5047a9306c79da131f8766",
        "75a15f5762042f5568f2329663b2d18828553c1211e737ee44fe33bb0020a178",
        "282cc6a467c2aea1841b52618713dc081e0e996f245055e8ba16387964cb7afd",
        "PARTIAL_VFILE_DEVICE_API_TRACE",
        "SOURCE_TRACED_DECLARATION; TEST FIXTURE USES PINNED VFILE ABI",
    ),
    "src/platform/qt/Window.cpp": (
        "af6592985329f08898cf078a666763954383c832",
        "67fcb2da1d2990e20bf57fd78f51881ce6a62a193cbabb5af5c3ec8fae29dea3",
        "21da719393e20ace0bb1a7080aa8fc1d674fb10072d27fbbe06c74454d4a2398",
        "PARTIAL_FILE_DIALOG_USER_LOAD_ENTRY_TRACE",
        "SOURCE_TRACED_FILENAME_DISPATCH; WINDOW NOT EXECUTED",
    ),
    "src/platform/sdl/main.c": (
        "91f22bd593d4952076c2a9a11da5a8d6951db2a8",
        "8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b",
        "9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c",
        "PARTIAL_SDL_USER_LOAD_ENTRY_TRACE",
        "SOURCE_TRACED_OPTIONAL_STATE_OPEN_RUNFUNCTION_AND_CLOSE; SDL NOT EXECUTED",
    ),
}

CALLER_BODIES = {
    "void CoreController::loadState(QIODevice* iodev, int flags)": (
        "src/platform/qt/CoreController.cpp",
        "b2c111f89228dab6aa53c07e3e2475ee6894683c467aeaa88431f1712e73d989",
    ),
    "void CoreController::loadState(const QString& path, int flags)": (
        "src/platform/qt/CoreController.cpp",
        "0a326ed4783abd42cf4c5eb27943ecee733e9e3cc3e718c9184c7505a226e129",
    ),
    "void CoreController::loadBackupState()": (
        "src/platform/qt/CoreController.cpp",
        "f904d5ba24d51e184d68701645a1098d01ffcd46373a91a185762147011983b8",
    ),
    "class VFileAbstractWrapper : public VFile": (
        "src/platform/qt/VFileDevice.cpp",
        None,
    ),
    "VFile* VFileDevice::wrap(QIODevice* iodev, QIODevice::OpenMode mode)": (
        "src/platform/qt/VFileDevice.cpp",
        "e2c976bfdfe419c034bf83b8df224a763d7d517cd19dd441303ad3e072519956",
    ),
    "VFile* VFileDevice::open(const QString& path, int mode)": (
        "src/platform/qt/VFileDevice.cpp",
        "db69e2be1408c4af0e0156019df0479b8c9812a10dc5ea8151d8f46333a3273b",
    ),
}

WRAPPER_METHODS = {
    "VFileAbstractWrapper::VFileAbstractWrapper(QIODevice* iodev)": "ba8f95f9bd78c92a5ee8f1bebb7d1791ebb0ddca29f533fc7efc94019851cd35",
    "bool VFileAbstractWrapper::close(VFile* vf)": "60b0132710b58f08d88fe22ad30d21cc382ef9592e91772497cdc666e6e6cbe5",
    "off_t VFileAbstractWrapper::seek(VFile* vf, off_t offset, int whence)": "5ff472269218a71e4804e2915e1e03c96ba63605caad69078507762d7c847cdb",
    "ssize_t VFileAbstractWrapper::read(VFile* vf, void* buffer, size_t size)": "8d6ed2fd8d663c60fbba2a5869320723d2e143ab0b889e0e686b960aa4d0fb70",
    "ssize_t VFileAbstractWrapper::readline(VFile* vf, char* buffer, size_t size)": "37ba030ba348db90fffd9f232d7a13599aea0294e3b826afc9fb966f1427d03f",
    "ssize_t VFileAbstractWrapper::write(VFile* vf, const void* buffer, size_t size)": "3aabf3293a5642f70ebe5ad116d81413c27decdc69463e15f5160504d89f6508",
    "void* VFileAbstractWrapper::map(VFile*, size_t, int)": "815b4a626bdc3834412c1f3969b07ad8476182487408cac7ddc0042e8fc7a4cf",
    "void VFileAbstractWrapper::unmap(VFile*, void*, size_t)": "85da835fffe68e9fa35bfc331e5f5e04fdded28d120452cd1ff66541f9a8a819",
    "void VFileAbstractWrapper::truncate(VFile*, size_t)": "7597f0a064ddad637297aeb7fbb8e97c492a085f21ba9d8f8cadc66cb79c8da3",
    "ssize_t VFileAbstractWrapper::size(VFile* vf)": "20914c31966a5131a72a6b836686f288ff725d1a50c0f0148899ef72164501b2",
    "bool VFileAbstractWrapper::sync(VFile*, void*, size_t)": "b67c1786cecfefd5e46862b575df42fd3d3c38b5c526690a463243415c2d0200",
}

EXPECTED_LINES = (
    "PHASE1_QT_RESTORE_CASE rejected open=1 close=1 result=0 frame=0 state=0 "
    "backup_open=1 core_unchanged=1",
    "PHASE1_QT_RESTORE_CASE recovery result=1 frame=1 state=1 "
    "backup_open=0 core_original=1",
    "PHASE1_QT_RESTORE_CASE filename_retry open=1 close=1 result=1 frame=2 "
    "state=2 flags=70 core_updated=1",
    "PHASE1_QT_RESTORE_CASE open_failure open=1 close=0 thread_calls=0 "
    "signals_unchanged=1",
    "PHASE1_QT_RESTORE_CASE filename_open_failure "
    "thread_calls=1 core_calls=0 signals_unchanged=1",
)
TERMINAL = "PHASE1_QT_RESTORE_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")

FILE_FINDINGS = {
    "src/core/serialize.c": (
        "The pinned named-state loader returns false when fixed-size state extraction "
        "fails; that branch has no direct log call."
    ),
    "src/platform/qt/CoreController.cpp": (
        "The QIODevice and filename loaders capture a backup, propagate the core "
        "bool only into success signals, and close their input VFiles after either "
        "result; backup recovery also closes its temporary VFile."
    ),
    "src/platform/qt/CoreController.h": (
        "The public slots expose QIODevice and filename/slot load entrypoints plus "
        "stateLoaded, but no dedicated load-failed signal."
    ),
    "src/platform/qt/LoadSaveState.cpp": (
        "The slot-dialog selection dispatches a selected slot to CoreController and "
        "then closes the dialog."
    ),
    "src/platform/qt/LogController.cpp": (
        "Log forwarding is filter- and sink-dependent; a Qt-category ERROR may open "
        "a dialog, but this does not establish a dialog for core SAVESTATE failures."
    ),
    "src/platform/qt/VFileDevice.cpp": (
        "VFileDevice::wrap opens the QIODevice or returns null; the abstract wrapper "
        "delegates I/O and closes the device before deleting only its wrapper."
    ),
    "src/platform/qt/VFileDevice.h": (
        "The API declares filename opens, QIODevice-to-VFile wrapping and a "
        "VFileDevice owner; the test compiles against the pinned VFile ABI."
    ),
    "src/platform/qt/Window.cpp": (
        "The file-dialog user path dispatches a selected filename to the named "
        "CoreController load slot."
    ),
    "src/platform/sdl/main.c": (
        "SDL opens the optional user state path, runs _loadState on the core thread, "
        "ignores the loader bool, and closes the VFile afterward."
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *command):
    return subprocess.check_output(
        ["git", "-C", str(root), *command], text=True, stderr=subprocess.DEVNULL
    ).strip()


def extract_block(source, signature):
    require(source.count(signature) == 1, "missing or ambiguous source anchor: " + signature)
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for offset in range(brace, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced source block: " + signature)


def source_sha(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def expected_source_records():
    return [
        {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "review_scope": values[3],
            "execution_scope": values[4],
            "finding": FILE_FINDINGS[path],
        }
        for path, values in SOURCES.items()
    ]


def source_map(checkout, root):
    checkout = Path(checkout)
    root = Path(root)
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "upstream checkout is not the pinned revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "pinned upstream tree mismatch")
    dossier_path = root / DOSSIER
    raw_dossier = dossier_path.read_bytes()
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB and
            hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "compressed dossier identity mismatch")
    rows = {}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and path in SOURCES):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                require(path not in rows, "duplicate pinned dossier row: " + path)
                rows[path] = (
                    hashlib.sha256(canonical).hexdigest(),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                )
    require(set(rows) == set(SOURCES), "pinned dossier source inventory incomplete")
    sources = {}
    for path, (blob, digest, row_hash, _, _) in SOURCES.items():
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned Git blob mismatch: " + path)
        raw = (checkout / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 mismatch: " + path)
        require(rows[path] == (row_hash, blob, digest),
                "pinned dossier row/source identity mismatch: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "MPL-2.0 header missing: " + path)
        sources[path] = raw.decode("utf-8")
    return sources


def checked_bodies(sources):
    core = sources["src/platform/qt/CoreController.cpp"]
    vfile = sources["src/platform/qt/VFileDevice.cpp"]
    bodies = {}
    for signature, (path, expected_hash) in CALLER_BODIES.items():
        body = extract_block(sources[path], signature)
        if expected_hash:
            require(source_sha(body) == expected_hash,
                    "pinned extracted body hash mismatch: " + signature)
        bodies[signature] = body
    for signature, expected_hash in WRAPPER_METHODS.items():
        body = extract_block(vfile, signature)
        require(source_sha(body) == expected_hash,
                "pinned VFile wrapper body hash mismatch: " + signature)
        bodies[signature] = body
    require("void loadState(QIODevice* iodev, int flags = -1);" in
            sources["src/platform/qt/CoreController.h"],
            "pinned QIODevice load declaration missing")
    require("void loadBackupState();" in
            sources["src/platform/qt/CoreController.h"],
            "pinned backup load declaration missing")
    require("m_controller->loadState(filename);" in
            sources["src/platform/qt/Window.cpp"],
            "Qt filename user-load entrypoint changed")
    require("m_controller->loadState(slot);" in
            sources["src/platform/qt/LoadSaveState.cpp"],
            "Qt slot user-load entrypoint changed")
    require("mCoreLoadStateNamed(thread->core, _state, SAVESTATE_RTC);" in
            sources["src/platform/sdl/main.c"],
            "SDL load-state callback changed")
    require("mCoreThreadRunFunction(&thread, _loadState);" in
            sources["src/platform/sdl/main.c"] and
            "state->close(state);" in sources["src/platform/sdl/main.c"],
            "SDL user-load ownership chain changed")
    require("if (!state) {" in extract_block(
        sources["src/core/serialize.c"], "bool mCoreLoadStateNamed(") and
        "return false;" in extract_block(
            sources["src/core/serialize.c"], "bool mCoreLoadStateNamed("),
            "pinned core load result branch changed")
    require("emit controller->stateLoaded();" in bodies[
        "void CoreController::loadState(QIODevice* iodev, int flags)"] and
        "vf->close(vf);" in bodies[
            "void CoreController::loadState(QIODevice* iodev, int flags)"],
        "Qt caller success or cleanup branch changed")
    require("if (!mLogFilterTest(&m_filter, category, static_cast<mLogLevel>(level)))" in
            sources["src/platform/qt/LogController.cpp"] and
            "category == s_qtCat && level == mLOG_ERROR" in
            sources["src/platform/qt/LogController.cpp"],
            "Qt conditional log presentation changed")
    return bodies


def reject_source_mutations(bodies):
    cases = (
        ("void CoreController::loadState(QIODevice* iodev, int flags)",
         "vf->close(vf);", "/* omitted close */"),
        ("void CoreController::loadState(QIODevice* iodev, int flags)",
         "if (!m_stateVf) {", "if (m_stateVf) {"),
        ("void CoreController::loadState(QIODevice* iodev, int flags)",
         "if (mCoreLoadStateNamed(", "if (true || mCoreLoadStateNamed("),
        ("VFile* VFileDevice::wrap(QIODevice* iodev, QIODevice::OpenMode mode)",
         "if (!iodev->open(mode)) {", "if (iodev->open(mode)) {"),
        ("bool VFileAbstractWrapper::close(VFile* vf)",
         "iodev->close();", "/* omitted device close */"),
        ("void CoreController::loadState(const QString& path, int flags)",
         "vf->close(vf);", "/* omitted named input close */"),
        ("VFile* VFileDevice::open(const QString& path, int mode)",
         "return VFileOpen(path.toUtf8().constData(), mode);",
         "return nullptr;"),
    )
    for signature, before, after in cases:
        body = bodies[signature]
        require(body.count(before) == 1, "source mutation anchor changed")
        mutated = body.replace(before, after, 1)
        try:
            expected_hash = CALLER_BODIES.get(signature, (None, None))[1]
            if expected_hash is None:
                expected_hash = WRAPPER_METHODS[signature]
            require(source_sha(mutated) == expected_hash,
                    "pinned body hash mismatch: " + signature)
        except ValueError:
            continue
        raise ValueError("source mutation escaped: " + signature)
    return len(cases)


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "Qt restore witness terminal marker missing or duplicated")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES, "Qt restore witness observations changed")
    return {
        "rejected_state": {
            "load_result": False,
            "qiodevice_closed": True,
            "success_signals": 0,
            "backup_retained": True,
            "core_unchanged": True,
        },
        "backup_recovery": {
            "load_result": True,
            "backup_closed": True,
            "success_signals": 1,
            "original_state_restored": True,
        },
        "filename_retry": {
            "load_result": True,
            "qiodevice_closed": True,
            "success_signals": 2,
            "requested_flags_observed": 0x46,
        },
        "open_failure": {
            "device_close_calls": 0,
            "core_callback_invoked": False,
            "success_signals_unchanged": True,
        },
        "filename_open_failure": {
            "core_callback_invoked": True,
            "mcore_load_or_save_called": False,
            "success_signals_unchanged": True,
        },
    }


def reject_output_mutations(output):
    mutations = (
        output.replace("close=1", "close=0", 1),
        output.replace("result=0", "result=1", 1),
        output.replace("frame=0 state=0", "frame=1 state=0", 1),
        output.replace("backup_open=0", "backup_open=1", 1),
        output.replace("flags=70", "flags=17", 1),
        output.replace("thread_calls=0", "thread_calls=1", 1),
        output.replace("signals_unchanged=1", "signals_unchanged=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for mutated in mutations:
        try:
            parse_output(mutated)
        except ValueError:
            continue
        raise ValueError("contradictory Qt restore output escaped")
    return len(mutations)


def expected_receipt():
    expected_output = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    bodies = {
        signature: digest
        for signature, (_, digest) in CALLER_BODIES.items()
        if digest is not None
    }
    bodies.update(WRAPPER_METHODS)
    return {
        "schema": "phase1.mgba.qt-restore-caller.v1",
        "repository": "mgba-emu/mgba",
        "pinned_revision": PIN,
        "pinned_tree": TREE,
        "machine_dossier": {
            "path": DOSSIER,
            "git_blob": DOSSIER_BLOB,
            "compressed_sha256": DOSSIER_SHA256,
        },
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "evidence_class": (
            "COMPILED_EXTRACTED_PINNED_QT_QIODEVICE_AND_FILENAME_CALLERS_"
            "AND_VFILE_WRAPPER_"
            "WITH_NATIVE_QT6CORE_AND_HOST_CORE_THREAD_FIXTURES"
        ),
        "source_records": expected_source_records(),
        "extracted_original_body_sha256": bodies,
        "source_call_graph": [
            "Qt Window file dialog -> CoreController::loadState(filename); "
            "LoadSaveState slot dialog -> CoreController::loadState(slot).",
            "The tested original QIODevice overload calls VFileDevice::wrap; the "
            "tested filename overload calls VFileDevice::open. Both capture a "
            "backup, call mCoreLoadStateNamed on the core thread, emit "
            "frameAvailable/stateLoaded only on true, and close their temporary "
            "input VFile after the callback.",
            "VFileDevice::open is the original pinned forwarder; this harness "
            "substitutes only VFileOpen with a Qt QBuffer fixture, then executes "
            "the original filename CoreController method and wrapper close path.",
            "VFileDevice::wrap opens the caller-owned QIODevice and returns null "
            "on open failure; its abstract VFile wrapper delegates read/seek and "
            "close closes the QIODevice then deletes the wrapper.",
            "mCoreLoadStateNamed returns false when mCoreExtractState cannot "
            "produce fixed-size state; this source branch has no direct log call. "
            "The Qt load slot has no explicit false-result signal.",
            "Qt LogController presentation remains filter/sink/category dependent; "
            "the Qt-category error dialog is not evidence that savestate failures "
            "are presented.",
            "SDL's optional state path opens a VFile, runs _loadState on the core "
            "thread, ignores mCoreLoadStateNamed's bool, and closes the VFile.",
        ],
        "observations": parse_output(expected_output),
        "source_mutations_rejected": 7,
        "output_mutations_rejected": 8,
        "limitations": {
            "compiled_original_corecontroller_qiodevice_loadstate_body": True,
            "compiled_original_corecontroller_filename_loadstate_body": True,
            "compiled_original_corecontroller_loadbackupstate_body": True,
            "compiled_original_vfiledevice_open_wrap_and_abstract_wrapper_bodies": True,
            "native_qt6core_qiodevice": True,
            "pinned_vfile_abi_header": True,
            "core_thread_execution": "SYNCHRONOUS_HOST_FIXTURE",
            "mcore_save_and_load_implementation": "HOST_FIXTURE_NOT_PINNED_CORE",
            "backup_memory_file": "HOST_FIXTURE_NOT_PINNED_VFILEMEMCHUNK",
            "full_qt_frontend_build": False,
            "qt_widgets_or_window_execution": False,
            "qt_filename_overload_execution": True,
            "native_filesystem_open": False,
            "vfileopen_implementation": "HOST_QBUFFER_FIXTURE",
            "qt_log_controller_execution": False,
            "sdl_frontend_build_or_execution": False,
            "prior_libretro_caller_behavior_repeated": False,
            "native_filesystem_state_file_or_natural_malformed_state": False,
            "durable_savestate_or_save_data": False,
            "stock_gameplay_or_physical_flash": False,
            "transitive_distribution_licensing_resolved": False,
        },
        "prior_evidence": {
            "libretro_caller_receipt": (
                "docs/phase1-review-readiness/"
                "mgba-savestate-caller-integration-20261109.json"
            ),
            "overlap": (
                "Reuses prior core restore concepts only; this witness executes "
                "the distinct Qt QIODevice caller and Qt VFile wrapper."
            ),
            "frontend_runtime_feasibility": (
                "docs/phase1-review-readiness/"
                "mgba-frontend-runtime-feasibility-20261106.json"
            ),
            "known_blocker": (
                "The full pinned Qt frontend was previously not buildable in the "
                "recorded configurations; this native Qt6Core extracted-method "
                "witness does not claim a full frontend."
            ),
        },
        "licensing": {
            "all_source_records_mpl_2_0": True,
            "upstream_modified": False,
            "transitive_distribution_licensing_resolved": False,
        },
    }


def verify_receipt(root):
    path = Path(root) / RECEIPT
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt == expected_receipt(),
            "Qt restore caller receipt differs from fail-closed contract")
    return receipt


def run(checkout, root, harness_path):
    sources = source_map(checkout, root)
    bodies = checked_bodies(sources)
    source_mutations = reject_source_mutations(bodies)
    output_mutations = reject_output_mutations(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    )
    receipt = verify_receipt(root)
    harness_path = Path(root) / harness_path
    harness = harness_path.read_text(encoding="utf-8")
    if HARNESS_SHA256 is not None:
        require(hashlib.sha256(harness.encode()).hexdigest() == HARNESS_SHA256,
                "Qt restore harness hash mismatch")

    insertions = {
        "PHASE1_INSERT_PINNED_VFILE_ABSTRACT_WRAPPER_CLASS":
            bodies["class VFileAbstractWrapper : public VFile"] + ";",
        "PHASE1_INSERT_PINNED_VFILE_ABSTRACT_WRAPPER_METHODS":
            "\n\n".join(
                bodies[signature] for signature in WRAPPER_METHODS
                if signature != "VFileAbstractWrapper::VFileAbstractWrapper(QIODevice* iodev)"
            ) + "\n" + bodies[
                "VFileAbstractWrapper::VFileAbstractWrapper(QIODevice* iodev)"
            ],
        "PHASE1_INSERT_PINNED_QT_VFILE_WRAP":
            bodies["VFile* VFileDevice::wrap(QIODevice* iodev, QIODevice::OpenMode mode)"],
        "PHASE1_INSERT_PINNED_QT_VFILE_OPEN":
            bodies["VFile* VFileDevice::open(const QString& path, int mode)"],
        "PHASE1_INSERT_PINNED_QT_LOADSTATE_QIODEVICE":
            bodies["void CoreController::loadState(QIODevice* iodev, int flags)"],
        "PHASE1_INSERT_PINNED_QT_LOADSTATE_FILENAME":
            bodies["void CoreController::loadState(const QString& path, int flags)"],
        "PHASE1_INSERT_PINNED_QT_LOADBACKUPSTATE":
            bodies["void CoreController::loadBackupState()"],
    }
    expanded = harness
    for marker, body in insertions.items():
        require(expanded.count(marker) == 1,
                "missing or ambiguous harness insertion marker: " + marker)
        expanded = expanded.replace(marker, body, 1)

    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True
    ).split()
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-qt-restore-") as temp:
        source_path = Path(temp) / "qt_restore.cpp"
        binary_path = Path(temp) / "qt_restore"
        source_path.write_text(expanded, encoding="utf-8")
        compiled = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
             "-Werror", "-I", str(Path(checkout) / "include"),
             str(source_path), "-o", str(binary_path), *flags],
            capture_output=True, text=True, timeout=60,
        )
        require(compiled.returncode == 0,
                "native Qt6Core caller witness compile failed:\n" +
                compiled.stderr[-8000:])
        executed = subprocess.run(
            [str(binary_path)], capture_output=True, text=True, timeout=20
        )
        require(executed.returncode == 0,
                "Qt restore caller witness failed:\n" +
                executed.stdout + executed.stderr)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations == receipt["source_mutations_rejected"] and
                output_mutations == receipt["output_mutations_rejected"],
                "Qt witness does not match its receipt")
    print(
        "PHASE1_MGBA_QT_RESTORE_CALLER "
        f"pinned={PIN} sources={len(SOURCES)} "
        f"source_mutations_rejected={source_mutations} "
        f"output_mutations_rejected={output_mutations} "
        f"qt6core={subprocess.check_output(['pkg-config', '--modversion', 'Qt6Core'], text=True).strip()}"
    )
    print(executed.stdout, end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--harness", default=HARNESS)
    args = parser.parse_args()
    run(args.checkout, args.root, args.harness)


if __name__ == "__main__":
    main()

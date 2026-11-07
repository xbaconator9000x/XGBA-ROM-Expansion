#!/usr/bin/env python3
"""Verify and execute the pinned mGBA headless save-sync lifecycle."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import signal
import struct
import subprocess
import tempfile
import time
from pathlib import Path

_BASE_SPEC = importlib.util.spec_from_file_location(
    "phase1_mgba_frontend_runtime_feasibility",
    Path(__file__).resolve().with_name("phase1_mgba_frontend_runtime_feasibility.py"),
)
_BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE)

DOSSIER = _BASE.DOSSIER
DOSSIER_BLOB = _BASE.DOSSIER_BLOB
DOSSIER_SHA256 = _BASE.DOSSIER_SHA256
PIN = _BASE.PIN
TREE = _BASE.TREE
git = _BASE.git
require = _BASE.require

MATRIX = (
    "docs/phase1-review-readiness/"
    "mgba-headless-runtime-sync-20261106.json"
)

SOURCES = {
    "src/platform/headless-main.c": (
        "61110b1e84a25f702b5e7d158887d93b150e1b66",
        "51687802777b8e831622e28fbd278782084e4c0d65e1ba28b7c1dec4e5617c68",
        "7cd9f22ce4878d5f9cab92adbe4b26a011a3fd6fbce9f21f7e20668be5c16e4e",
        "reuse_existing_feasibility_review",
        "Pinned headless startup, script loading, run loop, and SIGINT cleanup caller.",
        {74: "signal(SIGINT, _headlessShutdown);", 211: "mScriptContextLoadFile(&scriptContext", 227: "core->runLoop(core);", 232: "core->unloadROM(core);"},
    ),
    "src/core/core.c": (
        "17edcde68b8d4f0885c6c6ddd17c4e6ca64701f8",
        "94b5dc1cec2d9b157ef2933681c644a6dfb43dcebe9f6b887d68b104ac640ea5",
        "6e453bae6a2dd590ac92ce6f86821a8e342dcc34f9f762836152bdad9b49e989",
        "reuse_existing_feasibility_review",
        "Script-facing file open returns the core loadSave result; it is not headless autoload.",
        {244: "bool mCoreLoadSaveFile(", 245: "VFileOpen(path, O_CREAT | O_RDWR);",
         247: "return false;", 252: "return core->loadSave(core, vf);"},
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "bounded_new_runtime_path_review",
        "VFileOpen dispatches this POSIX fd build to VFileOpenFD; the failed open is returned as NULL.",
        {22: "struct VFile* VFileOpen(const char* path, int flags) {",
         100: "return VFileOpenFD(path, flags);"},
    ),
    "src/core/scripting.c": (
        "7ccb51e897685ce24b37dabc76beb27427331b4f",
        "8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1",
        "9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8",
        "bounded_new_runtime_path_review",
        "Binds loadSaveFile and memory bus writes into the Lua-visible core adapter.",
        {495: "mSCRIPT_DECLARE_STRUCT_METHOD(mCore, BOOL, loadSaveFile", 527: "mSCRIPT_DECLARE_STRUCT_VOID_D_METHOD(mCore, busWrite8", 1450: "void mScriptContextAttachCore("},
    ),
    "src/script/context.c": (
        "fbed31862e349042073eee2487094e4206f00e16",
        "ea826939374515b914e0fc93684f982e0171eeca939aa1d0b7fa1dab91cf8d2e",
        "47ba093eaf4471acb1d0328831e477ad68db0e57f18f2cc011c7a02f95439409",
        "bounded_new_runtime_path_review",
        "Selects the registered scripting engine and reports script load/run failure.",
        {161: "void mScriptContextRegisterEngines(", 414: "bool mScriptContextLoadVF(", 431: "bool mScriptContextLoadFile(", 436: "bool ret = mScriptContextLoadVF(context, path, vf);"},
    ),
    "src/script/engines/lua.c": (
        "7168ffd1dff7112805779f3ad059cbf71b04cf8b",
        "3bcdc874c03c13128e7599d4d9129766a935159ed4cd49e7e20cb57ee666825e",
        "916f1e89a99f15db27a3e93c88ea0269e6b329e11f3b759f2f866401c2f658da",
        "bounded_new_runtime_path_review",
        "Creates a Lua engine, opens Lua standard libraries, and routes print through mGBA logging.",
        {403: "struct mScriptEngineContext* _luaCreate(", 417: "luaContext->lua = luaL_newstate();", 420: "luaL_openlibs(luaContext->lua);", 438: "_luaPrintShim"},
    ),
    "src/script/stdlib.c": (
        "f84b62515315c119ec4ff5b9fb6df4de4517c738",
        "52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99",
        "db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1",
        "dependency_identity_only",
        "Script stdlib support is an identity-bound dependency, not a new whole-file review.",
        {},
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
        "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
        "reuse_existing_feasibility_review",
        "Core loadSave/GBALoadSave uses the GBA's real savedata VFile.",
        {656: "return GBALoadSave(core->board, vf);"},
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
        "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
        "reuse_existing_feasibility_review",
        "GBA frame-end cleaning attempts VFile sync and emits INFO without exposing a result.",
        {969: "GBASavedataClean(&gba->memory.savedata", 1005: "wasDirty && !gba->memory.savedata.dirty"},
    ),
    "src/gba/memory.c": (
        "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
        "4b18ab8b7b5f947457093503c6c085e0ba6677f321255d140720cb2965b07f54",
        "bounded_new_runtime_path_review",
        "The script bus write to SRAM autodetects SRAM and marks it dirty.",
        {1064: "if (memory->savedata.type == GBA_SAVEDATA_AUTODETECT)", 1069: "mLOG(GBA_MEM, INFO, \"Detected SRAM savegame\");", 1083: "memory->savedata.dirty |= mSAVEDATA_DIRT_NEW;"},
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
        "reuse_existing_savedata_review",
        "Sync failure logs INFO after the dirty-clean decision and has no returned status.",
        {586: "void GBASavedataClean(", 596: "savedata->vf->sync(savedata->vf", 600: "mLOG(GBA_SAVE, INFO, \"Savedata failed to sync!\");"},
    ),
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
        "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
        "reuse_existing_vfs_review",
        "Native POSIX mapped-file callback and teardown use msync(MS_ASYNC) and msync(MS_SYNC); injected EIO tests these host boundaries.",
        {151: "static void _vfdUnmap(", 153: "msync(memory, size, MS_SYNC);",
         154: "munmap(memory, size);", 246: "static bool _vfdSync(",
         258: "return msync(buffer, size, MS_ASYNC) == 0;"},
    ),
    "src/core/log.c": (
        "39d6db88cad3ca6f521a532c114b6488adb77279",
        "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
        "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
        "dependency_identity_only",
        "Previously source-reviewed logger dependency; emitted messages remain INFO-filter-dependent.",
        {},
    ),
}

DEPENDENCY_EDGES = [
    ["headless-main.c", "mScriptContextLoadFile"],
    ["core/scripting.c", "mCore.loadSaveFile BOOL binding"],
    ["core/core.c", "mCoreLoadSaveFile -> VFileOpen(path, O_CREAT | O_RDWR)"],
    ["util/vfs.c", "VFileOpen -> VFileOpenFD"],
    ["util/vfs/vfs-fd.c", "VFileOpenFD -> POSIX open"],
    ["headless-main.c", "mScriptContextAttachCore"],
    ["core/scripting.c", "mCoreLoadSaveFile"],
    ["core/core.c", "GBALoadSave"],
    ["gba/core.c", "GBASavedataLoad"],
    ["gba/memory.c", "GBASavedataInitSRAM"],
    ["gba/gba.c", "GBASavedataClean"],
    ["gba/savedata.c", "VFile.sync"],
    ["util/vfs/vfs-fd.c", "msync(MS_ASYNC)"],
    ["headless-main.c", "core->unloadROM(core)"],
    ["util/vfs/vfs-fd.c", "_vfdUnmap -> msync(MS_SYNC) -> munmap"],
    ["gba/savedata.c", "mLOG(GBA_SAVE, INFO)"],
    ["script/context.c", "script/engines/lua.c"],
    ["script/engines/lua.c", "core/scripting.c Lua core adapter"],
]


def expected_matrix():
    return {
        "schema": "phase1.mgba.headless-runtime-sync.v2",
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
        "evidence_class": "COMPILED_PINNED_HEADLESS_PROCESS_WITH_HOST_FAULT_INJECTION",
        "source_records": [
            {
                "path": path,
                "git_blob": data[0],
                "full_source_sha256": data[1],
                "canonical_dossier_row_sha256": data[2],
                "license": "MPL-2.0",
                "review_scope": data[3],
                "role": data[4],
                "anchors": [
                    {"line": line, "contains": needle}
                    for line, needle in data[5].items()
                ],
            }
            for path, data in SOURCES.items()
        ],
        "dependency_edges": DEPENDENCY_EDGES,
        "reopen_failure_contract": {
            "caller": "A later headless Lua script calls mCore.loadSaveFile(path, false) on an existing .sav.",
            "pinned_call_path": "Lua BOOL binding -> mCoreLoadSaveFile -> VFileOpen -> VFileOpenFD -> POSIX open.",
            "host_fault": "The LD_PRELOAD test interposer targets only that exact existing save path and returns -1/EIO before the host open.",
            "expected_api_result": False,
            "expected_script_observation": "loadSaveFile=false",
            "expected_headless_process_exit_status": 0,
            "expected_headless_script_load_error_log": False,
            "recovery_control": "A later separate headless process reopens the unchanged save and reads the pre-fault SRAM byte.",
            "evidence_class": "COMPILED_PINNED_HEADLESS_PROCESS_WITH_HOST_OPEN_FAULT_INJECTION",
            "persistence_claim": False,
            "status": "REQUIRED_IN_EXISTING_CI",
        },
        "path_contract": {
            "caller": "Original pinned mgba-headless main; --script calls the pinned mCore script adapter's loadSaveFile and write8 methods.",
            "save_open": "Script-mediated mCoreLoadSaveFile(path, temporary=false), not headless autoload.",
            "write": "Script busWrite8 targets GBA SRAM, which the pinned core detects and marks dirty.",
            "sync": "Real pinned GBAFrameEnded -> GBASavedataClean -> VFile sync -> Linux vfs-fd msync(MS_ASYNC).",
            "fault_injection": "LD_PRELOAD interposer matches only the mapped .sav path and can make only the selected MS_ASYNC callback or MS_SYNC unmap msync return -1/EIO; it does not replace mGBA savedata logic.",
            "backend_sync_distinction": "The savedata callback uses msync(MS_ASYNC); teardown unmap separately calls msync(MS_SYNC). Each injected case targets only one operation and records both results.",
            "shutdown": "Harness sends SIGINT only after the sync event; headless exits 0 through its normal signal cleanup path.",
            "reopen_failure": "A second script-mediated loadSaveFile call encounters a path-specific injected POSIX open EIO; the Lua caller records false, then a later fresh process performs an ordinary reopen control.",
        },
        "local_execution": {
            "pinned_headless_binary_built": True,
            "lua_scripting_enabled": True,
            "synthetic_rom_used": True,
            "sync_success_control": {
                "host_backend_call": "msync(MS_ASYNC) returned success",
                "teardown_unmap_call": "msync(MS_SYNC) returned success",
                "mGBA_log": "Savedata synced",
                "save_sync_callback_attempts": 1,
                "teardown_unmap_attempts": 1,
                "process_exit_status": 0,
            },
            "injected_sync_failure": {
                "host_backend_call": "msync(MS_ASYNC) returned -1 with errno EIO",
                "teardown_unmap_call": "msync(MS_SYNC) returned success",
                "mGBA_log": "Savedata failed to sync!",
                "save_sync_callback_attempts": 1,
                "teardown_unmap_attempts": 1,
                "additional_save_sync_callbacks": 0,
                "process_exit_status": 0,
                "error_propagated_to_process_status": False,
            },
            "teardown_sync_failure": {
                "callback_ms_async": "success",
                "teardown_ms_sync": "returned -1 with errno EIO",
                "unmap_ms_sync_return_observed_by_mGBA": False,
                "mGBA_log_for_teardown_error": None,
                "process_exit_status": 0,
            },
            "cold_process_reopen_after_failed_sync": {
                "separate_headless_process": True,
                "preceded_by_successful_teardown_unmap": True,
                "script_loadSaveFile_succeeded": True,
                "script_read_sram_byte": "0x43",
                "process_exit_status": 0,
            },
            "cold_process_reopen_after_teardown_failure": {
                "separate_headless_process": True,
                "script_loadSaveFile_succeeded": True,
                "script_read_sram_byte": "0x44",
                "process_exit_status": 0,
                "same_os_page_cache_durability_claim": False,
            },
            "native_frontend_ui_observed": False,
            "full_gui_frontend_observed": False,
            "durable_persistence_or_power_loss_observed": False,
            "physical_flash_observed": False,
            "stock_gameplay_observed": False,
            "independent_semantic_approval": False,
            "gate_or_approval_state_changed": False,
        },
        "limitations": [
            "This runs the exact pinned headless executable and real GBA core/VFile code, but the ROM and Lua script are controlled synthetic inputs.",
            "Lua calls loadSaveFile explicitly; this does not change or prove the default headless startup autoload path.",
            "The msync failure is host-level injected EIO, not a physical storage failure or frontend UI observation.",
            "A second process reads the OS-visible .sav after the callback msync failure, but shutdown's separate MS_SYNC unmap succeeded first; the read is not attributable to the failed callback and is not proof of durable storage, power-loss survival, or independent media persistence.",
            "The headless process exit code is 0 after callback sync failure; the INFO logger is the observed failure channel, not a propagated process error. Teardown separately issues an MS_SYNC unmap flush.",
            "The distinct final MS_SYNC teardown error is injected in the compiled headless process; pinned void _vfdUnmap ignores the msync result and emits no teardown-specific mGBA log. A fresh process observes the same-host OS-visible byte, not evidence that the failed flush persisted data.",
            "The distinct save-reopen failure case injects EIO at the host open boundary for an existing .sav, observes the original script API's false result, and checks a later ordinary reopen; that same-host read is not durable-storage evidence.",
            "Only the newly added VFile dispatcher receives bounded runtime-path review for the reopen case; other dependency identities are reused or dependency-only and are not counted as new whole-file reviews.",
        ],
        "distribution_notice": (
            "All upstream source records are MPL-2.0. Preserve upstream notices and the repository license when redistributing combined artifacts; this package includes provenance and test harness code, not copied upstream implementation."
        ),
    }


def validate_matrix(payload):
    require(payload == expected_matrix(), "headless runtime matrix differs from the fail-closed contract")
    require(payload["status"] == "NEEDS_EVIDENCE" and payload["overall"] == "FAIL_INCOMPLETE",
            "runtime witness cannot be treated as independent semantic approval")
    require(payload["local_execution"]["injected_sync_failure"]["error_propagated_to_process_status"] is False,
            "the pinned headless return channel does not propagate this sync failure")
    require(payload["local_execution"]["native_frontend_ui_observed"] is False,
            "a headless process must not be relabeled as GUI frontend UI")
    require(payload["local_execution"]["durable_persistence_or_power_loss_observed"] is False,
            "process reopen cannot establish durable persistence")
    require(payload["local_execution"]["teardown_sync_failure"]["unmap_ms_sync_return_observed_by_mGBA"] is False,
            "pinned POSIX unmap has no result channel")
    require(payload["local_execution"]["cold_process_reopen_after_teardown_failure"]["same_os_page_cache_durability_claim"] is False,
            "cold reopen after teardown failure cannot establish persistence")
    reopen = payload["reopen_failure_contract"]
    require(reopen["expected_api_result"] is False
            and reopen["expected_script_observation"] == "loadSaveFile=false"
            and reopen["expected_headless_process_exit_status"] == 0,
            "the caller-observed open failure must not be changed into success or process failure")
    require(reopen["persistence_claim"] is False
            and reopen["status"] == "REQUIRED_IN_EXISTING_CI",
            "a same-host reopen control is not a persistence receipt")
    return True


def _canonical_source_rows(root):
    rows = {}
    with gzip.open(root / DOSSIER, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba"
                    and provenance.get("pinned_revision") == PIN
                    and path in SOURCES):
                canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
                require(path not in rows, "duplicate pinned dossier row " + path)
                rows[path] = hashlib.sha256(canonical).hexdigest()
    return rows


def verify_checkout(checkout, root=None):
    checkout = Path(checkout)
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    require(git(checkout, "rev-parse", "HEAD") == PIN, "source checkout is not the pinned revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE, "source checkout tree changed")
    dossier = root / DOSSIER
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB, "dossier Git blob changed")
    require(hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256, "dossier compressed hash changed")
    rows = _canonical_source_rows(root)
    require(set(rows) == set(SOURCES), "pinned dossier source set mismatch")
    for path, values in SOURCES.items():
        blob, source_hash, row_hash = values[:3]
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob, "pinned blob mismatch: " + path)
        raw = (checkout / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == source_hash, "pinned source hash mismatch: " + path)
        require(rows[path] == row_hash, "dossier row hash mismatch: " + path)
        text = raw.decode("utf-8")
        require("Mozilla Public" in text and "License, v. 2.0." in text, "MPL notice missing: " + path)
        for line, needle in values[5].items():
            lines = text.splitlines()
            require(line <= len(lines) and needle in lines[line - 1],
                    "pinned source anchor mismatch: %s:%d" % (path, line))
    require(hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256,
            "compressed dossier hash mismatch")
    return True


def _lua_string(value):
    return json.dumps(str(value))


def _make_rom(path):
    rom = bytearray(0x10000)
    struct.pack_into("<I", rom, 0, 0xEA00002E)
    rom[0xA0:0xAC] = b"XGBASAVEDEMO"
    rom[0xAC:0xB0] = b"XGBA"
    rom[0xB0:0xB2] = b"01"
    rom[0xB2] = 0x96
    rom[0xBD] = (-sum(rom[0xA0:0xBD]) - 0x19) & 0xFF
    struct.pack_into("<II", rom, 0xC0, 0xEF000003, 0xEAFFFFFE)
    path.write_bytes(rom)


def _wait_and_interrupt(process, event_path, log_path, release_path=None, event_operation=None, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("headless process exited before event: " + log_path.read_text(errors="replace")[-2000:])
        event_seen = event_path.exists() and event_path.stat().st_size
        if event_seen and event_operation:
            event_seen = any(
                line.startswith("operation=" + event_operation + " ")
                for line in event_path.read_text(encoding="utf-8").splitlines()
            )
        if event_seen:
            if release_path:
                release_path.touch()
            process.send_signal(signal.SIGINT)
            break
        time.sleep(0.005)
    else:
        process.kill()
        process.wait()
        raise RuntimeError("timed out waiting for native save event: " + str(event_path))
    try:
        return process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RuntimeError("headless process did not exit after SIGINT")


def _run(headless, script, rom, directory, name, sync_path=None, inject_operation=None,
         harness=None, event_operation=None, open_target=None):
    log_path = directory / (name + ".log")
    marker = directory / (name + ".marker")
    release = directory / (name + ".release")
    env = os.environ.copy()
    library_path = str(headless.resolve().parent)
    if env.get("LD_LIBRARY_PATH"):
        library_path += os.pathsep + env["LD_LIBRARY_PATH"]
    env["LD_LIBRARY_PATH"] = library_path
    if sync_path is not None or open_target is not None:
        env["LD_PRELOAD"] = str(harness.resolve())
    else:
        env.pop("LD_PRELOAD", None)
    if sync_path is not None:
        env["XGBA_SYNC_TARGET"] = str(sync_path.resolve())
        env["XGBA_SYNC_MARKER"] = str(marker)
        env["XGBA_SYNC_RELEASE"] = str(release)
        env["XGBA_SYNC_INJECT_OPERATION"] = inject_operation or ""
    else:
        env.pop("XGBA_SYNC_TARGET", None)
        env.pop("XGBA_SYNC_MARKER", None)
        env.pop("XGBA_SYNC_RELEASE", None)
        env.pop("XGBA_SYNC_INJECT_OPERATION", None)
    if open_target is not None:
        env["XGBA_OPEN_TARGET"] = str(open_target.resolve())
        env["XGBA_OPEN_MARKER"] = str(directory / (name + ".open-marker"))
    else:
        env.pop("XGBA_OPEN_TARGET", None)
        env.pop("XGBA_OPEN_MARKER", None)
    with log_path.open("wb") as output:
        process = subprocess.Popen(
            [str(headless), "-l", "8", "-S", "3", "--script", str(script), str(rom)],
            stdout=output,
            stderr=subprocess.STDOUT,
            env=env,
        )
        exit_status = _wait_and_interrupt(
            process,
            marker,
            log_path,
            release_path=release if sync_path is not None else None,
            event_operation=event_operation,
        )
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return exit_status, marker.read_text(encoding="utf-8") if marker.exists() else "", text, log_path


def execute_runtime(headless, harness, root=None):
    headless = Path(headless).resolve()
    harness = Path(harness).resolve()
    require(headless.is_file() and os.access(headless, os.X_OK), "pinned headless executable is unavailable")
    require(harness.is_file(), "native msync interposer source is unavailable")
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="phase1-mgba-headless-sync-") as temp:
        directory = Path(temp)
        interposer = directory / "libsync-control.so"
        subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
             str(harness), "-ldl", "-o", str(interposer)],
            check=True, capture_output=True, text=True,
        )
        rom = directory / "probe.gba"
        _make_rom(rom)
        write_script = directory / "write.lua"
        positive_save = directory / "positive.sav"
        failed_save = directory / "failed.sav"
        positive_save.write_bytes(b"\xff" * 32768)
        failed_save.write_bytes(b"\xff" * 32768)

        def save_script(save, value):
            return (
                "assert(emu:loadSaveFile(" + _lua_string(save) + ", false))\n"
                "print(\"SCRIPT_SAVE_OPENED\")\n"
                "emu:write8(0x0E000000, " + str(value) + ")\n"
                "print(\"SCRIPT_SRAM_WRITE_SENT\")\n"
                "for i = 1, 17 do emu:runFrame() end\n"
            )

        write_script.write_text(save_script(positive_save, 0x42), encoding="utf-8")
        pos_exit, pos_marker, pos_log, _ = _run(
            headless, write_script, rom, directory, "positive",
            sync_path=positive_save, harness=interposer,
        )
        write_script.write_text(save_script(failed_save, 0x43), encoding="utf-8")
        fail_exit, fail_marker, fail_log, _ = _run(
            headless, write_script, rom, directory, "failure",
            sync_path=failed_save, inject_operation="async", harness=interposer,
        )
        teardown_save = directory / "teardown-failure.sav"
        teardown_save.write_bytes(b"\xff" * 32768)
        write_script.write_text(save_script(teardown_save, 0x44), encoding="utf-8")
        teardown_exit, teardown_marker, teardown_log, _ = _run(
            headless, write_script, rom, directory, "teardown-failure",
            sync_path=teardown_save, inject_operation="sync", harness=interposer,
            event_operation="async",
        )

        open_failure_script = directory / "reopen-open-failure.lua"
        open_failure_script.write_text(
            "local loaded = emu:loadSaveFile(" + _lua_string(positive_save) + ", false)\n"
            "local f = assert(io.open(" + _lua_string(directory / "reopen-open-failure.marker")
            + ", \"w\"))\n"
            "f:write(\"loadSaveFile=\" .. tostring(loaded) .. \"\\n\")\n"
            "f:close()\n"
            "assert(loaded == false)\n"
            "print(\"SAVE_REOPEN_OPEN_FAILURE_CAUGHT\")\n",
            encoding="utf-8",
        )
        save_before_open_failure = hashlib.sha256(positive_save.read_bytes()).hexdigest()
        open_failure_exit, open_failure_marker, open_failure_log, _ = _run(
            headless, open_failure_script, rom, directory, "reopen-open-failure",
            harness=interposer, open_target=positive_save,
        )
        open_fault_marker_path = directory / "reopen-open-failure.open-marker"
        open_fault_marker = (
            open_fault_marker_path.read_text(encoding="utf-8")
            if open_fault_marker_path.exists() else ""
        )
        save_after_open_failure = hashlib.sha256(positive_save.read_bytes()).hexdigest()

        reopen_marker = directory / "reopen.marker"
        reopen_script = directory / "reopen.lua"
        reopen_script.write_text(
            "assert(emu:loadSaveFile(" + _lua_string(failed_save) + ", false))\n"
            "local value = emu:read8(0x0E000000)\n"
            "assert(value == 0x43)\n"
            "local f = assert(io.open(" + _lua_string(reopen_marker) + ", \"w\"))\n"
            "f:write(string.format(\"loaded=true value=%02X\\n\", value))\n"
            "f:close()\n"
            "print(\"COLD_PROCESS_SAV_REOPEN_OK\")\n",
            encoding="utf-8",
        )
        reopen_exit, _, reopen_log, _ = _run(
            headless, reopen_script, rom, directory, "reopen",
        )
        reopened = reopen_marker.read_text(encoding="utf-8").strip() if reopen_marker.exists() else ""
        teardown_reopen_marker = directory / "teardown-reopen.marker"
        teardown_reopen_script = directory / "teardown-reopen.lua"
        teardown_reopen_script.write_text(
            "assert(emu:loadSaveFile(" + _lua_string(teardown_save) + ", false))\n"
            "local value = emu:read8(0x0E000000)\n"
            "assert(value == 0x44)\n"
            "local f = assert(io.open(" + _lua_string(teardown_reopen_marker) + ", \"w\"))\n"
            "f:write(string.format(\"loaded=true value=%02X\\n\", value))\n"
            "f:close()\n"
            "print(\"COLD_PROCESS_TEARDOWN_REOPEN_OK\")\n",
            encoding="utf-8",
        )
        teardown_reopen_exit, _, teardown_reopen_log, _ = _run(
            headless, teardown_reopen_script, rom, directory, "teardown-reopen",
        )
        teardown_reopened = (
            teardown_reopen_marker.read_text(encoding="utf-8").strip()
            if teardown_reopen_marker.exists() else ""
        )

        recovery_marker = directory / "open-failure-recovery.marker"
        recovery_script = directory / "open-failure-recovery.lua"
        recovery_script.write_text(
            "assert(emu:loadSaveFile(" + _lua_string(positive_save) + ", false))\n"
            "local value = emu:read8(0x0E000000)\n"
            "assert(value == 0x42)\n"
            "local f = assert(io.open(" + _lua_string(recovery_marker) + ", \"w\"))\n"
            "f:write(string.format(\"loaded=true value=%02X\\n\", value))\n"
            "f:close()\n"
            "print(\"OPEN_FAILURE_RECOVERY_REOPEN_OK\")\n",
            encoding="utf-8",
        )
        recovery_exit, _, recovery_log, _ = _run(
            headless, recovery_script, rom, directory, "open-failure-recovery",
        )
        recovered = recovery_marker.read_text(encoding="utf-8").strip() if recovery_marker.exists() else ""

        require(pos_exit == 0 and fail_exit == 0 and teardown_exit == 0
                and open_failure_exit == 0 and reopen_exit == 0
                and teardown_reopen_exit == 0 and recovery_exit == 0,
                "headless process exit status changed")
        pos_async = [line for line in pos_marker.splitlines() if line.startswith("operation=async ")]
        pos_sync = [line for line in pos_marker.splitlines() if line.startswith("operation=sync ")]
        fail_async = [line for line in fail_marker.splitlines() if line.startswith("operation=async ")]
        fail_sync = [line for line in fail_marker.splitlines() if line.startswith("operation=sync ")]
        require(len(pos_async) == 1 and "injected=0 result=0" in pos_async[0],
                "successful sync control was not observed exactly once: "
                + repr(pos_marker) + " / " + repr(pos_log))
        require(len(pos_sync) == 1 and "injected=0 result=0" in pos_sync[0],
                "successful teardown unmap flush was not observed exactly once: " + repr(pos_marker))
        require(len(fail_async) == 1 and "injected=1 result=-1" in fail_async[0],
                "EIO callback sync injection was not observed exactly once: " + repr(fail_marker))
        require(len(fail_sync) == 1 and "injected=0 result=0" in fail_sync[0],
                "teardown unmap flush after injected failure was not observed: " + repr(fail_marker))
        teardown_async = [
            line for line in teardown_marker.splitlines() if line.startswith("operation=async ")
        ]
        teardown_sync = [
            line for line in teardown_marker.splitlines() if line.startswith("operation=sync ")
        ]
        require(len(teardown_async) == 1 and "injected=0 result=0" in teardown_async[0],
                "teardown case did not first complete its MS_ASYNC callback: " + repr(teardown_marker))
        require(len(teardown_sync) == 1 and "injected=1 result=-1" in teardown_sync[0],
                "final MS_SYNC EIO was not observed exactly once: " + repr(teardown_marker))
        require(teardown_log.count("Savedata synced") == 1
                and "Savedata failed to sync!" not in teardown_log,
                "teardown failure changed the callback logger contract")
        require(pos_log.count("Savedata synced") == 1,
                "successful mGBA sync log was not observed exactly once")
        require(fail_log.count("Savedata failed to sync!") == 1,
                "failed-sync INFO log was not observed exactly once")
        require("COLD_PROCESS_SAV_REOPEN_OK" in reopen_log and reopened == "loaded=true value=43",
                "separate-process save reopen/read did not match the injected-run value: "
                + repr(reopened) + " / " + repr(reopen_log))
        require(
            "COLD_PROCESS_TEARDOWN_REOPEN_OK" in teardown_reopen_log
            and teardown_reopened == "loaded=true value=44",
            "fresh process did not observe the OS-visible byte after injected teardown EIO: "
            + repr(teardown_reopened) + " / " + repr(teardown_reopen_log),
        )
        require(open_fault_marker == "operation=open injected=1 result=-1 errno=EIO\n"
                or open_fault_marker == "operation=open64 injected=1 result=-1 errno=EIO\n",
                "targeted existing-save open EIO was not observed exactly once: "
                + repr(open_fault_marker))
        require(open_failure_marker.strip() == "loadSaveFile=false",
                "the original script API caller did not observe the failed save reopen: "
                + repr(open_failure_marker) + " / " + repr(open_failure_log))
        require(save_before_open_failure == save_after_open_failure,
                "injected failed reopen modified the pre-existing save file")
        require("Failed to load script" not in open_failure_log,
                "the handled false result was incorrectly propagated as a headless script-load failure")
        require(
            "OPEN_FAILURE_RECOVERY_REOPEN_OK" in recovery_log
            and recovered == "loaded=true value=42",
            "fresh process did not reopen the unchanged save after the injected open failure: "
            + repr(recovered) + " / " + repr(recovery_log),
        )
        return {
            "pinned_headless_binary_sha256": hashlib.sha256(headless.read_bytes()).hexdigest(),
            "native_interposer_sha256": hashlib.sha256(interposer.read_bytes()).hexdigest(),
            "synthetic_rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
            "success": {
                "exit_status": pos_exit,
                "sync_marker": pos_marker.strip(),
                "sync_log": "Savedata synced",
                "save_sync_callback_attempts": len(pos_async),
                "teardown_unmap_attempts": len(pos_sync),
            },
            "injected_failure": {
                "exit_status": fail_exit,
                "sync_marker": fail_marker.strip(),
                "sync_log": "Savedata failed to sync!",
                "save_sync_callback_attempts": len(fail_async),
                "additional_save_sync_callbacks": len(fail_async) - 1,
                "teardown_unmap_attempts": len(fail_sync),
                "errno": "EIO",
                "error_propagated_to_process_status": False,
            },
            "teardown_failure": {
                "exit_status": teardown_exit,
                "sync_marker": teardown_marker.strip(),
                "callback_ms_async": "success",
                "teardown_ms_sync": "injected EIO",
                "mGBA_log": "Savedata synced",
                "teardown_error_logged_by_mGBA": False,
                "mGBA_unmap_error_return_channel": False,
                "cold_reopen": teardown_reopened,
                "cold_reopen_exit_status": teardown_reopen_exit,
                "cold_reopen_durability_claim": False,
            },
            "reopen_failure": {
                "exit_status": open_failure_exit,
                "host_open_marker": open_fault_marker.strip(),
                "script_result_marker": open_failure_marker.strip(),
                "mGBA_script_load_error_logged": "Failed to load script" in open_failure_log,
                "preexisting_save_sha256_before": save_before_open_failure,
                "preexisting_save_sha256_after": save_after_open_failure,
                "save_unchanged": save_before_open_failure == save_after_open_failure,
                "error_propagated_to_process_status": False,
                "separate_process_recovery_reopen": recovered,
                "recovery_exit_status": recovery_exit,
                "same_os_page_cache_durability_claim": False,
            },
            "cold_reopen": {
                "exit_status": reopen_exit,
                "marker": reopened,
                "read_byte": "0x43",
                "same_os_page_cache_durability_claim": False,
            },
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, help="exact pinned mGBA checkout")
    parser.add_argument("--headless", required=True, help="compiled pinned mgba-headless executable")
    parser.add_argument("--harness", required=True, help="msync injection interposer source")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root)
    verify_checkout(args.checkout, root)
    payload = json.loads((root / MATRIX).read_text(encoding="utf-8"))
    validate_matrix(payload)
    execution = execute_runtime(args.headless, args.harness, root)
    print("PHASE1_MGBA_HEADLESS_RUNTIME_SYNC " + json.dumps(execution, sort_keys=True))


if __name__ == "__main__":
    main()

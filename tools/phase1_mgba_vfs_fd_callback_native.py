#!/usr/bin/env python3
"""Compile and run pinned mGBA savedata-failure callback paths on Linux."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FILES = {
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "src/gba/video.c": (
        "28f072ec0b880d272f4f9564cc5ca8f5af389caf",
        "77f6bd32b19a5e78f06b0826cf3b5135abfcc3be24e08bd278829cdc564eda4d",
    ),
    "include/mgba/internal/defines.h": (
        "67b8ec8fd2f51ee2c0c6231443af752158397b03",
        "167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
    ),
    "include/mgba-util/vector.h": (
        "c837379e2102ca6535db2b292233bd4983c3532c",
        "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
    ),
    "include/mgba/core/interface.h": (
        "b5ffa3049749b9141aa09fc3693bf758a13f4e13",
        "da6ea4e344c46be5943859a24c0149c12a803b3e951c07140cc795cab09651de",
    ),
    "src/core/scripting.c": (
        "7ccb51e897685ce24b37dabc76beb27427331b4f",
        "8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1",
    ),
    "src/script/stdlib.c": (
        "f84b62515315c119ec4ff5b9fb6df4de4517c738",
        "52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99",
    ),
    "src/core/log.c": (
        "39d6db88cad3ca6f521a532c114b6488adb77279",
        "7f320ca361e0d4d6c846e6bcc8833d82d884bb3defd9b6ca800c7af9f065b170",
    ),
    "src/platform/qt/CoreController.cpp": (
        "183cea418a70963bd5332ef66bdff54a0dcccd46",
        "8ca7ca7b26fa030ef76322085a6f634b5e3ca4fd40a4e6549b6a12abace260b2",
    ),
    "src/platform/qt/Window.cpp": (
        "af6592985329f08898cf078a666763954383c832",
        "67fcb2da1d2990e20bf57fd78f51881ce6a62a193cbabb5af5c3ec8fae29dea3",
    ),
    "src/platform/sdl/main.c": (
        "91f22bd593d4952076c2a9a11da5a8d6951db2a8",
        "8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b",
    ),
    "src/platform/libretro/libretro.c": (
        "12e79131c38e06a8ba46cef97e0872ec51544e38",
        "da8800c76929e25729573760b6180452cdefa824aa6df21b51c3566553ad67ac",
    ),
}
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROWS = {
    "src/util/vfs/vfs-fd.c": "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
    "src/gba/savedata.c": "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
    "src/gba/gba.c": "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
    "src/gba/video.c": "20c76a3c969ef4b98f090290b1183872d6c87cb4f68521375e5f5369d16479c0",
    "include/mgba/internal/defines.h": "05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2",
    "include/mgba/core/interface.h": "093b18935d1a1968f5ce81caa23611a578cc8810a03bde39f3e3f55d0d6b2830",
    "src/core/scripting.c": "9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8",
    "src/script/stdlib.c": "db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1",
    "src/core/log.c": "a446ca3d2c3895cae2b2e15f0a888f1e427df79162eabb3b75d37f66981f42bb",
    "src/platform/qt/CoreController.cpp": "1cbedd6e36f387b7c579bcea8c77bed82e9c3e8b18954974847c647dcf8b0f28",
    "src/platform/qt/Window.cpp": "21da719393e20ace0bb1a7080aa8fc1d674fb10072d27fbbe06c74454d4a2398",
    "src/platform/sdl/main.c": "9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c",
    "src/platform/libretro/libretro.c": "70da3c3b8a3280ad6d077f9998fc73d69b443505d2d13dfee3dae791105f5f18",
}
CLEAN_SIGNATURE = (
    "void GBASavedataClean(struct GBASavedata* savedata, uint32_t frameCount)"
)
CLEAN_BODY_SHA256 = "3fc3989ccac6c04fa32780fcffcb5cd49ff22ff306826e569c85d52647f701bb"
DIRTY_HELPER_SIGNATURE = (
    "static inline bool mSavedataClean(int* dirty, uint32_t* dirtAge, "
    "uint32_t frameCount)"
)
DIRTY_HELPER_SHA256 = "c34a3ce89da1f2e1823314ea38692d471a762746aa4d9d020c2faa50263d9fcb"
FRAME_ENDED_SIGNATURE = "void GBAFrameEnded(struct GBA* gba)"
FRAME_ENDED_SHA256 = "79da6a49b3bdb7101a950cef81837a5f18d2f1bda6294fa3ffe589ae25679942"
FRAME_CALLER_SIGNATURE = (
    "void _startHdraw(struct mTiming* timing, void* context, uint32_t cyclesLate)"
)
FRAME_CALLER_SHA256 = "831f441ef1f338c939c7bebfb2d4b90273edcf510ef19710d10c70fa41c6284c"
UNLOAD_SIGNATURE = "void GBAUnloadROM(struct GBA* gba)"
UNLOAD_SHA256 = "1c7090ddfe712b836048af6492dedb4f8c4d2ec94ac0f30f3b8e92648071b7f6"
DEINIT_SIGNATURE = "void GBASavedataDeinit(struct GBASavedata* savedata)"
DEINIT_SHA256 = "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2"
SCRIPTING_MACRO_SHA256 = "3857ee6e17aaf6f8874466bdd6df62f3dbee68af3babd9e35d09fae5ddaffc5f"
SCRIPT_CALLBACK_SHA256 = "86988bda927d9c4508caaea271a399d68e3052154e662cf57b0ee5c9671aeadb"
FIXTURE_SHA256 = "97316d7965f440239308548f8182068e407fdf6d6a8894d9e31dc759e9ed7b3b"
LOGGER_FUNCTION_HASHES = {
    "struct mLogger* mLogGetThreadLogger(void)": "3d970d27d308e3254cf4378e700a0a976312ef1338350788cd3da6c9dad78991",
    "struct mLogger* mLogGetContext(void)": "741c7b1d0d604d083ec96cec49dfadf59826794d37ea8bb6c2412f3cad82b0bf",
    "void mLogSetDefaultLogger(struct mLogger* logger)": "9b2a934daaf6a20a3f6815e83acab6be9e564b3323421522a4a403772d019597",
    "void mLog(int category, enum mLogLevel level, const char* format, ...)": "7de1b3df9d9db21bb6a537dd3d7c7089f1728795eb06f1eecc2ed851d858b523",
}
FRONTEND_NO_CALLBACK = (
    "src/platform/qt/CoreController.cpp",
    "src/platform/qt/Window.cpp",
    "src/platform/sdl/main.c",
    "src/platform/libretro/libretro.c",
)
CASE_PATTERN = re.compile(
    r"^PHASE1_GBA_CALLBACK_CASE failure_async_ms=((?:0|[1-9][0-9]*)) failure_rtc=((?:0|[1-9][0-9]*)) "
    r"failure_dirty=((?:0|-?[1-9][0-9]*)) failure_script_events=((?:0|[1-9][0-9]*)) retry_async_ms=((?:0|[1-9][0-9]*)) "
    r"retry_script_events=((?:0|[1-9][0-9]*)) retry_rtc=((?:0|[1-9][0-9]*)) new_write_success_async_ms=((?:0|[1-9][0-9]*)) "
    r"success_rtc=((?:0|[1-9][0-9]*)) success_script_events=((?:0|[1-9][0-9]*)) "
    r"failure_info_logs=((?:0|[1-9][0-9]*)) failure_info_message=((?:0|[1-9][0-9]*)) "
    r"failure_info_level=((?:0|[1-9][0-9]*)) success_info_logs=((?:0|[1-9][0-9]*)) "
    r"persistence_ack=((?:0|[1-9][0-9]*))$"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, *, timeout=60, cwd=None):
    return subprocess.run(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout
    )


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def extract_function(source, signature):
    require(source.count(signature) == 1,
            "missing or ambiguous pinned function: " + signature)
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced pinned function: " + signature)


def verify_sources(source_root, checkout_identity):
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
    sources = {}
    for path, (blob, digest) in FILES.items():
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned source tree blob changed: " + path)
        source_path = source_root / path
        raw = source_path.read_bytes()
        require(git(source_root, "hash-object", path) == blob,
                "pinned source worktree blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier = root / DOSSIER
    require(dossier.is_file(), "pinned machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "machine-dossier Git blob changed")
    require(hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256,
            "machine-dossier SHA-256 changed")
    found = {}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    path not in DOSSIER_ROWS):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(hashlib.sha256(canonical).hexdigest() ==
                    DOSSIER_ROWS[path],
                    "canonical machine-dossier row changed: " + path)
            require(provenance.get("git_blob_sha") == FILES[path][0] and
                    provenance.get("source_content_sha256") == FILES[path][1],
                    "machine-dossier source identity changed: " + path)
            require(path not in found, "duplicate machine-dossier row: " + path)
            found[path] = True
    require(set(found) == set(DOSSIER_ROWS),
            "machine dossier is missing a callback-closure row")

    clean = extract_function(sources["src/gba/savedata.c"], CLEAN_SIGNATURE)
    require(hashlib.sha256(clean.encode()).hexdigest() == CLEAN_BODY_SHA256,
            "GBASavedataClean body hash changed")
    require(clean.count(
        "savedata->vf->sync(savedata->vf, savedata->data, size)") == 1,
        "cleanup VFile sync callback anchor changed")
    require(clean.count("GBASavedataRTCWrite(savedata);") == 1 and
            clean.index("GBASavedataRTCWrite(savedata);") >
            clean.index("savedata->vf->sync(savedata->vf, savedata->data, size)"),
            "RTC write no longer follows successful sync branch")
    deinit = extract_function(
        sources["src/gba/savedata.c"], DEINIT_SIGNATURE
    )
    require(hashlib.sha256(deinit.encode()).hexdigest() == DEINIT_SHA256 and
            deinit.index("savedata->vf->unmap(savedata->vf, savedata->data, size)") <
            deinit.index("savedata->vf = NULL;"),
            "savedata deinit no longer unmaps before dropping the VFile")

    frame = extract_function(sources["src/gba/gba.c"], FRAME_ENDED_SIGNATURE)
    require(hashlib.sha256(frame.encode()).hexdigest() == FRAME_ENDED_SHA256,
            "GBAFrameEnded body hash changed")
    order = (
        "int wasDirty = gba->memory.savedata.dirty;",
        "GBASavedataClean(&gba->memory.savedata, gba->video.frameCounter);",
        "if (callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty) {",
        "callbacks->savedataUpdated(callbacks->context);",
    )
    offsets = [frame.index(anchor) for anchor in order]
    require(offsets == sorted(offsets), "GBA savedata callback order changed")
    frame_caller = extract_function(
        sources["src/gba/video.c"], FRAME_CALLER_SIGNATURE
    )
    require(hashlib.sha256(frame_caller.encode()).hexdigest() ==
            FRAME_CALLER_SHA256 and
            frame_caller.index("case GBA_VIDEO_VERTICAL_PIXELS:") <
            frame_caller.index("GBAFrameEnded(video->p);") <
            frame_caller.index("mCoreSyncPostFrame(video->p->sync);"),
            "VBlank frame-end caller sequence changed")
    unload = extract_function(sources["src/gba/gba.c"], UNLOAD_SIGNATURE)
    require(hashlib.sha256(unload.encode()).hexdigest() == UNLOAD_SHA256 and
            unload.index("GBASavedataDeinit(&gba->memory.savedata);") <
            unload.index("gba->memory.savedata.realVf->close("),
            "GBA unload no longer deinitializes savedata before closing realVf")

    helper = extract_function(
        sources["include/mgba/internal/defines.h"], DIRTY_HELPER_SIGNATURE
    )
    require(hashlib.sha256(helper.encode()).hexdigest() == DIRTY_HELPER_SHA256 and
            "frameCount - *dirtAge > mSAVEDATA_CLEANUP_THRESHOLD" in helper and
            "*dirty = 0;" in helper,
            "dirty-state transition semantics changed")

    script = sources["src/core/scripting.c"]
    macro_start = script.index("#define mCoreCallback(NAME)")
    macro_end = script.index("\nDEFINE_CALLBACK(frame)", macro_start)
    macro_source = script[macro_start:macro_end]
    require(hashlib.sha256(macro_source.encode()).hexdigest() ==
            SCRIPTING_MACRO_SHA256,
            "script callback macro source changed")
    callback_source = "DEFINE_CALLBACK(savedataUpdated)"
    require(hashlib.sha256(callback_source.encode()).hexdigest() ==
            SCRIPT_CALLBACK_SHA256 and
            macro_source.count("mScriptContextTriggerCallback(scriptContext, #NAME, NULL);") == 1,
            "script callback implementation source changed")
    attach = extract_function(
        script, "void mScriptContextAttachCore(struct mScriptContext* context, struct mCore* core)"
    )
    registration = ".savedataUpdated = mCoreCallback(savedataUpdated),"
    callback_context = ".context = context"
    require(attach.count(registration) == 1 and
            attach.count(callback_context) == 1 and
            attach.index(registration) < attach.index(callback_context),
            "pinned scripting callback registration is absent or ambiguous")
    require("The emulation has just finished modifying save data" in
            sources["src/script/stdlib.c"],
            "pinned script API callback description changed")
    interface = sources["include/mgba/core/interface.h"]
    require(interface.count("void (*savedataUpdated)(void* context);") == 1,
            "core callback interface member changed")

    logger = sources["src/core/log.c"]
    logger_functions = {}
    for signature, expected_hash in LOGGER_FUNCTION_HASHES.items():
        body = extract_function(logger, signature)
        require(hashlib.sha256(body.encode()).hexdigest() == expected_hash,
                "pinned core logger function changed: " + signature)
        logger_functions[signature] = body
    require(logger.count("static struct mLogger* _defaultLogger = NULL;") == 1,
            "pinned logger default context changed")

    no_registration = {
        path: "savedataUpdated" not in sources[path]
        for path in FRONTEND_NO_CALLBACK
    }
    require(all(no_registration.values()),
            "frontend callback scan changed: " + repr(no_registration))
    registration_block = registration + "\n.context = context,"
    return (
        sources, clean, frame, macro_source, callback_source, registration_block,
        logger_functions,
    )


def reject_source_mutations(sources, macro_source):
    mutations = (
        (sources["src/gba/savedata.c"], CLEAN_SIGNATURE,
         CLEAN_BODY_SHA256,
         'mLOG(GBA_SAVE, INFO, "Savedata failed to sync!");',
         'mLOG(GBA_SAVE, ERROR, "Savedata failed to sync!");'),
        (sources["src/gba/gba.c"], FRAME_ENDED_SIGNATURE,
         FRAME_ENDED_SHA256,
         "callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty",
         "callbacks->savedataUpdated && wasDirty"),
        (sources["src/gba/savedata.c"], CLEAN_SIGNATURE,
         CLEAN_BODY_SHA256,
         "savedata->vf->sync(savedata->vf, savedata->data, size)",
         "savedata->vf->sync(savedata->vf, NULL, 0)"),
        (macro_source, None, SCRIPTING_MACRO_SHA256,
         "mScriptContextTriggerCallback(scriptContext, #NAME, NULL);",
         "/* trigger removed */"),
    )
    for original, signature, expected_hash, anchor, replacement in mutations:
        require(original.count(anchor) == 1,
                "source mutation anchor missing or ambiguous: " + anchor)
        changed = original.replace(anchor, replacement, 1)
        if signature:
            try:
                changed = extract_function(changed, signature)
            except ValueError:
                continue
        if hashlib.sha256(changed.encode()).hexdigest() == expected_hash:
            raise ValueError("pinned-source mutation escaped validation: " + anchor)
    require(sources["src/gba/gba.c"].count(
        "callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty"
    ) == 1, "callback mutation control anchor changed")
    return len(mutations)


def parse_output(output):
    marker = "PHASE1_GBA_CALLBACK_DONE\n"
    require(output.endswith(marker) and output.count(marker) == 1,
            "native callback output missing unique terminal marker")
    case = output[:-len(marker)].removesuffix("\n")
    match = CASE_PATTERN.fullmatch(case)
    require(match is not None, "native callback evidence missing or malformed")
    values = tuple(int(value) for value in match.groups())
    expected = (1, 0, 0, 1, 0, 1, 0, 2, 1, 2, 1, 1, 8, 1, 0)
    require(values == expected,
            "native callback outcome does not match failed/success controls")
    return {
        "failed_sync_calls": values[0],
        "failed_sync_rtc_writes": values[1],
        "failed_sync_dirty_after_clean": values[2],
        "script_notifications_after_failed_sync": values[3],
        "sync_retries_without_new_write": values[4],
        "script_notifications_after_clean_next_frame": values[5],
        "rtc_writes_after_clean_next_frame": values[6],
        "sync_calls_after_new_write_then_success": values[7],
        "rtc_writes_after_success": values[8],
        "script_notifications_after_success": values[9],
        "failed_sync_info_log_events": values[10],
        "failed_sync_info_message_matches": values[11],
        "failed_sync_info_level": values[12],
        "successful_sync_info_log_events": values[13],
        "persistence_acknowledgment": values[14],
    }


def reject_evidence_mutations(output):
    changes = (
        output.replace("failure_script_events=1", "failure_script_events=0", 1),
        output.replace("retry_async_ms=0", "retry_async_ms=1", 1),
        output.replace("retry_script_events=1", "retry_script_events=0", 1),
        output.replace("retry_rtc=0", "retry_rtc=1", 1),
        output.replace("success_rtc=1", "success_rtc=0", 1),
        output.replace("success_script_events=2", "success_script_events=1", 1),
        output.replace("failure_info_logs=1", "failure_info_logs=0", 1),
        output.replace("failure_info_message=1", "failure_info_message=0", 1),
        output.replace("failure_info_level=8", "failure_info_level=2", 1),
        output.replace("success_info_logs=1", "success_info_logs=0", 1),
        output.replace("persistence_ack=0", "persistence_ack=1", 1),
        output.replace("PHASE1_GBA_CALLBACK_DONE\n",
                       "PHASE1_GBA_CALLBACK_DONE\nPHASE1_GBA_CALLBACK_DONE\n"),
        output.replace("PHASE1_GBA_CALLBACK_DONE\n", ""),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("callback evidence mutation escaped")
    return len(changes)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    source_root = (args.checkout or args.source_dir).resolve()
    checkout_identity = bool(args.checkout)
    sources, clean, frame, macro_source, callback_source, registration, logger_functions = (
        verify_sources(source_root, checkout_identity)
    )
    source_mutations_rejected = reject_source_mutations(
        sources, macro_source
    )

    fixture = args.harness.read_text(encoding="utf-8")
    fixture_digest = hashlib.sha256(fixture.encode()).hexdigest()
    require(fixture_digest == FIXTURE_SHA256,
            "native callback fixture SHA-256 changed")
    replacements = {
        "PHASE1_INSERT_SCRIPT_CALLBACK_MACROS":
            macro_source + callback_source + "\n",
        "PHASE1_INSERT_SCRIPT_CALLBACK_REGISTRATION": registration,
        "PHASE1_INSERT_PINNED_GBASAVEDATACLEAN": clean,
        "PHASE1_INSERT_PINNED_GBAFRAMEENDED": frame,
        "PHASE1_INSERT_PINNED_LOGGER_GLOBAL":
            "static struct mLogger* _defaultLogger = NULL;",
        "PHASE1_INSERT_PINNED_LOGGER_FUNCTIONS": "\n".join(
            logger_functions.values()
        ) + "\n",
    }
    expanded = fixture
    for marker, body in replacements.items():
        require(expanded.count(marker) == 1, "harness extraction marker drift: " + marker)
        expanded = expanded.replace(marker, body)

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-gba-callback-") as directory:
        directory = Path(directory)
        source_path = directory / "gba-callback-native.c"
        binary = directory / "gba-callback-native"
        source_path.write_text(expanded, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-DDISABLE_THREADING",
            "-DENABLE_VFS_FD",
            "-I", str(source_root / "include"), "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter",
            str(source_root / "src/util/vfs/vfs-fd.c"), str(source_path),
            "-Wl,--wrap=msync", "-o", str(binary),
        ]
        compiled = run(command, timeout=90)
        require(compiled.returncode == 0,
                "native callback harness compilation failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "native callback harness failed:\n" + executed.stdout)
        output = executed.stdout
        try:
            observations = parse_output(output)
        except ValueError as error:
            raise ValueError(str(error) + ":\n" + output) from error
        evidence_mutations_rejected = reject_evidence_mutations(output)
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "class": "PINNED_MGBA_GBA_SAVEDATA_FAILED_SYNC_CALLBACK_NATIVE",
        "mgba_commit": PIN,
        "source_tree_identity_verified": checkout_identity,
        "source_git_blobs": {path: value[0] for path, value in FILES.items()},
        "source_sha256": {path: value[1] for path, value in FILES.items()},
        "machine_dossier_blob": DOSSIER_BLOB,
        "machine_dossier_sha256": DOSSIER_SHA256,
        "machine_dossier_row_sha256": DOSSIER_ROWS,
        "GBASavedataClean_body_sha256": CLEAN_BODY_SHA256,
        "GBAFrameEnded_body_sha256": FRAME_ENDED_SHA256,
        "GBAFrameEnded_caller_body_sha256": FRAME_CALLER_SHA256,
        "GBASavedataDeinit_body_sha256": DEINIT_SHA256,
        "GBAUnloadROM_body_sha256": UNLOAD_SHA256,
        "mSavedataClean_body_sha256": DIRTY_HELPER_SHA256,
        "scripting_callback_macro_sha256": SCRIPTING_MACRO_SHA256,
        "scripting_callback_invocation_sha256": SCRIPT_CALLBACK_SHA256,
        "fixture_sha256": fixture_digest,
        "original_vfs_fd_translation_unit_compiled": True,
        "original_GBASavedataClean_body_executed": True,
        "original_GBAFrameEnded_body_executed": True,
        "original_script_callback_macro_and_registration_compiled": True,
        "frontend_registration_scan": {
            path: "NO_SAVEDATA_UPDATED_REFERENCE" for path in FRONTEND_NO_CALLBACK
        },
        "compiler_version": subprocess.check_output(
            ["gcc", "--version"], text=True
        ).splitlines()[0],
        "compile_command": command,
        "artifact_sha256": artifact_sha256,
        "source_mutations_rejected": source_mutations_rejected,
        "evidence_mutations_rejected": evidence_mutations_rejected,
        "observations": observations,
        "raw_output": output.splitlines(),
        "full_gba_translation_unit_compiled": False,
        "power_loss_durability_tested": False,
        "stock_gameplay_tested": False,
        "sav_restart_tested": False,
        "physical_flash_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_GBA_CALLBACK_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()

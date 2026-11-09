#!/usr/bin/env python3
"""Verify and execute the pinned mCoreAutoloadSave POSIX VFile path."""
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
PREVIOUS_RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-core-loadsave-allocation-recovery-20261107.json"
)
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-core-autoload-save-ownership-20261107.json"
)

SOURCES = {
    "src/core/core.c": (
        "17edcde68b8d4f0885c6c6ddd17c4e6ca64701f8",
        "94b5dc1cec2d9b157ef2933681c644a6dfb43dcebe9f6b887d68b104ac640ea5",
        "6e453bae6a2dd590ac92ce6f86821a8e342dcc34f9f762836152bdad9b49e989",
        "COMPILED_EXTRACTED_MCORE_AUTOLOAD_SAVE_BODY",
    ),
    "src/core/directories.c": (
        "2337f5d47c8db428c62da13afa2743afa6d83f1e",
        "a878d5eada8bf7443061d571f6cdd998d1f19934381278cca415275dc245d0f4",
        "d589bb948b805041abe73209873e21525b69ef9fc92e6e3a501cacc4e83658dd",
        "COMPILED_EXTRACTED_OPEN_SUFFIX_BODY",
    ),
    "src/util/vfs/vfs-dirent.c": (
        "806148b8965a3020d37af3a0cdb77cc5f514f340",
        "a5572f969bd358a1ce14b779d423a4f7af928766dc9b124ff0bbb4e7fe67c15c",
        "a0237ba84d23261f27495244cf6401c03e70c732a47c21993fa73d4a853b1625",
        "COMPILED_ORIGINAL_POSIX_VDIR_TRANSLATION_UNIT",
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "COMPILED_ORIGINAL_VFILE_DISPATCH_TRANSLATION_UNIT",
    ),
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
        "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
        "COMPILED_ORIGINAL_POSIX_VFILE_FD_TRANSLATION_UNIT",
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
        "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
        "SOURCE_TRACED_GBA_LOADSAVE_CALLBACK_NOT_COMPILED",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
        "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
        "SOURCE_TRACED_GBA_SAVE_LOADER_NOT_COMPILED",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
        "SOURCE_TRACED_GBA_SAVEDATA_LIFECYCLE_NOT_COMPILED",
    ),
    "src/platform/sdl/main.c": (
        "91f22bd593d4952076c2a9a11da5a8d6951db2a8",
        "8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b",
        "9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c",
        "SOURCE_TRACED_SDL_CALLSITE_NOT_COMPILED",
    ),
    "src/platform/qt/CoreManager.cpp": (
        "459846c61103b77645a4170ebd784599cb4cbe79",
        "1961c67b62916f301b76620a01a30479d79fe2c807d47990753914a8cef3d753",
        "6e8985a122d48aa5ddd00854c325bd87bb16ff30f49425a4500a8b09fb45edcc",
        "SOURCE_TRACED_QT_CALLSITE_NOT_COMPILED",
    ),
    "include/mgba/core/core.h": (
        "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
        "e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9",
        "0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87",
        "SOURCE_TRACED_MCORE_CALLBACK_INTERFACE",
    ),
    "include/mgba/core/directories.h": (
        "5d65be8a3dbf8b062565aea186e64f9edf72f1e5",
        "5b05c8373421f85d05752c19e71d989d4afc782eca03586ffe1f594ba1437685",
        "43c9324ac29140feb07758c6f1b244183a78c9e4ad8d4a740f0ee6ebf89c1655",
        "SOURCE_TRACED_DIRECTORY_INTERFACE",
    ),
    "include/mgba/core/config.h": (
        "4a68b49eed99a7b874fbcf971df853f778f8dfd0",
        "010093e4be456563d787661ff7f0c05dff6ec925d772e9e92aac41b963df78fb",
        "cf31fc3ff0f5fc0b5157724823d83541273e273f3c261c3aff5aa8fe86926677",
        "SOURCE_TRACED_CONFIG_INTERFACE",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/string.h": (
        "bc29e28d71bbb4cbb51261a9ded26399c019fb2e",
        "80434f7f78cf6fa0bb60a7d3fcc4fe2ee09acf8ac14295a8c9e5c9a6a8715a9d",
        "6c046cb5d36c75862236163fb73973c308d6f61d1c93470e5ce69fc1940ccc77",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/vector.h": (
        "c837379e2102ca6535db2b292233bd4983c3532c",
        "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
        "6a1179a47870dc93b443eff57599611d1b8d43d87560de25863a9e5805d83eb7",
        "COMPILED_INTERFACE",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
        "5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070",
        "COMPILED_INTERFACE",
    ),
}

CALLER_SIGNATURE = "bool mCoreAutoloadSave(struct mCore* core)"
CALLER_BODY_SHA256 = "c0f1ef5babb3aa2b325d188cbad0ec146ba382913a5668f5c5520ac737110eb2"
SUFFIX_SIGNATURE = (
    "struct VFile* mDirectorySetOpenSuffix(struct mDirectorySet* dirs, "
    "struct VDir* dir, const char* suffix, int mode)"
)
SUFFIX_BODY_SHA256 = "68003098204e66066dba75241f562a4eecba5a11af7d28b729875843a4ea3445"
VDIR_OPEN_SIGNATURE = "struct VDir* VDirOpen(const char* path)"
VDIR_OPEN_BODY_SHA256 = "a5b809ab86975077c02abe647894742d9200a4426a07144bd16ef21d9fd6ba10"
VDIR_FILE_SIGNATURE = (
    "struct VFile* _vdOpenFile(struct VDir* vd, const char* path, int mode) {"
)
VDIR_FILE_BODY_SHA256 = "c93a90b080905d037a03aca462e116bea4cbe5309f6dabbd5631f459fe6ead93"
DISPATCH_SIGNATURE = "struct VFile* VFileOpen(const char* path, int flags)"
DISPATCH_BODY_SHA256 = "e41233c9f3694959554a63cb8ef2a2fdb456f245a11b26e79a533ff1e1c7a137"
OPEN_SIGNATURE = "struct VFile* VFileOpenFD(const char* path, int flags)"
OPEN_BODY_SHA256 = "1e166c42b6f3ae8a3c1f8b9886e5a00dd1282645dfd37c720c83b1ac1f31ff3e"
FROM_FD_SIGNATURE = "struct VFile* VFileFromFD(int fd)"
FROM_FD_BODY_SHA256 = "13cb910fdbbafbe0712bc985e9f1be0b03f01cd5a61c31173879e491ca3fef63"
OLD_CALLER_BODY_SHA256 = "623abab0e9024f839ebd661ae941e1bc386280db728beff527394d3d46328efe"
HARNESS_SHA256 = "05aa7cfe7cb39b953fc1d1ad1b3b40cf35414ef154c5a84ba49b7f0705c86a38"
TERMINAL = "PHASE1_AUTOLOAD_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")

EXPECTED_LINES = (
    "PHASE1_AUTOLOAD_CASE success return=1 target_opens=1 "
    "allocation_attempts=1 allocation_failures=0 save_callbacks=1 "
    "null_callbacks=0 close_calls=1 target_fd_open=0",
    "PHASE1_AUTOLOAD_CASE allocation_failure return=0 target_opens=1 "
    "allocation_attempts=1 allocation_failures=1 save_callbacks=1 "
    "null_callbacks=1 close_calls=0 leaked_fd_open=1",
    "PHASE1_AUTOLOAD_CASE retry failure_return=0 retry_return=1 "
    "target_opens=2 allocation_attempts=2 allocation_failures=1 "
    "save_callbacks=2 null_callbacks=1 close_calls=1 "
    "leaked_first_fd_open=1 retry_fd_closed=1",
    "PHASE1_AUTOLOAD_CASE missing_save_directory return=0 target_opens=0 "
    "allocation_attempts=0 save_callbacks=0",
)

OBJECTION_NOTES = [
    "The malloc failure is injected by a host linker wrapper, not observed as a naturally occurring OS allocation failure.",
    "The exact pinned mCoreAutoloadSave and mDirectorySetOpenSuffix bodies are extracted from original source; the original POSIX VDir, VFile dispatcher, and fd backend translation units are compiled.",
    "The caller uses narrow mCore, mDirectorySet, and config fixtures; the complete mGBA core and frontend are not compiled.",
    "The callback is a controlled fixture that observes NULL and closes the successful retry VFile; the real GBA savedata callback is source-traced but not executed.",
    "SDL and Qt autoload call sites are pinned and source-traced only; neither native frontend is executed by this witness.",
    "The leaked descriptor is observed in-process and explicitly closed by harness cleanup; this is not durable-storage, .sav interoperability, gameplay, or physical Flash evidence.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


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


def validate_body(source, signature, digest, anchors):
    body = extract_function(source, signature)
    require(hashlib.sha256(body.encode()).hexdigest() == digest,
            "pinned function body hash changed: " + signature)
    for anchor in anchors:
        require(body.count(anchor) == 1,
                "pinned function anchor missing or ambiguous: " + anchor)
    return body


def expected_source_records():
    body_hashes = {
        "src/core/core.c": {"mCoreAutoloadSave": CALLER_BODY_SHA256},
        "src/core/directories.c": {
            "mDirectorySetOpenSuffix": SUFFIX_BODY_SHA256,
        },
        "src/util/vfs/vfs-dirent.c": {
            "VDirOpen": VDIR_OPEN_BODY_SHA256,
            "_vdOpenFile": VDIR_FILE_BODY_SHA256,
        },
        "src/util/vfs.c": {"VFileOpen": DISPATCH_BODY_SHA256},
        "src/util/vfs/vfs-fd.c": {
            "VFileOpenFD": OPEN_BODY_SHA256,
            "VFileFromFD": FROM_FD_BODY_SHA256,
        },
        "src/gba/core.c": {
            "_GBACoreLoadSave": "0e348b801d98712108765d16b23ce7faa2ab2b9382011cf1d521d543b053c4de",
        },
        "src/gba/gba.c": {
            "GBALoadSave": "cfbfe0068178dbc3c1ed8e8a034ed861cfc0deb777e32bcc48979ad710732b73",
        },
        "src/gba/savedata.c": {
            "GBASavedataInit": "e7acccd1db65be1be7e20e49b23167b4c237d6e6646bac75d16be857269be408",
            "GBASavedataDeinit": "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2",
        },
    }
    records = []
    for path, values in SOURCES.items():
        record = {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "execution_scope": values[3],
        }
        if path in body_hashes:
            record["function_body_sha256"] = body_hashes[path]
        records.append(record)
    return records


def verify_prior_inventory(root):
    path = root / PREVIOUS_RECEIPT
    require(path.is_file(), "previous caller allocation receipt is missing")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.core-loadsave-allocation-recovery.v1" and
            receipt.get("pinned_revision") == PIN,
            "previous caller receipt pin or schema changed")
    caller_records = [
        row for row in receipt.get("source_records", [])
        if row.get("path") == "src/core/core.c"
    ]
    require(len(caller_records) == 1 and
            caller_records[0].get("function_body_sha256") ==
            OLD_CALLER_BODY_SHA256,
            "previous mCoreLoadSaveFile caller identity changed")
    require(CALLER_BODY_SHA256 != OLD_CALLER_BODY_SHA256,
            "new autoload caller overlaps the previous caller body")
    return {
        "receipt": PREVIOUS_RECEIPT,
        "previous_caller": "mCoreLoadSaveFile",
        "previous_function_body_sha256": OLD_CALLER_BODY_SHA256,
        "current_caller": "mCoreAutoloadSave",
        "current_function_body_sha256": CALLER_BODY_SHA256,
        "distinct_caller_body": True,
    }


def verify_sources(checkout):
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "wrong pinned mGBA revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA source tree")
    sources = {}
    for path, (blob, digest, _, _) in SOURCES.items():
        file_path = checkout / path
        raw = file_path.read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned tree blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        require(subprocess.check_output(
            ["git", "-C", str(checkout), "hash-object", str(file_path)],
            text=True,
        ).strip() == blob, "pinned source Git blob changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 source notice: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier_path = root / DOSSIER
    require(dossier_path.is_file(), "pinned machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned machine-dossier Git blob changed")
    require(hashlib.sha256(dossier_path.read_bytes()).hexdigest() ==
            DOSSIER_SHA256, "pinned machine-dossier SHA-256 changed")

    expected_rows = {
        path: (values[2], values[0], values[1])
        for path, values in SOURCES.items()
    }
    found = {path: [] for path in SOURCES}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and
                    path in found):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                found[path].append((
                    hashlib.sha256(canonical).hexdigest(),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                ))
    require(found == {path: [value] for path, value in expected_rows.items()},
            "pinned dossier rows changed or are ambiguous")

    validate_body(
        sources["src/core/core.c"], CALLER_SIGNATURE, CALLER_BODY_SHA256,
        ("if (!core->dirs.save)", 'char sav[16] = ".sav";',
         "savePlayerId > 1",
         "return core->loadSave(core, mDirectorySetOpenSuffix("),
    )
    validate_body(
        sources["src/core/directories.c"], SUFFIX_SIGNATURE,
        SUFFIX_BODY_SHA256,
        ("if (!dir)", 'snprintf(name, sizeof(name) - 1, "%s%s", dirs->baseName, suffix);',
         "return dir->openFile(dir, name, mode);"),
    )
    validate_body(
        sources["src/util/vfs/vfs-dirent.c"], VDIR_OPEN_SIGNATURE,
        VDIR_OPEN_BODY_SHA256,
        ("opendir(path)", "vd->d.openFile = _vdOpenFile;"),
    )
    validate_body(
        sources["src/util/vfs/vfs-dirent.c"], VDIR_FILE_SIGNATURE,
        VDIR_FILE_BODY_SHA256,
        ("VFileOpen(combined, mode)", "return file;"),
    )
    validate_body(
        sources["src/util/vfs.c"], DISPATCH_SIGNATURE,
        DISPATCH_BODY_SHA256,
        ("#elif defined(ENABLE_VFS_FD)", "return VFileOpenFD(path, flags);"),
    )
    validate_body(
        sources["src/util/vfs/vfs-fd.c"], OPEN_SIGNATURE, OPEN_BODY_SHA256,
        ("int fd = open(path, flags, 0666);", "return VFileFromFD(fd);"),
    )
    validate_body(
        sources["src/util/vfs/vfs-fd.c"], FROM_FD_SIGNATURE,
        FROM_FD_BODY_SHA256,
        ("struct VFileFD* vfd = malloc(sizeof(struct VFileFD));",
         "if (!vfd) {\n\t\treturn 0;\n\t}"),
    )
    validate_body(
        sources["src/gba/core.c"],
        "static bool _GBACoreLoadSave(struct mCore* core, struct VFile* vf)",
        "0e348b801d98712108765d16b23ce7faa2ab2b9382011cf1d521d543b053c4de",
        ("return GBALoadSave(core->board, vf);",),
    )
    require("core->loadSave = _GBACoreLoadSave;" in sources["src/gba/core.c"],
            "pinned GBA save callback assignment changed")
    validate_body(
        sources["src/gba/gba.c"],
        "bool GBALoadSave(struct GBA* gba, struct VFile* sav)",
        "cfbfe0068178dbc3c1ed8e8a034ed861cfc0deb777e32bcc48979ad710732b73",
        ("GBASavedataDeinit(&gba->memory.savedata);",
         "GBASavedataInit(&gba->memory.savedata, sav);", "return sav;"),
    )
    validate_body(
        sources["src/gba/savedata.c"],
        "void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf)",
        "e7acccd1db65be1be7e20e49b23167b4c237d6e6646bac75d16be857269be408",
        ("savedata->realVf = vf;",
         "savedata->realVf->close(savedata->realVf);"),
    )
    validate_body(
        sources["src/gba/savedata.c"],
        "void GBASavedataDeinit(struct GBASavedata* savedata)",
        "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2",
        ("if (savedata->vf)", "savedata->data = 0;"),
    )
    require("bool (*loadSave)(struct mCore*, struct VFile* vf);" in
            sources["include/mgba/core/core.h"],
            "pinned mCore save callback declaration changed")
    require(SUFFIX_SIGNATURE + ";" in
            sources["include/mgba/core/directories.h"] and
            "bool mCoreConfigGetIntValue(const struct mCoreConfig*, "
            "const char* key, int* value);" in
            sources["include/mgba/core/config.h"],
            "pinned directory/config interface changed")
    require(sources["src/platform/sdl/main.c"].count(
        "mCoreAutoloadSave(renderer->core);") == 1,
        "pinned SDL autoload callsite changed")
    require(sources["src/platform/qt/CoreManager.cpp"].count(
        "if (!mCoreAutoloadSave(core)) {") == 1,
        "pinned Qt autoload error-handling callsite changed")
    return sources


def reject_source_mutations(sources):
    cases = (
        ("src/core/core.c", CALLER_SIGNATURE, CALLER_BODY_SHA256,
         "if (!core->dirs.save) {\n\t\treturn false;\n\t}",
         "if (!core->dirs.save) {\n\t\treturn true;\n\t}"),
        ("src/core/core.c", CALLER_SIGNATURE, CALLER_BODY_SHA256,
         'char sav[16] = ".sav";', 'char sav[16] = ".saves";'),
        ("src/core/core.c", CALLER_SIGNATURE, CALLER_BODY_SHA256,
         "savePlayerId > 1", "savePlayerId >= 1"),
        ("src/core/core.c", CALLER_SIGNATURE, CALLER_BODY_SHA256,
         "return core->loadSave(core, mDirectorySetOpenSuffix(&core->dirs, "
         "core->dirs.save, sav, O_CREAT | O_RDWR));",
         "return core->loadSave(core, NULL);"),
        ("src/core/directories.c", SUFFIX_SIGNATURE, SUFFIX_BODY_SHA256,
         "return dir->openFile(dir, name, mode);", "return NULL;"),
        ("src/util/vfs/vfs-dirent.c", VDIR_FILE_SIGNATURE,
         VDIR_FILE_BODY_SHA256, "VFileOpen(combined, mode)", "NULL"),
        ("src/util/vfs/vfs-dirent.c", VDIR_OPEN_SIGNATURE,
         VDIR_OPEN_BODY_SHA256, "vd->d.openFile = _vdOpenFile;",
         "vd->d.openFile = NULL;"),
        ("src/gba/core.c",
         "static bool _GBACoreLoadSave(struct mCore* core, struct VFile* vf)",
         "0e348b801d98712108765d16b23ce7faa2ab2b9382011cf1d521d543b053c4de",
         "return GBALoadSave(core->board, vf);", "return false;"),
        ("src/gba/gba.c",
         "bool GBALoadSave(struct GBA* gba, struct VFile* sav)",
         "cfbfe0068178dbc3c1ed8e8a034ed861cfc0deb777e32bcc48979ad710732b73",
         "return sav;", "return true;"),
    )
    rejected = 0
    for path, signature, digest, before, after in cases:
        body = extract_function(sources[path], signature)
        require(body.count(before) == 1,
                "source mutation anchor changed: " + before)
        changed = body.replace(before, after, 1)
        try:
            validate_body(changed, signature, digest, (before,))
        except ValueError:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "autoload witness lacks a unique terminal marker")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES,
            "autoload witness output differs from the pinned contract")
    return {
        "successful_autoload": {
            "caller_return": True,
            "target_open_attempts": 1,
            "allocation_attempts": 1,
            "allocation_failures": 0,
            "save_callbacks": 1,
            "null_save_callbacks": 0,
            "target_close_calls": 1,
            "target_fd_open_after_callback": False,
        },
        "injected_allocation_failure": {
            "caller_return": False,
            "target_open_attempts": 1,
            "allocation_attempts": 1,
            "allocation_failures": 1,
            "save_callbacks": 1,
            "null_save_callbacks": 1,
            "target_close_calls": 0,
            "leaked_fd_open_after_callback": True,
        },
        "retry_after_allocation_failure": {
            "failure_return": False,
            "retry_return": True,
            "target_open_attempts": 2,
            "allocation_attempts": 2,
            "allocation_failures": 1,
            "save_callbacks": 2,
            "null_save_callbacks": 1,
            "target_close_calls": 1,
            "leaked_first_fd_open": True,
            "retry_fd_closed": True,
        },
        "missing_save_directory_control": {
            "caller_return": False,
            "target_open_attempts": 0,
            "allocation_attempts": 0,
            "save_callbacks": 0,
        },
    }


def prior_inventory_record():
    return {
        "receipt": PREVIOUS_RECEIPT,
        "previous_caller": "mCoreLoadSaveFile",
        "previous_function_body_sha256": OLD_CALLER_BODY_SHA256,
        "current_caller": "mCoreAutoloadSave",
        "current_function_body_sha256": CALLER_BODY_SHA256,
        "distinct_caller_body": True,
    }


def verify_receipt(path):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.core-autoload-save-ownership.v1" and
            receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "autoload receipt pin or schema changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "autoload receipt approval status changed")
    require(receipt.get("source_records") == expected_source_records(),
            "autoload source identities or scopes changed")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "autoload machine dossier identity changed")
    require(receipt.get("prior_witness_nonoverlap") ==
            prior_inventory_record(),
            "autoload nonoverlap inventory changed")
    expected_graph = [
        "Pinned SDL mSDLRun loads the ROM, calls mCoreAutoloadSave, and ignores its result.",
        "Pinned Qt CoreManager calls mCoreAutoloadSave and checks false to enter saveFailed handling.",
        "mCoreAutoloadSave checks core->dirs.save, chooses .sav by default, and calls mDirectorySetOpenSuffix.",
        "mDirectorySetOpenSuffix delegates to the original VDir openFile callback.",
        "POSIX VDirOpen installs _vdOpenFile; _vdOpenFile constructs directory/baseName.sav and calls VFileOpen.",
        "VFileOpen dispatches to VFileOpenFD; VFileOpenFD calls POSIX open then VFileFromFD.",
        "Injected VFileFD allocation failure returns NULL without closing the opened descriptor.",
        "Unlike the previous mCoreLoadSaveFile witness, mCoreAutoloadSave passes that NULL to core->loadSave and returns the fixture callback's false result.",
        "The pinned GBA callback assignment routes _GBACoreLoadSave to GBALoadSave; GBALoadSave deinitializes then initializes savedata with the received VFile and returns that pointer as bool.",
        "Pinned GBASavedataInit stores the incoming VFile and may close a prior realVf; these GBA callback and savedata lifecycle bodies are source-traced, not executed.",
    ]
    require(receipt.get("call_graph") == expected_graph,
            "autoload call graph changed")
    require(receipt.get("evidence_class") ==
            "COMPILED_EXTRACTED_PINNED_MCORE_AUTOLOAD_CALLER_AND_DIRECTORY_"
            "HELPERS_WITH_ORIGINAL_POSIX_VDIR_VFILE_BACKEND_AND_HOST_"
            "ALLOCATOR_INJECTION" and
            receipt.get("objection_notes") == OBJECTION_NOTES,
            "autoload evidence class or objection notes changed")
    require(receipt.get("observations") == parse_output(
        "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    ), "autoload receipt observations changed")
    require(receipt.get("source_mutations_rejected") == 9 and
            receipt.get("output_mutations_rejected") == 7,
            "autoload negative-control counts changed")
    required_true = (
        "host_allocator_fault_injection",
        "compiled_original_caller_body",
        "compiled_original_open_suffix_body",
        "compiled_original_vdir_translation_unit",
        "compiled_original_vfile_dispatcher",
        "compiled_original_fd_backend",
        "sdl_callsite_source_traced",
        "qt_callsite_source_traced",
        "prior_caller_nonoverlap_verified",
        "caller_core_struct_is_narrow_fixture",
        "save_callback_is_test_fixture",
    )
    for field in required_true:
        require(receipt.get(field) is True,
                "autoload evidence scope missing: " + field)
    required_false = (
        "natural_os_allocation_failure_observed",
        "real_gba_savedata_callback_executed",
        "native_sdl_frontend_executed",
        "native_qt_frontend_executed",
        "durable_persistence_tested",
        "sav_interoperability_tested",
        "stock_gameplay_tested",
        "physical_flash_tested",
    )
    for field in required_false:
        require(receipt.get(field) is False,
                "autoload receipt overstates evidence: " + field)
    return receipt


def reject_output_mutations(output):
    changes = (
        output.replace("save_callbacks=1 null_callbacks=1 close_calls=0",
                       "save_callbacks=0 null_callbacks=0 close_calls=0", 1),
        output.replace("leaked_fd_open=1", "leaked_fd_open=0", 1),
        output.replace("failure_return=0 retry_return=1",
                       "failure_return=1 retry_return=1", 1),
        output.replace("save_callbacks=2 null_callbacks=1",
                       "save_callbacks=1 null_callbacks=1", 1),
        output.replace("retry_fd_closed=1", "retry_fd_closed=0", 1),
        output.replace("target_opens=0 allocation_attempts=0 save_callbacks=0",
                       "target_opens=1 allocation_attempts=0 save_callbacks=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("autoload output mutation escaped")
    return len(changes)


def run(command, timeout=90):
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    root = Path(__file__).resolve().parents[1]
    receipt = verify_receipt(root / RECEIPT)
    nonoverlap = verify_prior_inventory(root)
    sources = verify_sources(checkout)
    source_mutations_rejected = reject_source_mutations(sources)

    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "autoload harness SHA-256 changed")
    replacements = {
        "PHASE1_INSERT_PINNED_MDIRECTORYSET_OPEN_SUFFIX":
            extract_function(sources["src/core/directories.c"],
                             SUFFIX_SIGNATURE),
        "PHASE1_INSERT_PINNED_MCORE_AUTOLOAD_SAVE":
            extract_function(sources["src/core/core.c"], CALLER_SIGNATURE),
    }
    expanded_harness = harness
    for marker, body in replacements.items():
        require(expanded_harness.count(marker.encode()) == 1,
                "pinned extraction marker changed: " + marker)
        expanded_harness = expanded_harness.replace(
            marker.encode(), body.encode()
        )

    with tempfile.TemporaryDirectory(
            prefix="xgba-mgba-core-autoload-save-") as temp:
        temp = Path(temp)
        expanded_source = temp / "core-autoload-save.c"
        binary = temp / "core-autoload-save"
        expanded_source.write_bytes(expanded_harness)
        command = [
            "gcc", "-std=c11", "-D_DEFAULT_SOURCE",
            "-D_POSIX_C_SOURCE=200809L", "-DENABLE_VFS",
            "-DENABLE_VFS_FD", "-DENABLE_DIRECTORIES",
            "-ffunction-sections", "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-Wno-format-truncation",
            str(checkout / "src/util/vfs.c"),
            str(checkout / "src/util/vfs/vfs-fd.c"),
            str(checkout / "src/util/vfs/vfs-dirent.c"),
            str(expanded_source),
            "-Wl,--wrap=malloc", "-Wl,--wrap=open", "-Wl,--wrap=close",
            "-Wl,--gc-sections", "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned autoload/backend witness compile failed:\n" +
                compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned autoload/backend witness failed:\n" + executed.stdout)
        observations = parse_output(executed.stdout)
        output_mutations_rejected = reject_output_mutations(executed.stdout)
        require(observations == receipt["observations"] and
                nonoverlap == receipt["prior_witness_nonoverlap"] and
                source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                output_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "execution or negative controls disagree with receipt")
        artifact_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()

    print(json.dumps({
        "schema": "phase1.mgba.core-autoload-save-execution.v1",
        "pinned_revision": PIN,
        "status": "NEEDS_EVIDENCE",
        "overall": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "observations": observations,
        "source_mutations_rejected": source_mutations_rejected,
        "output_mutations_rejected": output_mutations_rejected,
        "prior_witness_nonoverlap": nonoverlap,
        "compiled_artifact_sha256": artifact_sha256,
        "compile_command": command,
        "native_frontend_executed": False,
        "durable_persistence_tested": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

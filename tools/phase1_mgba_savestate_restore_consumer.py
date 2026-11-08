#!/usr/bin/env python3
"""Verify the pinned mGBA savestate extdata restore-consumer boundary."""

import argparse
import gzip
import hashlib
import importlib.util
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
    "mgba-savestate-restore-consumer-20261109.json"
)

SOURCES = {
    "src/core/serialize.c": (
        "ff8a9a86747336bd792bf9c964c53f232a702a08",
        "45fb69d5da0c0c4c135efb2641c7d1c6140d575b1819f60a45985ebfa0081f3c",
        "e9ad34d5514e106adc1f56111abf530b72118d1780d8593ae490ee63772ab9b5",
        "PARTIAL_FUNCTION_CLOSURE",
        "COMPILED_EXTRACTED_EXTDATA_DESERIALIZE_STATE_EXTRACT_AND_LOAD",
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
        "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
        "PARTIAL_EXTRACTED_CALLBACK",
        "COMPILED_EXTRACTED_GBA_SAVEDATA_RESTORE_CALLBACK",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
        "PARTIAL_FUNCTION_CLOSURE",
        "COMPILED_EXTRACTED_SRAM_LOAD_MASK_UNMASK_AND_CLEANUP",
    ),
    "src/util/vfs/vfs-mem.c": (
        "048194e2dd2d0b3b395a852d2092c694663c88a2",
        "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b",
        "3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce",
        "COMPLETE_TRANSLATION_UNIT",
        "COMPILED_PINNED_VFILE_MEMORY_BACKEND",
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
        "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
        "PARTIAL_FUNCTION",
        "COMPILED_EXTRACTED_VFILE_READLINE_HELPER",
    ),
    "src/platform/headless-main.c": (
        "61110b1e84a25f702b5e7d158887d93b150e1b66",
        "51687802777b8e831622e28fbd278782084e4c0d65e1ba28b7c1dec4e5617c68",
        "7cd9f22ce4878d5f9cab92adbe4b26a011a3fd6fbce9f21f7e20668be5c16e4e",
        "PARTIAL_CALLSITE_TRACE",
        "SOURCE_TRACED_HEADLESS_SAVESTATE_FLAGS_ZERO_AND_INPUT_CLOSE",
    ),
    "include/mgba/core/core.h": (
        "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
        "e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9",
        "0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87",
        "PARTIAL_INTERFACE",
        "COMPILED_MCORE_RESTORE_CALLBACK_INTERFACE",
    ),
    "include/mgba/core/serialize.h": (
        "177a7871aa2761c0b478256ce16c7015a36b0fb8",
        "c1301365f7f24c8842e84b51324cc419e5ea01843f5366e9edbbf1cdf40f5c49",
        "4e61192f417f79c7210d2aae3132db1afbedff078fc1e6779b8944ec07bc38b7",
        "PARTIAL_INTERFACE",
        "COMPILED_EXTDATA_TAG_AND_FLAGS_INTERFACE",
    ),
    "include/mgba/core/cheats.h": (
        "23a15c42976c998d292b382d08d51c0e3b797a65",
        "b25d46751653727f0a9814fef105b1efbd9498b7aa9d594f3547c6c2307ba3c7",
        "ddfa71cad7442c8052fe976d215288fa149cde7e7f5c6de8fe67249b62a97d00",
        "PARTIAL_INTERFACE",
        "COMPILED_DORMANT_CHEAT_BRANCH_DECLARATIONS",
    ),
    "include/mgba/core/log.h": (
        "892a8f2f94f75ff5bb7b9acb04bf973b537b916b",
        "c90656a9e5d34b5cdded45eac7a855937f1d53f6de55093d8fa40caaff80447a",
        "99259bb5e81cc6df879134a343051232040bf2442a0612aa7211c3b298d33d95",
        "PARTIAL_INTERFACE",
        "COMPILED_LOG_LEVEL_AND_STUB_INTERFACE",
    ),
    "include/mgba/internal/gba/gba.h": (
        "65e994dc63a304cc9fb207536f09bb2c8a6cf3e5",
        "b50fc8ae1467f9ac1c6be3ba8452e22027571ff5c886695edb9be529d7962d4e",
        "d6e61894ce31db089d3fd04e64e0938d1e689fb6c7498a8056fced405bf2bba0",
        "PARTIAL_LAYOUT",
        "COMPILED_GBA_BOARD_AND_SAVEDATA_LAYOUT",
    ),
    "include/mgba/internal/gba/memory.h": (
        "0aad912613e726560d06bbdbf6061986e69e5842",
        "fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41",
        "6d4aad1e87edf5e5e07bc6af2af6f36c396f1a5530518ca575a765e3640dea8e",
        "PARTIAL_LAYOUT",
        "COMPILED_GBA_SAVEDATA_CONSTANTS_AND_LAYOUT",
    ),
    "include/mgba/internal/gba/savedata.h": (
        "6227be25e8c9d2c1cc14c06ded34389b96138577",
        "30481cada83cc0e3a88b55298f3081cc660e18e55ca7f5a57356e6f2a75224dc",
        "eaee2c8bdb65c51e4f40daeb80af916f57ed430c48c88286562363f687ca6de9",
        "PARTIAL_INTERFACE",
        "COMPILED_GBA_SAVEDATA_FIELDS_AND_CALLS",
    ),
    "include/mgba/gba/interface.h": (
        "6edb38e6bf3161e28f3130b49b5598fc5d21884a",
        "d75c2c6bdcef009197252dcfbe059ae61084b137eeab677f818a837e3226038d",
        "44cd0490e58f1be562051dd1f5ce1240245573f3dc24e447df4176a2c2a1f1a2",
        "PARTIAL_ENUM",
        "COMPILED_GBA_SAVEDATA_TYPE_ENUM",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
        "PARTIAL_INTERFACE",
        "COMPILED_VFILE_OPERATIONS",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "PARTIAL_MACROS",
        "COMPILED_ENDIAN_AND_CALLBACK_MACROS",
    ),
    "include/mgba-util/math.h": (
        "f7b3269c9d51967765379b951ba6f43d24c61865",
        "04f5ee1686f4b30744d4e62caef4cf16f2f4b80682b88a87e7e18cf117fd421e",
        "87d819c03b064e4665a27b5563f4a7261cfcdad051913229884d4f72cfd813f9",
        "PARTIAL_INTERFACE",
        "COMPILED_VFILE_MEMORY_MATH_DEPENDENCY",
    ),
    "include/mgba-util/memory.h": (
        "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
        "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
        "PARTIAL_INTERFACE",
        "COMPILED_VFILE_MEMORY_MAP_API",
    ),
}

FILE_EDGES = {
    "src/core/serialize.c": [
        "mCoreLoadStateNamed -> mCoreExtractState -> mStateExtdataDeserialize",
        "mCoreLoadStateNamed -> core->savedataRestore and mStateExtdataDeinit",
        "Uses declarations and SAVESTATE flags from include/mgba/core/serialize.h, callbacks from include/mgba/core/core.h, and I/O from include/mgba-util/vfs.h",
    ],
    "src/gba/core.c": [
        "mCore.savedataRestore registration -> _GBACoreSavedataRestore",
        "_GBACoreSavedataRestore -> VFileMemChunk, GBASavedataLoad, and GBASavedataMask",
    ],
    "src/gba/savedata.c": [
        "GBASavedataLoad -> GBASavedataSize -> SRAM extent from include/mgba/internal/gba/memory.h",
        "GBASavedataMask/Unmask -> Deinit, ForceType, InitSRAM, VFile map/unmap/close",
    ],
    "src/util/vfs/vfs-mem.c": [
        "VFileMemChunk -> VFile methods from include/mgba-util/vfs.h",
        "VFileMemChunk -> toPow2 and anonymousMemoryMap/mappedMemoryFree",
        "Called by the pinned GBA restore callback for temporary savedata streams",
    ],
    "src/util/vfs.c": [
        "VFileReadline -> the VFile read callback",
        "Assigned as the readline operation by the pinned VFileMemChunk backend",
    ],
    "src/platform/headless-main.c": [
        "main -> mCoreLoadStateNamed(core, savestate, 0)",
        "main -> savestate->close after the load function returns",
    ],
    "include/mgba/core/core.h": [
        "Declares state load callbacks and savedataRestore on struct mCore",
        "Used by src/core/serialize.c and src/gba/core.c",
    ],
    "include/mgba/core/serialize.h": [
        "Declares extdata operations, SAVESTATE_SAVEDATA, and EXTDATA_SAVEDATA",
        "Used by src/core/serialize.c",
    ],
    "include/mgba/core/cheats.h": [
        "Provides dormant cheat branch declarations referenced by mCoreLoadStateNamed",
        "Cheat load behavior is not executed by this witness",
    ],
    "include/mgba/core/log.h": [
        "Declares the logging interface used by extracted serializer and SRAM functions",
        "Log emission is replaced by a no-op host stub and is not an observed frontend log",
    ],
    "include/mgba/internal/gba/gba.h": [
        "Defines the GBA board containing GBAMemory",
        "Used for the board-to-savedata callback path",
    ],
    "include/mgba/internal/gba/memory.h": [
        "Defines GBAMemory.savedata and GBA_SIZE_SRAM",
        "Used by the GBA board and SRAM restore path",
    ],
    "include/mgba/internal/gba/savedata.h": [
        "Defines GBASavedata fields and the load/mask/unmask APIs",
        "Used by src/gba/core.c and src/gba/savedata.c",
    ],
    "include/mgba/gba/interface.h": [
        "Defines GBA_SAVEDATA_SRAM used by the restore callback and SRAM loader",
    ],
    "include/mgba-util/vfs.h": [
        "Defines VFile read, map, unmap, and close callbacks",
        "Used by serializer, GBA savedata, and VFileMemChunk",
    ],
    "include/mgba-util/common.h": [
        "Supplies little-endian load/store macros used by extdata headers",
        "Also supplies callback macros used by SRAM initialization",
    ],
    "include/mgba-util/math.h": [
        "Declares toPow2 used by the pinned VFileMemChunk implementation",
    ],
    "include/mgba-util/memory.h": [
        "Declares memory mapping functions used by VFileMemChunk and state extraction",
        "Witness supplies host allocation shims for these interfaces",
    ],
}

FILE_OBJECTIONS = {
    "src/core/serialize.c": "Only extracted extdata and named-load functions run; the full translation unit, PNG path, native malformed state, and frontend behavior are not exercised.",
    "src/gba/core.c": "Only the extracted restore callback runs; full GBA core initialization and callback registration are not compiled or executed.",
    "src/gba/savedata.c": "Only the listed SRAM load/mask/unmask closure runs; non-SRAM type initializers are fixture stubs and flash/EEPROM paths are excluded.",
    "src/util/vfs/vfs-mem.c": "The complete translation unit is compiled, but memory mapping is shimmed with host allocation and no OS-backed save file is used.",
    "src/util/vfs.c": "Only the extracted VFileReadline body is compiled; it is assigned to the memory VFile but never invoked by these cases.",
    "src/platform/headless-main.c": "The headless callsite and flags are source-traced, not executed as a frontend process.",
    "include/mgba/core/core.h": "Only the callback interface needed by the extracted functions is compiled; this is not whole-header semantic review.",
    "include/mgba/core/serialize.h": "Only the extdata structure, tag, and flag interface is exercised; other state API behaviors remain outside scope.",
    "include/mgba/core/cheats.h": "Cheat declarations are required by the unexecuted branch; cheat parsing and cleanup are not tested.",
    "include/mgba/core/log.h": "Log declarations are compiled, but the logger implementation and frontend log routing are not exercised.",
    "include/mgba/internal/gba/gba.h": "The board layout is compiled but the full GBA core object graph and lifecycle are not run.",
    "include/mgba/internal/gba/memory.h": "Only the savedata member and SRAM extent are relevant to this case; other memory behavior is not reviewed.",
    "include/mgba/internal/gba/savedata.h": "Only the savedata layout and called API declarations are compiled; other savedata operations are not reviewed.",
    "include/mgba/gba/interface.h": "Only the SRAM enum branch is exercised; other savedata types are excluded.",
    "include/mgba-util/vfs.h": "The VFile method contract is compiled; this does not establish other backend behavior.",
    "include/mgba-util/common.h": "Only endian and callback macros needed by the witness are in scope.",
    "include/mgba-util/math.h": "The toPow2 declaration is used, but its upstream implementation is not linked into the witness.",
    "include/mgba-util/memory.h": "Memory-map declarations are used with host shims; native OS mapping behavior is not tested.",
}

FUNCTIONS = {
    "struct mStateExtdataHeader": (
        "src/core/serialize.c",
        "struct mStateExtdataHeader {",
        "3402135372a9421cae40fc1d86a79b9dab0dd32eee6e82a7252709540112a459",
        "declaration",
    ),
    "mStateExtdataInit": (
        "src/core/serialize.c",
        "void mStateExtdataInit(struct mStateExtdata* extdata)",
        "59161c62c270319177d850fae8a4b913d490ebe3a43215343444ea7cfef74a26",
        "function",
    ),
    "mStateExtdataDeinit": (
        "src/core/serialize.c",
        "void mStateExtdataDeinit(struct mStateExtdata* extdata)",
        "e909282685c02445a7e16ed9f63e2e630e4587626da1a20a121894b8db5185c4",
        "function",
    ),
    "mStateExtdataPut": (
        "src/core/serialize.c",
        "void mStateExtdataPut(struct mStateExtdata* extdata, enum mStateExtdataTag tag, struct mStateExtdataItem* item)",
        "7aab775b2bd3769b433149cca6f3de9ba583abfaf0d8f147c3021c12d10c7a9b",
        "function",
    ),
    "mStateExtdataGet": (
        "src/core/serialize.c",
        "bool mStateExtdataGet(const struct mStateExtdata* extdata, enum mStateExtdataTag tag, struct mStateExtdataItem* item)",
        "cd981ae228ceff9e64697a51ef193f3089cd0c573259a2bd6ce2fda0c5d99349",
        "function",
    ),
    "mStateExtdataDeserialize": (
        "src/core/serialize.c",
        "bool mStateExtdataDeserialize(struct mStateExtdata* extdata, struct VFile* vf)",
        "81699573b8d6590f08955286bfe1c619549f085b6e77bbd61617d0bb7a05836a",
        "function",
    ),
    "mCoreExtractState": (
        "src/core/serialize.c",
        "void* mCoreExtractState(struct mCore* core, struct VFile* vf, struct mStateExtdata* extdata)",
        "804cac225a0d57e3f3cbbd698a850b0ad6f1025aca2df6a0b4959343236b21a9",
        "function",
    ),
    "mCoreLoadStateNamed": (
        "src/core/serialize.c",
        "bool mCoreLoadStateNamed(struct mCore* core, struct VFile* vf, int flags)",
        "3001619f50c68d9caabe6fb6159097e7efc73019059d1193e726240339d6396c",
        "function",
    ),
    "_GBACoreSavedataRestore": (
        "src/gba/core.c",
        "static bool _GBACoreSavedataRestore(struct mCore* core, const void* sram, size_t size, bool writeback)",
        "8f3654b0b9164674275a28137a89decf55047436aa8df09225ccfcb326a6ea0b",
        "function",
    ),
    "GBASavedataLoad": (
        "src/gba/savedata.c",
        "bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in)",
        "f272ab49e19f5be2284c9dc851f53b070606fd75b626db60a92b499c2d05c2b2",
        "function",
    ),
    "GBASavedataSize": (
        "src/gba/savedata.c",
        "size_t GBASavedataSize(const struct GBASavedata* savedata)",
        "9f3e0774073a8f44195f2b1b8c2d4c20977dedd1eb8c4d7ec4c1c42e467b02d1",
        "function",
    ),
    "GBASavedataDeinit": (
        "src/gba/savedata.c",
        "void GBASavedataDeinit(struct GBASavedata* savedata)",
        "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2",
        "function",
    ),
    "GBASavedataMask": (
        "src/gba/savedata.c",
        "void GBASavedataMask(struct GBASavedata* savedata, struct VFile* vf, bool writeback)",
        "713b702618c61c33848bf9d88c9c4799d4f133471369df394747275c3e739277",
        "function",
    ),
    "GBASavedataUnmask": (
        "src/gba/savedata.c",
        "void GBASavedataUnmask(struct GBASavedata* savedata)",
        "6517182aaa42db3fdc6fc4eb8582a5c9f5ff2e4364fedbf1abe4e7b7fc644709",
        "function",
    ),
    "GBASavedataForceType": (
        "src/gba/savedata.c",
        "void GBASavedataForceType(struct GBASavedata* savedata, enum GBASavedataType type)",
        "7ffbdeaf9944c79c2fc2811070817427e071c9e49faa5f865b58d50e12b25cea",
        "function",
    ),
    "GBASavedataInitSRAM": (
        "src/gba/savedata.c",
        "void GBASavedataInitSRAM(struct GBASavedata* savedata)",
        "d9b4d85db33cea2da5073208f512fe3c82d8f7450c1d074baeff37c79a29efbc",
        "function",
    ),
    "VFileMemChunk": (
        "src/util/vfs/vfs-mem.c",
        "struct VFile* VFileMemChunk(const void* mem, size_t size)",
        "ccae145be03fecd65a114d81f9192980e0b7bee4ad11495cac501a2650d3548f",
        "function",
    ),
    "VFileReadline": (
        "src/util/vfs.c",
        "ssize_t VFileReadline(struct VFile* vf, char* buffer, size_t size)",
        "fdde65bdbd39a6bfd39eb68d132776c4daa5b5edcbbba34dd9bf9787ff960df5",
        "function",
    ),
    "headless main": (
        "src/platform/headless-main.c",
        "int main(int argc, char * argv[])",
        "f94bb7805c72c7c9679739c5056f38b1ce8c6c7cedc7d37341a6f2102df908d4",
        "function",
    ),
}

HARNESS_SHA256 = "bfd62a370537587eb473c4ff81eee8cb5b554c7ab6adc9f1e4deafdc5d2f111b"
TERMINAL = "PHASE1_SAVESTATE_RESTORE_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")

EXPECTED_LINES = (
    "PHASE1_RESTORE_CASE absent caller_return=1 restore_vfiles=0 "
    "close_after_load=0 save_unchanged=1 clean=1",
    "PHASE1_RESTORE_CASE short_header caller_return=1 restore_vfiles=0 "
    "close_after_load=0 save_unchanged=1 clean=1",
    "PHASE1_RESTORE_CASE short_payload caller_return=1 restore_vfiles=0 "
    "close_after_load=0 save_unchanged=1 clean=1",
    "PHASE1_RESTORE_CASE valid_writeback caller_return=1 restore_vfiles=1 "
    "close_after_load=1 save_match=1 clean=1",
    "PHASE1_RESTORE_CASE valid_deferred caller_return=1 restore_vfiles=1 "
    "close_after_load=0 mask_owned=1 save_match_after_unmask=1 "
    "close_after_unmask=1 clean=1",
    "PHASE1_RESTORE_CASE retry_after_malformed malformed_return=1 "
    "malformed_restore_vfiles=0 retry_return=1 retry_restore_vfiles=1 "
    "save_match=1 clean=1",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *command):
    return subprocess.check_output(
        ["git", "-C", str(root), *command], text=True
    ).strip()


def load_source_helpers(root):
    path = root / "tools/phase1_mgba_gba_clone_vfile_alloc.py"
    spec = importlib.util.spec_from_file_location(
        "phase1_mgba_gba_clone_vfile_alloc", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_old_runner(root)


def body_hashes(source_map, old):
    result = {}
    for name, (path, signature, digest, kind) in FUNCTIONS.items():
        source = source_map[path]
        if kind == "declaration":
            body = old.extract_declaration(source, signature)
        else:
            body = old.extract_function(source, signature)
        require(hashlib.sha256(body.encode()).hexdigest() == digest,
                "pinned function body changed: " + name)
        result[name] = digest
    return result


def expected_source_records():
    records = []
    for path, values in SOURCES.items():
        record = {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "review_scope": values[3],
            "execution_scope": values[4],
        }
        records.append(record)
    return records


def verify_sources(checkout, root, old):
    source_map = {}
    for path, values in SOURCES.items():
        raw = (checkout / path).read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == values[0],
                "pinned source tree blob changed: " + path)
        require(hashlib.sha1(
            b"blob " + str(len(raw)).encode() + b"\0" + raw
        ).hexdigest() == values[0], "pinned source Git blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == values[1],
                "pinned source SHA-256 changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 notice: " + path)
        source_map[path] = raw.decode("utf-8")

    dossier = root / DOSSIER
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB and
            hashlib.sha256(dossier.read_bytes()).hexdigest() == DOSSIER_SHA256,
            "pinned machine dossier identity changed")
    expected_rows = {
        path: (values[2], values[0], values[1])
        for path, values in SOURCES.items()
    }
    found = {path: [] for path in SOURCES}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
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
    body_hashes(source_map, old)
    require(
        "mCoreLoadStateNamed(core, savestate, 0);" in
        source_map["src/platform/headless-main.c"] and
        "savestate->close(savestate);" in
        source_map["src/platform/headless-main.c"],
        "pinned headless restore caller or input lifetime changed",
    )
    require("mStateExtdataDeserialize(extdata, vf);" in
            source_map["src/core/serialize.c"],
            "pinned state extractor no longer calls extdata deserializer")
    return source_map


def reject_source_mutations(source_map, old):
    cases = (
        ("src/core/serialize.c", FUNCTIONS["mStateExtdataDeserialize"][1],
         FUNCTIONS["mStateExtdataDeserialize"][2],
         "if (vf->read(vf, &buffer, sizeof(buffer)) != sizeof(buffer)) {",
         "if (vf->read(vf, &buffer, sizeof(buffer)) == sizeof(buffer)) {"),
        ("src/core/serialize.c", FUNCTIONS["mCoreExtractState"][1],
         FUNCTIONS["mCoreExtractState"][2],
         "mStateExtdataDeserialize(extdata, vf);",
         "if (!mStateExtdataDeserialize(extdata, vf)) return 0;"),
        ("src/core/serialize.c", FUNCTIONS["mCoreLoadStateNamed"][1],
         FUNCTIONS["mCoreLoadStateNamed"][2],
         "mStateExtdataDeinit(&extdata);",
         "mStateExtdataInit(&extdata);"),
        ("src/gba/core.c", FUNCTIONS["_GBACoreSavedataRestore"][1],
         FUNCTIONS["_GBACoreSavedataRestore"][2],
         "vf->close(vf);", "vf->unmap(vf, NULL, 0);"),
        ("src/gba/savedata.c", FUNCTIONS["GBASavedataUnmask"][1],
         FUNCTIONS["GBASavedataUnmask"][2],
         "vf->close(vf);", "vf->unmap(vf, NULL, 0);"),
    )
    rejected = 0
    for path, signature, digest, before, after in cases:
        body = old.extract_function(source_map[path], signature)
        require(body.count(before) == 1, "source mutation anchor changed")
        mutated = body.replace(before, after, 1)
        try:
            old.validate_body(mutated, signature, digest)
        except ValueError:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "restore witness lacks a unique terminal marker")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES, "restore witness output changed")
    return {
        "absent_extdata": {
            "mcore_return": True,
            "restore_vfiles_created": 0,
            "save_unchanged": True,
            "state_vfile_closed_by_caller": True,
            "cleanup_balanced": True,
        },
        "short_header": {
            "mcore_return": True,
            "restore_vfiles_created": 0,
            "save_unchanged": True,
            "cleanup_balanced": True,
        },
        "short_payload": {
            "mcore_return": True,
            "restore_vfiles_created": 0,
            "save_unchanged": True,
            "failed_extdata_allocation_released": True,
            "cleanup_balanced": True,
        },
        "valid_writeback": {
            "mcore_return": True,
            "restore_vfiles_created": 1,
            "restore_vfile_closed_before_return": True,
            "savedata_matches": True,
            "cleanup_balanced": True,
        },
        "valid_deferred_restore": {
            "mcore_return": True,
            "restore_vfiles_created": 1,
            "restore_vfile_owned_by_mask_after_return": True,
            "restore_vfile_closed_by_unmask": True,
            "savedata_matches_after_unmask": True,
            "cleanup_balanced": True,
        },
        "retry_after_malformed_payload": {
            "malformed_first_load_return": True,
            "malformed_restore_vfiles_created": 0,
            "valid_retry_return": True,
            "valid_retry_restore_vfiles_created": 1,
            "savedata_matches_after_retry": True,
            "cleanup_balanced": True,
        },
    }


def reject_output_mutations(output):
    changes = (
        output.replace("restore_vfiles=0", "restore_vfiles=1", 1),
        output.replace("close_after_load=1", "close_after_load=0", 1),
        output.replace("mask_owned=1", "mask_owned=0", 1),
        output.replace("save_match=1", "save_match=0", 1),
        output.replace("close_after_unmask=1", "close_after_unmask=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("restore witness output mutation escaped")
    return len(changes)


def verify_receipt(root, old, receipt_path=None):
    receipt_path = receipt_path or root / RECEIPT
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.savestate-restore-consumer.v1" and
            receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "restore receipt schema or source pin changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "restore receipt must remain non-approving")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "restore receipt machine dossier identity changed")
    require(receipt.get("source_records") == expected_source_records(),
            "restore receipt source records changed")
    require(receipt.get("function_body_sha256") == {
        name: info[2] for name, info in FUNCTIONS.items()
    }, "restore receipt function-body identities changed")
    require(receipt.get("file_dependencies") == FILE_EDGES and
            receipt.get("per_file_objections") == FILE_OBJECTIONS,
            "restore receipt per-file dependency or objection changed")
    expected_output = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    require(receipt.get("observations") == parse_output(expected_output),
            "restore receipt observations changed")
    require(receipt.get("source_mutations_rejected") == 5 and
            receipt.get("output_mutations_rejected") == 6,
            "restore mutation-control counts changed")
    require(receipt.get("source_closure") == [
        "headless-main.c calls mCoreLoadStateNamed(core, savestate, 0) and closes the input VFile after it returns.",
        "mCoreLoadStateNamed calls mCoreExtractState, then consumes EXTDATA_SAVEDATA only when deserialization populated that tag.",
        "mCoreExtractState ignores the boolean result from mStateExtdataDeserialize and returns the state buffer when its fixed-size core bytes were read.",
        "A short extdata header or payload can therefore leave the state-load return true while no savedata restore VFile is created; the harness observes this on the pinned extracted bodies.",
        "With flags including SAVESTATE_SAVEDATA, the GBA callback writeback path loads through a temporary VFileMemChunk and closes it before returning.",
        "With flags zero, the GBA callback transfers the temporary VFile to GBASavedataMask; GBASavedataUnmask later reads it into the real save VFile and closes it.",
        "mCoreLoadStateNamed deinitializes extdata after the callback, freeing its item buffer; VFileMemChunk owns a separate copied buffer in the controlled witness.",
    ], "restore source closure changed")
    require(receipt.get("nonoverlap") == {
        "producer_receipt": (
            "docs/phase1-review-readiness/"
            "mgba-core-savestate-clone-caller-20261108.json"
        ),
        "producer_case": "mCoreSaveStateNamed zero clone result omits savedata extdata",
        "prior_restore_receipt": (
            "docs/phase1-review-readiness/"
            "mgba-savedata-truncated-restore-20261107.json"
        ),
        "prior_restore_case": (
            "_GBACoreSavedataRestore(writeback=true) with a 32-byte "
            "snapshot partially updates the SRAM prefix before returning false"
        ),
        "new_case": (
            "mCoreLoadStateNamed extdata absent/short parse, successful restore "
            "VFile cleanup, and deferred mask/unmask ownership"
        ),
        "distinct_downstream_consumer": True,
    }, "restore witness overlap inventory changed")
    require(receipt.get("limitations") == {
        "compiled_extracted_mcore_deserialize_extract_load": True,
        "compiled_extracted_gba_restore_callback_and_sram_functions": True,
        "compiled_complete_vfile_memory_translation_unit": True,
        "headless_caller_source_traced_not_executed": True,
        "host_memory_vfile_and_allocator_tracking": True,
        "natural_malformed_savestate_observed": False,
        "full_mgba_core_or_frontend_compiled": False,
        "native_frontend_or_stock_gameplay_executed": False,
        "durable_savestate_or_sav_persistence_tested": False,
        "physical_flash_tested": False,
        "transitive_distribution_licensing_resolved": False,
    }, "restore receipt evidence limits changed")
    require(receipt.get("licensing") == {
        "source_notices": "All 18 listed upstream files carry MPL-2.0 notices.",
        "upstream_modified": False,
        "transitive_distribution_licensing_resolved": False,
    }, "restore receipt licensing boundary changed")
    return receipt


def run(command, timeout=90):
    return subprocess.run(
        command, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    root = Path(__file__).resolve().parents[1]
    old = load_source_helpers(root)
    receipt = verify_receipt(root, old)
    require(git(checkout, "rev-parse", "HEAD") == PIN and
            git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA revision or tree")
    source_map = verify_sources(checkout, root, old)
    source_mutations_rejected = reject_source_mutations(source_map, old)
    output = "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
    output_mutations_rejected = reject_output_mutations(output)
    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "savestate restore harness SHA-256 changed")
    expanded = harness.decode("utf-8")
    marker = "PHASE1_INSERT_PINNED_RESTORE_FUNCTIONS"
    require(expanded.count(marker) == 1, "restore extraction marker changed")
    bodies = []
    for name, (path, signature, digest, kind) in FUNCTIONS.items():
        source = source_map[path]
        if kind == "declaration":
            body = old.validate_declaration(source, signature, digest)
        else:
            body = old.validate_body(source, signature, digest)
        bodies.append(body)
    expanded = expanded.replace(marker, "\n\n".join(bodies), 1)

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-restore-consumer-") as temp:
        temp = Path(temp)
        expanded_source = temp / "restore-consumer.c"
        binary = temp / "restore-consumer"
        expanded_source.write_text(expanded, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            str(expanded_source), str(checkout / "src/util/vfs/vfs-mem.c"),
            "-Wl,--wrap=malloc", "-Wl,--wrap=free",
            "-Wl,--wrap=VFileMemChunk", "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned restore witness compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned restore witness failed:\n" + executed.stdout)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                output_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "restore runtime differs from its receipt")
        print(
            "PHASE1_SAVESTATE_RESTORE_CONSUMER_WITNESS "
            f"pinned={PIN} sources={len(receipt['source_records'])} "
            f"source_mutations_rejected={source_mutations_rejected} "
            f"output_mutations_rejected={output_mutations_rejected}"
        )
        print(executed.stdout, end="")


if __name__ == "__main__":
    main()

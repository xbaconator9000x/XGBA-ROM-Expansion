#!/usr/bin/env python3
"""Source-verified mGBA savedata handoff controls; never an approval."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOBS = {
    "src/gba/savedata.c": "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
    "include/mgba/internal/gba/savedata.h": "6227be25e8c9d2c1cc14c06ded34389b96138577",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "src/gba/serialize.c": "a307a51e751f412c64a7378323c56758304ebe85",
    "src/gba/gba.c": "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
    "include/mgba-util/vfs.h": "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
}
DEFINITIONS = (
    "_ashesToAshes", "GBASavedataInit", "GBASavedataReset", "GBASavedataDeinit",
    "GBASavedataMask", "GBASavedataUnmask", "GBASavedataClone",
    "GBASavedataSize", "GBASavedataLoad", "GBASavedataForceType",
    "GBASavedataInitFlash", "GBASavedataInitEEPROM", "GBASavedataInitSRAM",
    "GBASavedataInitSRAM512", "GBASavedataReadFlash", "GBASavedataWriteFlash",
    "_ensureEeprom", "GBASavedataWriteEEPROM", "GBASavedataReadEEPROM",
    "GBASavedataClean", "GBASavedataRTCWrite", "_unBCD", "GBASavedataRTCRead",
    "GBASavedataSerialize", "GBASavedataDeserialize", "_flashSwitchBank",
    "_flashErase", "_flashEraseSector",
)
ANCHORS = {
    285: "if (end < flashSize) {",
    292: "if (end < GBA_SIZE_FLASH512) {",
    316: "if (end < eepromSize) {",
    321: "if (end < GBA_SIZE_EEPROM512) {",
    154: "out->write(out, buffer, read);",
    210: "read = savedata->vf->write(savedata->vf, buffer, read);",
    653: "size = savedata->vf->read(savedata->vf, &buffer, sizeof(buffer));",
    720: "GBASerializedSavedataFlagsTestFillFlashBank(flags, savedata->currentBank == &savedata->data[0x10000]);",
}
CONSUMER_ANCHORS = {
    "src/gba/memory.c": {614: "GBASavedataReadEEPROM", 995: "GBASavedataWriteEEPROM", 1076: "GBASavedataWriteFlash"},
    "src/gba/serialize.c": {89: "GBASavedataSerialize", 234: "GBASavedataDeserialize"},
    "src/gba/gba.c": {87: "GBASavedataInit", 172: "GBASavedataDeinit", 969: "GBASavedataClean"},
    "include/mgba-util/vfs.h": {43: "ssize_t (*read)(struct VFile* vf, void* buffer, size_t size);"},
}

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\\0" + data).hexdigest()

def check_blob(path, data):
    if blob_sha(data) != BLOBS[path]:
        raise ValueError("Pinned Git blob mismatch: " + path)
    if b"\\0" in data:
        raise ValueError("Text source unexpectedly contains NUL: " + path)
    return data.decode("utf-8").splitlines()

def check_source(data):
    lines = check_blob("src/gba/savedata.c", data)
    if len(lines) != 800:
        raise ValueError("Savedata whole-file line count drift")
    defs = re.findall(r"^(?:static\\s+)?(?:void|bool|size_t|uint8_t|uint16_t)\\s+(\\w+)\\s*\\([^;\\n]*\\)\\s*\\{", data.decode(), re.M)
    if tuple(defs) != DEFINITIONS:
        raise ValueError("Savedata function-definition inventory drift")
    for line, snippet in ANCHORS.items():
        if snippet not in lines[line - 1]:
            raise ValueError(f"Savedata risk anchor drift at line {line}")
    return lines

def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args]).strip()

def verify_checkout(repo):
    if git(repo, "rev-parse", "HEAD").decode() != PIN:
        raise ValueError("Not the exact pinned mGBA commit")
    data_by_path = {}
    for path, expected in BLOBS.items():
        if git(repo, "rev-parse", "HEAD:" + path).decode() != expected:
            raise ValueError("Pinned tree identity drift: " + path)
        data = subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", expected])
        check_blob(path, data)
        data_by_path[path] = data
    check_source(data_by_path["src/gba/savedata.c"])
    for path, anchors in CONSUMER_ANCHORS.items():
        lines = data_by_path[path].decode().splitlines()
        for number, text in anchors.items():
            if number > len(lines) or text not in lines[number - 1]:
                raise ValueError(f"Consumer anchor drift: {path}:{number}")
    return data_by_path

def negative_controls(data):
    checks = 0
    for bad in (
        data.replace(b"if (end < GBA_SIZE_FLASH512)", b"if (end <= GBA_SIZE_FLASH512)", 1),
        data.replace(b"GBASavedataSerialize(", b"GBASavedataSerializeChanged(", 1),
        data + b"\\n",
        b"\\x00" + data,
    ):
        try:
            check_source(bad)
        except ValueError:
            checks += 1
        else:
            raise AssertionError("Corrupted source passed fail-closed validation")
    if checks != 4:
        raise AssertionError("Negative controls incomplete")
    return checks

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkout", type=Path, required=True, help="Existing exact-pinned mGBA checkout")
    args = p.parse_args()
    data = verify_checkout(args.checkout)
    controls = negative_controls(data["src/gba/savedata.c"])
    print(f"PASS pinned savedata whole-file evidence: {len(BLOBS)} blobs, 28 definitions, {len(ANCHORS)} risk anchors, {controls} negative controls; 0 approvals")

if __name__ == "__main__":
    main()

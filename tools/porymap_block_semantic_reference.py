#!/usr/bin/env python3
"""Porymap pinned 16-bit block ABI reference model: candidates, not C++ runtime proof."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
SOURCES = {
    "src/core/block.cpp": "fc4fe774ccd75673c549734055907eb7c79c0fc2",
    "src/core/bitpacker.cpp": "34f86b4e3910021613a1d090746ae53a1c6782a2",
    "src/core/blockdata.cpp": "5fcd4e32b115790f5a86b5cef5726cace8005017",
    "src/core/maplayout.cpp": "44616ab6c9c3ea9b04eff011586b7ec29183588f",
}
DEFAULT = (0x03FF, 0x0C00, 0xF000)

class InvalidMapBlock(ValueError):
    pass

def bit_positions(mask):
    return [i for i in range(16) if mask & (1 << i)]

def unpack(raw, mask):
    return sum(((raw >> bit) & 1) << j for j,bit in enumerate(bit_positions(mask)))

def pack(value, mask):
    return sum(((value >> j) & 1) << bit for j,bit in enumerate(bit_positions(mask)))

def validate_masks(masks):
    if len(masks) != 3 or any(not isinstance(x,int) or x < 1 or x > 0xFFFF for x in masks):
        raise InvalidMapBlock("Three nonzero 16-bit masks required")
    assigned = 0
    for mask in masks:
        if assigned & mask:raise InvalidMapBlock("Overlapping Porymap masks")
        assigned |= mask
    if assigned != 0xFFFF:
        raise InvalidMapBlock("Roundtrip requires full 16-bit coverage, or explicit reserved bits handling")

def legacy_clamp(value, mask):
    size = 1 << len(bit_positions(mask))
    return value % size

def strict_encode(fields, masks=DEFAULT):
    validate_masks(masks)
    value = 0
    for field,mask in zip(fields,masks):
        if not isinstance(field,int) or field < 0 or field >= (1 << len(bit_positions(mask))):
            raise InvalidMapBlock("Unrepresentable metatile/collision/elevation value")
        value |= pack(field,mask)
    return value.to_bytes(2,"little")

def strict_decode(data, expected_count, masks=DEFAULT):
    validate_masks(masks)
    if len(data) & 1:raise InvalidMapBlock("Odd-length native map block stream")
    if expected_count <= 0:raise InvalidMapBlock("Invalid layout dimensions")
    if len(data) != expected_count * 2:
        raise InvalidMapBlock("Map block count disagrees with dimensions; do not silently resize")
    return [tuple(unpack(int.from_bytes(data[i:i+2],"little"),m) for m in masks)
            for i in range(0,len(data),2)]

def git_blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def verify_pinned_sources(root):
    if not (root/".git").is_dir():
        raise InvalidMapBlock("Pinned Porymap Git checkout absent")
    head = subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if head != PIN:raise InvalidMapBlock("Wrong pinned editor source revision")
    for path,sha in SOURCES.items():
        actual=git_blob((root/path).read_bytes())
        if actual != sha:raise InvalidMapBlock("Porymap source Git blob drift at "+path)

def self_test():
    validate_masks(DEFAULT)
    assert sum(DEFAULT) == 0xFFFF
    for raw in range(65536):
        fields=tuple(unpack(raw,mask) for mask in DEFAULT)
        result=strict_encode(fields)
        if result!=raw.to_bytes(2,"little"):
            raise AssertionError(f"Invalid native roundtrip: {raw:04X}")
        if strict_decode(result,1)[0]!=fields:
            raise AssertionError(f"Decoded field mismatch: {raw:04X}")
    assert legacy_clamp(1024,DEFAULT[0])==0
    assert legacy_clamp(4,DEFAULT[1])==0
    assert legacy_clamp(16,DEFAULT[2])==0
    negatives=[
        lambda:strict_encode((1024,0,0)),
        lambda:strict_encode((0,4,0)),
        lambda:strict_encode((0,0,16)),
        lambda:strict_encode((-1,0,0)),
        lambda:strict_encode((0,0,0),(0x03FF,0x0FFF,0xF000)),
        lambda:strict_decode(b"\x00",1),
        lambda:strict_decode(b"\x00\x00",2),
        lambda:strict_decode(b"\x00\x00",0),
        lambda:strict_decode(b"\x00\x00\x00",1),
        lambda:strict_decode(b"\x00\x00",1,(0x000F,0x00F0,0x0F00)),
    ]
    for i,case in enumerate(negatives,1):
        try:case()
        except InvalidMapBlock:continue
        raise AssertionError(f"Fail-open invalid native block fixture {i}")
    return {
        "source_revisions":{"huderlem/porymap":PIN},
        "static_default_masks":[f"0x{x:04X}" for x in DEFAULT],
        "exhaustive_16bit_raw_words_roundtripped":65536,
        "strict_adapter_negative_fixtures_rejected":len(negatives),
        "modulo_clamp_hazard_fixtures":3,
        "compiled_Porymap_runtime_roundtrip_tested":False,
        "source_semantic_dispositions_approved":0,
        "phase1_mapping_complete":False,
        "scope":"Source-grounded Python reference; compiled Qt behavior requires separate tests"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--source-root",type=Path,default=Path("upstream/porymap"))
    p.add_argument("--out",type=Path,default=Path("porymap-compiler-evidence/porymap_native_block_reference.json"))
    a=p.parse_args()
    results=self_test()
    if a.self_test:
        print("Porymap block reference: 65536 exact roundtrips + 10 negative controls PASS")
        return
    verify_pinned_sources(a.source_root)
    results["pinned_Git_source_blobs_verified"]=SOURCES
    results["source_revision_verified"]=True
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(results,indent=2,sort_keys=True)+"\n")
    print(json.dumps(results,indent=2))

if __name__=="__main__":
    main()

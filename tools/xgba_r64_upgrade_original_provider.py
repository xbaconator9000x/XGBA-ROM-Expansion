#!/usr/bin/env python3
"""R64: privately add the three authenticated ORIGINAL NPC scripts to an R62 provider.

The previous private R62 pack contained all R49 events and real Rocket art,
but not the 256-byte R48 original witness scripts that actual native
Emerald A-button resolution fetches by ID. This upgrader validates ALL
source R49 SHA pages against the imported R62 index, the original witness
SHA/source metadata and the entire original R62 host manifest before it
creates an unshared new private manifest. The public source contains no
copyrighted text, sprite bytes or ROM image.

This is a resource availability fix; NOT proof that foreign NPC dialogue
has already executed in native mGBA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import xgba_resource_sidecar as sidecar
from xgba_r62_private_original_provider_bundle import (
    PrivateBundleError,zip_manifest_pages,SOURCES,_sha
)

def _read_pack(r62_zip:Path):
    with zipfile.ZipFile(r62_zip) as z:
        if set(("manifest.json",
                "r62-private-original-three-world-provider.bin"))-set(z.namelist()):
            raise PrivateBundleError("R62 original provider resource files missing")
        manifest=json.loads(z.read("manifest.json"))
        blob=z.read(manifest["data_file"])
        if manifest.get("format")!=sidecar.FORMAT or \
           manifest.get("version")!=sidecar.VERSION or \
           manifest.get("source_identity",{}).get("id")!=\
                 "private-all-original-events-with-rocket-source-art" or \
           manifest["source_identity"].get("sha256")!=\
                 _sha(json.dumps(SOURCES,sort_keys=True).encode()):
            raise PrivateBundleError("Wrong original R62 provider identity")
        resources=manifest.get("resources",[])
        if not isinstance(resources,list) or not resources:
            raise PrivateBundleError("R62 provider resources absent")
        ids=set()
        for record in resources:
            if not isinstance(record,dict) or \
               set(record)!={"id","offset","length","sha256"}:
                raise PrivateBundleError("R62 resource manifest record malformed")
            rid=record["id"];offset=record["offset"];size=record["length"]
            if not isinstance(rid,str) or rid in ids or \
               type(offset) is not int or type(size) is not int or \
               offset<0 or not 1<=size<=16384 or \
               offset+size>len(blob):
                raise PrivateBundleError("Invalid R62 resource boundary or identity")
            ids.add(rid)
            if _sha(blob[offset:offset+size])!=record["sha256"]:
                raise PrivateBundleError("Corrupted old R62 page: "+rid)
        return manifest,blob,ids

def upgrade(r62_zip:Path,r49_zip:Path,out:Path):
    if out.exists() and any(out.iterdir()):
        raise PrivateBundleError("Destination must be empty, never overwrite source")
    manifest,original_blob,old_ids=_read_pack(r62_zip)
    source=zip_manifest_pages(r49_zip,"r49")
    # The reference data must be the SAME real R49 source pages already
    # included in R62, not a detached set of similarly named scripts.
    for rid,payload in source.items():
        if rid.endswith(".r48.npc"):continue
        match=next((r for r in manifest["resources"] if r["id"]==rid),None)
        if not match or original_blob[match["offset"]:match["offset"]+
                                      match["length"]]!=payload:
            raise PrivateBundleError("Original R49 page mismatched existing R62: "+rid)
    scripts={}
    for rid in ("emerald.r48.npc","rocket.r48.npc","heart_soul.r48.npc"):
        if rid not in source or rid in old_ids:
            raise PrivateBundleError("Original R48 guest script missing or already attached")
        scripts[rid]=source[rid]
        if len(scripts[rid])!=256:
            raise PrivateBundleError("Original R48 payload not exactly 256 bytes")
    out.mkdir(parents=True,exist_ok=True)
    name="r64-private-three-world-original-rocket-and-npc.bin"
    data=out/name
    records=list(manifest["resources"])
    with data.open("xb") as f:
        f.write(original_blob)
        for rid,raw in scripts.items():
            offset=f.tell()
            f.write(raw)
            records.append({"id":rid,"offset":offset,"length":len(raw),
                            "sha256":_sha(raw)})
    enriched=dict(manifest)
    enriched["data_file"]=name
    enriched["resources"]=records
    (out/"manifest.json").write_text(json.dumps(enriched,sort_keys=True)+"\n")
    verified=sidecar.load_manifest(out/"manifest.json",
                                  expected_source_identity=manifest["source_identity"])
    for rec in records:
        raw=b"".join(sidecar.iter_resource_chunks(verified,rec["id"]))
        if _sha(raw)!=rec["sha256"]:
            raise PrivateBundleError("Post-bundle original R48/graphics SHA mismatch")
    report={
        "source_ROM_sha256":SOURCES,
        "source_original_npc_script_resource_ids":list(scripts),
        "original_npc_script_length_each":256,
        "old_provider_resources":len(manifest["resources"]),
        "new_provider_resources":len(records),
        "original_rocket_art_pages_preserved_byte_exact":True,
        "original_R49_map_event_pages_preserved_byte_exact":True,
        "all_pages_sha256_verified":True,
        "full_original_johto_art_present":False,
        "original_script_played_in_native_emerald":False,
        "complete_three_world_fly_verified":False,
        "private_ROM_data_uploaded_to_public_git":False,
    }
    (out/"private-evidence.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n")
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r62-pack",required=True,type=Path)
    parser.add_argument("--r49-pack",required=True,type=Path)
    parser.add_argument("--private-out",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(upgrade(args.r62_pack,args.r49_pack,args.private_out),
                     sort_keys=True,indent=2))
if __name__=="__main__":main()

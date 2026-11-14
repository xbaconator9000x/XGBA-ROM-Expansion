#!/usr/bin/env python3
"""R85: bind an owner-private R79 original-source pack to a REAL built GBA ROM.

The private R79 archive is an *original-source catalogue*, not an mGBA
sidecar. Its offsets start at 0 and source_identity names the source
catalogue, not the built Emerald GBA. Copy exact R17 native sidecar resources,
append authenticated private bytes beyond 32 MiB, and bind resulting manifest
to the exact built Emerald SHA without publishing any game/asset bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import xgba_resource_sidecar as sidecar

GBA_WINDOW = 32 * 1024 * 1024
MAX_PRIVATE_DATA = 16 * 1024 * 1024
MAX_PRIVATE_RESOURCES = 4000
PRIVATE_ID = "private-all-original-events-with-rocket-source-art"
PRIVATE_SOURCE_DIGEST = "e4e1bc315221bcc5c2a08d865cedd839fbbefd0dbe78323b3fccafb211c03e00"
ORIGINAL_R79_SHA = "92980dd3dc1144e54288669988f60bf7d39a191980d428220675fb073c21e948"
REQUIRED_WITNESSES = {
    "emerald.r48.npc": "f2b7ce36eddd274eea749abbb7f8df405120651229c83208f3fa5e7f064e229c",
    "rocket.r48.npc": "48c1ccdb732a8be2db6e231f65731aa82fcae7c2e908469d5c35f11e1a8b4562",
    "heart_soul.r48.npc": "d671fce2609ca52db5314d14ecfaf89aca31863c9e36cff88a6c111a12094661",
}
REQUIRED_ORIGINAL_PREFIXES = ("r49.index.", "r49.events.", "r51.grid.",
                              "r52.mapmeta.", "r53.w1.", "r56.w1.")

class PrivateProviderAdmissionError(ValueError):
    pass

def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def _validated_entries(payload: bytes, entries: list, *, prefix: str):
    if not isinstance(entries, list) or not entries:
        raise PrivateProviderAdmissionError(prefix + ": empty resource index")
    names, spans = set(), []
    for e in entries:
        if not isinstance(e, dict) or set(e) != {"id","offset","length","sha256"}:
            raise PrivateProviderAdmissionError(prefix + ": resource schema changed")
        rid, start, count, claimed = e["id"], e["offset"], e["length"], e["sha256"]
        if not isinstance(rid, str) or not sidecar.IDENTIFIER.fullmatch(rid) or rid in names:
            raise PrivateProviderAdmissionError(prefix + ": duplicate/invalid resource ID")
        if type(start) is not int or type(count) is not int or \
           start < 0 or not 1 <= count <= 16384 or start + count > len(payload):
            raise PrivateProviderAdmissionError(prefix + ": invalid resource bounds")
        if not isinstance(claimed, str) or hashlib.sha256(payload[start:start+count]).hexdigest() != claimed:
            raise PrivateProviderAdmissionError(prefix + ": source SHA mismatch: " + rid)
        names.add(rid)
        spans.append((start,start+count))
    spans.sort()
    if any(a[1] > b[0] for a,b in zip(spans,spans[1:])):
        raise PrivateProviderAdmissionError(prefix + ": source resource sections overlap")
    return names

def bind_private_sources(
    built_emerald_rom: Path, native_manifest: Path, private_r79_zip: Path,
    out_dir: Path, *,
    expected_private_sha: str = ORIGINAL_R79_SHA,
    required_witnesses: dict[str,str] = REQUIRED_WITNESSES,
    required_prefixes: tuple[str,...] = REQUIRED_ORIGINAL_PREFIXES,
    hns_source_manifest: Path | None = None
):
    built_emerald_rom = Path(built_emerald_rom).resolve(strict=True)
    native_manifest = Path(native_manifest).resolve(strict=True)
    private_r79_zip = Path(private_r79_zip).resolve(strict=True)
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise PrivateProviderAdmissionError("Output must be a NEW private directory")
    base = sidecar.load_manifest(native_manifest)
    if digest_file(built_emerald_rom) != base.source_identity.sha256 or \
       built_emerald_rom.stat().st_size > GBA_WINDOW:
        raise PrivateProviderAdmissionError("Native manifest does not identify this exact built Emerald game")
    if digest_file(private_r79_zip) != expected_private_sha:
        raise PrivateProviderAdmissionError("Original private R79 ZIP SHA-256 changed")
    base_entries = [
        {"id": e.id, "offset": e.offset, "length": e.length, "sha256": e.sha256}
        for e in base.resources.values()
    ]
    # Base game resources have physical, not source-relative, positions.
    if not base_entries or any(e["offset"] <= GBA_WINDOW for e in base_entries):
        raise PrivateProviderAdmissionError("Native Emerald resource offsets are not beyond 32 MiB")
    base_data = base.data_path.read_bytes()
    names = _validated_entries(base_data,base_entries,prefix="native")
    with zipfile.ZipFile(private_r79_zip) as z:
        records = {i.filename:i for i in z.infolist()}
        if "manifest.json" not in records or records["manifest.json"].file_size > 1024*1024:
            raise PrivateProviderAdmissionError("Private original manifest unavailable/oversized")
        private_manifest = json.loads(z.read("manifest.json"))
        ident = private_manifest.get("source_identity",{})
        if ident.get("id") != PRIVATE_ID or ident.get("sha256") != PRIVATE_SOURCE_DIGEST:
            raise PrivateProviderAdmissionError("Original source-catalogue identity changed")
        data_name = private_manifest.get("data_file")
        if data_name not in records or records[data_name].file_size > MAX_PRIVATE_DATA:
            raise PrivateProviderAdmissionError("Private resource data unavailable/oversized")
        private_payload = z.read(data_name)
        original_entries = private_manifest.get("resources")
        if not isinstance(original_entries,list) or len(original_entries)>MAX_PRIVATE_RESOURCES:
            raise PrivateProviderAdmissionError("Private source resource count invalid")
        private_names = _validated_entries(private_payload, original_entries,prefix="original")
    if names & private_names:
        raise PrivateProviderAdmissionError("Native/private resource ID collision")
    for id, claimed in required_witnesses.items():
        found = next((e for e in original_entries if e["id"] == id),None)
        if not found or found["sha256"] != claimed:
            raise PrivateProviderAdmissionError("Missing exact original NPC Fly witness " + id)
    for prefix in required_prefixes:
        if not any(k.startswith(prefix) for k in private_names):
            raise PrivateProviderAdmissionError("Original source resource family missing: " + prefix)
    # R94: HnS is an official OPEN SOURCE project. The released v2.0.6
    # source build (R93) yields authentic source-linked world2 BG art. Merge
    # its independently hashed pages into the existing owner-private R79
    # provider. The original user's HnS ROM is not required and NO assets
    # are copied into the public repository.
    hns_data=b""
    hns_entries=[]
    hns_sha=None
    if hns_source_manifest is not None:
        source_manifest=Path(hns_source_manifest).resolve(strict=True)
        hns=sidecar.load_manifest(source_manifest)
        provenance_path=source_manifest.parent/"provenance.json"
        if not provenance_path.is_file():
            raise PrivateProviderAdmissionError("HnS upstream v2.0.6 source provenance is missing")
        provenance=json.loads(provenance_path.read_text())
        if hns.source_identity.id!="upstream-hns-v2.0.6-built" or \
           provenance.get("commit")!="167aa6d537b109bb229c231ddce4616974c4da71" or \
           provenance.get("rom_sha256")!=hns.source_identity.sha256 or \
           len(provenance.get("tilesets",[]))!=2 or \
           provenance.get("original_owner_rom_sha_equal_claimed") is not False:
            raise PrivateProviderAdmissionError("Wrong or falsely claimed official HnS source build")
        hns_data=hns.data_path.read_bytes()
        hns_entries=[{"id":x.id,"offset":x.offset,
                     "length":x.length,"sha256":x.sha256}
                     for x in hns.resources.values()]
        hns_names=_validated_entries(hns_data,hns_entries,prefix="upstream-hns")
        needed={"r53.w2.v2.t00f8823c.meta","r53.w2.v2.t00f885e4.meta"}
        if not needed.issubset(hns_names) or \
           names & hns_names or private_names & hns_names:
            raise PrivateProviderAdmissionError("Missing original HnS primary/secondary BG or resource ID collision")
        for prefix in ("r53.w2.v2.t00f8823c","r53.w2.v2.t00f885e4"):
            for suffix in (".g00",".m00",".a00",".p00"):
                if prefix+suffix not in hns_names:
                    raise PrivateProviderAdmissionError("Incomplete HnS source-built tile/metatile/palette section")
        hns_sha=hns.source_identity.sha256
    first = (len(base_data)+15) & ~15
    if first <= GBA_WINDOW:
        first = GBA_WINDOW+16
    if first + len(private_payload) >= 2**32:
        raise PrivateProviderAdmissionError("mGBA host source exceeds 32-bit resource range")
    hns_start=(first+len(private_payload)+15)&~15
    if hns_data and hns_start+len(hns_data)>=2**32:
        raise PrivateProviderAdmissionError("HnS open-source provider exceeds host GBA 32-bit address space")
    new_entries = base_entries + [
        {**entry,"offset":first+entry["offset"]} for entry in original_entries
    ] + [
        {**entry,"offset":hns_start+entry["offset"]} for entry in hns_entries
    ]
    # Recheck that no original resource absolute offset intersects native content.
    if any(e["offset"] < first or e["offset"]+e["length"] > first+len(private_payload)
           for e in new_entries[len(base_entries):]):
        raise PrivateProviderAdmissionError("Private source relocation invalid")
    out_dir.mkdir(parents=True,exist_ok=False)
    data_path = out_dir / "xgba-private-original-emerald-sidecar.bin"
    manifest_path = out_dir / "manifest.json"
    with data_path.open("wb") as f:
        f.write(base_data)
        f.write(bytes(first-len(base_data)))
        f.write(private_payload)
        if hns_data:
            f.write(bytes(hns_start-(first+len(private_payload))))
            f.write(hns_data)
    manifest = {
        "format":sidecar.FORMAT, "version":sidecar.VERSION,
        "source_identity":{
            "id":base.source_identity.id,
            "sha256":base.source_identity.sha256
        },
        "data_file":data_path.name, "resources":new_entries
    }
    manifest_path.write_text(json.dumps(manifest,sort_keys=True)+"\n")
    bound = sidecar.load_manifest(manifest_path)
    if len(bound.resources)!=len(new_entries) or bound.source_identity.sha256!=digest_file(built_emerald_rom):
        raise PrivateProviderAdmissionError("Relocated output manifest revalidation failed")
    with data_path.open("rb") as f:
        f.seek(0)
        if f.read(len(base_data))!=base_data:
            raise PrivateProviderAdmissionError("Existing native source bytes modified")
        for entry in new_entries[len(base_entries):]:
            f.seek(entry["offset"])
            if hashlib.sha256(f.read(entry["length"])).hexdigest()!=entry["sha256"]:
                raise PrivateProviderAdmissionError("Relocated original source SHA invalid")
    report = {
        "status":"R85_PRIVATE_SOURCE_MANIFEST_BOUND_TO_EXACT_BUILT_EMERALD",
        "native_rom_sha256":base.source_identity.sha256,
        "native_resources_preserved":len(base_entries),
        "authenticated_original_private_resources":len(original_entries),
        "authenticated_official_hns_source_build_bg_resources":len(hns_entries),
        "official_hns_release_commit":
            "167aa6d537b109bb229c231ddce4616974c4da71" if hns_entries else None,
        "official_hns_source_built_rom_sha256":hns_sha,
        "total_mgba_registerable_resources":len(new_entries),
        "original_source_catalogue_sha256":PRIVATE_SOURCE_DIGEST,
        "exact_parent_private_zip_sha256":expected_private_sha,
        "original_game_roms_published":False,
        "original_graphics_published":False,
        "actual_emulator_player_route_completed":False,
        "manifest_path":str(manifest_path),
        "data_file_size":data_path.stat().st_size
    }
    (out_dir/"R85_PRIVATE_BINDING_PROOF.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n"
    )
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--built-emerald",required=True,type=Path)
    p.add_argument("--native-manifest",required=True,type=Path)
    p.add_argument("--original-private-r79",required=True,type=Path)
    p.add_argument("--private-output-dir",required=True,type=Path)
    p.add_argument("--hns-source-manifest",type=Path,
                   help="R93 exact official open-source v2.0.6 Goldenrod BG source pack")
    args=p.parse_args()
    report=bind_private_sources(args.built_emerald,args.native_manifest,
                                args.original_private_r79,args.private_output_dir,
                                hns_source_manifest=args.hns_source_manifest)
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=="__main__":
    main()

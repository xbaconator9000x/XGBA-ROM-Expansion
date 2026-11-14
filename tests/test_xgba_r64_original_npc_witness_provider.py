"""R64 source-safe tests for original NPC script witness provider admission.

Author all fixture bytes. Never publish the user's actual source dialogue.
"""
from __future__ import annotations
import hashlib
import io
import tempfile
import json
from pathlib import Path
import struct
import sys
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r62_private_original_provider_bundle as r64
import xgba_r64_upgrade_original_provider as upgrade

CASES=(
    ("emerald.r48.npc","emerald",0,0,9,2,12,13,17,0x1e8022,0x1e8acf),
    ("rocket.r48.npc","rocket",1,0,9,2,14,13,17,0x215543,0x1dc3364),
    ("heart_soul.r48.npc","heart_soul",2,0,4,7,39,22,406,0x390519,0x3908e6),
)
def fixture():
    archive=io.BytesIO()
    records=[]
    with zipfile.ZipFile(archive,"w") as z:
        for rid,name,world,group,m,local,x,y,gfx,s_at,t_at in CASES:
            # Test-authored speech, not game text or an original ROM byte.
            speech=b"AUTHORED UNIT TEST\xff"
            payload=bytearray(256)
            payload[:4]=b"X48N"
            payload[4:9]=bytes((1,world,group,m,local))
            struct.pack_into("<hhHIIHH",payload,9,x,y,gfx,s_at,t_at,9,len(speech))
            payload[32:41]=b"\x0f\x00"+struct.pack("<I",0x08000000+t_at)+b"\x09\x02\x02"
            payload[41:41+len(speech)]=speech
            raw=bytes(payload)
            z.writestr(rid+".bin",raw)
            records.append({
                "id":rid,"length":256,"source_sha256":r64.SOURCES[name],
                "original_npc_id":local,"original_script_offset":s_at,
                "original_text_offset":t_at,
                "sha256":hashlib.sha256(raw).hexdigest(),
            })
        z.writestr("private-r48-original-npc-witnesses.json",
                   json.dumps({"resources":records}))
    archive.seek(0)
    return archive.getvalue()

def authored_packs(root:Path):
    """Create one completely authored source page + three authored witnesses."""
    src=fixture()
    with zipfile.ZipFile(io.BytesIO(src)) as z:
        original={n:z.read(n) for n in z.namelist()}
    page=bytes((i*9+3)%256 for i in range(16384))
    source_entry={
        "id":"r49.index.000","offset":0,"length":len(page),
        "sha256":hashlib.sha256(page).hexdigest()
    }
    manifest={
       "sources":{name:{"sha256":digest}
                  for name,digest in r64.SOURCES.items()},
       "manifest_resources":[source_entry],
    }
    original["private-manifest.json"]=json.dumps(manifest).encode()
    original["r49.index.000.bin"]=page
    r49=root/"authored-r49.zip"
    with zipfile.ZipFile(r49,"w") as z:
        for n,data in original.items():z.writestr(n,data)
    origin={
       "id":"private-all-original-events-with-rocket-source-art",
       "sha256":hashlib.sha256(json.dumps(r64.SOURCES,sort_keys=True).encode()).hexdigest()
    }
    resource_manifest={
        "format":"xgba-resource-manifest","version":1,
        "source_identity":origin,"data_file":
           "r62-private-original-three-world-provider.bin",
        "resources":[source_entry],
    }
    r62=root/"authored-r62.zip"
    with zipfile.ZipFile(r62,"w") as z:
        z.writestr("manifest.json",json.dumps(resource_manifest))
        z.writestr(resource_manifest["data_file"],page)
    return r62,r49

class PrivateProviderUpgraderTests(unittest.TestCase):
    def test_authored_provider_remains_byte_identical_after_original_witness_attach(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            r62,r49=authored_packs(root)
            out=root/"upgraded"
            summary=upgrade.upgrade(r62,r49,out)
            self.assertEqual(summary["old_provider_resources"],1)
            self.assertEqual(summary["new_provider_resources"],4)
            self.assertFalse(summary["original_script_played_in_native_emerald"])
            self.assertTrue(summary["all_pages_sha256_verified"])
            manifest=json.loads((out/"manifest.json").read_text())
            self.assertEqual({r["id"] for r in manifest["resources"]},{
                "r49.index.000","emerald.r48.npc",
                "rocket.r48.npc","heart_soul.r48.npc",
            })
            blob=(out/manifest["data_file"]).read_bytes()
            with zipfile.ZipFile(r62) as z:
                previous=z.read("r62-private-original-three-world-provider.bin")
            self.assertEqual(blob[:len(previous)],previous)
            self.assertEqual(len(blob)-len(previous),3*256)
            with self.assertRaisesRegex(r64.PrivateBundleError,"empty"):
                upgrade.upgrade(r62,r49,out)

    def test_reject_original_event_index_page_from_unrelated_pack(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            r62,r49=authored_packs(root)
            with zipfile.ZipFile(r62) as z:
                files={n:z.read(n) for n in z.namelist()}
            wrong=bytearray(files["r62-private-original-three-world-provider.bin"])
            wrong[31]^=1
            files["r62-private-original-three-world-provider.bin"]=bytes(wrong)
            manifest=json.loads(files["manifest.json"])
            manifest["resources"][0]["sha256"]=hashlib.sha256(wrong).hexdigest()
            files["manifest.json"]=json.dumps(manifest).encode()
            bad=root/"bad-r62.zip"
            with zipfile.ZipFile(bad,"w") as z:
                for n,raw in files.items():z.writestr(n,raw)
            with self.assertRaisesRegex(r64.PrivateBundleError,"mismatched existing R62"):
                upgrade.upgrade(bad,r49,root/"new")

class PrivateOriginalNpcWitnessTests(unittest.TestCase):
    def test_all_three_original_resource_ids_and_hashes_are_required(self):
        with zipfile.ZipFile(io.BytesIO(fixture())) as z:
            pages=r64.original_r48_witnesses(z)
        self.assertEqual(sorted(pages),sorted(c[0] for c in CASES))
        self.assertTrue(all(len(p)==256 for p in pages.values()))
        self.assertEqual([p[5] for p in pages.values()],[0,1,2])
        self.assertFalse(any(b"Rocket Cache" in p for p in pages.values()))

    def test_reject_source_identity_mismatch(self):
        data=fixture()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            files={n:z.read(n) for n in z.namelist()}
        meta=json.loads(files["private-r48-original-npc-witnesses.json"])
        meta["resources"][1]["source_sha256"]="0"*64
        files["private-r48-original-npc-witnesses.json"]=json.dumps(meta).encode()
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for n,v in files.items():z.writestr(n,v)
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            with self.assertRaisesRegex(r64.PrivateBundleError,"catalogue changed"):
                r64.original_r48_witnesses(z)

    def test_reject_tampered_original_payload(self):
        with zipfile.ZipFile(io.BytesIO(fixture())) as z:
            files={n:z.read(n) for n in z.namelist()}
        tampered=bytearray(files["rocket.r48.npc.bin"])
        tampered[52]^=0xff
        files["rocket.r48.npc.bin"]=bytes(tampered)
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for n,v in files.items():z.writestr(n,v)
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            with self.assertRaisesRegex(r64.PrivateBundleError,"SHA integrity"):
                r64.original_r48_witnesses(z)

    def test_reject_reencoded_original_text_pointer_even_with_valid_sha(self):
        with zipfile.ZipFile(io.BytesIO(fixture())) as z:
            files={n:z.read(n) for n in z.namelist()}
        target="heart_soul.r48.npc.bin"
        tampered=bytearray(files[target])
        tampered[34]^=1
        files[target]=bytes(tampered)
        meta=json.loads(files["private-r48-original-npc-witnesses.json"])
        meta["resources"][2]["sha256"]=hashlib.sha256(files[target]).hexdigest()
        files["private-r48-original-npc-witnesses.json"]=json.dumps(meta).encode()
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for n,v in files.items():z.writestr(n,v)
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            with self.assertRaisesRegex(r64.PrivateBundleError,"interpreter bytecode"):
                r64.original_r48_witnesses(z)

    def test_reject_missing_original_witness(self):
        with zipfile.ZipFile(io.BytesIO(fixture())) as z:
            files={n:z.read(n) for n in z.namelist()
                   if n!="heart_soul.r48.npc.bin"}
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for n,v in files.items():z.writestr(n,v)
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
            with self.assertRaises(KeyError):
                r64.original_r48_witnesses(z)

if __name__=="__main__":unittest.main()

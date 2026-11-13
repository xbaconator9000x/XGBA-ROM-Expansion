"""R64 source-safe tests for original NPC script witness provider admission.

Author all fixture bytes. Never publish the user's actual source dialogue.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r62_private_original_provider_bundle as r64

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

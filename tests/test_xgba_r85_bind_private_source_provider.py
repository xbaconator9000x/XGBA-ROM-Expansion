"""R85 authored-data tests: private original pack must be bound to built GBA SHA.

Do not commit any actual source-ROM graphics, NPC dialogue or R79 pack.
"""
from pathlib import Path
import hashlib,json,struct,sys,tempfile,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import xgba_r85_bind_private_source_provider as r85

def sha(x):return hashlib.sha256(x).hexdigest()
class R85OriginalBindingTests(unittest.TestCase):
 def setup_assets(self,root):
  rom=root/"authored-emerald.gba";rom.write_bytes(b"ORIGINAL_AUTHORED_FIXTURE"*64)
  base=root/"base";base.mkdir()
  raw=bytearray(32*1024*1024+32768)
  at=32*1024*1024+8192;body=b"AUTHORED_Emerald_Resource"
  raw[at:at+len(body)]=body
  (base/"game.bin").write_bytes(raw)
  m={"format":"xgba-resource-manifest","version":1,
     "source_identity":{"id":"authored-build","sha256":sha(rom.read_bytes())},
     "data_file":"game.bin","resources":[
       {"id":"emerald.littleroot","offset":at,"length":len(body),"sha256":sha(body)}
     ]}
  (base/"manifest.json").write_text(json.dumps(m))
  sections=[("emerald.r48.npc",b"AUTHORED_WITNESS_EMERALD"),
            ("rocket.r48.npc",b"AUTHORED_WITNESS_ROCKET"),
            ("heart_soul.r48.npc",b"AUTHORED_WITNESS_JOHTO"),
            ("r49.index.000",b"AUTHORED_INDEX"),
            ("r49.events.000",b"AUTHORED_EVENTS"),
            ("r51.grid.00000",b"AUTHORED_GRID"),
            ("r52.mapmeta.000",b"AUTHORED_MAPMETA"),
            ("r53.w1.v2.t00e9ffe0.meta",b"AUTHORED_TILESET"),
            ("r56.w1.s0011.meta",b"AUTHORED_SPRITE")]
  payload=b"";entries=[];wid={}
  for name,part in sections:
   entries.append({"id":name,"offset":len(payload),"length":len(part),"sha256":sha(part)})
   payload+=part
   if ".r48.npc" in name:wid[name]=sha(part)
  zpath=root/"private-source-fixture.zip"
  with zipfile.ZipFile(zpath,"w") as z:
   z.writestr("manifest.json",json.dumps({
     "format":"xgba-resource-manifest","version":1,
     "source_identity":{"id":r85.PRIVATE_ID,"sha256":r85.PRIVATE_SOURCE_DIGEST},
     "data_file":"authored-private.bin","resources":entries}))
   z.writestr("authored-private.bin",payload)
  return rom,base/"manifest.json",zpath,wid
 def test_authored_resources_relocated_byte_identical_and_rom_bound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom,base,private,witness=self.setup_assets(root)
   result=r85.bind_private_sources(rom,base,private,root/"out",
        expected_private_sha=r85.digest_file(private),required_witnesses=witness)
   self.assertEqual(result["native_resources_preserved"],1)
   self.assertEqual(result["authenticated_original_private_resources"],9)
   self.assertEqual(result["total_mgba_registerable_resources"],10)
   m=json.loads((root/"out/manifest.json").read_text())
   self.assertEqual(m["source_identity"]["sha256"],sha(rom.read_bytes()))
   data=(root/"out/xgba-private-original-emerald-sidecar.bin").read_bytes()
   self.assertEqual(data[m["resources"][0]["offset"]:][:25],b"AUTHORED_Emerald_Resource")
   for e in m["resources"]:
    self.assertGreater(e["offset"],32*1024*1024)
    self.assertEqual(sha(data[e["offset"]:e["offset"]+e["length"]]),e["sha256"])
   self.assertFalse(result["actual_emulator_player_route_completed"])
 def test_rejects_wrong_rom_and_parent_sha_no_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom,base,private,witness=self.setup_assets(root)
   rom.write_bytes(b"WRONG_BUILD")
   with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"exact built Emerald"):
    r85.bind_private_sources(rom,base,private,root/"bad",expected_private_sha=r85.digest_file(private),
                             required_witnesses=witness)
   self.assertFalse((root/"bad").exists())
   with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"original private R79"):
    r85.bind_private_sources(rom,base,private,root/"bad",expected_private_sha="0"*64,
                             required_witnesses=witness)
 def test_rejects_missing_exact_authentic_original_witness(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom,base,private,witness=self.setup_assets(root)
   wrong={**witness,"rocket.r48.npc":"0"*64}
   with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"exact original NPC"):
    r85.bind_private_sources(rom,base,private,root/"bad",expected_private_sha=r85.digest_file(private),
                             required_witnesses=wrong)
if __name__=="__main__":unittest.main()

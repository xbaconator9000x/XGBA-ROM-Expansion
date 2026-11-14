"""R94 original public HnS v2.0.6 source pages merge with R79 and Emerald."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
import xgba_r85_bind_private_source_provider as r85
from test_xgba_r85_bind_private_source_provider import R85OriginalBindingTests
def sha(x):return hashlib.sha256(x).hexdigest()
class R94OfficialSourceMergeTests(unittest.TestCase):
 def authored_hns(self,root,*,corrupt=False):
  folder=root/"hns";folder.mkdir()
  ids=[]
  for prefix in ("r53.w2.v2.t00f8823c","r53.w2.v2.t00f885e4"):
   ids.extend(prefix+suffix for suffix in (".meta",".g00",".m00",".a00",".p00"))
  offset=0;data=b"";entries=[]
  for key in ids:
   blob=(b"AUTHORED_ART_NOT_REAL_HNS_"+key.encode()).ljust(64,b"\0")
   entries.append({"id":key,"offset":offset,"length":len(blob),"sha256":sha(blob)})
   data+=blob;offset+=len(blob)
  (folder/"source.bin").write_bytes(data)
  binarysha="d"*64
  identity={"id":"upstream-hns-v2.0.6-built","sha256":binarysha}
  (folder/"manifest.json").write_text(json.dumps({
   "format":"xgba-resource-manifest","version":1,
   "source_identity":identity,"data_file":"source.bin","resources":entries}))
  (folder/"provenance.json").write_text(json.dumps({
   "commit":"167aa6d537b109bb229c231ddce4616974c4da71",
   "rom_sha256":"a"*64 if corrupt else binarysha,
   "tilesets":[{"source_symbol":"one"},{"source_symbol":"two"}],
   "original_owner_rom_sha_equal_claimed":False}))
  return folder/"manifest.json"
 def test_combined_native_owner_original_rocket_and_upstream_hns_resources(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   rom,native,original,wit=R85OriginalBindingTests().setup_assets(root)
   hns=self.authored_hns(root)
   result=r85.bind_private_sources(rom,native,original,root/"out",
      expected_private_sha=r85.digest_file(original),
      required_witnesses=wit,hns_source_manifest=hns)
   self.assertEqual(result["authenticated_official_hns_source_build_bg_resources"],10)
   manifest=json.loads((root/"out/manifest.json").read_text())
   self.assertEqual(len(manifest["resources"]),20)
   self.assertEqual(result["total_mgba_registerable_resources"],20)
   data=(root/"out/xgba-private-original-emerald-sidecar.bin").read_bytes()
   ids=set()
   for row in manifest["resources"]:
    self.assertNotIn(row["id"],ids);ids.add(row["id"])
    self.assertEqual(sha(data[row["offset"]:row["offset"]+row["length"]]),row["sha256"])
   self.assertIn("r53.w2.v2.t00f8823c.meta",ids)
   self.assertIn("r53.w2.v2.t00f885e4.p00",ids)
   self.assertFalse(result["actual_emulator_player_route_completed"])
 def test_wrong_source_provenance_fails_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rom,native,original,wit=R85OriginalBindingTests().setup_assets(root)
   hns=self.authored_hns(root,corrupt=True)
   with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"Wrong or falsely"):
    r85.bind_private_sources(rom,native,original,root/"out",
      expected_private_sha=r85.digest_file(original),
      required_witnesses=wit,hns_source_manifest=hns)
   self.assertFalse((root/"out").exists())
if __name__=="__main__":unittest.main()

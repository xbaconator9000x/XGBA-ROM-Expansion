"""R95 source-authenticated HnS OBJ merge: authored-only provider fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
sys.path.insert(0,str(ROOT/"tests"))
import xgba_r95_hns_original_obj as r95
import xgba_r85_bind_private_source_provider as r85
from test_xgba_r94_hns_official_source_provider_merge import R94OfficialSourceMergeTests
from test_xgba_r85_bind_private_source_provider import R85OriginalBindingTests
from test_xgba_r95_hns_original_obj import fixture

def sha(x):return hashlib.sha256(x).hexdigest()

def source_actor_pack(root,hns_manifest):
    src,rom,symbols=fixture(root/"authored-hns")
    parts,original=r95.extract_original_boy2(src,rom,symbols)
    manifest=json.loads(hns_manifest.read_text())
    raw_path=hns_manifest.parent/manifest["data_file"]
    raw=bytearray(raw_path.read_bytes())
    for rid,data in parts:
        offset=len(raw);raw.extend(data)
        manifest["resources"].append({"id":rid,"offset":offset,
            "length":len(data),"sha256":sha(data)})
    raw_path.write_bytes(raw)
    hns_manifest.write_text(json.dumps(manifest))
    provenance_path=hns_manifest.parent/"provenance.json"
    provenance=json.loads(provenance_path.read_text())
    provenance["npc_sprites"]=[original]
    provenance_path.write_text(json.dumps(provenance))
    return parts

class R95MergedActualActorContract(unittest.TestCase):
    def setup(self,root):
        emerald,native,original,witness=R85OriginalBindingTests().setup_assets(root)
        hns=R94OfficialSourceMergeTests().authored_hns(root)
        parts=source_actor_pack(root,hns)
        return emerald,native,original,witness,hns,parts
    def test_source_9_frame_sprite_merged_into_exact_native_emerald_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);emerald,native,original,witness,hns,parts=self.setup(root)
            report=r85.bind_private_sources(emerald,native,original,root/"out",
                expected_private_sha=r85.digest_file(original),
                required_witnesses=witness,hns_source_manifest=hns)
            self.assertEqual(report["authenticated_official_hns_source_build_bg_resources"],10)
            self.assertEqual(report["authenticated_official_hns_source_build_obj_resources"],5)
            self.assertEqual(report["total_mgba_registerable_resources"],25)
            output=json.loads((root/"out/manifest.json").read_text())
            self.assertEqual(sum(r["id"].startswith("r56.w2.s0196") for r in output["resources"]),5)
            self.assertFalse(report["actual_emulator_player_route_completed"])
    def test_declared_hns_actor_missing_original_oam_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);emerald,native,original,witness,hns,parts=self.setup(root)
            m=json.loads(hns.read_text())
            m["resources"]=[r for r in m["resources"] if r["id"]!="r56.w2.s0196.o00"]
            hns.write_text(json.dumps(m))
            with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"Incomplete original HnS"):
                r85.bind_private_sources(emerald,native,original,root/"out",
                    expected_private_sha=r85.digest_file(original),
                    required_witnesses=witness,hns_source_manifest=hns)
            self.assertFalse((root/"out").exists())
    def test_valid_host_sha_cannot_hide_corrupted_original_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);emerald,native,original,witness,hns,parts=self.setup(root)
            m=json.loads(hns.read_text())
            row=next(r for r in m["resources"] if r["id"]=="r56.w2.s0196.a00")
            payload=hns.parent/m["data_file"]
            raw=bytearray(payload.read_bytes());raw[row["offset"]]^=0x40
            payload.write_bytes(raw)
            # Even if the malicious manifest updates its page SHA, original
            # source-provenance section SHA/CRC must still reject the mutation.
            row["sha256"]=sha(raw[row["offset"]:row["offset"]+row["length"]])
            hns.write_text(json.dumps(m))
            with self.assertRaisesRegex(r85.PrivateProviderAdmissionError,"section integrity changed"):
                r85.bind_private_sources(emerald,native,original,root/"out",
                    expected_private_sha=r85.digest_file(original),
                    required_witnesses=witness,hns_source_manifest=hns)
            self.assertFalse((root/"out").exists())
if __name__=="__main__":unittest.main()

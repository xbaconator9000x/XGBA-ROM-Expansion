"""Negative controls for Phase 1 pinned bulk machine triage."""
import hashlib,json,sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import phase1_bulk_triage as t
class Tests(unittest.TestCase):
 def test_git_blob(self):
  self.assertEqual(t.git_blob(b'abc'),'f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f')
 def test_structure(self):
  b=b'#include "x.h"\n#ifdef X\nvoid f(void);\n#endif\n';s=t.structure(b)
  self.assertEqual(s['source_lines'],4)
  self.assertEqual(s['includes'],[{'line':1,'include':'x.h'}])
  self.assertEqual(s['conditional_directive_lines'],[2,4])
  self.assertEqual(s['whole_blob_sha256'],hashlib.sha256(b).hexdigest())
 def test_deterministic_selection_and_resume(self):
  q=[dict(repo='r',path=str(i),priority=p,incoming_includes='0',lexical_match_count='0') for i,p in [(1,'P2'),(2,'P0'),(3,'P1'),(4,'P0')]]
  self.assertEqual([x['path'] for x in t.select(q,{('r','2')},2,0)],['4','3'])
  self.assertEqual([x['path'] for x in t.select(q,{('r','2')},1,1)],['3'])
 def test_exact_git_tree_and_blob_verification(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);checkout=root/'pokefirered';checkout.mkdir()
   subprocess.run(['git','-C',str(checkout),'init','-q'],check=True)
   (checkout/'src').mkdir();(checkout/'src'/'a.c').write_bytes(b'int f(void) { return 7; }\n')
   subprocess.run(['git','-C',str(checkout),'add','.'],check=True)
   subprocess.run(['git','-C',str(checkout),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-qm','fixture'],check=True)
   pin=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
   blob=t.git_blob(b'int f(void) { return 7; }\n')
   self.assertEqual(t.source_bytes(root,'pret/pokefirered',pin,'src/a.c',blob),b'int f(void) { return 7; }\n')
   with self.assertRaisesRegex(ValueError,'tree path/blob mismatch'):t.source_bytes(root,'pret/pokefirered',pin,'src/a.c','f'*40)
   with self.assertRaisesRegex(ValueError,'Pinned checkout mismatch'):t.source_bytes(root,'pret/pokefirered','0'*40,'src/a.c',blob)
 def test_gate_change_fails_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'phase1_mapping_gate.json').write_text(json.dumps({'decision':'PASS_MAPPING_ONLY','approved_semantic_dispositions':0}))
   with self.assertRaisesRegex(ValueError,'gate changed'):t.build(root,root/'register',root/'out',1,0)
 def test_invalid_batch_bounds(self):
  with self.assertRaises(ValueError):t.select([],set(),1,0)
 def test_canonical_hash_stable(self):
  self.assertEqual(t.canonical({'b':2,'a':1}),b'{"a":1,"b":2}')
 def test_typed_binary_formats_fail_closed(self):
  import struct,zlib
  def chunk(tag,payload):
   return struct.pack('>I',len(payload))+tag+payload+struct.pack('>I',zlib.crc32(tag+payload)&0xffffffff)
  ihdr=struct.pack('>IIBBBBB',1,1,8,2,0,0,0)
  png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',ihdr)+chunk(b'tEXt',b'EEPROM SaveSector')+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\x00'))+chunk(b'IEND',b'')
  gba=bytearray(192);gba[0xb2]=0x96;gba[0xbd]=(-sum(gba[0xa0:0xbd])-0x19)&255
  gba=bytes(gba)+b'EEPROM SaveSector'
  cases=[('image.png',png,'image_png'),('game.gba',gba,'compiled_rom'),('layout.bin',b'\x00EEPROM\x00','opaque_binary'),('layout.bin',b'EEPROM','unknown_binary'),('corrupt.png',png[:-1]+b'!', 'unknown_binary'),('bad.gba',b'\x00'*192+b'EEPROM','unknown_binary'),('unknown.dat',b'\x00EEPROM','unknown_binary')]
  for path,data,kind in cases:
   with self.subTest(path=path,kind=kind):
    s=t.typed_structure(path,data)
    self.assertEqual(s['file_kind'],kind)
    self.assertIsNone(s['source_lines'])
    self.assertIsNone(s['all_lines_sha256'])
    self.assertFalse(s['risk_flags_line_anchors'])
    self.assertEqual(s['whole_blob_sha256'],hashlib.sha256(data).hexdigest())
 def test_typed_text_anchors(self):
  b=b'#include "x.h"\n#ifdef X\nEEPROM\n#endif\n'
  s=t.typed_structure('sample.h',b)
  self.assertEqual(s['file_kind'],'text_source')
  self.assertEqual(s['source_lines'],4)
  self.assertEqual(s['includes'][0],{'line':1,'include':'x.h'})
  self.assertEqual(s['risk_flags_line_anchors']['save_state'],[3])
 def test_typed_integrity_negative_controls(self):
  import phase1_bulk_triage_integrity as integrity
  data=b'\x00EEPROM\x00'
  q={'repo':'pret/pokefirered','path':'layout.bin','blob_sha':t.git_blob(data),'evidence_sha256':'a'*64,'priority':'P2'}
  x={'identity':{'repository':q['repo'],'pinned_commit':t.PINS[q['repo']],'path':q['path'],'git_blob_sha1':q['blob_sha']},
     'evidence':{'dossier_sha256':q['evidence_sha256'],'snapshot_provenance_verified':True,'source_blob_reverified_this_run':True},
     'priority':'P2','state':'MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW','prepared_whole_file_candidate':False,'independent_approval':False,
     'whole_file_structure':t.typed_structure('layout.bin',data),'machine_triage':{'lexical_evidence_applicable':False},'review_obligations':['whole-file review required']}
  integrity.check_record(x,q,'xgba-phase1-machine-triage-v2')
  for field,value in [('source_lines',1),('risk_flags_line_anchors',{'save_state':[1]})]:
   bad=json.loads(json.dumps(x));bad['whole_file_structure'][field]=value
   with self.assertRaises(ValueError):integrity.check_record(bad,q,'xgba-phase1-machine-triage-v2')
  bad=json.loads(json.dumps(x));bad['machine_triage']['lexical_rule_counts']={'save_state':1}
  with self.assertRaises(ValueError):integrity.check_record(bad,q,'xgba-phase1-machine-triage-v2')
  bad=json.loads(json.dumps(x));bad['independent_approval']=True
  with self.assertRaises(ValueError):integrity.check_record(bad,q,'xgba-phase1-machine-triage-v2')
  old=json.loads(json.dumps(x));old['whole_file_structure']=t.structure(data)
  integrity.check_record(old,q,'xgba-phase1-machine-triage-v1')
  with self.assertRaises(ValueError):integrity.check_record(x,q,'xgba-phase1-machine-triage-v3')
if __name__=='__main__':unittest.main()

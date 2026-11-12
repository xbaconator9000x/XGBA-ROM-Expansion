"""R37 ROM-independent static script graph tests. Never distribute game bytes."""
from __future__ import annotations
import hashlib
import struct
import sys
from pathlib import Path
import random
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import xgba_r37_script_graph as r37
import xgba_r34_binary_maps as r34
import xgba_r36_binary_pages as r36
from test_xgba_r34_binary_maps import FakeEmeraldBinary

class ScriptGraphTests(unittest.TestCase):
    def setUp(self):
        self.rom=bytearray(512)
        self.root={'source_rom_offset':20,'group':0,'map':9,'kind':'object_event_script','slot':0}

    def put(self,off,command):
        self.rom[off:off+len(command)]=command

    def scan(self,root=None):
        return r37.analyze_root(self.rom,root or self.root)

    def test_identify_flag_variable_item_and_script_end(self):
        self.put(20,b'\x29'+struct.pack('<H',0x123)+b'\x16'+struct.pack('<HH',0x4020,7)+
                 b'\x44'+struct.pack('<HH',53,1)+b'\x02')
        result=self.scan()
        self.assertEqual(result['status'],'syntactically_terminated')
        self.assertEqual(result['recognized_commands'],4)
        self.assertEqual(result['dependencies']['flags'],[0x123])
        self.assertEqual(result['dependencies']['vars'],[0x4020])
        self.assertEqual(result['dependencies']['items'],[53])

    def test_goto_never_guesses_unreachable_fallthrough(self):
        self.put(20,b'\x05'+struct.pack('<I',0x08000000+200)+b'\x44'+struct.pack('<HH',999,1)+b'\x02')
        self.put(200,b'\x29\x34\x12\x02')
        result=self.scan()
        self.assertEqual(result['recognized_commands'],3)
        self.assertEqual(result['dependencies']['items'],[])
        self.assertEqual(result['dependencies']['flags'],[0x1234])
        self.assertEqual(result['branch_targets'],[200])

    def test_call_includes_fallthrough_and_called_branch(self):
        self.put(20,b'\x04'+struct.pack('<I',0x08000000+200)+b'\x2a\x35\x12\x02')
        self.put(200,b'\x29\x34\x12\x03')
        result=self.scan()
        self.assertEqual(result['recognized_commands'],5)
        self.assertEqual(result['dependencies']['flags'],[0x1234,0x1235])

    def test_conditional_branch_tracks_both_without_executing(self):
        self.put(20,b'\x06\x01'+struct.pack('<I',0x08000000+200)+b'\x02')
        self.put(200,b'\x44'+struct.pack('<HH',17,2)+b'\x02')
        self.assertEqual(self.scan()['dependencies']['items'],[17])
        self.assertEqual(self.scan()['recognized_commands'],4)

    def test_repeated_branch_cycle_does_not_loop(self):
        self.put(20,b'\x05'+struct.pack('<I',0x08000000+20))
        r=self.scan()
        self.assertEqual(r['recognized_commands'],1)
        self.assertEqual(r['branch_targets'],[20])

    def test_bounded_branch_explosion_is_not_silent(self):
        for n in range(30):
            off=20+n*6
            self.put(off,b'\x06\x01'+struct.pack('<I',0x08000000+250+n))
        for n in range(30):self.put(250+n,b'\x02')
        r=r37.analyze_root(self.rom,self.root,max_commands=12,max_branches=4)
        self.assertTrue(r['counts'].get('instruction_budget_reached') or
                        r['counts'].get('branch_budget_reached'))
        self.assertEqual(r['status'],'bounded_or_uncertain')

    def test_unrecognized_command_must_stop_not_infer_length(self):
        self.put(20,b'\xfe\x29\x34\x12\x02')
        r=self.scan()
        self.assertEqual(r['recognized_commands'],0)
        self.assertEqual(r['status'],'bounded_or_uncertain')
        self.assertEqual(r['counts']['unsupported_opcode'],1)
        self.assertEqual(r['dependencies']['flags'],[])

    def test_variable_length_trainerbattle_stops_before_payload(self):
        self.put(20,b'\x5c\x29\x34\x12\x02')
        self.assertEqual(self.scan()['recognized_commands'],0)
        self.assertEqual(self.scan()['counts']['unsupported_opcode'],1)

    def test_truncated_u32_is_detected(self):
        tiny=bytearray(b'\x02'*21)
        tiny[20]=0x04
        r=r37.analyze_root(tiny,self.root)
        self.assertEqual(r['counts']['truncated_command'],1)

    def test_untrusted_control_pointer_rejected_without_execution(self):
        self.put(20,b'\x05'+struct.pack('<I',0x03000000))
        r=self.scan()
        self.assertEqual(r['counts']['invalid_branch_target'],1)
        self.assertEqual(r['status'],'bounded_or_uncertain')

    def test_native_callback_records_adaptation_dependency(self):
        self.put(20,b'\x23'+struct.pack('<I',0x08000080)+b'\x02')
        result=self.scan()
        self.assertEqual(result['counts']['native_engine_callback_dependency'],1)
        self.assertEqual(result['status'],'syntactically_terminated')
        self.assertEqual(result['recognized_commands'],2)

    def test_warp_record_preserves_original_destination_ids(self):
        self.put(20,b'\x39'+struct.pack('<BBBHH',75,13,255,8,9)+b'\x02')
        r=self.scan()
        self.assertEqual(r['counts']['warp_references'],1)
        self.assertEqual(r['recognized_commands'],2)
        self.assertEqual(self.rom[21:28],struct.pack('<BBBHH',75,13,255,8,9))

    def test_duplicate_entrypoints_scanned_once_but_all_sources_counted(self):
        self.put(20,b'\x02')
        roots=[dict(self.root),dict(self.root,group=3,map=16),dict(self.root,source_rom_offset=21)]
        self.put(21,b'\x03')
        r=r37.analyze_rom(self.rom,roots)
        self.assertEqual(r['entrypoint_references'],3)
        self.assertEqual(r['unique_entrypoints'],2)
        self.assertEqual(r['entrypoints_scanned'],2)
        self.assertEqual(r['recognized_commands'],2)
        self.assertFalse(r['analysis_executed_scripts'])

    def test_no_mutation_of_original_binary(self):
        self.put(20,b'\x29\x12\x00\x02')
        original=hashlib.sha256(self.rom).hexdigest()
        r37.analyze_rom(self.rom,[self.root])
        self.assertEqual(original,hashlib.sha256(self.rom).hexdigest())

    def test_untrusted_entrypoint_fails_closed(self):
        for value in (-1,512,True,'20'):
            with self.subTest(value=value):
                with self.assertRaises(r37.ScriptError):
                    r37.analyze_root(self.rom,dict(self.root,source_rom_offset=value))

    def test_large_root_budget_refuses_false_completion(self):
        self.put(20,b'\x02')
        rs=[dict(self.root,source_rom_offset=20),dict(self.root,source_rom_offset=21),
            dict(self.root,source_rom_offset=22)]
        d=r37.analyze_rom(self.rom,rs,max_total_commands=1)
        self.assertEqual(d['entrypoints_scanned'],1)
        self.assertEqual(d['unscanned_unique_entrypoints_due_to_budget'],2)
        self.assertFalse(d['analysis_executed_scripts'])

    def test_hostile_random_bytes_never_escape_bounds_or_execute(self):
        rand=random.Random(924)
        for _ in range(400):
            raw=rand.randbytes(300)
            r=r37.analyze_root(raw,dict(self.root,source_rom_offset=rand.randrange(300)))
            self.assertLessEqual(r['recognized_commands'],r37.MAX_STEPS_PER_ROOT)
            self.assertIn(r['status'],('bounded_or_uncertain','syntactically_partial','syntactically_terminated'))

    def test_known_original_r36_roots_are_supported_as_inputs(self):
        fake=FakeEmeraldBinary()
        image=bytearray(fake.image())
        script=0x1A0000
        # No map source nor decoded script data is copied from any real game.
        image[script:script+4]=b'\x29\x01\x00\x02'
        # ObjectEvent pointer at +16 on first map.
        event=fake.first_event
        obj=struct.unpack_from('<I',image,event+4)[0]-r34.GBA_BASE
        struct.pack_into('<I',image,obj+16,0x08000000+script)
        from xgba_r36_binary_pages import _root_census
        scanner=r34.BinaryMapDiscovery(image)
        census=_root_census(scanner,scanner.discover())
        roots=[x for x in census['original_script_entrypoints']
               if x['source_rom_offset']==script]
        self.assertGreater(len(roots),0)
        r=r37.analyze_rom(image,roots)
        self.assertEqual(r['dependencies']['flags'],[1])
        self.assertEqual(r['recognized_commands'],2)
        self.assertFalse(r['cross_world_script_runtime_implemented'])

    def test_reconstruct_from_existing_verified_r36_sidecars_without_rom_file(self):
        import tempfile
        fake=FakeEmeraldBinary()
        image=bytearray(fake.image())
        script=0x1A0000
        image[script:script+4]=b'\x29\x01\x00\x02'
        obj=struct.unpack_from('<I',image,fake.first_event+4)[0]-r34.GBA_BASE
        struct.pack_into('<I',image,obj+16,0x08000000+script)
        scanner=r34.BinaryMapDiscovery(image)
        with tempfile.TemporaryDirectory() as d:
            r36.export_binary_pages(scanner,scanner.discover(),d,'synthetic',pages_per_shard=8)
            pages=r36.PagedBinaryPool(Path(d)/'xgba-binary-rom-pages.json')
            recovered=r37.verified_rom_bytes(pages)
            self.assertEqual(recovered,bytes(image))
            result=r37.analyze_rom(recovered,pages.script_roots['original_script_entrypoints'],detail_limit=0)
            self.assertIn(1,result['dependencies']['flags'])
            self.assertTrue(result['details_truncated'])
            self.assertFalse(result['custom_engine_compatibility_proven'])

    def test_script_opcodes_are_restricted_to_explicit_pinned_layouts(self):
        self.assertNotIn(0x5c,r37.SPECS)
        self.assertNotIn(0xff,r37.SPECS)
        self.assertEqual(r37.SPECS[0x16]['fmt'],'HH')
        self.assertEqual(r37.SPECS[0x29]['fmt'],'H')
        self.assertEqual(r37.SPECS[0x04]['fmt'],'P')

if __name__=='__main__':unittest.main()

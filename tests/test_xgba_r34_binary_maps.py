"""Synthetic, licensed-free whole binary map database and adversarial R34 tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import xgba_r34_binary_maps as r34
import xgba_resource_sidecar as sidecar


class FakeEmeraldBinary:
    def __init__(self, groups=(7, 5, 5, 5, 5, 5, 5, 5), padding=0):
        self.bytes = bytearray(b"\x00" * (2 * 1024 * 1024))
        self.at = 0x2000 + padding
        self.groups = groups
        self.layout_offsets = []
        self.header_offsets = []
        self.event_offsets = []
        self.first_grid = None
        self.first_event = None
        self.table_offset = None
        self._make()

    def alloc(self, n, align=4):
        self.at = (self.at + align - 1) & ~(align - 1)
        pos = self.at
        self.at += n
        assert self.at <= len(self.bytes)
        return pos

    def pointer(self, offset):
        return r34.GBA_BASE + offset

    def write(self, off, fmt, *values):
        struct.pack_into(fmt, self.bytes, off, *values)

    def _make(self):
        self.bytes[0xA0:0xAC] = b"TEST EMERALD"
        self.bytes[0xAC:0xB0] = b"BPEE"
        self.bytes[0xB0:0xB2] = b"01"
        self.bytes[0xB2] = 0x96
        self.bytes[0xBC] = 0
        self.bytes[0xBD] = (-sum(self.bytes[0xA0:0xBD]) - 0x19) & 0xff
        tiles = [self.alloc(64, align=4) for _ in range(4)]
        tilesets = [self.alloc(24) for _ in range(2)]
        for t in tilesets:
            self.bytes[t:t+2] = b"\x01\x00"
            self.write(t+4, "<4I", *(self.pointer(x) for x in tiles))
        for group, count in enumerate(self.groups):
            rows = []
            for number in range(count):
                w, h = ((48, 32) if (group, number) == (0, 0) else (8 + number, 9 + group))
                border = self.alloc(8)
                grid = self.alloc(2 * w * h)
                self.bytes[grid:grid+2*w*h] = bytes([group+1]) * (2 * w * h)
                if self.first_grid is None:
                    self.first_grid = grid
                layout = self.alloc(24)
                self.layout_offsets.append(layout)
                self.write(layout, "<6I", w, h, self.pointer(border), self.pointer(grid),
                           self.pointer(tilesets[0]), self.pointer(tilesets[1]))
                obj = self.alloc(24)
                warp = self.alloc(8)
                self.write(warp, "<hh4B", 2, 5, 0, 0, (number + 1) % count, group)
                bg = self.alloc(12)
                event = self.alloc(20)
                self.event_offsets.append(event)
                if self.first_event is None:
                    self.first_event = event
                self.write(event, "<4B4I", 1, 1, 0, 1,
                           self.pointer(obj), self.pointer(warp), 0, self.pointer(bg))
                c = self.alloc(12)
                self.bytes[c] = 1
                self.bytes[c+8] = group
                self.bytes[c+9] = (number+1) % count
                conn = self.alloc(8)
                self.write(conn, "<iI", 1, self.pointer(c))
                script = self.alloc(5, align=1)
                self.bytes[script:script+5] = b"\x06\x01\x10\x02\x01"
                header = self.alloc(28)
                self.write(header, "<4I2H", self.pointer(layout), self.pointer(event),
                           self.pointer(script), self.pointer(conn), 120, 10+group)
                self.header_offsets.append(header)
                rows.append(header)
            if group == 0:
                all_rows = []
            all_rows.append(rows)
        starts = []
        for rows in all_rows:
            off = self.alloc(len(rows)*4)
            starts.append(off)
            for j,h in enumerate(rows):
                self.write(off+j*4, "<I", self.pointer(h))
        table = self.alloc(len(self.groups)*4)
        self.table_offset = table
        for g,off in enumerate(starts):
            self.write(table+g*4, "<I", self.pointer(off))
        for i in range(5):
            self.write(0x200+i*4, "<I", self.pointer(table))

    def image(self):
        return bytes(self.bytes)


class BinaryMapDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.synthetic = FakeEmeraldBinary()
        self.image = self.synthetic.image()

    def discovered(self, data=None):
        engine = r34.BinaryMapDiscovery(self.image if data is None else data)
        return engine, engine.discover()

    def test_finds_referenced_group_table_without_pinned_offsets(self):
        s, d = self.discovered()
        self.assertEqual(d["table_offset"], self.synthetic.table_offset)
        self.assertEqual(d["reference_count"], 5)
        self.assertEqual(d["group_count"], len(self.synthetic.groups))
        self.assertEqual(d["group_map_counts"], list(self.synthetic.groups))
        self.assertEqual(d["map_count"], sum(self.synthetic.groups))

    def test_packs_complete_synthetic_binary_metadata_and_sha_readback(self):
        engine,discovered = self.discovered()
        out = self.root/"import"
        output = engine.export_maps(discovered,out,"rocket",max_shard_entries=10,max_shard_bytes=4096)
        self.assertEqual(output["summary"]["maps"],sum(self.synthetic.groups))
        self.assertGreater(output["summary"]["exported_fixed_segments"],400)
        self.assertGreater(len(output["shards"]),5)
        self.assertFalse(output["engine_runtime_compatibility_certified"])
        self.assertEqual(output["script_bytecode"],"roots_only_unknown_lengths_not_copied")
        for segment in output["segments"]:
            m = sidecar.load_manifest(out/segment["manifest"])
            restored = b"".join(sidecar.iter_resource_chunks(m,segment["id"],chunk_size=19))
            off = segment["source_rom_offset"]
            self.assertEqual(restored,self.image[off:off+segment["length"]])
        self.assertEqual(hashlib.sha256(engine.data).hexdigest(),engine.digest)

    def test_every_original_map_id_and_structured_event_is_preserved(self):
        _,d = self.discovered()
        maps = d["maps"]
        self.assertEqual(len({(m["group"],m["map"]) for m in maps}),len(maps))
        self.assertEqual(d["summary"]["object_events"],len(maps))
        self.assertEqual(d["summary"]["warp_events"],len(maps))
        self.assertEqual(d["summary"]["background_events"],len(maps))
        self.assertEqual(d["summary"]["coordinate_events"],0)
        self.assertEqual(d["summary"]["connections"],len(maps))
        self.assertEqual(d["summary"]["maps_with_script_roots"],len(maps))

    def test_relocation_changes_table_discovery_not_map_identity(self):
        x = FakeEmeraldBinary(padding=0x4B0)
        s,d = self.discovered(x.image())
        self.assertEqual(d["table_offset"],x.table_offset)
        self.assertNotEqual(d["table_offset"],self.synthetic.table_offset)
        self.assertEqual(d["group_map_counts"],list(self.synthetic.groups))

    def test_no_referenced_table_fail_closed(self):
        data = bytearray(self.image)
        data[0x200:0x214] = b"\0"*20
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            self.discovered(bytes(data))

    def test_bad_header_checksum_rejected_before_pointer_scanning(self):
        data = bytearray(self.image)
        data[0xBD] ^= 0x01
        with self.assertRaisesRegex(r34.DiscoveryError,"GBA header failed"):
            r34.BinaryMapDiscovery(bytes(data))

    def test_invalid_map_layout_fails_entire_table_not_skip_one_map(self):
        data = bytearray(self.image)
        struct.pack_into('<I',data,self.synthetic.layout_offsets[19],0)
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            self.discovered(bytes(data))

    def test_bad_event_array_pointer_fails_entire_table(self):
        data = bytearray(self.image)
        struct.pack_into('<I',data,self.synthetic.event_offsets[20]+4,r34.GBA_BASE+len(data)-4)
        with self.assertRaisesRegex(r34.DiscoveryError,"No validated"):
            self.discovered(bytes(data))

    def test_untrusted_extra_shard_file_refuses_overwrite(self):
        engine,d = self.discovered()
        out = self.root/'refuse'
        out.mkdir()
        (out/'unrelated.txt').write_text('keep')
        with self.assertRaisesRegex(r34.DiscoveryError,'empty'):
            engine.export_maps(d,out,'rocket')
        self.assertEqual((out/'unrelated.txt').read_text(),'keep')

    def test_invalid_namespace_or_tiny_shard_fails_closed(self):
        engine,d = self.discovered()
        with self.assertRaisesRegex(r34.DiscoveryError,'namespace'):
            engine.export_maps(d,self.root/'bad-id','../rocket')
        with self.assertRaisesRegex(r34.DiscoveryError,'shard byte cap'):
            engine.export_maps(d,self.root/'low-cap','rocket',max_shard_bytes=1024)
        self.assertEqual(list((self.root/'low-cap').iterdir()),[])

    def test_original_script_pointer_is_not_executed_or_guessed(self):
        s,d = self.discovered()
        self.assertEqual(d['summary']['script_bytecode_decoded'],0)
        self.assertFalse(d['summary']['battle_species_moves_abilities_decoded'])
        for m in d['maps']:
            self.assertIsNotNone(m['script_root_offset'])
            self.assertFalse(any(k=='script' for k,_,_ in s.segments(m)))

    def test_rejected_unsupported_image_even_with_matching_game_code(self):
        image = bytearray(b'\x00'*(2*1024*1024))
        image[0xA0:0xAC] = b'TEST EMERALD'
        image[0xAC:0xB0] = b'BPEE'
        image[0xB2] = 0x96
        image[0xBD] = (-sum(image[0xA0:0xBD])-0x19)&0xff
        with self.assertRaisesRegex(r34.DiscoveryError,'No validated'):
            r34.BinaryMapDiscovery(bytes(image)).discover()

    def test_user_binary_never_changes_through_export(self):
        path = self.root/'unmodified.gba'
        path.write_bytes(self.image)
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        s = r34.BinaryMapDiscovery(path)
        s.export_maps(s.discover(),self.root/'segments','rocket',max_shard_entries=10,max_shard_bytes=4096)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),h)


if __name__ == '__main__':
    unittest.main()

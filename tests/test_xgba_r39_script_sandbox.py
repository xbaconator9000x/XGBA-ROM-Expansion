"""R39 source-bound, deterministic script IR and transactional state acceptance.

Original Emerald behavior is checked in pinned upstream source independently.
All bytes here are authored synthetic fixtures, never user or Nintendo ROMs.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_r39_script_sandbox as r39


def h(value):
    return struct.pack("<H", value)


def ptr(offset):
    return struct.pack("<I", 0x08000000 + offset)


class FakePool:
    """Tiny source-identity-only fixture. Full R36/R38 integration tested below."""
    def __init__(self, names=("emerald", "rocket", "third"), images=None):
        self.source_ids = names
        self.images = {}
        for index, sid in enumerate(names):
            b = bytearray(4096)
            b[32:36] = bytes((41, index + 1, 0, 2))
            if images and sid in images:
                b = bytearray(images[sid])
            self.images[sid] = bytes(b)
        self.sha = {sid: hashlib.sha256(b).hexdigest() for sid,b in self.images.items()}

    def _source(self, sid):
        if sid not in self.images: raise ValueError("Unknown source")
        return SimpleNamespace(source_sha256=self.sha[sid], rom_bytes=len(self.images[sid]))

    def script_roots(self, sid):
        self._source(sid)
        return ({"source_rom_offset":32, "group":0, "map":0, "kind":"object_event_script"},)

    def read_rom(self, sid, offset, length):
        self._source(sid)
        if not 0<=offset<=len(self.images[sid]) or length<0 or offset+length>len(self.images[sid]):
            raise ValueError("Bad source read")
        return self.images[sid][offset:offset+length]


def pool_with(code, *, target=None, source="emerald"):
    b = bytearray(4096)
    b[32:32+len(code)] = code
    if target is not None:
        b[96:96+len(target)] = target
    return FakePool((source,), {source:bytes(b)})


class ScriptSandbox(unittest.TestCase):
    def run_code(self, code, *, target=None, policy=None, max_steps=200):
        pool = pool_with(code, target=target)
        program = r39.compile_script(pool, "emerald", 32)
        bank = r39.SourceStateBank(pool, bag_policies={"emerald":policy} if policy else None)
        return bank, program, bank.execute(program, max_steps=max_steps)

    def test_original_root_and_immutable_program_identity(self):
        p=FakePool()
        for i,s in enumerate(p.source_ids):
            ir=r39.compile_script(p,s,32)
            self.assertEqual(ir.source_id,s)
            self.assertEqual(ir.root_offset,32)
            self.assertEqual(ir.source_sha256,p.sha[s])
            self.assertEqual(ir.commands[0][1],41)
            self.assertTrue(ir.host_sandbox_only)
        self.assertEqual(len({r39.compile_script(p,s,32).source_sha256 for s in p.source_ids}),3)

    def test_setvar_addvar_subvar_wrap_and_copy(self):
        code = b"\x16"+h(0x4020)+h(65535)+b"\x17"+h(0x4020)+h(2)+\
               b"\x18"+h(0x4020)+h(3)+b"\x19"+h(0x4021)+h(0x4020)+b"\x02"
        bank,ir,result=self.run_code(code)
        self.assertEqual(result["steps"],5)
        self.assertEqual(bank.world("emerald").vars,{0x4020:65534,0x4021:65534})

    def test_setorcopyvar_reads_literal_or_source_variable(self):
        code=b"\x16"+h(0x4020)+h(45)+b"\x1a"+h(0x4021)+h(0x4020)+b"\x1a"+h(0x4022)+h(88)+b"\x02"
        b,_,_=self.run_code(code)
        self.assertEqual(b.world("emerald").vars[0x4021],45)
        self.assertEqual(b.world("emerald").vars[0x4022],88)

    def test_call_return_and_source_local_branch(self):
        code=b"\x16"+h(0x4020)+h(4)+b"\x04"+ptr(96)+b"\x02"
        target=b"\x17"+h(0x4020)+h(5)+b"\x03"
        bank,ir,r=self.run_code(code,target=target)
        self.assertEqual(bank.world("emerald").vars[0x4020],9)
        self.assertEqual(r["steps"],5)
        self.assertTrue(any(op[0]==96 for op in ir.commands))

    def test_all_original_comparison_condition_ids(self):
        for cond in range(6):
            with self.subTest(condition=cond):
                code=b"\x16"+h(0x4020)+h(10)+b"\x21"+h(0x4020)+h(10)+\
                     b"\x06"+bytes((cond,))+ptr(96)+b"\x16"+h(0x4021)+h(2)+b"\x02"
                target=b"\x16"+h(0x4021)+h(7)+b"\x02"
                b,_,_=self.run_code(code,target=target)
                should_jump=cond in (1,3,4)
                self.assertEqual(b.world("emerald").vars[0x4021],7 if should_jump else 2)

    def test_comparison_greater_and_less_and_var_to_var(self):
        code=b"\x16"+h(0x4020)+h(3)+b"\x16"+h(0x4021)+h(9)+\
             b"\x22"+h(0x4020)+h(0x4021)+b"\x06\x00"+ptr(96)+b"\x02"
        target=b"\x29"+h(123)+b"\x02"
        b,_,_=self.run_code(code,target=target)
        self.assertIn(123,b.world("emerald").flags)

    def test_setflag_checkflag_and_clearflag(self):
        code=b"\x29"+h(123)+b"\x2b"+h(123)+b"\x06\x01"+ptr(96)+b"\x02"
        target=b"\x2a"+h(123)+b"\x02"
        b,_,_=self.run_code(code,target=target)
        self.assertNotIn(123,b.world("emerald").flags)

    def test_trainer_defeated_flags_scoped_and_checked(self):
        code=b"\x61"+h(700)+b"\x60"+h(700)+b"\x06\x01"+ptr(96)+b"\x02"
        target=b"\x62"+h(700)+b"\x02"
        b,_,_=self.run_code(code,target=target)
        self.assertNotIn(700,b.world("emerald").trainers)

    def test_bag_policy_required_and_atomic_failure(self):
        code=b"\x29"+h(2)+b"\x44"+h(15)+h(3)+b"\x02"
        p=pool_with(code);ir=r39.compile_script(p,"emerald",32)
        b=r39.SourceStateBank(p)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"policy"):
            b.execute(ir)
        self.assertEqual(b.world("emerald").data(),r39.WorldState().data())

    def test_bag_add_check_remove_and_result(self):
        code=b"\x44"+h(15)+h(3)+b"\x47"+h(15)+h(3)+b"\x45"+h(15)+h(2)+b"\x02"
        b,_,r=self.run_code(code,policy=r39.BagPolicy(distinct_slots=2,stack_limit=6))
        self.assertEqual(b.world("emerald").items,{15:1})
        self.assertEqual(b.world("emerald").result,1)
        self.assertEqual(r["steps"],4)

    def test_bag_overflow_returns_false_not_unsafe_write(self):
        code=b"\x44"+h(15)+h(5)+b"\x44"+h(15)+h(5)+b"\x02"
        b,_,_=self.run_code(code,policy=r39.BagPolicy(1,6))
        self.assertEqual(b.world("emerald").items,{15:5})
        self.assertEqual(b.world("emerald").result,0)

    def test_varget_special_result_as_quantity(self):
        code=b"\x44"+h(12)+h(2)+b"\x44"+h(13)+h(0x800d)+b"\x02"
        b,_,_=self.run_code(code,policy=r39.BagPolicy())
        self.assertEqual(b.world("emerald").items,{12:2,13:1})

    def test_dry_run_does_not_commit(self):
        p=pool_with(b"\x29"+h(5)+b"\x02")
        ir=r39.compile_script(p,"emerald",32);bank=r39.SourceStateBank(p)
        report=bank.execute(ir,dry_run=True)
        self.assertFalse(report["committed"])
        self.assertEqual(report["world"]["flags"],[5])
        self.assertEqual(bank.world("emerald").flags,set())

    def test_unknown_or_unsafe_native_opcodes_refused_before_replay(self):
        for opcode in (0x25,0x39,0x5c,0xff,0x67):
            with self.subTest(op=opcode):
                p=pool_with(b"\x29"+h(5)+bytes((opcode,))+b"\x02")
                with self.assertRaises(r39.ScriptCompatibilityError):
                    r39.compile_script(p,"emerald",32)

    def test_invalid_branch_and_non_root_entry_refused(self):
        p=pool_with(b"\x05"+ptr(0x1ffff0))
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.compile_script(p,"emerald",32)
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.compile_script(p,"emerald",96)

    def test_uninitialised_conditional_fails_without_commit(self):
        p=pool_with(b"\x29"+h(5)+b"\x06\x01"+ptr(96)+b"\x02",target=b"\x02")
        bank=r39.SourceStateBank(p);ir=r39.compile_script(p,"emerald",32)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"without comparison"):
            bank.execute(ir)
        self.assertEqual(bank.world("emerald").flags,set())

    def test_unbalanced_return_refuses_commit(self):
        p=pool_with(b"\x29"+h(5)+b"\x03")
        b=r39.SourceStateBank(p)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"without a source"):
            b.execute(r39.compile_script(p,"emerald",32))
        self.assertEqual(b.world("emerald").flags,set())

    def test_cyclic_branch_budget_rolls_back_everything(self):
        p=pool_with(b"\x29"+h(5)+b"\x05"+ptr(32))
        b=r39.SourceStateBank(p)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"budget"):
            b.execute(r39.compile_script(p,"emerald",32),max_steps=15)
        self.assertEqual(b.world("emerald").flags,set())

    def test_deep_recursion_stack_overflow_rolls_back(self):
        p=pool_with(b"\x29"+h(5)+b"\x04"+ptr(32)+b"\x02")
        b=r39.SourceStateBank(p)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"stack overflow"):
            b.execute(r39.compile_script(p,"emerald",32),max_steps=100)
        self.assertEqual(b.world("emerald").flags,set())

    def test_cross_source_identity_cannot_replay_foreign_program(self):
        p=FakePool();bank=r39.SourceStateBank(p)
        ir=r39.compile_script(p,"emerald",32)
        forged=r39.ScriptIR("rocket",ir.source_sha256,ir.root_offset,ir.commands)
        with self.assertRaises(r39.ScriptCompatibilityError):
            bank.execute(forged)
        self.assertEqual(bank.world("rocket").flags,set())

    def test_forged_same_source_instruction_payload_is_not_executable(self):
        p=pool_with(b"\\x29"+h(5)+b"\\x02")
        ir=r39.compile_script(p,"emerald",32)
        bad=r39.ScriptIR(ir.source_id,ir.source_sha256,ir.root_offset,
                         ((32,41,(999,),3),(35,2,(),1)))
        b=r39.SourceStateBank(p)
        with self.assertRaisesRegex(r39.ScriptCompatibilityError,"differs"):
            b.execute(bad)
        self.assertEqual(b.world("emerald").flags,set())

    def test_variable_backed_trainer_ids_resolved_from_own_world(self):
        code=(b"\\x16"+h(0x4020)+h(700)+b"\\x61"+h(0x4020)+b"\\x60"+h(0x4020)+
             b"\\x06\\x01"+ptr(96)+b"\\x02"
        target=b"\\x62"+h(0x4020)+b"\\x02"
        b,_,_=self.run_code(code,target=target)
        self.assertEqual(b.world("emerald").vars[0x4020],700)
        self.assertEqual(b.world("emerald").trainers,set())

    def test_unsupported_special_variable_rejected_at_compile(self):
        for value in (0x8000,0x800c,0xffff):
            p=pool_with(b"\x18"+h(0x4020)+h(value)+b"\x02")
            with self.assertRaises(r39.ScriptCompatibilityError):
                r39.compile_script(p,"emerald",32)

    def test_snapshot_restore_all_sources_and_original_binding(self):
        p=FakePool();b=r39.SourceStateBank(p)
        for sid in p.source_ids:
            b.execute(r39.compile_script(p,sid,32))
        data=b.snapshot()
        restored=r39.SourceStateBank.restore(p,data)
        self.assertEqual(data,restored.snapshot())
        for i,sid in enumerate(p.source_ids):
            self.assertIn(i+1,restored.world(sid).flags)
            self.assertEqual(len(restored.world(sid).flags),1)

    def test_snapshot_corruption_and_cross_rom_identity_refused(self):
        p=FakePool();b=r39.SourceStateBank(p)
        original=b.snapshot()
        tampered=bytearray(original);tampered[20]^=1
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.SourceStateBank.restore(p,bytes(tampered))
        altered=FakePool(("rocket", "emerald", "third"))
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.SourceStateBank.restore(altered,original)

    def test_snapshot_duplicate_json_keys_and_invalid_state_refused(self):
        p=FakePool();b=r39.SourceStateBank(p)
        original=json.loads(b.snapshot())
        raw=b'{"body":1,"body":2,"sha256":"no"}'
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.SourceStateBank.restore(p,raw)
        body=original["body"]
        body["worlds"]["emerald"]["flags"]=[1,1]
        digest=hashlib.sha256(r39._canonical(body)).hexdigest()
        forged=r39._canonical({"body":body,"sha256":digest})
        with self.assertRaises(r39.ScriptCompatibilityError):
            r39.SourceStateBank.restore(p,forged)

    def test_3worlds_60000_separate_replays_with_source_id_collisions(self):
        p=FakePool();b=r39.SourceStateBank(p)
        scripts={sid:r39.compile_script(p,sid,32) for sid in p.source_ids}
        for i in range(60000):
            sid=p.source_ids[i%3]
            b.execute(scripts[sid])
        for j,sid in enumerate(p.source_ids):
            self.assertEqual(b.world(sid).flags,{j+1})
        self.assertEqual(len(b.snapshot()),len(r39.SourceStateBank.restore(p,b.snapshot()).snapshot()))


class R39RealPagePoolIntegration(unittest.TestCase):
    """Actual R36 SHA-256 disk paging and R38 3x32MiB synthetic ROMs."""

    @classmethod
    def setUpClass(cls):
        # Existing R38 acceptance creates and SHA-verifies all 96 MiB.
        from test_xgba_r38_multi_rom_pool import ThreeROMStress
        ThreeROMStress.setUpClass()
        cls.fixture=ThreeROMStress

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def test_96mib_independently_verified_pages_replay_same_address_three_worlds(self):
        pool=self.fixture.pool
        self.assertEqual(pool.total_source_bytes,100663296)
        self.assertEqual(pool.total_pages,6144)
        bank=r39.SourceStateBank(pool)
        for sid in pool.source_ids:
            program=r39.compile_script(pool,sid,0x1a0000)
            self.assertEqual(program.source_sha256,pool._source(sid).source_sha256)
            bank.execute(program)
        for i,sid in enumerate(pool.source_ids):
            self.assertEqual(bank.world(sid).flags,{i+1})
        save=bank.snapshot()
        recovered=r39.SourceStateBank.restore(pool,save)
        self.assertEqual(save,recovered.snapshot())
        self.assertFalse(bank.execute(r39.compile_script(pool,"emerald",0x1a0000))
                         ["native_emerald_execution_proven"])


if __name__=="__main__":
    unittest.main()

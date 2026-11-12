#!/usr/bin/env python3
"""R39 source-scoped, fail-closed Emerald script IR and HOST-ONLY state sandbox.

This is NOT a GBA interpreter or a compatibility translation for ROM hacks.
Every decoded operation is allowlisted against the pinned original Emerald
opcode table; state mutation is transactional and per original ROM identity.
Unknown/custom callbacks, trainer battles, warps, UI and native engine commands
are rejected, not skipped or silently treated as no-ops.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import struct

import xgba_r37_script_graph as r37

MAX_COMPILED = 384
MAX_STEPS = 1024
MAX_STACK = 24
MAX_SNAPSHOT = 2 * 1024 * 1024
MAX_RECORDS = 65536
FORMAT = "xgba-r39-source-state"
VERSION = 1

# Only known original Emerald command layouts for explicitly modelled effects.
# Real engine semantics, save capacity and callback compatibility are NOT proven.
OPERATIONS = frozenset((
    0, 1, 2, 3, 4, 5, 6, 7,   # control flow / nop
    22, 23, 24, 25, 26, 33, 34,  # 16-bit var and comparisons
    41, 42, 43,  # flags
    68, 69, 70, 71,  # modelled bag transactions (requires policy)
    96, 97, 98,  # trainer defeated flags
))
BRANCH = frozenset((4, 5, 6, 7))
CONDITIONS = ((True, False, False), (False, True, False),
              (False, False, True), (True, True, False),
              (False, True, True), (True, False, True))


class ScriptCompatibilityError(ValueError):
    """Unsupported operations fail without committing any state."""


def _int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ScriptCompatibilityError("Invalid " + name)
    return value


def _var(value):
    return _int(value, 0x4000, 0x7fff, "persistent event variable")


def _value(value):
    _int(value, 0, 65535, "script value")
    if 0x8000 <= value and value != 0x800d:
        raise ScriptCompatibilityError("Unsupported special-variable source")
    return value


def _flag(value):
    return _int(value, 0, 0x3fff, "persistent event flag")


def _pointer(value, size):
    off = r37._pointer(value, size)
    if off is None:
        raise ScriptCompatibilityError("Invalid or cross-source script branch")
    return off


@dataclass(frozen=True)
class ScriptIR:
    source_id: str
    source_sha256: str
    root_offset: int
    commands: tuple  # (rom_offset, opcode, tuple(args), encoded_length)
    host_sandbox_only: bool = True


@dataclass(frozen=True)
class BagPolicy:
    """Explicit synthetic policy; NOT a reconstruction of game pocket tables."""
    distinct_slots: int = 30
    stack_limit: int = 99

    def __post_init__(self):
        _int(self.distinct_slots, 1, 4096, "bag slots")
        _int(self.stack_limit, 1, 65535, "bag stack limit")


@dataclass
class WorldState:
    flags: set = field(default_factory=set)
    vars: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)
    trainers: set = field(default_factory=set)
    result: int = 0

    def copy(self):
        return WorldState(set(self.flags), dict(self.vars), dict(self.items),
                          set(self.trainers), self.result)

    def data(self):
        return {"flags": sorted(self.flags),
                "vars": [[k, self.vars[k]] for k in sorted(self.vars)],
                "items": [[k, self.items[k]] for k in sorted(self.items)],
                "trainers": sorted(self.trainers), "result": self.result}


def compile_script(pool, source_id, root_offset, *, max_commands=MAX_COMPILED):
    """Read a verified R38 source and preflight every reachable opcode.

    No mutation, no fallback decoding and no implicit source switch. Only
    original R36 root references are accepted as entry points.
    """
    _int(max_commands, 1, MAX_COMPILED, "compile budget")
    source = pool._source(source_id)
    _int(root_offset, 0, source.rom_bytes - 1, "root address")
    if root_offset not in {e["source_rom_offset"] for e in pool.script_roots(source_id)}:
        raise ScriptCompatibilityError("Root is absent from the source R36 census")
    todo = [root_offset]
    queued = {root_offset}
    commands = {}
    while todo:
        if len(commands) >= max_commands:
            raise ScriptCompatibilityError("Compilation budget exhausted")
        pc = todo.pop()
        if pc in commands:
            continue
        opcode = pool.read_rom(source_id, pc, 1)[0]
        if opcode not in OPERATIONS or opcode not in r37.SPECS:
            raise ScriptCompatibilityError("Opcode requires an unimplemented native/custom adapter: %d" % opcode)
        spec = r37.SPECS[opcode]
        length = 1 + sum(r37.FORMATS[x][0] for x in spec["fmt"])
        if length > source.rom_bytes - pc:
            raise ScriptCompatibilityError("Truncated script command")
        raw = pool.read_rom(source_id, pc, length)
        args = []
        pos = 1
        for name in spec["fmt"]:
            width, fmt = r37.FORMATS[name]
            args.append(struct.unpack_from(fmt, raw, pos)[0])
            pos += width
        a = tuple(args)
        if opcode in (22, 23, 24, 25, 26, 33, 34):
            _var(a[0])
            if opcode in (25, 34):
                _var(a[1])
            elif opcode in (24, 26):
                _value(a[1])
        if opcode in (41, 42, 43):
            _flag(a[0])
        if opcode in (68, 69, 70, 71):
            _value(a[0]); _value(a[1])
        if opcode in (96, 97, 98):
            _value(a[0])  # original Emerald uses VarGet for trainer ID operands
        if opcode in (6, 7):
            _int(a[0], 0, 5, "Emerald comparison condition")
        commands[pc] = (pc, opcode, a, length)
        if opcode in (2, 3):
            successors = ()
        elif opcode in BRANCH:
            target = _pointer(a[-1], source.rom_bytes)
            successors = (target,) if opcode == 5 else (target, pc + length)
        else:
            successors = (pc + length,)
        for nxt in successors:
            if nxt >= source.rom_bytes:
                raise ScriptCompatibilityError("Script fallthrough outside original ROM")
            if nxt not in queued:
                queued.add(nxt); todo.append(nxt)
                if len(queued) > max_commands:
                    raise ScriptCompatibilityError("Reachability budget exhausted")
    return ScriptIR(source_id, source.source_sha256, root_offset,
                    tuple(commands[x] for x in sorted(commands)))


def _canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _pairs(items):
    out = {}
    for k, v in items:
        if k in out:
            raise ScriptCompatibilityError("Duplicate snapshot JSON key")
        out[k] = v
    return out


def _no_constant(_):
    raise ScriptCompatibilityError("Forbidden snapshot numeric constant")


def _parse_state(data):
    if not isinstance(data, dict) or set(data) != {"flags", "vars", "items", "trainers", "result"}:
        raise ScriptCompatibilityError("Invalid source state structure")
    if not all(isinstance(data[k], list) and len(data[k]) <= MAX_RECORDS
               for k in ("flags", "vars", "items", "trainers")):
        raise ScriptCompatibilityError("Source state exceeds record limits")
    flags = set()
    trainers = set()
    for v in data["flags"]:
        _flag(v)
        if v in flags: raise ScriptCompatibilityError("Duplicate flag")
        flags.add(v)
    for v in data["trainers"]:
        _int(v, 0, 65535, "trainer")
        if v in trainers: raise ScriptCompatibilityError("Duplicate trainer")
        trainers.add(v)
    def pairs(values, low, high):
        result = {}
        for pair in values:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ScriptCompatibilityError("Invalid state pair")
            k, v = pair
            _int(k, low, high, "state key")
            _int(v, 0, 65535, "state value")
            if k in result or (low == 1 and v == 0):
                raise ScriptCompatibilityError("Duplicate or empty state entry")
            result[k] = v
        return result
    variables = pairs(data["vars"], 0x4000, 0x7fff)
    items = pairs(data["items"], 1, 65535)
    result = _int(data["result"], 0, 65535, "result variable")
    return WorldState(flags, variables, items, trainers, result)


class SourceStateBank:
    """Source-identity-checked, separately stored event state; no shared save."""

    def __init__(self, pool, *, bag_policies=None):
        self._pool = pool
        self._trusted_ir = {}
        self.identities = {sid: pool._source(sid).source_sha256 for sid in pool.source_ids}
        self._worlds = {sid: WorldState() for sid in self.identities}
        self.bag_policies = dict(bag_policies or {})
        if any(sid not in self.identities or not isinstance(p, BagPolicy)
               for sid, p in self.bag_policies.items()):
            raise ScriptCompatibilityError("Invalid source bag-policy binding")

    def world(self, source_id):
        if source_id not in self._worlds:
            raise ScriptCompatibilityError("Unknown state namespace")
        return self._worlds[source_id].copy()

    def snapshot(self):
        body = {"format": FORMAT, "version": VERSION,
                "identities": dict(self.identities),
                "worlds": {sid: w.data() for sid, w in self._worlds.items()}}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        encoded = _canonical({"body": body, "sha256": digest})
        if len(encoded) > MAX_SNAPSHOT:
            raise ScriptCompatibilityError("Snapshot exceeds host bound")
        return encoded

    @classmethod
    def restore(cls, pool, snapshot, *, bag_policies=None):
        if not isinstance(snapshot, bytes) or len(snapshot) > MAX_SNAPSHOT:
            raise ScriptCompatibilityError("Invalid snapshot size")
        try:
            doc = json.loads(snapshot.decode("ascii"), object_pairs_hook=_pairs,
                             parse_constant=_no_constant)
        except (UnicodeError, ValueError) as exc:
            raise ScriptCompatibilityError("Malformed state snapshot") from exc
        if not isinstance(doc, dict) or set(doc) != {"body", "sha256"}:
            raise ScriptCompatibilityError("Malformed snapshot envelope")
        body = doc["body"]
        if not isinstance(body, dict) or set(body) != {"format", "version", "identities", "worlds"}:
            raise ScriptCompatibilityError("Unsupported snapshot payload")
        if doc["sha256"] != hashlib.sha256(_canonical(body)).hexdigest():
            raise ScriptCompatibilityError("Corrupted snapshot checksum")
        bank = cls(pool, bag_policies=bag_policies)
        if body["format"] != FORMAT or type(body["version"]) is not int or body["version"] != VERSION or \
           body["identities"] != bank.identities or not isinstance(body["worlds"], dict) or \
           set(body["worlds"]) != set(bank._worlds):
            raise ScriptCompatibilityError("Snapshot sources/version do not match")
        replacement = {sid: _parse_state(body["worlds"][sid]) for sid in bank.identities}
        bank._worlds = replacement  # atomic after ALL sources validated
        return bank

    def execute(self, program, *, max_steps=MAX_STEPS, dry_run=False):
        """Host-only deterministic replay; commits a world only on clean END."""
        _int(max_steps, 1, MAX_STEPS, "script step budget")
        if not isinstance(program, ScriptIR) or not program.host_sandbox_only:
            raise ScriptCompatibilityError("Untrusted script IR")
        sid = program.source_id
        if sid not in self.identities or program.source_sha256 != self.identities[sid]:
            raise ScriptCompatibilityError("Program/original ROM source identity mismatch")
        # A dataclass alone is not an authorization token. Verify that every
        # operation came from the mounted, SHA-checked source, not a forged IR.
        key = (sid, program.source_sha256, program.root_offset)
        expected = self._trusted_ir.get(key)
        if expected is None:
            expected = compile_script(self._pool, sid, program.root_offset)
            self._trusted_ir[key] = expected
        if expected != program:
            raise ScriptCompatibilityError("Script IR differs from verified source bytes")
        instructions = {c[0]: c for c in program.commands}
        if len(instructions) != len(program.commands) or not instructions:
            raise ScriptCompatibilityError("Corrupted or empty script IR")
        state = self._worlds[sid].copy()
        pc = program.root_offset
        stack = []
        cmp = None
        steps = 0
        policy = self.bag_policies.get(sid)

        def get(value):
            _value(value)
            if value == 0x800d:
                return state.result
            if value >= 0x4000:
                return state.vars.get(value, 0)
            return value

        while True:
            if steps >= max_steps:
                raise ScriptCompatibilityError("Execution budget exhausted (transaction rolled back)")
            if pc not in instructions:
                raise ScriptCompatibilityError("Uncompiled/invalid instruction target")
            offset, opcode, args, length = instructions[pc]
            steps += 1
            next_pc = offset + length
            if opcode in (0, 1):
                pass
            elif opcode == 2:
                if stack:
                    raise ScriptCompatibilityError("END with unbalanced script call stack")
                break
            elif opcode == 3:
                if not stack:
                    raise ScriptCompatibilityError("RETURN without a source-local CALL")
                next_pc = stack.pop()
            elif opcode in (4, 5, 6, 7):
                taken = opcode in (4, 5)
                if opcode in (6, 7):
                    if cmp is None:
                        raise ScriptCompatibilityError("Conditional branch without comparison")
                    taken = CONDITIONS[args[0]][cmp]
                if taken:
                    if opcode in (4, 7):
                        if len(stack) >= MAX_STACK:
                            raise ScriptCompatibilityError("Source script call stack overflow")
                        stack.append(next_pc)
                    next_pc = _pointer(args[-1], 1 << 25)
            elif opcode == 22:
                state.vars[args[0]] = args[1]
            elif opcode == 23:
                state.vars[args[0]] = (state.vars.get(args[0], 0) + args[1]) & 65535
            elif opcode == 24:
                state.vars[args[0]] = (state.vars.get(args[0], 0) - get(args[1])) & 65535
            elif opcode == 25:
                state.vars[args[0]] = state.vars.get(args[1], 0)
            elif opcode == 26:
                state.vars[args[0]] = get(args[1])
            elif opcode in (33, 34):
                a = state.vars.get(args[0], 0)
                b = args[1] if opcode == 33 else state.vars.get(args[1], 0)
                cmp = 0 if a < b else 1 if a == b else 2
            elif opcode == 41:
                state.flags.add(args[0])
            elif opcode == 42:
                state.flags.discard(args[0])
            elif opcode == 43:
                cmp = 1 if args[0] in state.flags else 0
            elif opcode in (96, 97, 98):
                trainer_id = get(args[0])  # original ScrCmd_*trainerflag uses VarGet
                if opcode == 96:
                    cmp = 1 if trainer_id in state.trainers else 0
                elif opcode == 97:
                    state.trainers.add(trainer_id)
                else:
                    state.trainers.discard(trainer_id)
            elif opcode in (68, 69, 70, 71):
                if policy is None:
                    raise ScriptCompatibilityError("Bag operation requires an explicit source policy")
                item, amount = get(args[0]), get(args[1]) & 255
                if item == 0 or amount == 0:
                    raise ScriptCompatibilityError("Invalid bag item/quantity")
                old = state.items.get(item, 0)
                if opcode in (68, 70):
                    yes = old + amount <= policy.stack_limit and \
                          (old != 0 or len(state.items) < policy.distinct_slots)
                else:
                    yes = old >= amount
                state.result = int(yes)
                if yes and opcode == 68:
                    state.items[item] = old + amount
                elif yes and opcode == 69:
                    if old == amount:
                        state.items.pop(item, None)
                    else:
                        state.items[item] = old - amount
            else:
                raise ScriptCompatibilityError("Rejected unknown script adapter")
            pc = next_pc
        if not dry_run:
            self._worlds[sid] = state
        return {"source_id": sid, "steps": steps, "committed": not dry_run,
                "sandbox_only": True, "world": state.data(),
                "native_emerald_execution_proven": False,
                "cross_rom_quest_compatibility_proven": False}

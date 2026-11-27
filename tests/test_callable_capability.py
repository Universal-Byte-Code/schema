"""Draft callable-bank semantics; deliberately not a full PMF verifier."""
from dataclasses import dataclass
import struct
import unittest

ROOT = 0xFFFFFFFF
PREFIX = b"\xff\x13"
MAX_SLOTS = 4096


@dataclass(frozen=True)
class Signature:
    result: int
    args: tuple[int, ...] = ()


@dataclass(frozen=True)
class Op:
    code: int
    operands: tuple[int, ...]


def decode_table(data, function_count, admitted_signatures):
    """Parse section payload; the caller supplies verified scalar signatures."""
    cursor = 0

    def u32():
        nonlocal cursor
        if cursor + 4 > len(data):
            raise ValueError("truncated")
        n = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        return n

    if u32() != 0 or u32() != function_count:
        raise ValueError("header")
    result = []
    for _ in range(function_count):
        count = u32()
        if count > MAX_SLOTS or count > (len(data) - cursor) // 8:
            raise ValueError("slot count")
        slots = []
        for _ in range(count):
            ret, argc = u32(), u32()
            if argc > (len(data) - cursor) // 4:
                raise ValueError("argument count")
            sig = Signature(ret, tuple(u32() for _ in range(argc)))
            if sig not in admitted_signatures:
                raise ValueError("signature")
            slots.append(sig)
        result.append(tuple(slots))
    if cursor != len(data):
        raise ValueError("trailing bytes")
    return tuple(result)


def encode_table(banks):
    words = [0, len(banks)]
    for bank in banks:
        words.append(len(bank))
        for sig in bank:
            words.extend((sig.result, len(sig.args), *sig.args))
    return struct.pack("<" + "I" * len(words), *words)


def decode_op(data):
    if len(data) < 3 or data[:2] != PREFIX or data[2] > 3:
        raise ValueError("opcode")
    code = data[2]
    count = 2 if code in (0, 1) else 1
    if len(data) != 3 + 4 * count:
        raise ValueError("operand width")
    return Op(code, struct.unpack_from("<" + "I" * count, data, 3))


def encode_op(code, *operands):
    return PREFIX + bytes([code]) + struct.pack("<" + "I" * len(operands), *operands)


class Module:
    def __init__(self, parents, signatures, banks):
        self.parents, self.signatures, self.banks = tuple(parents), tuple(signatures), tuple(tuple(b) for b in banks)
        if not len(self.parents) == len(self.signatures) == len(self.banks):
            raise ValueError("function count")
        active = []
        for index, parent in enumerate(self.parents):
            if parent != ROOT and not 0 <= parent < index:
                raise ValueError("parent")
            while active and active[-1] != parent:
                active.pop()
            if parent != ROOT and not active:
                raise ValueError("reopened subtree")
            active.append(index)

    def visible(self, caller, target):
        parent = self.parents[target]
        if parent == ROOT:
            return True
        while caller != ROOT:
            if caller == parent:
                return True
            caller = self.parents[caller]
        return False

    def verify(self, caller, op):
        if not 0 <= caller < len(self.banks) or op.code not in range(4):
            raise ValueError("function or opcode")
        if len(op.operands) != (2 if op.code in (0, 1) else 1):
            raise ValueError("operand width")
        bank = self.banks[caller]
        dst = op.operands[0]
        if not 0 <= dst < len(bank):
            raise ValueError("slot")
        if op.code == 0:
            target = op.operands[1]
            if not 0 <= target < len(self.signatures) or not self.visible(caller, target):
                raise ValueError("target visibility")
            if bank[dst] != self.signatures[target]:
                raise ValueError("signature")
        elif op.code == 1:
            src = op.operands[1]
            if not 0 <= src < len(bank) or bank[dst] != bank[src]:
                raise ValueError("copy signature or slot")

    def activate(self, caller):
        if not 0 <= caller < len(self.banks):
            raise ValueError("function")
        return Activation(self, caller)


class Activation:
    """Private bank model. Returned target IDs are test observations, not guest values."""
    def __init__(self, module, caller):
        self.module, self.caller = module, caller
        self._slots = [None] * len(module.banks[caller])
        self._live = True

    def finish(self):
        self._slots[:] = [None] * len(self._slots)
        self._live = False

    def execute(self, op):
        if not self._live:
            raise ValueError("dead activation")
        self.module.verify(self.caller, op)
        dst = op.operands[0]
        if op.code == 0:
            self._slots[dst] = op.operands[1]
        elif op.code == 1:
            self._slots[dst] = self._slots[op.operands[1]]
        elif op.code == 2:
            self._slots[dst] = None
        else:
            target = self._slots[dst]
            if target is None:
                raise ValueError("empty callable")
            # Model the dispatch decision, not the native/scalar call itself.
            if not self.module.visible(self.caller, target) or self.module.signatures[target] != self.module.banks[self.caller][dst]:
                raise ValueError("corrupt callable")
            return target


class CallableTests(unittest.TestCase):
    def setUp(self):
        self.a = Signature(1, (2,))
        self.b = Signature(1, (3,))  # same arity, wrong argument type
        self.c = Signature(2, (2,))  # same arity, wrong return type
        # root 0 owns nested 1, 2; roots 3/4/5.
        self.banks = ((self.a, self.a, self.b), (), (), (self.a,), (), ())
        self.module = Module((ROOT, 0, 0, ROOT, ROOT, ROOT),
                             (self.a, self.a, self.a, self.a, self.b, self.c), self.banks)

    def test_table_roundtrip_and_duplicate_signatures(self):
        data = encode_table(self.banks)
        self.assertEqual(self.banks, decode_table(data, 6, {self.a, self.b, self.c}))

    def test_table_rejects_bad_framing(self):
        data = encode_table(self.banks)
        for bad in (data[:-1], data + b"\x00", b"\x01" + data[1:],
                    data[:4] + struct.pack("<I", 5) + data[8:],
                    data[:8] + struct.pack("<I", 0xFFFFFFFF) + data[12:]):
            with self.subTest(bad=bad[:12]):
                with self.assertRaises(ValueError):
                    decode_table(bad, 6, {self.a, self.b, self.c})

    def test_table_rejects_unadmitted_signature(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            decode_table(encode_table(self.banks), 6, {self.a})

    def test_opcode_framing(self):
        for code, args in ((0, (0, 1)), (1, (1, 0)), (2, (0,)), (3, (0,))):
            wire = encode_op(code, *args)
            self.assertEqual(Op(code, args), decode_op(wire))
            for bad in (wire[:-1], wire + b"\x00", b"\xff" + wire):
                with self.assertRaises(ValueError):
                    decode_op(bad)
        with self.assertRaises(ValueError):
            decode_op(b"\xff\x13\x04")

    def test_dynamic_selection(self):
        act = self.module.activate(0)
        for target in (1, 2, 1):
            act.execute(Op(0, (0, target)))
            self.assertEqual(target, act.execute(Op(3, (0,))))

    def test_copy_clear_independence(self):
        act = self.module.activate(0)
        act.execute(Op(0, (0, 1)))
        act.execute(Op(1, (1, 0)))
        act.execute(Op(2, (0,)))
        with self.assertRaisesRegex(ValueError, "empty"):
            act.execute(Op(3, (0,)))
        self.assertEqual(1, act.execute(Op(3, (1,))))

    def test_empty_copy(self):
        act = self.module.activate(0)
        act.execute(Op(0, (0, 1)))
        act.execute(Op(1, (0, 1)))
        with self.assertRaisesRegex(ValueError, "empty"):
            act.execute(Op(3, (0,)))

    def test_recursive_activations_and_lifetime(self):
        outer = self.module.activate(0)
        inner = self.module.activate(0)
        outer.execute(Op(0, (0, 1)))
        with self.assertRaisesRegex(ValueError, "empty"):
            inner.execute(Op(3, (0,)))
        inner.execute(Op(0, (0, 2)))
        self.assertEqual(1, outer.execute(Op(3, (0,))))
        inner.finish()
        with self.assertRaisesRegex(ValueError, "dead"):
            inner.execute(Op(3, (0,)))
        self.assertEqual(1, outer.execute(Op(3, (0,))))

    def test_rejects_unrelated_nested_target(self):
        with self.assertRaisesRegex(ValueError, "visibility"):
            self.module.verify(3, Op(0, (0, 1)))

    def test_rejects_same_arity_wrong_argument_or_return(self):
        for target in (4, 5):
            with self.assertRaisesRegex(ValueError, "signature"):
                self.module.verify(0, Op(0, (0, target)))

    def test_rejects_wrong_copy_signature(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            self.module.verify(0, Op(1, (2, 0)))

    def test_rejects_bad_slot_and_target(self):
        for op in (Op(0, (99, 1)), Op(0, (0, 99)), Op(3, (99,)), Op(1, (0, 99))):
            with self.assertRaises(ValueError):
                self.module.verify(0, op)

    def test_rejects_scalar_as_capability_instruction(self):
        # PUSH scalar or legacy CALLI cannot be decoded as a capability op.
        for wire in (b"\x11\x01\x01", b"\x62\x01\x01"):
            with self.assertRaises(ValueError):
                decode_op(wire)


if __name__ == "__main__":
    unittest.main()

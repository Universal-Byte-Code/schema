# Indexed Executable Representation v0

This document defines the first architecture-neutral executable profile carried by
Portable Module Format (PMF) modules. It lowers source/AST names to canonical table
indices and encodes executable Ubytec instructions as binary opcode streams.

This profile is **not** native code. It contains no x86-64/ARM64 instructions,
ELF/PE relocations, process addresses or host ABI details.

## Goals

The v0 profile establishes these invariants:

1. direct function calls use `FunctionIndex`, never a source function name;
2. frame accesses use `BindingIndex`, never a source variable name;
3. type references use `TypeIndex`;
4. imports, exports and constants have canonical table indices;
5. code preserves the opcode identity defined by `docs/opcode-encoding.md`;
6. the same normalized program produces the same section bytes;
7. structural verification does not require reparsing Ubytec source or AST JSON.

Unsafe memory operations remain unsafe. This verifier establishes structural and
reference integrity; it does not claim memory safety.

## PMF sections

An indexed executable image is represented by the following PMF section kinds:

| Kind | Name | Required in executable profile | Flags |
| ---: | --- | --- | --- |
| `0x0010` | String table | yes | critical |
| `0x0011` | Type table | yes | critical |
| `0x0012` | Function table | yes | critical |
| `0x0013` | Import table | yes | critical |
| `0x0014` | Export table | yes | critical |
| `0x0015` | Constant table | yes | critical |
| `0x0016` | Code | yes | critical |

All seven sections MUST either be present exactly once or be absent as a group.
Zero-entry tables are encoded as sections with `EntryCount = 0`; omitting one table
from an otherwise executable profile is invalid.

The PMF Semantic AST section remains required by PMF v0. During this transition a
module may therefore carry both the canonical AST and indexed executable sections.
A later PMF revision may make the executable profile independently sufficient.

## Common integer rules

All integers use unsigned little-endian fixed-width encodings unless explicitly
stated otherwise. v0 deliberately uses fixed widths instead of variable-length
integers so each integer has exactly one byte representation.

`NoIndex` is `0xFFFFFFFF` for all `u32` index fields. It is valid only where this
document explicitly permits an absent reference.

Every table payload begins with:

| Size | Field |
| ---: | --- |
| 4 | `EntryCount` (`u32`) |

A decoder MUST reject arithmetic overflow, truncated entries, indices outside the
referenced table, duplicate canonical entries where uniqueness is required, and
trailing bytes after the declared entries.

## String table — `0x0010`

Each entry is:

| Size | Field |
| ---: | --- |
| 4 | UTF-8 byte length |
| n | UTF-8 bytes |

Strings MUST be valid UTF-8, MUST NOT contain a BOM, and MUST be unique. Writers
MUST sort entries by unsigned lexicographic comparison of their UTF-8 bytes. Empty
strings are allowed only when another table explicitly permits them.

Source-local names do not need to appear merely because they existed in source.
Strings are principally boundary identities such as module/import/export names and
custom type names.

## Type table — `0x0011`

Each type entry is 25 bytes:

| Size | Field |
| ---: | --- |
| 1 | `PrimitiveType` |
| 4 | `TypeModifiers` (`u32`) |
| 8 | `FixedArraySize` (`u64`) |
| 4 | `NameStringIndex` (`u32`) |
| 8 | reserved, MUST be zero |

`NameStringIndex` MUST be `NoIndex` for standard primitive types. A custom type MAY
reference its canonical name in the String table. Type entries MUST be unique and
writers MUST sort them by the complete encoded entry bytes before assigning
`TypeIndex` values.

The reserved bytes exist to keep v0 extensible without borrowing meaning from
host-language object layout.

## Function table — `0x0012`

Functions are assigned `FunctionIndex` values in canonical declaration order after
flattening executable module-level and nested callables. Source names are used by
the compiler only to resolve references during lowering; they are not required in
this table.

Each function entry begins with the fixed header:

| Size | Field |
| ---: | --- |
| 4 | return `TypeIndex` |
| 4 | argument count |
| 4 | local binding count |
| 4 | first code byte offset |
| 4 | code byte length |
| 4 | flags, reserved in v0 and MUST be zero |

It is followed immediately by:

- `argument count` × `u32 TypeIndex` values;
- `local binding count` × `u32 TypeIndex` values.

### Binding index space

Each function has its own zero-based `BindingIndex` namespace:

```text
0 .. ArgumentCount-1                         arguments in declaration order
ArgumentCount .. ArgumentCount+LocalCount-1 local/frame bindings
```

A symbolic source instruction such as `load @counter` is lowered to the numeric
binding index for `counter`. Names do not survive in the Code section.

`CodeOffset + CodeLength` MUST be within the Code section and function code ranges
MUST NOT overlap. Canonical writers lay function bodies consecutively in ascending
`FunctionIndex` order with no padding.

## Import table — `0x0013`

Each import entry is:

| Size | Field |
| ---: | --- |
| 4 | module `StringIndex` |
| 4 | symbol `StringIndex` |
| 4 | return `TypeIndex` |
| 4 | argument count |
| 4 × count | argument `TypeIndex` values |

Import entries MUST be unique and canonically sorted by their complete encoded
entry bytes. Calls to an imported callable use an import-reference operand defined
by the importing opcode contract; an implementation MUST NOT convert the index to
a process address inside the portable image.

Capabilities required by an import remain declared through the PMF Capability
manifest. Presence of an import or capability is not an authority grant.

## Export table — `0x0014`

Each export entry is exactly 8 bytes:

| Size | Field |
| ---: | --- |
| 4 | symbol `StringIndex` |
| 4 | `FunctionIndex` |

Export names MUST be unique. Writers MUST sort exports by the encoded UTF-8 symbol
bytes, not by host locale.

## Constant table — `0x0015`

Each constant entry is:

| Size | Field |
| ---: | --- |
| 4 | payload byte length |
| n | payload bytes |

Constants are opaque portable byte strings at this layer. Entries MUST be unique
and sorted by `(length, unsigned lexicographic payload)` before assigning
`ConstantIndex` values. Typed interpretation is supplied by the opcode that
references the constant.

Small immediates already defined as opcode operands MAY remain inline and do not
have to be interned in this table.

## Code section — `0x0016`

The Code payload is the concatenation of all function instruction streams. It has
no count, padding or embedded function names; the Function table provides exact
byte ranges.

### Opcode identity

Each instruction begins with exactly the opcode byte sequence defined by
`docs/opcode-encoding.md`:

```text
<core-opcode>
```

or

```text
FF...FF <ExtensionGroup> <ExtendedOpCode>
```

Escape depth is semantic and MUST be preserved exactly. A decoder MUST reject
truncated escape sequences and MUST NOT normalize one escape depth to another.

### Operand framing

Operands follow immediately after the opcode and are defined by that opcode's wire
contract. There is no generic JSON operand envelope and no generic instruction
length field in v0. Consequently, a verifier must know the wire contract of every
opcode it accepts.

The initial reference implementation defines these portable operand forms for the
currently executable scalar subset:

| Instruction form | Operand bytes |
| --- | --- |
| operand-free core opcode | none |
| `PUSH` | `u8 ByteCount` followed by 1..8 immediate bytes |
| `DROP`, `PICK`, `ROLL` | `u8 StackIndex` |
| direct `CALL`, `FNADDR` | `u32 FunctionIndex` |
| named `LOAD`, `STORE` | `u8 mode=2`, `u32 BindingIndex` |
| raw untyped `LOAD`, `STORE` | `u8 mode=0` |
| raw typed `LOAD`, `STORE` | `u8 mode=1`, `u8 PrimitiveType` |
| `CALLI` | `u8 ArgumentCount`, `u8 PrimitiveReturnType` |

An opcode that has source/AST metadata for which no portable operand contract is
defined MUST be rejected by the v0 executable lowerer rather than silently dropping
that metadata.

## Direct-call lowering

Given source:

```text
func Twice(x:t_int64) -> t_int64 { ... }
func Main() -> t_int64 {
    push 21
    call Twice
    return
}
```

if `Twice` is `FunctionIndex = 0`, the Code stream contains:

```text
11 01 15        ; PUSH, 1 immediate byte, 0x15
60 00 00 00 00  ; CALL FunctionIndex 0
09              ; RETURN (when using its operand-free form)
```

The string `Twice` is not present in the instruction stream.

## Frame-binding lowering

Given a function whose binding namespace assigns `counter -> BindingIndex 2`:

```text
load @counter
store @counter
```

its code is represented as:

```text
50 02 02 00 00 00
51 02 02 00 00 00
```

The first operand byte selects named-frame mode and the following `u32` is the
binding index.

## Verification

Before backend code generation or interpretation, a conforming executable verifier
MUST check at least:

1. all seven executable sections are present as a complete group;
2. each table consumes its payload exactly;
3. canonical string/type/import/export/constant ordering and uniqueness;
4. every referenced table index is in range;
5. every function code range is in bounds, non-overlapping and canonically packed;
6. every function instruction stream ends exactly at its declared `CodeLength`;
7. every opcode identity is complete and supported by the verifier;
8. each operand has the exact wire width required by that opcode;
9. every `CALL`/`FNADDR` target is a valid `FunctionIndex`;
10. every named `LOAD`/`STORE` uses a valid binding index in the current function;
11. primitive type operands contain defined values accepted by that instruction;
12. control-flow, stack-depth, signature and return validation required by the
    language semantics is performed before execution.

A structurally valid executable image may still contain unsafe raw memory
operations. Structural validity must not be confused with memory safety.

## Determinism

Canonical table ordering plus fixed-width integer operands make index assignment
and byte encoding deterministic. Parser-instance GUIDs, source locations, native
labels, temporary file names, process addresses and backend register choices MUST
NOT affect any executable-profile section.

Optional diagnostics/source maps belong in a separate non-semantic PMF section in
a future revision.

## Non-goals of v0

This version does not define:

- native object files or target-specific relocations;
- a Windows, SysV, ARM64 or other host ABI;
- floating-point/vector/tensor/quantum instruction semantics not already allocated;
- memory safety or borrow checking;
- JIT/AOT policy;
- a debug/source-map format.

Those concerns can evolve independently without changing the basic indexed
reference model.

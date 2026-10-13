# Indexed Executable Representation v0

This document defines the first architecture-neutral executable profile carried by
Portable Module Format (PMF) modules. It lowers source/AST names to canonical table
indices and encodes executable Ubytec instructions as binary opcode streams.

This profile is **not** native code. It contains no x86-64/ARM64 instructions,
ELF/PE relocations, process addresses, runtime handles or host ABI symbols.

## Goals

The v0 profile establishes these invariants:

1. direct function calls use numeric target indices, never source function names;
2. frame accesses use `BindingIndex`, never source variable names;
3. language type references use `TypeIndex`;
4. imports, exports and constants have canonical table indices;
5. module-boundary loan semantics are preserved independently from language types;
6. code preserves the opcode identity defined by `docs/opcode-encoding.md`;
7. the same normalized program produces the same section bytes;
8. structural verification does not require reparsing Ubytec source or AST JSON.

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

The following host/runtime identities MUST NOT be serialized merely because an
implementation currently uses them:

- source-local import aliases;
- numeric module-bridge handles;
- generated host adapter symbols such as `ubytec_host_contract_*`;
- process addresses or loader-specific relocation names.

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

`LoanRead` and `LoanWrite` are deliberately **not** type-table entries. They are
module-boundary passing modes. Treating them as primitive types would conflate the
language type system with authority/lifetime semantics at a module interface.

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

Locals declared by the high-level function-local block are semantically initialized
at function entry. The reference lowerer represents those initializations as
synthetic portable `VAR` instructions at the start of the function body. A source
`VAR` retains its source execution position. This prevents initialization timing
from becoming an implicit backend convention.

`CodeOffset + CodeLength` MUST be within the Code section and function code ranges
MUST NOT overlap. Canonical writers lay function bodies consecutively in ascending
`FunctionIndex` order with no padding.

## Boundary parameter descriptors

Imports and exports use a boundary descriptor for each logical argument:

| Size | Field |
| ---: | --- |
| 1 | `PassingMode` |
| 4 | carrier `TypeIndex` |

`PassingMode` values are:

| Value | Name | Meaning |
| ---: | --- | --- |
| `0x00` | `Value` | ordinary value argument |
| `0x01` | `LoanRead` | read-only borrowed region/capability |
| `0x02` | `LoanWrite` | writable borrowed region/capability |
| `0x03..0xFF` | reserved | MUST be rejected in v0 |

The `TypeIndex` describes the portable carrier type used by the callable contract.
For the existing v0 module-call contract, `LoanRead` and `LoanWrite` MUST use the
canonical `UInt64` carrier type. Their loan semantics come from `PassingMode`, not
from inventing `LoanRead`/`LoanWrite` primitive types or type modifiers.

A passing mode describes one logical receiver argument. The import-call semantics
below define the architecture-neutral caller-side extent and control cells that are
observable in Ubytec source. A runtime bridge MAY materialize additional validation,
ownership, transport or host-ABI metadata internally, but those additional details
are not part of the portable module image.

Return values have no passing mode in v0. Loan returns are therefore not representable
and MUST be rejected rather than silently downgraded to a value return.

## Import table — `0x0013`

Each import entry is:

| Size | Field |
| ---: | --- |
| 4 | module `StringIndex` |
| 4 | exported symbol `StringIndex` |
| 4 | return `TypeIndex` |
| 4 | logical argument count |
| 5 × count | boundary argument descriptors |

The source-local alias and any implementation-assigned bridge handle are resolved
while lowering and are not serialized. Thus a source declaration such as:

```text
import Copy from memory.Copy (t_loan_rw,t_loan_ro,t_uint64) -> t_int64
```

is identified portably by the boundary identity `memory.Copy` plus its complete
signature. A loader or supervisor may allocate any private handle it wants without
changing module bytes.

Import rows MUST be canonically sorted by their complete encoded bytes in
non-decreasing order before `ImportIndex` values are assigned. Unlike String, Type,
Export and Constant entries, Import rows are **not required to be unique**. Two
source import declarations that resolve to the same module, public symbol and
signature remain two distinct table occurrences and therefore two distinct
`ImportIndex` authority slots. Their encoded rows may be byte-for-byte identical.

This distinction is semantic: a trusted loader may grant one import occurrence and
deny another even when both target the same receiver. The source-local aliases are
used only to resolve source `CALL` instructions to those occurrences and are still
not serialized. Repeated identical rows therefore preserve per-import authority
without turning an alias, host handle or process address into portable identity.

Capabilities required by an import remain declared through the PMF Capability
manifest. Presence of an import or capability is not an authority grant.

## Export table — `0x0014`

Each export entry is:

| Size | Field |
| ---: | --- |
| 4 | public symbol `StringIndex` |
| 4 | `FunctionIndex` |
| 4 | return `TypeIndex` |
| 4 | logical argument count |
| 5 × count | boundary argument descriptors |

The public symbol is the portable export name from the Ubytec contract. A generated
host symbol such as `ubytec_host_contract_Main` is backend-specific and MUST NOT be
serialized into this table.

Export names MUST be unique. Writers MUST sort exports by the encoded UTF-8 public
symbol bytes before assigning their table order.

If an export has no explicit boundary annotation, its signature is derived from the
referenced Function table entry with every argument using `PassingMode.Value`.
If it has an explicit contract annotation, the boundary signature MUST be compatible
with the referenced function's scalar signature. In the current v0 contract,
`LoanRead`/`LoanWrite` require a corresponding `UInt64` carrier argument internally.

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
truncated escape sequences and MUST NOT normalize one escape depth into another.

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
| `RETURN` inferred type | `u8 mode=0` |
| `RETURN` explicit type | `u8 mode=1`, `u32 TypeIndex` |
| `VAR` / local initialization | `u32 BindingIndex`, `u64 InitialCell` |
| `PUSH` | `u8 ByteCount` followed by 1..8 immediate bytes |
| `DROP`, `PICK`, `ROLL` | `u8 StackIndex` |
| direct `CALL` | `u8 TargetKind`, `u32 TargetIndex` |
| `FNADDR` | `u32 FunctionIndex` |
| named `LOAD`, `STORE` | `u8 mode=2`, `u32 BindingIndex` |
| raw untyped `LOAD`, `STORE` | `u8 mode=0` |
| raw typed `LOAD`, `STORE` | `u8 mode=1`, `u8 PrimitiveType` |
| `CALLI` | `u8 ArgumentCount`, `u8 PrimitiveReturnType` |

`CALL.TargetKind` values are:

| Value | Target |
| ---: | --- |
| `0x00` | local `FunctionIndex` |
| `0x01` | `ImportIndex` |
| `0x02..0xFF` | reserved, MUST be rejected in v0 |

`FNADDR` remains local-only in v0. An imported callable is a module-boundary
reference, not a portable process address, so taking an imported native address is
outside this profile.

### Import-target CALL stack semantics

A `CALL` with `TargetKind = 0x01` preserves the current supervised Ubytec import-call
semantics; the `ImportIndex` identifies one receiver-contract authority slot, not a
native address or a host bridge handle.

Except for the reserved legacy signature described below, caller cells are consumed
in declaration order as follows:

- `PassingMode.Value`: one value cell;
- `PassingMode.LoanRead`: two cells, `(local_address, logical_length)`;
- `PassingMode.LoanWrite`: two cells, `(local_address, logical_length)`;
- after all declared arguments: one `budget_ms` cell;
- finally: one local `result_address` cell.

`budget_ms = 0` requests no deadline. Loan lengths constrain the supervised region
and are not additional receiver arguments. The receiver sees one carrier value per
logical argument; for a loan that carrier is the address of the receiver's isolated
mapping. The receiver's declared return value is written to `result_address` after a
successful invocation. The importing `CALL` itself pushes the supervisor status
result, preserving the source-level distinction between invocation status and the
receiver's return value.

The compiler/runtime MAY allocate a private import handle, staging records, mappings
or transport descriptors, but those are implementation details. They MUST NOT be
required as explicit portable stack cells and MUST NOT appear in the Import table or
Code stream.

For compatibility with the existing one-buffer bridge, the exact reserved receiver
signature

```text
(UInt64, UInt64, UInt64, UInt64) -> Int64
```

uses the legacy five-control-cell caller form:

```text
local_buffer, logical_length, requested_rights, budget_ms, result_address
```

rather than the generic four-value-plus-two-control-cell form. This signature is
reserved in v0; typed callers that need four ordinary `UInt64` receiver arguments
MUST use a different contract shape until the legacy bridge is retired or versioned.

A semantic verifier SHOULD derive the required imported-call stack effect from the
referenced Import entry and MUST apply this reserved-signature rule consistently.

`InitialCell` is the exact 64-bit cell value produced by the current scalar local
initializer semantics. An implementation MUST reject a local initializer whose
value/type cannot be represented by that contract rather than truncate it.

An opcode that has source/AST metadata for which no portable operand contract is
defined MUST be rejected by the v0 executable lowerer rather than silently dropping
that metadata.

## Direct-call lowering

Given source:

```text
func Twice(t_int64 x) -> t_int64 { ... }
func Main() -> t_int64 {
    push 21
    call Twice
    return
}
```

if `Twice` is `FunctionIndex = 0`, the Code stream contains:

```text
11 01 15           ; PUSH, 1 immediate byte, 0x15
60 00 00 00 00 00  ; CALL TargetKind.Function, FunctionIndex 0
09 00              ; RETURN, infer enclosing function result type
```

The string `Twice` is not present in the instruction stream.

For an import at `ImportIndex = 3`, the call operand is:

```text
60 01 03 00 00 00  ; CALL TargetKind.Import, ImportIndex 3
```

No runtime bridge handle or process address is embedded in either form.

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
3. canonical ordering and required uniqueness for String, Type, Export and Constant tables,
   plus non-decreasing canonical ordering for Import rows while allowing equal rows;
4. every referenced table index is in range;
5. every function code range is in bounds, non-overlapping and canonically packed;
6. every function instruction stream ends exactly at its declared `CodeLength`;
7. every opcode identity is complete and supported by the verifier;
8. each operand has the exact wire width required by that opcode;
9. every `CALL` uses a defined target kind and an in-range `FunctionIndex` or `ImportIndex`;
10. every `FNADDR` references an in-range local `FunctionIndex`;
11. every named `LOAD`/`STORE` and `VAR` uses a valid binding index in the current function;
12. primitive type operands contain defined values accepted by that instruction;
13. an explicit `RETURN TypeIndex` matches the enclosing function result type;
14. each boundary argument uses a defined `PassingMode` and an in-range `TypeIndex`;
15. v0 `LoanRead`/`LoanWrite` descriptors use the canonical `UInt64` carrier type;
16. each export `FunctionIndex` exists and its boundary signature is compatible with that function;
17. each Import table occurrence remains addressable as its own authority slot even when another
    occurrence has identical encoded receiver identity and signature bytes;
18. imported-call stack effects are derived from the referenced Import entry, including loan
    extent cells, the trailing budget/result cells and the reserved legacy bridge signature;
19. control-flow, stack-depth, signature and return validation required by the
    language semantics is performed before execution.

A structurally valid executable image may still contain unsafe raw memory
operations. Structural validity must not be confused with memory safety.

## Determinism

Canonical table ordering plus fixed-width integer operands make index assignment
and byte encoding deterministic. Equal Import rows are ordered stably by their
source declaration occurrence; because equal rows have identical payloads, the table
bytes remain canonical while their distinct `ImportIndex` positions retain authority
slot identity for the corresponding lowered calls. Parser-instance GUIDs, source
locations, native labels, source-local import aliases, module bridge handles,
generated host adapter symbols, temporary file names, process addresses and backend
register choices MUST NOT affect any executable-profile section.

Optional diagnostics/source maps belong in a separate non-semantic PMF section in
a future revision.

## Non-goals of v0

This version does not define:

- native object files or target-specific relocations;
- a Windows, SysV, ARM64 or other host ABI;
- floating-point/vector/tensor/quantum instruction semantics not already allocated;
- memory safety or borrow checking;
- JIT/AOT policy;
- a debug/source-map format;
- loan returns or imported native function addresses.

Those concerns can evolve independently without changing the basic indexed
reference model.
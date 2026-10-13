# Ubytec opcode encoding

This document defines the canonical byte-level opcode namespace for Ubytec.

## Core opcodes

Core instructions use one byte in the range `0x00..0xFE`.

`0xFF` is permanently reserved as the opcode escape byte and MUST NOT be assigned to a core instruction.

## Recursive extended opcodes

An extended opcode is encoded as:

```text
FF...FF <ExtensionGroup> <ExtendedOpCode>
└ n>=1 ┘
```

The number of leading consecutive `0xFF` bytes is the **EscapeDepth** and is part of the opcode identity.

Both `ExtensionGroup` and `ExtendedOpCode` MUST be in `0x00..0xFE`. The value `0xFF` is reserved at every escape-sensitive position and MUST NOT be allocated.

Examples:

```text
01                core opcode 0x01
FF 10 11          depth 1, group 0x10, opcode 0x11
FF FF 10 11       depth 2, group 0x10, opcode 0x11
FF FF FF 10 11    depth 3, group 0x10, opcode 0x11
```

These extended encodings identify different opcodes. No implementation may normalize one escape depth into another.

A sequence consisting only of escape bytes is incomplete and is never an instruction:

```text
FF
FF FF
FF FF FF
...
```

The abstract namespace therefore has no finite maximum escape depth and cannot be exhausted by a finite number of allocations.

## Implementation limits

The specification does not define a maximum `EscapeDepth`. Implementations MAY impose a finite defensive limit.

An implementation that encounters a syntactically valid opcode whose escape depth exceeds its supported limit MUST report it as unsupported rather than reinterpret it at another depth.

Implementations MUST reject truncated escape sequences.

## AST representation

Core opcode:

```json
{
  "OpCode": 1
}
```

Extended opcode at depth 1:

```json
{
  "OpCode": {
    "OpCode": 255,
    "EscapeDepth": 1,
    "ExtensionGroup": 16,
    "ExtendedOpCode": 17
  }
}
```

Extended opcode at depth 3:

```json
{
  "OpCode": {
    "OpCode": 255,
    "EscapeDepth": 3,
    "ExtensionGroup": 80,
    "ExtendedOpCode": 16
  }
}
```

For backward compatibility, an extended AST opcode that omits `EscapeDepth` has an implicit `EscapeDepth` of `1`.

## Registry

`registry/opcodes.json` is the canonical allocation registry.

An opcode or extension group is not part of the standard merely because an implementation accepts it. Standard allocations MUST be registered before use.

Registry statuses are:

- `assigned`: stable allocation with defined semantics.
- `draft`: official allocation under active specification.
- `reserved`: allocation held for a defined family or future standardization; no instruction semantics implied.
- `deprecated`: historical allocation that MUST NOT be reused.
- `experimental`: unstable/private allocation space.
- `vendor`: vendor-controlled allocation space.

The historical grammar families are rationalized as follows:

- `vector` -> `vector-simd`
- `threading` -> `atomics` + `concurrency`
- `exception` -> `exceptions`
- `ml` -> `tensor` + `linear-algebra` + `accelerator`
- `security` -> `cryptography`
- `audio` -> `dsp`
- `quantum` -> `quantum`

Historical `system`, `syscall`, and `power` concepts are represented as execution-environment capabilities in `registry/capabilities.json`, not as portable opcode families.

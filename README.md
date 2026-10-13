# Extended Ubytec Schema

This repository contains the canonical schema and allocation registries used by **Universal Byte Code (Ubytec)**.

## Repository contents

- `.ubc.ast.json` — JSON Schema for the Ubytec AST.
- `docs/opcode-encoding.md` — normative opcode namespace and recursive `0xFF` escape encoding.
- `registry/opcode-id.schema.json` — schema for core and recursive extended opcode identities.
- `registry/opcodes.json` — canonical opcode and extension-group allocation registry.
- `registry/capabilities.json` — portable execution-environment capability names that are intentionally not opcode families.

## AST model

A Ubytec AST is rooted at `RootSentence` and contains nested syntax sentences and nodes. Each node carries an `Operation`, source tokens, and metadata. The schema is intended to preserve enough structural and source information for compilers, interpreters, analyzers, debuggers, and other tooling to exchange Ubytec programs consistently.

## Opcode namespace

Core opcodes occupy the one-byte range `0x00..0xFE`.

`0xFF` is permanently reserved as an escape byte. Extended opcodes use one or more consecutive escape bytes followed by an extension group and an opcode:

```text
FF...FF <ExtensionGroup> <ExtendedOpCode>
└ n>=1 ┘
```

`EscapeDepth` is the number of leading `0xFF` bytes and is part of the opcode identity. Therefore these are distinct namespaces:

```text
FF 10 11
FF FF 10 11
FF FF FF 10 11
```

Both `ExtensionGroup` and `ExtendedOpCode` are restricted to `0x00..0xFE`; `0xFF` remains reserved at every escape-sensitive position. A sequence containing only escape bytes is an incomplete prefix, never an instruction.

The specification intentionally places no finite upper bound on `EscapeDepth`. Individual runtimes may impose a defensive implementation limit and must report deeper valid namespaces as unsupported rather than reinterpret them.

See [`docs/opcode-encoding.md`](docs/opcode-encoding.md) for the normative rules.

## AST representation of extended opcodes

An extended AST opcode is represented as:

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

For compatibility with existing Ubytec ASTs, an omitted `EscapeDepth` means `1`.

## Canonical registry

`registry/opcodes.json` is the source of truth for allocation. An opcode or group does not become part of the Ubytec standard merely because one implementation accepts it.

The registry records current core instructions, the existing `FF 10 xx` extended-stack instructions, reserved standard families, and allocation classes for ecosystem, vendor, and experimental extensions.

Initial standard family reservations include:

- `vector-simd`
- `atomics`
- `concurrency`
- `exceptions`
- `tensor`
- `linear-algebra`
- `accelerator`
- `cryptography`
- `dsp`
- `quantum`

These reservations do **not** assign instruction semantics inside the family. Individual operations move from `reserved` to `draft` and then `assigned` only when their semantics are specified.

## Host capabilities

Historical grammar categories such as `system`, `syscall`, and `power` mix portable computation with environment-specific services. Ubytec keeps those services out of the portable opcode ISA and registers them under `registry/capabilities.json` instead.

Examples include `host.filesystem`, `host.clock`, `host.power`, `host.audio-device`, and `host.random`.

## Registry statuses

- `assigned` — stable allocation with defined semantics.
- `draft` — official allocation under active specification.
- `reserved` — held for a defined family or future standardization.
- `deprecated` — historical allocation that must not be reused.
- `experimental` — unstable/private allocation space.
- `vendor` — vendor-controlled allocation space.

## Compatibility

The existing depth-1 extended encoding remains unchanged. For example, the current extended stack instruction `PUSH16` remains:

```text
FF 10 11
```

Recursive escape depth extends the namespace without renumbering any existing core or depth-1 opcode.

## Validation

`.ubc.ast.json` targets JSON Schema Draft 2020-12. Consumers may validate serialized ASTs with any compatible validator. `registry/opcode-id.schema.json` provides the stricter recursive-opcode identity constraints while legacy AST validation remains permissive enough to accept existing documents.

When adding an opcode or extension group, update the canonical registry in the same change that introduces the allocation. Implementations should derive or verify their local opcode tables against this registry where practical.

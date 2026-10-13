# Portable Module Format v0

This document defines the canonical binary container for portable Ubytec modules.
It defines framing and canonical transport of the semantic AST. The optional
indexed executable profile defined by `indexed-executable-v0.md` lowers symbolic
AST references to architecture-neutral binary tables and opcode streams while
retaining the same outer container.

The format is intentionally architecture-neutral. A conforming module does not
contain x86-64, ARM64, ELF, PE or host ABI details.

## Byte order and limits

All integer fields are unsigned little-endian values.

A v0 decoder MUST reject a module that exceeds its implementation limits rather
than reinterpret or truncate it. The reference runtime limits a module to 64 MiB
and 32 sections. Other implementations may use stricter documented limits.

## File header

Every module begins with the following 12-byte header:

| Offset | Size | Field | v0 value |
| ---: | ---: | --- | --- |
| 0 | 4 | Magic | ASCII `UBCM` (`55 42 43 4D`) |
| 4 | 2 | MajorVersion | `0` |
| 6 | 2 | MinorVersion | `0` |
| 8 | 4 | SectionCount | number of following sections |

A decoder MUST reject unknown major versions. v0 decoders MUST reject minor
versions they do not implement.

## Section framing

The header is followed immediately by `SectionCount` sections. Each section has a
12-byte header followed immediately by its payload:

| Size | Field |
| ---: | --- |
| 2 | SectionKind |
| 2 | SectionFlags |
| 8 | PayloadLength |
| PayloadLength | Payload |

Sections MUST appear in strictly increasing `SectionKind` order. Duplicate kinds,
overlapping/truncated payloads and bytes after the final section are invalid.
There is no implicit alignment or padding in v0.

### Flags

`SectionFlags` bit 0 is `critical`. All other bits are reserved and MUST be zero.
An unknown critical section MUST cause rejection. An unknown non-critical section
MAY be retained or skipped, but canonical writers MUST preserve the global section
ordering rule.

## Standard v0 sections

| Kind | Name | Required | Flags | Payload |
| ---: | --- | --- | --- | --- |
| `0x0001` | Semantic AST | yes | critical | canonical UTF-8 JSON |
| `0x0002` | Contract manifest | no | critical | canonical UTF-8 text |
| `0x0003` | Capability manifest | no | critical | canonical UTF-8 JSON |
| `0x0010` | Indexed string table | profile | critical | binary |
| `0x0011` | Indexed type table | profile | critical | binary |
| `0x0012` | Indexed function table | profile | critical | binary |
| `0x0013` | Indexed import table | profile | critical | binary |
| `0x0014` | Indexed export table | profile | critical | binary |
| `0x0015` | Indexed constant table | profile | critical | binary |
| `0x0016` | Indexed code | profile | critical | binary |

`profile` means the section is required exactly once when any indexed executable
section is present. The seven indexed sections form one all-or-none group and are
defined normatively in `indexed-executable-v0.md`.

The Semantic AST section is the normalized Ubytec AST and is required exactly
once. Its JSON model is governed by `.ubc.ast.json` plus the opcode identity rules
in `registry/opcode-id.schema.json`.

Parser/runtime-ephemeral syntax identities are not part of that normalized
semantic representation. A canonical Semantic AST MUST omit `guid` entries inside
syntax `Metadata` objects. Stable semantic `ID` fields produced by semantic
normalization remain part of the payload. A verifier MUST reject a Semantic AST
payload that still contains the omitted volatile syntax GUID metadata.

The Contract manifest carries portable import/export contract metadata when a
compiler emits such contracts. It is semantic input to linking/dispatch, not an
authority grant. v0 text is UTF-8 without a BOM and uses LF line endings only.

A payload in `0x0002` MUST itself be architecture/runtime-neutral. A legacy native
runtime manifest containing implementation-assigned import handles, source-local
aliases used only for host dispatch, generated adapter symbols such as
`ubytec_host_contract_*`, process addresses or host ABI identities MUST NOT be
serialized as PMF Contract manifest data.

When the indexed executable profile is present, sections `0x0013` and `0x0014` are
the normative portable import/export representation. Canonical writers SHOULD omit
`0x0002` unless they have additional architecture-neutral contract information that
is not already represented by those tables; any such information MUST NOT conflict
with the indexed tables.

The Capability manifest carries portable execution-environment capability
requirements from `registry/capabilities.json`. Presence of a capability states a
requirement; it does not itself grant access.

## Canonical JSON v0

JSON payloads use UTF-8 without a BOM and no insignificant whitespace. Object
properties are emitted in ascending ordinal Unicode name order. Array order is
preserved because it may be semantic. Duplicate object property names are invalid.

Writers MUST emit the same bytes for the same normalized AST. A verifier MUST
reject a standard JSON section whose bytes are not in canonical v0 layout.

v0 intentionally defines structural JSON canonicalization plus the Semantic AST
volatile-metadata exclusion above. The indexed executable profile uses binary
payloads and therefore has its own canonicalization and verification rules.

## Canonical module production

The base source pipeline is:

```text
source
  -> tokenize / parse
  -> semantic normalization
  -> semantic validation
  -> Portable Module Format encoder
```

When indexed executable output is requested, lowering occurs after semantic
normalization/validation and before PMF assembly:

```text
normalized semantic module
  -> indexed tables + opcode stream
  -> indexed executable verification
  -> PMF sections 0x0010..0x0016
```

Backend-specific code generation is downstream of semantic normalization and is
not serialized into PMF v0.

## Verification

A base v0 verifier MUST check at least:

1. magic, version and total size;
2. section count and exact end-of-file;
3. strictly increasing unique section kinds;
4. known flag bits and unknown-critical rejection;
5. required Semantic AST presence and critical flag;
6. UTF-8 validity and canonical JSON layout for JSON sections;
7. exclusion of volatile syntax `Metadata.guid` entries from the Semantic AST;
8. canonical LF text for the Contract manifest;
9. implementation resource limits before allocation;
10. all-or-none presence of sections `0x0010..0x0016`.

When the indexed executable profile is present, the verifier MUST additionally
apply all checks in `indexed-executable-v0.md`.

Semantic AST validation (opcode identities, control flow, stack discipline,
signatures and similar language rules) remains a separate layer and should run
before backend code generation. PMF framing validation is required even when the
module came from a trusted source compiler.

## Indexed executable code

The indexed executable profile replaces symbolic references such as
`call FunctionName` and named local accesses with canonical numeric indices while
preserving Ubytec opcode identity. See `indexed-executable-v0.md` for the normative
wire format.
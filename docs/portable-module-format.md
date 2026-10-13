# Portable Module Format v0

This document defines the canonical binary container for portable Ubytec modules.
It defines framing and canonical transport of the semantic AST; it does **not** yet
replace symbolic AST operands with the future indexed executable instruction
encoding.

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

The Semantic AST section is the normalized Ubytec AST and is required exactly
once. Its JSON model is governed by `.ubc.ast.json` plus the opcode identity rules
in `registry/opcode-id.schema.json`.

The Contract manifest carries portable import/export contract metadata when a
compiler emits such contracts. It is semantic input to linking/dispatch, not an
authority grant. v0 text is UTF-8 without a BOM and uses LF line endings only.

The Capability manifest is reserved for portable execution-environment capability
requirements from `registry/capabilities.json`. Presence of a capability states a
requirement; it does not itself grant access.

## Canonical JSON v0

JSON payloads use UTF-8 without a BOM and no insignificant whitespace. Object
properties are emitted in ascending ordinal Unicode name order. Array order is
preserved because it may be semantic. Duplicate object property names are invalid.

Writers MUST emit the same bytes for the same normalized AST. A verifier MUST
reject a standard JSON section whose bytes are not in canonical v0 layout.

v0 intentionally defines structural JSON canonicalization only. A later format
revision may replace the AST JSON payload with an indexed executable instruction
section without changing the outer framing rules.

## Canonical module production

The source pipeline is:

```text
source
  -> tokenize / parse
  -> semantic normalization
  -> semantic validation
  -> Portable Module Format encoder
```

Backend-specific code generation is downstream of semantic normalization and is
not serialized into PMF v0.

## Verification

A v0 verifier MUST check at least:

1. magic, version and total size;
2. section count and exact end-of-file;
3. strictly increasing unique section kinds;
4. known flag bits and unknown-critical rejection;
5. required Semantic AST presence and critical flag;
6. UTF-8 validity and canonical JSON layout for JSON sections;
7. canonical LF text for the Contract manifest;
8. implementation resource limits before allocation.

Semantic AST validation (opcode identities, control flow, stack discipline,
signatures and similar language rules) remains a separate layer and should run
before backend code generation. PMF framing validation is required even when the
module came from a trusted source compiler.

## Forward path: indexed executable code

PMF v0 deliberately separates the stable container from the next lowering step.
The planned executable representation replaces symbolic references such as
`call FunctionName` and named local accesses with indices into canonical function,
type, import/export and local tables. That representation will be introduced as a
new standard section/revision rather than by smuggling backend-specific addresses
into the AST.

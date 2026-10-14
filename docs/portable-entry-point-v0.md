# Portable Executable Entry Point v0

This document extends the Indexed Executable Representation v0 with an explicit,
architecture-neutral process entry point. It is stacked on `indexed-executable-v0`.

The purpose of this section is to make an indexed PMF image sufficient to identify
which portable function starts an executable program without consulting source names,
Semantic AST objects, generated native labels, or backend-specific metadata.

## Section kind

The entry point uses PMF section kind `0x0017`.

| Kind | Name | Presence | Flags |
| ---: | --- | --- | --- |
| `0x0017` | Entry point | optional | critical |

The section is valid only when the complete indexed executable section group
`0x0010..0x0016` is present. PMF section uniqueness rules permit at most one entry
point section.

Absence of `0x0017` means that the portable module declares no process entry point.
Such an image is a library/module image at this layer. A loader MAY invoke one of its
exports through an external contract, but it MUST NOT infer a process entry point from
a source function name, export name, table position, or native symbol.

Presence of `0x0017` means that the module is directly executable and designates one
local function as its process entry point.

## Payload

The payload is exactly four bytes:

| Size | Field |
| ---: | --- |
| 4 | entry `FunctionIndex` (`u32`, little-endian) |

No flags, string name, native address, relocation, calling-convention name, or source
identifier are serialized. The referenced `FunctionIndex` MUST exist in the Function
table.

`NoIndex` (`0xFFFFFFFF`) is not valid here. Omission of the entire section represents
absence of an entry point and therefore has exactly one canonical encoding.

## Entry function contract

The referenced function MUST:

1. have zero declared arguments;
2. have no module-boundary calling convention attached to the entry point itself;
3. return either `Void` or one scalar v0 execution-cell integer type:
   `Bool`, `Char8`, `Char16`, `Byte`, `SByte`, `UInt16`, `Int16`, `UInt32`,
   `Int32`, `UInt64`, or `Int64`;
4. otherwise satisfy every Function-table and Code-section invariant of Indexed
   Executable Representation v0.

The entry-point section does not make the function an Export and does not grant any
Import authority. Export visibility and import grants remain independent concepts.

## Process result semantics

A `Void` entry function produces logical process status `0`.

A non-void entry function produces its returned scalar cell as the logical process
status. The target runtime or operating-system adapter may apply the platform's
ordinary process-status narrowing when crossing from Ubytec into the host process
ABI. That host-specific narrowing is not encoded in PMF and MUST NOT affect the
portable function result itself.

## Lowering from source

A source frontend chooses the entry function according to the source-language rules
in force for that frontend. The current Ubytec source convention designates a
zero-argument function named `Main` when process-entry emission is requested.

That source name is a frontend concern only. After lowering, the executable identity
is the resulting `FunctionIndex` in section `0x0017`. A backend consuming indexed PMF
MUST use that index and MUST NOT search Semantic AST JSON for `Main`.

When source compilation is requested as a library, the lowerer MUST omit `0x0017`
even if a function named `Main` exists.

## Verification

A verifier MUST reject an entry-point section when:

- its payload length is not exactly 4 bytes;
- the indexed executable section group is absent or incomplete;
- the `FunctionIndex` is out of range or equals `NoIndex`;
- the referenced function has one or more arguments;
- the referenced return type is not `Void` or one of the scalar v0 execution-cell
  integer types listed above;
- the section is duplicated, non-critical, truncated, or otherwise violates PMF
  framing/canonical-order rules.

A canonical encoder emits no entry-point section for a library and exactly one
critical `0x0017` section for an executable module.

## Native backend requirement

A native backend may synthesize ELF `_start`, PE startup code, an ARM64 process
entry stub, or another target-specific adapter. That generated adapter MUST dispatch
to the portable entry `FunctionIndex`; its native symbol and machine address are not
portable identity and MUST NOT be written back into PMF.

This separation is required so the same UBCM bytes can later feed independent x64 and
ARM64 backends while preserving one executable entry decision.

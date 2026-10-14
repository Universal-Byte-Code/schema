# Indexed Executable Process Entrypoint v0

This document extends the Indexed Executable Representation v0 with an explicit,
architecture-neutral distinction between a library module and a process image.

The base indexed executable profile deliberately removes source function names from
the Function table. Consequently a native backend MUST NOT recover the process
entrypoint by reparsing the Semantic AST, searching for a source name such as
`Main`, or assuming a particular `FunctionIndex` by convention.

## Optional Process Entrypoint section — `0x0017`

Section kind `0x0017` carries process-start metadata for the indexed executable
profile.

The section is optional and MUST use PMF flags `0` (non-critical). Absence means the
module is a library and has no automatic process entrypoint.

Making this section non-critical is intentional and fail-closed: a PMF reader that
does not understand process-start metadata can still inspect or preserve the module,
but MUST NOT invent an entrypoint. Canonical PMF rewriters retain unknown optional
sections byte-for-byte.

When present, the payload is exactly four bytes:

| Size | Field |
| ---: | --- |
| 4 | entry `FunctionIndex` (`u32`) |

The value MAY be `NoIndex` (`0xFFFFFFFF`). A present section with `NoIndex` denotes
a process image that performs platform process startup/termination but invokes no
Ubytec function before termination. This preserves the existing source semantics of
an executable module with no `Main` function.

Any other value MUST reference an existing Function-table entry. The referenced
function MUST have zero arguments. Its result MAY be `Void` or any return type
accepted by the target backend's ordinary Ubytec function ABI.

A module MUST contain at most one `0x0017` section. Its payload length, flags and
FunctionIndex are part of structural verification.

## Source lowering

The reference source frontend uses the existing executable-module convention:

- when compiling a library, it emits no `0x0017` section;
- when compiling a process image with a top-level `Main`, it lowers that callable to
  its canonical `FunctionIndex` and stores that index in `0x0017`;
- when compiling a process image without `Main`, it emits `0x0017` with `NoIndex`;
- a source `Main` with arguments is rejected before producing a process image.

The source name `Main` is therefore a frontend convention only. It does not survive
as executable identity in the binary image.

## Native backend semantics

A native backend that produces a standalone process entrypoint consumes only the
verified `0x0017` metadata and indexed executable tables. It MUST NOT consult source
text or Semantic AST data to choose the function to invoke.

For the current Linux x86-64 reference backend, a present `0x0017` section lowers to
the existing process-start behavior:

```text
_start:
    [call FunctionIndex, when not NoIndex]
    [move non-void result to process exit status, otherwise zero]
    exit
```

The exact host entry symbol, syscall sequence and process ABI remain backend/platform
concerns and are not serialized into UBCM.

## Canonicality and verification

The section payload has one fixed-width encoding. Writers MUST NOT serialize source
names, native labels, addresses or host handles in this section.

A verifier MUST reject:

- duplicate `0x0017` sections;
- non-zero section flags;
- payload lengths other than four bytes;
- a non-`NoIndex` FunctionIndex outside the Function table;
- an entry function with one or more arguments.

This extension is stacked on `docs/indexed-executable-v0.md` and does not change the
wire encoding of the existing `0x0010..0x0016` section group.

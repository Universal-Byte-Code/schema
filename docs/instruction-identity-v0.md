# Derived instruction identity v0 (draft)

Companion: Universal-Byte-Code/ubytec-interpreter#38. This draft is stacked on
the contracted BLOCK executable profile (context wire version 3). It does not
allocate an opcode, section, instruction GUID or host capability.

## Identity layers

- ISA identity: the opcode registry/version and the entire encoded opcode path
  (including escape depth, group and operation).
- Instruction form: ISA identity plus its canonical operand bytes under the
  selected executable wire contract. Equality of forms is not identity of sites.
- Static occurrence: (ExecutableDigestV1, FunctionIndex, InstructionOffset).
  FunctionIndex is the verified u32 table index; InstructionOffset is the u32
  byte offset relative to that function's first code byte, pointing to the
  first opcode byte, not an operand, extension-group byte, or exclusive end.
- Loaded instance: loader-assigned identity within a runtime session; loading
  the same executable twice does not collapse two instances.
- Activation: an instance of a callable invocation, including recursive calls.
- Dynamic event: a runtime identity allocated at a specified observation or
  execution boundary; multiple events can refer to one static occurrence.

Identity is not authority. Neither a digest nor an occurrence grants access,
execution permission or any right to a callable or memory region.

## ExecutableDigestV1

Derive the digest only after independent raw-wire and semantic verification of
the indexed executable. Apply any separately required admission policy before
using identity for execution. PMF-only AST images have no static occurrence.

SHA-256 preimage is the concatenation of:

1. ASCII UBYTEC-EXEC-ID-V1 followed by one zero byte;
2. PMF MajorVersion (u16 LE), MinorVersion (u16 LE);
3. number of selected sections (u32 LE);
4. each selected section in ascending kind, using its exact PMF section header
   (u16 kind, u16 flags, u64 payload length, all LE) and exact payload.

Selected kinds: 0x0002, 0x0003, and 0x0010 through 0x0019 inclusive, if present.
This includes the process entrypoint 0x0017 even though it is noncritical.
The transitional AST (0x0001) and unknown noncritical sections are excluded;
unknown critical sections must already have been rejected by verification.
The digest assumes the current backend does not consume unknown optional
sections for executable semantics. Future semantic section additions outside
this set or changed projection rules require a revised identity domain.
No outer SectionCount or unselected section bytes enter this projection.

Binary digest is 32 bytes; display form is 64 uppercase hexadecimal characters.
A full-container hash is a different identity and must not substitute for
this projection. A native artifact hash is also distinct. SHA-256 collision
resistance is assumed, not a proof of semantic program equivalence.

A verifier must identify instruction starts during the raw operand-framing
walk, including unreachable instructions that pass verification. It must not
accept an operand byte simply because that byte is a valid opcode in isolation.
No occurrence is returned if any later validation of the image fails. This
contract gives no stability across changes to executable bytes or table indices;
different compiler outputs may have distinct digests even if behavior agrees.

## Native and dynamic provenance (design requirements; not implemented here)

Native ranges are relative to a named executable image and authenticated or
otherwise trusted artifact association. A mapping is a relation: one portable
site may yield zero or multiple ranges; a fused range may originate at multiple
sites. Synthetic checks must identify their originating occurrence, semantic
subsite (e.g. input index or result), and failure cause when available. Unmapped
or ambiguous faults must be reported as such rather than guessed. Source mapping
may be a separate sidecar, not normative executable identity. Backend maps are
not independent proofs of translation correctness.

Runtime event identity, activation allocation, restart and overflow policies,
trap attribution and deterministic replay are subsequent contracts. In
particular, a static TRAP occurrence is distinct from the event that executes
it and its trap reason. A physical timestamp is not a unique event identity.

## Acceptance

- Equal opcode forms at distinct verified offsets are distinct occurrences.
- Repeated queries for a verified unchanged occurrence agree.
- Offsets inside operands or outside the function, invalid images and admission
  mismatches cannot produce identities.
- Executable section changes change the digest; excluded metadata does not.
- Native and dynamic conformance require separate tests and implementation.

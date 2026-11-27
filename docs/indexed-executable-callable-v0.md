# Activation-local CallableCapability profile v0 (draft)

Companion to the contextual indexed executable profile. This is the first
restricted callable authority slice, not a general object-capability runtime.

## Identity, authority and representation

A declaration identity is (immutable module artifact, FunctionIndex). A
CallableCapability is authority to invoke one resolved declaration with an
exact signature in one activation of a verified function. The numeric identity
of a declaration is not itself a capability. A CallableSlotIndex is an immediate
index into the current activation's separate callable bank, not a scalar value
or a memory address. Slots are never addressable by scalar instructions.

A slot holds Empty or a valid callable reference, not an arbitrary integer.
Representation is backend-private, with no fixed portable bit width, pointer
representation or serialization. Neither PUSH, arithmetic, scalar frame LOAD/
STORE, raw addresses nor serialized constants can produce or access one.
No capture of another frame, closure environment, import/export delegation,
persistent references, cross-thread transfer or capability-valued arguments/
results is admitted in this slice. All scalar boundary restrictions are inherited
from DirectOnly. Each activation (including recursive calls) has an independent
bank initially Empty. Return, trap unwinding or activation destruction destroys
the bank; module code is immutable and remains live for all its activations.

## Admission and wire extension

ExecutionProfile=2 (CallableLocal) in critical section 0x0018 extends DirectOnly
with only the four capability operations below. UnsafeCells (0) and DirectOnly
(1) MUST reject these opcodes and MUST NOT contain section 0x0019. CallableLocal
MUST contain exactly one critical 0x0019. A reader that does not implement this
profile MUST reject it, never reinterpret it as UnsafeCells or DirectOnly.
Admission requiring CallableLocal explicitly requires profile 2, not merely a
valid PMF or a producer's label; other profiles are not substitutes.

Section 0x0019: Callable slot signatures. All fields are fixed-width u32
little-endian. It contains:

- Version = 0.
- FunctionCount = exact count of the Function table.
- For each FunctionIndex in ascending order: SlotCount, followed by SlotCount
  signatures in ascending CallableSlotIndex order.
- Each signature consists of ReturnTypeIndex, ArgumentCount, and ArgumentCount
  argument TypeIndex values in declaration order.

Every signature MUST use admitted scalar function signature types (void only
as a return). Exact equality of TypeIndex values and ordered argument lists
defines signature equality; no implicit coercion, variance or ABI-only matching.
The slot table may contain repeated signatures: slots have distinct identity
even when types are identical. All counts and byte lengths MUST be bounded and
consume the section exactly. A slot count of zero is valid. No capability values
or initial targets are serialized.

## Draft ISA allocations

The canonical registry reserves depth 1 group 0x13 for callable-capability
operations. Operands are u32 little-endian. These allocations are draft, not
stable. They are independent of the host capability registry.

| Wire opcode | Mnemonic | Operands | Effect |
| --- | --- | --- | --- |
| FF 13 00 | CAP_BIND | DestinationSlot, FunctionIndex | Resolve a visible local function and replace destination with a callable reference |
| FF 13 01 | CAP_COPY | DestinationSlot, SourceSlot | Copy the source slot into destination |
| FF 13 02 | CAP_CLEAR | Slot | Replace slot with Empty |
| FF 13 03 | CAP_CALL | Slot | Invoke the slot's target with its declared scalar signature |

CAP_BIND is the sole minting operation in this slice. The verifier MUST check
lexical visibility from the current function, target existence and exact
signature equality with the destination. The runtime may only materialize
authority from that verified resolution within the loaded module, never a
scalar target supplied by the program. CAP_COPY requires exact signature equality
and copies Empty as Empty; it does not grant authority outside the activation.
CAP_CLEAR is local release, not global revocation; copies remain valid.
CAP_CALL reads (does not consume) the slot; Empty deterministically traps before
invoking anything or changing the scalar stack. Nonempty calls consume the
declared number of scalar argument cells in existing CALL order, invoke the
resolved declaration, and push one scalar result unless void. The target
signature, identity and liveness MUST be guaranteed by construction or checked
at invocation; corrupted or invalid runtime representations MUST fail closed
within the stated trusted enforcement boundary.

All capability instructions MUST be verified even in unreachable code. Slot
indices are immediate, bounded by the current function's declared bank. There
is no dynamic scalar-to-slot indexing. The scalar stack effect of CAP_BIND,
CAP_COPY and CAP_CLEAR is zero. CAP_CALL derives its scalar stack effect solely
from the slot signature, never from an arity/result operand supplied by the
caller. The ordinary control-flow verifier still checks scalar stack depths at
joins and backedges. Capability banks can differ across branches: each slot has
one invariant signature, and Empty is permitted at any point with a trapping
call. A callee starts with an empty bank even when its caller has authority.
Frame-reusing tail transfers remain prohibited.

## Native implementation contract

A conventional backend may implement a separate private bank of finite dispatch
selectors per activation. It MUST initialize slots to Empty on every activation;
only verified CAP_BIND can establish an allowed selector; CAP_COPY/CLEAR are
restricted to that bank. For a first implementation, CAP_CALL dispatches via
checked cases and direct native calls to verified, visible, signature-matching
targets (default trap), not an unchecked CALL through a raw address. An explicit
upper bound on slots and dispatch size is permitted; exceeding it rejects the
module. The emitted dispatch domain and storage layout must be validated.
An optimizer MUST NOT introduce authority, scalar aliases or lifetime extension.

A CHERI backend may instead use suitable protected callable capabilities and
private typed slots, provided it enforces the same portable rules. No hardware
capability encoding is mandated by this document; CHERI does not by itself
establish the activation-lifetime policy, backend correctness or isolation from
an untrusted host. A backend without the required guarantees MUST reject the
profile. Source syntax and AST lowering are a separate implementation gate;
no raw FNADDR/CALLI translation is implicit.

## Threat model and non-goals

The input is an untrusted UBCM image and the verifier is independent of source
resolution. The implementation must trust or independently validate native
translation and enforce private bank storage, control-flow integrity at the
dispatch boundary, and immutable loaded code. The profile does not claim full
native CFI, memory/temporal safety, stack resource bounds, malicious embedding
host resistance, or correspondence to original source intent. General typed
capability values, argument passing, cross-module delegation, revocation,
closures, memory capabilities and persistent services require separate
specifications. Do not silently relax these restrictions to gain compatibility.

## Conformance evidence

Required cases: dynamic selection of two same-signature visible functions;
copy/clear independence; Empty trap; recursive activation isolation; rejection
of out-of-context bind, wrong argument/return type (even equal arity), bad slot,
bad target, missing/extra/noncritical section, unknown version/profile, truncated
or extra payload, wrong escape depth and scalar-to-callable attempts. Reject
FNADDR, CALLI, raw LOAD/STORE, imports and loan exports in CallableLocal.
Test verifier acceptance separately from backend execution. The reference model
in tests/test_callable_capability.py exercises only the new table/instruction
and activation-bank semantics, not full PMF or native execution.

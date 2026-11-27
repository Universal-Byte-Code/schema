# Contextual indexed executable profile v0 (draft)

This proposal extends the unreleased indexed executable profile. It preserves
lexical declaration topology without making instruction operands recursive or
reintroducing names into executable code. It does not certify source intent.

## Critical section 0x0018 — Function contexts

Every indexed executable module MUST contain exactly one critical 0x0018 section
in addition to the seven base indexed sections. AST-only PMF MUST NOT contain it.
Earlier draft indexed images lacking this section are not contextual images and
MUST be recompiled. A reader that does not recognize 0x0018 MUST reject it.

All fields are little-endian u32:

| Field | Meaning |
| --- | --- |
| Version | 0 |
| ExecutionProfile | 0 = UnsafeCells, 1 = DirectOnly, 2 = CallableLocal |
| FunctionCount | exactly the Function table count |
| ParentFunctionIndex × FunctionCount | one entry per FunctionIndex |

NoIndex (0xFFFFFFFF) means the module root. Otherwise parent indices MUST
precede their children. Rows MUST follow preorder: once a subtree is closed, a
later row MUST NOT reopen it. Every root and subtree occupies a contiguous range.
Reject unknown versions/profiles, count mismatch, dangling/self/forward parent,
reopened subtrees and trailing bytes. No context is inferred from source names,
native addresses, debug data or declaration order alone.

## Lexical visibility

A top-level declaration is visible to every function in the same module.
A nested declaration is directly referenceable only from its owning function
and that owner's descendants (including the target itself). This includes
sibling calls through a common owning context and recursion. CALL with
TargetKind=Function and FNADDR MUST enforce this relation even in unreachable
code. ImportIndex remains a separately authorized boundary slot. Only top-level
functions may be exported or selected as process entrypoints. BindingIndex
remains frame-local; parent metadata does not introduce captured variables.

Source name shadowing is resolved before encoding; this relation defines
admissible identity references, not a reconstruction of name lookup. A function
declaration's identity is module artifact + FunctionIndex; its lexical parent
chain is reconstructible. Runtime activations have distinct lifetimes and are
not identified solely by declaration identity.

## Execution profiles

UnsafeCells (0) retains existing integer cell/raw-address semantics, including
FNADDR, CALLI and raw memory. Lexical checks constrain encoded direct references,
not arbitrary native control flow. It MUST NOT be represented as a memory-safe,
capability-safe or control-flow-integrity profile.

DirectOnly (1) is an initial restricted scalar profile, not a full protected
capability runtime. It MUST reject FNADDR and CALLI, raw LOAD/STORE modes 0/1,
all imports, and non-Value export passing modes. Named frame LOAD/STORE, scalar
operations with defined stack effects, structured control and visible direct
calls are admitted. The allowed opcode set is closed: RETURN, VAR, PUSH,
DROP/PICK/ROLL, CALL(Function), named LOAD/STORE, BLOCK/LOOP/IF/WHILE/ELSE/END,
SWITCH/BRANCH/DEFAULT, BREAK/CONTINUE, NOP/TRAP/CLEAR/NULL, POP/DUP/SWAP/ROT/OVER/NIP,
2DUP/2SWAP/2ROT/2OVER, and the existing scalar arithmetic/bitwise/comparison
opcodes 0x20–0x2A, 0x30–0x36, 0x40–0x49, and depth-one group 0x10
PUSH16/DROP16/PICK16/ROLL16 subject to the exact stack bounds in the indexed
executable contract. Other opcodes MUST be rejected.
All regular independent verifier invariants still apply. This profile does not
establish temporal safety, correct native translation, stack resource limits,
complete native CFI, or isolation from an untrusted embedding host.

An admission policy requiring DirectOnly MUST check the profile explicitly and
reject UnsafeCells, CallableLocal and AST-only inputs; a producer's declaration is not itself
a grant or a trusted policy. Do not silently downgrade. No capability grants are
created by the section. Frame-reusing tail calls are excluded from DirectOnly
until lifetime/translation semantics are specified.

## Typed callable authority (separate draft)

[CallableLocal](indexed-executable-callable-v0.md) defines the initial activation-local bank, critical section and draft opcode allocations. The broader model below remains future work.

A protected capability profile will distinguish ordinary integers, raw addresses
and callable references, with a callable's exact signature, target identity,
authority scope and lifetime. Authority can only originate from verified
resolution or explicit trusted delegation, not from a numerical conversion or
serialized bytes. Indirect calls must consume a valid callable reference and
match its signature; reference flow through stack, locals, joins, memory and
boundary contracts must preserve authority and reject fabrication or unauthorized
escape. Define checked revocation and reference lifetime before claiming temporal
safety. Conventional and CHERI backends may realize the same semantics with
different trusted mechanisms, and MUST reject unsupported required guarantees.
Opcode/type allocations and ABI representation require their own reviewed
specification. DirectOnly is a deliberately smaller first step, not a substitute.

## Trust boundary

The raw verifier checks declared contextual and profile invariants independently
of source lowering. A malicious producer can still misdeclare a context graph or
alter intended computation. Source-to-binary equivalence, backend translation
validation, artifact authenticity and runtime enforcement are distinct obligations.

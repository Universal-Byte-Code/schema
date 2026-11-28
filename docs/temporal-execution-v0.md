# Temporal execution v0 (normative draft)

Companion: Universal-Byte-Code/ubytec-interpreter#39. Depends on
[instruction identity](instruction-identity-v0.md). MUST and MUST NOT express
requirements of the proposed temporal-v0 contract, not claims about existing
execution profiles. This document allocates no opcode, wire section, capability
or ABI. A runtime claiming temporal-v0 MUST implement the following observable
semantics or reject admission. Ordinary executable verification alone does not
establish temporal conformance.

## 1. Domain and identity

A session has one logical coordinator, an initial ordered list of admitted
contexts, and an ordered external input journal. Initial context creation is
committed in declared order at round zero by the coordinator. A context's
first semantic event depends on its creation. Creation during execution is a
primary turn effect of the parent; it does not introduce a same-round turn. Session identity is fresh for
each run, including replay. Context and loaded-instance ordinals are positive
u64, assigned by their respective coordinator in admission order, never reused.
An activation ordinal is positive u64 within a context and is allocated on entry,
including recursion. Activation return and abort are distinct transitions.
Event identity is (session, context ordinal, context-local event sequence).
The coordinator is also a distinguished event producer with context ordinal
zero, for external admissions and coordinator-owned transitions. It has its
own local sequence and logical clock. No timestamp is an identifier.

All counters start at zero before allocation; first allocated value is one.
No counter may wrap. An operation that would exhaust a required identity,
clock or commit namespace MUST fail before publishing or applying its effect.
A failed infrastructure transaction MUST NOT be represented as a successful
portable event. Session termination and failure reporting may be out of band
if no further event identity can be allocated. Admission MUST establish finite
resource limits, including context count, stack, queues, trace size and budget.
A bounded ledger can establish that event sequences and Lamport time never
reach u64 exhaustion (each logical increment follows a committed event and
all causal predecessors precede it). The complete multi-event effect batch
MUST be preflighted for capacity before publication. Already committed prior
turns are not rolled back by a later failed turn; infrastructure failure
poisons the session, preventing further effects or successful replay claims.

## 2. Three orders, one physical clock domain

Each context has a local event sequence S and a Lamport clock L. The
coordinator assigns global commit sequence G. For an admitted event with
explicit predecessor events D, all already committed:

    S' = S + 1
    L' = max(L, max(L(d) for d in D, default=0)) + 1
    G' = G + 1

The predecessor set includes all required semantic dependencies, not just
messages: creation, delivery, read-from, write serialization, synchronization,
external input and cancellation where applicable. Same-context order is
implicit. G is a linear extension of these dependencies; G(a) < G(b) does
not itself establish a causal edge. Equal logical times are allowed.
L(a) < L(b) does not imply a causal path. S, L and G are distinct quantities.

Physical clock observations have a separate domain C (§7). No logical
counter measures elapsed seconds. Host CPU scheduling and observation arrival
times MUST NOT decide G except through explicitly admitted external inputs.

## 3. Observable transitions and canonical fuel

The temporal event stream includes context creation/termination, invocation
entry/normal completion/abort, mediated shared memory and atomic operations,
message sends/deliveries, synchronization, capability/authority transitions,
external input/output requests and results, clock observations, explicit yield,
timer decisions, faults, and budget boundaries. This is an abstract event
taxonomy; it is not an opcode table. Private arithmetic, local state mutations
and debug probes are not independently observable unless the selected contract
explicitly exposes them. Debug tracing MUST NOT insert semantic events into G. A diagnostic ledger has
its own namespace/order; its entries cannot be submitted unchanged to a
semantic ledger. Semantic fault mediation must be specified independently.
For a portable budget/fault/return boundary record the round, boundary kind,
accumulated fuel, verified occurrence when applicable, and result where
applicable. A normal invocation return and final context termination are
separate transitions.

A logical work unit is one attempted verified portable instruction, charged
before execution, including a faulting instruction. Operand bytes, escape
bytes, native instructions and wall time are not units. A blocked effect
request retains its already-charged instruction; retries do not charge again.
Function entry/exit and other synthetic semantic transitions are separate
event boundaries, not extra portable instruction fuel. A pending instruction
can produce multiple specified transitions; it cannot start another
instruction while such transitions remain pending. A reference interpreter
defines the abstract portable execution order, including structured control
flow, synthetic guards and calls. An optimized backend MUST preserve that
order at observable boundaries and account for eliminated/fused instructions
as if interpreted; it MUST reject temporal-v0 if it cannot. Optimization may
change wall time, never the semantic fuel budget. Debug-only native INT3
markers are not the normative mechanism.
For the verified LOOP-only reference subset, LOOP charges on entry; END and
CONTINUE charge their own instruction and transfer to the first body
instruction (not a second execution of LOOP). BREAK charges its own
instruction and skips the target END. No implicit fuel is charged for label
resolution. Nested targets use verified relative control ordinals.

Each admitted context has a positive fixed fuel quantum Q for this profile.
A turn advances private computation until the next semantic event request,
blocking request, termination/fault, or Q charged instructions (whichever
comes first). If the Qth instruction produces a semantic request, that
request is the boundary, not a second simultaneous budget event. Otherwise
a budget event closes the turn. Entry/exit boundaries close a turn even
without fuel consumption. A pure infinite loop therefore yields at bounded
logical work intervals; this is not a wall-clock deadline.

## 4. Deterministic frontiers and turns

The normative reference is serial. At the start of round r the coordinator
admits the journal entries explicitly targeted to that boundary, in journal
ordinal order, then snapshots live context ordinals in ascending order.
Initial contexts are allocated in declaration/admission order. New contexts
created during a round join the next round. A context cancelled or terminated
before its turn is skipped. Each remaining context receives at most one turn
in that round. A blocked context retries its retained request when visited;
if still blocked it consumes neither new fuel nor a new event. If enabled
by an earlier commit in the same round it can proceed in that round; if
enabled after its visit it waits until the next round.

An effect request is committed atomically with its result and required
dependencies before the next turn. A blocked request MUST NOT expose
partial mutations or consume a local/global event number until a transition
is actually committed. Blocking state is coordinator state, not evidence
that an effect occurred. Cancellation of a pending request is a separately
committed transition with explicit outcome; no silent retry of irreversible
effects. A turn ends after its single primary boundary, not after arbitrary native
progress. A prepared request is bound to its session, round and context;
workers do not acquire publication authority. Coordinator-owned synthetic
delivery events (e.g. expiry triggered by a clock observation) belong to the
same admitted effect batch, not extra worker turns. A suspended timer waiter
has no turn until it is eligible at a later snapshot. Other blocked requests
are retried at their assigned visit as specified above.

If no turn or admission makes progress, the result is quiescent with explicit
blocked contexts and pending requests. The coordinator may resume only on
a specified subsequent external admission; it MUST NOT invent a timer tick,
receive or successful operation. For the finite reference, absent such input,
report quiescence rather than spin. A finite reference with a recorded future journal admission MAY resume at its
explicit target round, skipping only empty quiescent rounds. No implicit clock
sampling or autonomous wakeup is implied. Admission order is unchanged.
A fully terminated session admits no additional effects.

Parallel implementations may evaluate isolated private work concurrently.
They MUST produce exactly the serial reference observable sequence for
the same admitted program, initial state, Q and external journal. The
coordinator cannot skip a slower context because a later context arrived
first. Requests carry their intended round/turn and context; duplicates,
stale requests and wrong-turn publication cannot commit. Speculative reads
and computation must validate against the committed reference state or
reexecute. Irreversible effects cannot be executed speculatively. There is
no liveness promise if a worker fails to reach a frontier; a watchdog failure
is an explicit external admission or infrastructure abort, not a new
deterministic scheduler rule.

## 5. Shared state and causal edges

A shared location is a coordinator-owned, authorized location with a
committed version and last writer event (initial values have no event).
Reads observe the current committed value and depend on its last writer.
Writes and atomic read-modify-write operations serialize through the
coordinator and depend on the previous writer (RMW also reads that version).
A write updates version and last writer only on commit. Cross-location
atomicity and memory layout require separate contracts; arbitrary native
loads/stores are not automatically mediated. Conflicting operations have
the reference turn order, not an order inferred from physical time.

The initial managed reference uses bounded unsigned 64-bit scalar locations,
initialized by the host before round one (version zero, no writer event).
Read, write, and atomic rights are explicit per-context grants. Atomic add
uses modulo-2^64 arithmetic; compare-exchange compares the entire cell and
returns the observed old value and success. A successful write (including
an equal-value write or successful compare-exchange) increments version once;
a failed compare-exchange is an observable read-like operation, with unchanged
value/version/writer. Each depends on the last committed writer if one exists.
Trusted ledger evidence includes before/after values, versions, operands and
success; exposing those diagnostics to a guest requires separate authorization.
These are scalar reference effects, not portable opcode or memory-model allocations.

A send appends one message to the FIFO queue keyed by source and destination
context. Its message identity is the send event ID. A receive names its source
in v0; it removes the oldest matching committed message and depends on that
send event. Empty queue means blocked. Receive-from-any and multi-resource
waits are deferred until deterministic selection rules are specified.
A child creation event is a predecessor of its first event. Synchronization
operations must specify their release/acquire predecessors before admission.
An authorization check precedes the effect; identifiers and provenance
are not authority.

The initial managed reference grants a directional channel to its source and
destination before round one, uses bounded queues of u64 payloads, and grants
no implicit shared-memory or channel authority to spawned contexts. A retained
receive is retried by the coordinator without invoking private preparation again;
its empty attempts do not allocate events. A sender may not send to a terminated
destination. Already committed messages remain in their queues even if either
endpoint terminates; a live authorized receiver can drain a terminated source.
An empty queue from a terminated source remains blocked until explicit
cancellation (no implicit EOF policy). Cancel-wait removes a retained receive
and records its source and coordinator admission dependency; cancel-context
removes its pending wait and terminates it. Queue exhaustion fails before
publication and poisons the session; backpressure is a separate contract.
Replay compares initial grants and resource limits, final cell values, versions,
writer identities, FIFO contents/send identities and retained receives.

Raw shared memory, unmanaged I/O, live RNG, host clock instructions and other
unmediated external effects are forbidden in temporal-v0 unless their results
are observationally irrelevant and demonstrably isolated. Existing execution
profiles MUST NOT be silently promoted to temporal-v0.

## 6. External journal and replay

An external entry is (journal ordinal, target round, typed payload) with
contiguous positive ordinals starting at one and nondecreasing positive target
rounds. Already passed boundaries cannot be reopened.
At a round boundary the coordinator commits the admitted entries in that
order before context turns; delivery and cancellation transitions refer
to the admission event. A live adapter chooses and records the admission
boundary according to its declared policy. The timing of real-world
arrivals is not reproducible in general: determinism is conditional on
the same journal, not on identical source code alone. A request-driven
external result (including clock) is keyed to the requesting event/turn
and a positive session-local observation ordinal (also distinguishing multiple
coordinator samples at one boundary). Record it as part of the atomic effect
batch. Replay must validate its key and ordinal, not just consume an unkeyed
value. The reference must not read a
live external source during replay.

Replay compares the full normalized semantic trace: event IDs projected
to session-local ordinals, activation/instance/context creation order,
kind, occurrence when applicable, results, dependencies, S/L/G, final
shared state and terminal/blocked state. Physical samples and external
results are replayed from journal/recorded request results. Fresh session
identity, native RIP, ASLR, raw stack addresses and debug observations
are not semantic equality fields. A missing, extra, mismatched or
reordered record is a replay failure. External irreversible outputs
must be suppressed or directed to a replay sink, never issued again.
Durable serialization, crash consistency and distributed consensus are
separate contracts; this draft specifies logical content, not wire encoding.

## 7. Master monotonic observation

An explicitly granted clock capability exposes a session-local clock domain.
The proposed v0 physical clock adapter uses unsigned integer nanoseconds,
origin at session clock initialization, nondecreasing observations, and
a monotonic host source excluding system suspend (Linux CLOCK_MONOTONIC
reference). Other backends must document and match suspend semantics or
negotiate a distinct domain.
Clock grants are initially admitted by the host and may be attenuated at
spawn. An explicit journal revocation of an active grant commits a coordinator
admission and a context-local revocation transition with that admission as
predecessor, before the target's turn. Subsequent clock requests require a
still-active grant. Revocation of clock observation authority does not
implicitly revoke timer authority or remove an already registered timer. Precision/resolution is reported separately;
nanosecond units do not imply nanosecond accuracy. Equal samples are valid.
Overflow, unavailable clock or regression is an explicit failure, never
silent clamping. Wall time is not this domain. Cross-session/host subtraction
is invalid unless a separate synchronization contract exists.

A clock request is an observable effect; its sample is obtained once by
the coordinator's authorized adapter at the admitted turn and recorded.
Replay consumes that sample, never the current host clock. A duration is
the nonnegative difference of two samples within the same domain. Request
ordering is logical; sampling is physical. The coordinator does not
implicitly sample time to choose a runnable context.

A timer/deadline is expressed in the same domain. A clock observation
admitted to the coordinator can enable a timer when sample >= deadline;
equal deadlines are ordered by registration commit then timer ordinal.
Delivery is a separate committed event depending on both registration and
the enabling sample. The reference sleep-until operation registers a single absolute deadline per
context, commits registration, then suspends further turns. It requires
explicit timer authority. A later admitted clock sample (request result or
coordinator journal entry) delivers all eligible timers in ascending
(deadline, registration commit, timer ordinal) order. Delivery depends on
registration and sample, consumes no instruction fuel and makes the context
eligible at the next frontier snapshot (same round if before that snapshot).
Even an already-past deadline requires a subsequent admitted observation.
Cancellation of the sleeping context terminates that context and removes its
pending timer, with registration and coordinator cancellation admission as
predecessors; no later expiry. If an active invocation exists, cancellation
requires explicit abort/unwind transitions before context termination. A
separate cancel-wait admission removes the pending timer without terminating
the context; the waiter may resume at the next frontier snapshot. Both
operations are journal entries with explicit outcomes; the initial contract
rejects invalid targets rather than silently changing state. The initial
reference uses context ordinal as tie-break because only one timer per context
may be pending. Multiple timers, independent timer cancellation handles and
autonomous live wake policy remain separate. No hard real-time or exact wakeup guarantee.

Fixed-step application logic uses checked integer accumulation:

    total = accumulator + elapsed
    steps = min(total / step_duration, catchup_limit)
    accumulator = total - steps * step_duration

step_duration > 0; division is integer; catchup_limit is an explicit
nonnegative bound. Retain backlog even when capped; dropping or clamping
time requires an explicit application policy. Overflow is an error.
No implicit conversion between ticks, instructions and physical duration.

## 8. Conformance and staged implementation

A conformance suite MUST cover equal timestamps, local and cross-context
dependencies, conflicting RMW, blocked receives before/after a send in a
round, creation order, nested invocations and abort, bounded pure loops,
shuffled host arrival, cancellation at an admitted boundary, physical
sample replay and regression, resource/counter exhaustion, fixed-step
backlog, and rejection of a missing/extra/mismatched replay entry.
Parallel equivalence tests MUST vary host execution timing and compare the
normalized trace and state to the serial reference.

Current implementations cover subsets only. The C# managed coordinator is the
implementation target; its typed managed effects, journal and lifecycle do
not by themselves establish the complete portable instruction/effect binding.
The scalar verified UBCM interpreter covers a restricted scalar and LOOP-only subset.
The Python effect models are historical test references to retire after managed
parity. The native debug observer is a separate diagnostic ledger, not evidence
of normative scheduling, protected clock access or semantic effect mediation.
No conformance claim until the reference semantics and integration gates
are tested. Deadlock recovery, fairness beyond finite round visitation,
host crash recovery, multihost consensus, optimized provenance, and
production security are not solved by this contract.

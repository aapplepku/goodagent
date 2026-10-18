# Measurement-window correction before non-thin outcomes

Registered 2026-09-07 UTC, after the thin-history development diagnostic and
before any non-thin development or held-out rollout. The original protocol.md
and thin-history results remain unchanged. No held-out outcomes were inspected.

The durable executor's existing measurement schedule lasts seven days. A first
intervention at the end of warmup day six therefore remains under measurement
until day thirteen. The original six evaluation days end at day twelve, preventing
even one completed measurement followed by a fresh planning cycle. This is a
protocol timing defect, not a reason to shorten policy or measurement protection.

For every non-thin condition and every arm, retain six warmup days but use twelve
evaluation days and a twenty-four-day goal horizon. Existing world offers end at
the new common horizon. Seeds, fixtures, traffic, permissions, approval regime,
controller rules, accounting, outcome definitions and statistical reporting do
not change. Thin-history remains zero warmup, one evaluation day, with the original
sixteen-day goal horizon and its preserved first-pass evidence.

The driver records both original protocol and amendment hashes. The extension
does not require action, repetition, favorable outcomes or positive lift. If new
evidence is insufficient, the later cycles must still wait. All arms receive
the same additional exogenous opportunities. Do not pool the thin-history replay
as another independent case or retrospectively reinterpret its source version.

The evaluator calls the existing tenant-scoped worker measurement handler on
persisted measurement jobs after each virtual day. This exercises the same
measurement/guardrail persistence, but does not benchmark Redis delivery timing.
Queue durability is covered separately by integration/recovery tests. Safety-
paused goals remain paused and their absence of later actions is reported.

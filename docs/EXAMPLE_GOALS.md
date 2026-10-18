# Example Goals

These requests use the existing `POST /v1/goals` contract. Only synthetic data.
The examples do not activate goals or grant execution permission by themselves.
All use USD integer minor units, seed 42, a 30-day horizon and approval-required autonomy.

| Example | Objective | What to inspect |
| --- | --- | --- |
| [Acquisition](../examples/goals/acquisition.json) | 200 new customers | Baseline trajectory, campaign proposal, exact approval and observations |
| [Acquisition stretch](../examples/goals/acquisition-stretch.json) | 9,000 new customers | Changed diagnosis/proposals; difficult is not necessarily physically infeasible |
| [Excess inventory](../examples/goals/excess-inventory.json) | 200 scoped units sold | Overstock scope and legitimate no-action results when already on track |
| [Search conversion](../examples/goals/search-conversion.json) | 200 search-attributed purchases | Internal exposure, relevance constraints and five retrieval modes |

The primary story is **200 new customers / $10,000 / CAC <= $40 / margin >= 25% /
discount <= 15%**. The separate $250 daily cap is also present in these examples.
Today goal creation installs fixed CAC, margin and discount constraints; they are
not arbitrary fields in the creation request. Tenant policy can make limits
stricter. Natural-language parsing is a limited deterministic draft, not an LLM
understanding or accepting every sentence.

## Run Through The Browser

Choose a synthetic store, enter the example sentence, select **Draft**, inspect
**New goal review** and all warnings, then **Activate and run**. Editing the text
invalidates the previous draft; the saved goal is shown separately. A scenario
card's **Run scenario** launches its defaults, not an unreviewed edited draft.

For the stretch case enter: "Acquire 9000 new customers in 30 days with a $10000
budget." It does not promise 9,000 customers. Inspect whether the recorded
trajectory is at risk, whether any policy rejects the candidates, and what the
simulator actually observes. Do not compare only favorable outcomes.

## Run Through The API

From the repository root with the local stack healthy:

```bash
curl --fail-with-body http://localhost:8000/v1/goals \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-acquisition-seed42-v1' \
  --data-binary @examples/goals/acquisition.json
```

Use the returned `spec.id` to select the saved goal in the workspace, activate and
run it there. Reusing the same request key replays the same request; a different
payload with that key fails. Use a new key for an intentional new goal. A goal ID
is an opaque local record reference, not authentication or an API secret.

## Safe Policy-Rejection Story

On a **dedicated disposable** demo, create a stretch goal and tighten the tenant
maximum discount to 0.05. A proposed 10% discount must fail the 5% policy, not
execute. Inspect the recorded rule and execution status. Restore the original
policy afterward. This is a deliberately stricter-policy fixture, not a claim
that the default planner spontaneously proposes an excessive discount.

A rejected action, paused goal, insufficient measurement or no intervention is
valid demonstration evidence. Never substitute a favorable hardcoded result.

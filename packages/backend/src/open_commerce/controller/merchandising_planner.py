"""Enumerate observed alternatives, then select one after authoritative policy."""

from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from open_commerce.controller.merchandising_candidates import (
    MAX_DRAFTS,
    DecisionCandidate,
    candidate_order,
    generate_candidates,
    objective_kind,
    observation_fingerprint,
)
from open_commerce.controller.models import (
    ControllerActionRecord,
    EvidenceItem,
    Hypothesis,
    IntentDraft,
    Opportunity,
)
from open_commerce.core.enums import ActionStatus, ActionType
from open_commerce.core.goals import GoalSpec
from open_commerce.core.types import JsonObject, StrictDomainModel
from open_commerce.simulator.models import SimulatorState

PLANNER_VERSION = "merchandising-deterministic-v2"


class MerchandisingPlan(StrictDomainModel):
    opportunities: list[Opportunity]
    hypotheses: list[Hypothesis]
    drafts: list[IntentDraft]
    decision: JsonObject


def plan_merchandising(*, goal: GoalSpec, state: SimulatorState, run_id: UUID) -> MerchandisingPlan:
    rows = generate_candidates(goal, state)
    opportunities, hypotheses, drafts = [], [], []
    for row in sorted(rows, key=candidate_order):
        if not row.candidate_generated or row.action_type == ActionType.NO_OP:
            continue
        key = uuid5(NAMESPACE_URL, f"{run_id}:{PLANNER_VERSION}:{row.key}")
        hypothesis_id, draft_id = uuid5(key, "hypothesis"), uuid5(key, "draft")
        row.opportunity_id, row.draft_id = str(key), str(draft_id)
        statement = (
            "Review a deterministic constraint stop; retain past losses and redemption history"
            if row.classification == "constraint_stop"
            else "Review observed poor performance; before/after is not causal attribution"
            if row.classification == "observed_stop"
            else "Bounded approved experiment; demand response and incremental profit are unknown"
        )
        opportunities.append(
            Opportunity(
                id=key,
                tenant_id=goal.tenant_id,
                run_id=run_id,
                type="merchandising_investigation",
                title=row.key,
                description=statement,
                confidence=Decimal(0),
                expected_metric=goal.objective.metric,
                evidence=[EvidenceItem(source=PLANNER_VERSION, key=row.key, value=row.evidence)],
                detected_at=state.current_time,
            )
        )
        hypotheses.append(
            Hypothesis(
                id=hypothesis_id,
                tenant_id=goal.tenant_id,
                run_id=run_id,
                opportunity_ids=[key],
                statement=statement,
                confidence=Decimal(0),
                created_at=state.current_time,
            )
        )
        drafts.append(
            IntentDraft(
                id=draft_id,
                tenant_id=goal.tenant_id,
                run_id=run_id,
                hypothesis_id=hypothesis_id,
                opportunity_ids=[key],
                action_type=row.action_type,
                rationale=statement,
                parameters=row.parameters,
                confidence=Decimal(0),
            )
        )
    if not drafts:
        for row in rows:
            if row.key == "unchanged":
                row.selected, row.disposition = True, "selected"
    decision: JsonObject = {
        "planner_version": PLANNER_VERSION,
        "kind": "candidates_pending_policy" if drafts else "wait",
        "reason": "Selection awaits compilation and policy"
        if drafts
        else "No supported evidence-backed intervention; retain current configuration",
        "objective": objective_kind(goal),
        "candidate_limit": MAX_DRAFTS,
        "candidates": [row.model_dump(mode="json") for row in rows],
        "observation_fingerprint": observation_fingerprint(rows),
        "predicted_profit_minor": None,
        "demand_response": "insufficient_evidence",
        "model_calls": 0,
        "model_cost_minor": 0,
        "selection_method": (
            "Stops first; clearance uses excess units before action preference. Otherwise "
            "prefer observed serving gaps before monetary experiments, then fewer affected "
            "variants. Stable semantic key breaks exact ties. Not a profit score."
        ),
        "measurement_plan": {
            "method": "surface/window-matched observations, not causal attribution",
            "window": "complete days; existing durable seven-day schedule remains binding",
            "stop": "known bounds or sufficient matched observed profit deterioration",
            "insufficient": "wait; no assumed benefit or repeated monetary experiment",
            "rollback": "future configuration only; orders, cap use and losses remain",
        },
    }
    return MerchandisingPlan(
        opportunities=opportunities, hypotheses=hypotheses, drafts=drafts, decision=decision
    )


def select_merchandising(
    decision: JsonObject,
    records: list[ControllerActionRecord],
    *,
    compiler_rejections: list[JsonObject],
    duplicates: list[JsonObject] | None = None,
) -> list[ControllerActionRecord]:
    """A candidate passing policy is not yet an approved or executed action."""
    raw = decision.get("candidates")
    if not isinstance(raw, list):
        raise ValueError("v2 candidate ledger required")
    rows = [DecisionCandidate.model_validate(value) for value in raw]
    by_opportunity = {r.opportunity_id: r for r in rows if r.opportunity_id}
    by_draft = {r.draft_id: r for r in rows if r.draft_id}
    for rejection in compiler_rejections:
        row = by_draft.get(str(rejection.get("draft_id")))
        if row is not None:
            row.compiler_result, row.disposition = "rejected", "compiler_rejected"
            row.reason_codes.append(str(rejection.get("reason", "COMPILER_REJECTED")))
    eligible = []
    for record in records:
        row = next(
            (
                by_opportunity[str(key)]
                for key in record.action.intent.opportunity_ids
                if str(key) in by_opportunity
            ),
            None,
        )
        if row is None:
            raise ValueError("compiled candidate lacks its observation ledger")
        row.compiler_result = "compiled"
        row.policy_result = record.policy_decision.model_dump(mode="json")
        if record.action.status in {ActionStatus.EXECUTABLE, ActionStatus.AWAITING_APPROVAL}:
            eligible.append((row, record))
            row.disposition = "deferred"
            row.reason_codes.append("ONE_INTERVENTION_PER_CYCLE_OTHER_CANDIDATE_PREFERRED")
        else:
            row.disposition = "policy_rejected"
            row.reason_codes.extend(record.policy_decision.reason_codes)
    for duplicate in duplicates or []:
        row = by_draft.get(str(duplicate.get("draft_id")))
        if row is not None:
            row.compiler_result, row.disposition = "duplicate", "deferred"
            row.reason_codes.append("DUPLICATE_LOGICAL_ACTION")
    selected = []
    if eligible:
        row, record = min(eligible, key=lambda pair: candidate_order(pair[0]))
        row.selected, row.disposition = True, "selected"
        row.reason_codes.remove("ONE_INTERVENTION_PER_CYCLE_OTHER_CANDIDATE_PREFERRED")
        row.reason_codes.append("PREFERRED_ELIGIBLE_CANDIDATE_UNDER_DECLARED_OBJECTIVE")
        selected = [record]
        decision.update(
            selected_key=row.key,
            kind="propose",
            reason=f"Selected {row.key}; approval/execution are separate states",
        )
    else:
        decision.update(
            selected_key="unchanged",
            kind="wait",
            reason="No supported candidate passed compilation and policy",
        )
    for row in rows:
        if row.key == "unchanged":
            row.selected = not selected
            row.disposition = "selected" if not selected else "not_selected"
            row.reason_codes = [
                "NO_ELIGIBLE_INTERVENTION"
                if not selected
                else "BOUNDED_EXPERIMENT_OR_STOP_PREFERRED_NOT_PROVEN_LIFT"
            ]
        if row.disposition == "awaiting_compilation_and_policy":
            raise ValueError("candidate lacks a complete compilation/policy disposition")
    decision["candidates"] = [row.model_dump(mode="json") for row in rows]
    return selected

"""Checkpointed model investigation within the existing durable controller."""

import json
from typing import Literal
from uuid import UUID

from pydantic import Field

from open_commerce.controller.detectors import build_observation_snapshot
from open_commerce.controller.inference import InferenceJournal, InferencePendingError
from open_commerce.controller.model_evidence import (
    budget_evidence,
    inspect_evidence,
    overview,
    prior_evidence,
)
from open_commerce.controller.model_protocol import (
    PLANNER_PROMPT,
    PROMPT_VERSION,
    InspectTool,
    PlannerResponse,
    ProposeDecision,
    validated_drafts,
)
from open_commerce.controller.models import ControllerRunRecord
from open_commerce.controller.workflow import append_trace
from open_commerce.core.enums import GoalStatus
from open_commerce.core.types import JsonObject, StrictDomainModel, utc_now
from open_commerce.persistence.repositories.controller import ControllerRepository
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.simulator.durable import load_state


class PlanningCheckpoint(StrictDomainModel):
    status: Literal["pending", "ready", "compiled", "failed"] = "pending"
    observation_version: str
    goal_revision: int
    overview: JsonObject
    prior: list[JsonObject]
    messages: list[dict[str, str]]
    evidence_refs: list[str]
    turns: list[JsonObject] = Field(default_factory=list)
    tools: list[JsonObject] = Field(default_factory=list)
    error_code: str | None = None
    prompt_version: str = PROMPT_VERSION


def checkpoint_for(run: ControllerRunRecord) -> PlanningCheckpoint | None:
    value = run.summary.get("model_planning")
    return PlanningCheckpoint.model_validate(value) if value is not None else None


class ModelPlanningService:
    def __init__(self, database: RuntimeDatabase, journal: InferenceJournal | None = None) -> None:
        self.database = database
        self.journal = journal or InferenceJournal(database)

    async def prepare(self, *, tenant_id: UUID, run_id: UUID) -> ControllerRunRecord:
        settings = self.database.settings
        for _ in range(settings.model_max_iterations + 1):
            async with self.database.transaction(tenant_id, write=True) as session:
                repo = ControllerRepository(session, tenant_id)
                run = await repo.get_run(run_id)
                if run.status in {"completed", "failed", "cancelled"}:
                    return run
                recorded = checkpoint_for(run)
                if recorded is not None and recorded.status == "compiled":
                    return run
                goal = await repo.get_goal(run.goal_id)
                state = await load_state(session, tenant_id, run.simulator_instance_id)
                policy = await repo.get_policy()
                if (
                    goal.spec.status != GoalStatus.ACTIVE
                    or policy.kill_switch_enabled
                    or settings.deployment_kill_switch
                    or goal.planning_mode != "model_backed"
                    or run.summary.get("goal_revision") != goal.revision
                ):
                    return await self._stop(repo, run, "GOAL_OR_POLICY_CHANGED")
                checkpoint = checkpoint_for(run)
                if checkpoint is None:
                    await repo.ensure_daily_budget(goal, state.current_time)
                    prior = prior_evidence(await repo.list_actions(goal_id=goal.spec.id))
                    data = overview(goal, state, await budget_evidence(repo, goal, state), prior)
                    run.snapshot = build_observation_snapshot(
                        tenant_id=tenant_id, run_id=run_id, state=state
                    )
                    checkpoint = PlanningCheckpoint(
                        observation_version=state.state_hash,
                        goal_revision=goal.revision,
                        overview=data,
                        prior=prior,
                        evidence_refs=[str(data["evidence_ref"])],
                        messages=[
                            {"role": "system", "content": PLANNER_PROMPT},
                            {"role": "user", "content": json.dumps(data, sort_keys=True)},
                        ],
                    )
                    run.status = "running"
                    run.summary["model_planning"] = checkpoint.model_dump(mode="json")
                    await repo.save_run(run)
                    await append_trace(
                        repo,
                        run,
                        "build_snapshot",
                        "Recorded allowlisted model observations",
                        {"evidence_ref": data["evidence_ref"], "mode": "model_backed"},
                    )
                if state.state_hash != checkpoint.observation_version:
                    return await self._stop(repo, run, "STALE_MODEL_OBSERVATION")
                if checkpoint.status in {"ready", "compiled", "failed"}:
                    return run
                iteration = len(checkpoint.turns)
                if iteration >= settings.model_max_iterations:
                    return await self._stop(repo, run, "MODEL_ITERATION_LIMIT")
            try:
                call_id, result, reused = await self.journal.invoke(
                    tenant_id=tenant_id,
                    scope=f"goal:{run.goal_id}",
                    operation_key=f"run:{run_id}:turn:{iteration}",
                    messages=checkpoint.messages,
                    schema=PlannerResponse.model_json_schema(),
                    template_version=checkpoint.prompt_version,
                )
                response = PlannerResponse.model_validate_json(result.content)
            except InferencePendingError:
                return run
            except Exception as exc:
                async with self.database.transaction(tenant_id, write=True) as session:
                    repo = ControllerRepository(session, tenant_id)
                    failed_run = await repo.get_run(run_id)
                    return await self._stop(repo, failed_run, type(exc).__name__)
            async with self.database.transaction(tenant_id, write=True) as session:
                repo = ControllerRepository(session, tenant_id)
                run = await repo.get_run(run_id)
                goal = await repo.get_goal(run.goal_id)
                state = await load_state(session, tenant_id, run.simulator_instance_id)
                current = checkpoint_for(run)
                if current is None:
                    raise ValueError("model checkpoint disappeared")
                if run.status in {"failed", "cancelled"}:
                    return run
                if len(current.turns) != iteration:
                    continue
                checkpoint = current
                policy = await repo.get_policy()
                if (
                    state.state_hash != checkpoint.observation_version
                    or goal.revision != checkpoint.goal_revision
                    or goal.spec.status != GoalStatus.ACTIVE
                    or policy.kill_switch_enabled
                    or settings.deployment_kill_switch
                ):
                    return await self._stop(repo, run, "STALE_MODEL_RESULT")
                checkpoint.turns.append(
                    {
                        "inference_id": str(call_id),
                        "response_reused": reused,
                        "usage": result.model_dump(mode="json", exclude={"content"}),
                        "response": response.model_dump(mode="json"),
                    }
                )
                checkpoint.messages.append(
                    {"role": "assistant", "content": response.model_dump_json()}
                )
                decision = response.decision
                try:
                    if isinstance(decision, InspectTool):
                        if len(checkpoint.tools) >= settings.model_max_tool_calls:
                            raise ValueError("MODEL_TOOL_LIMIT")
                        evidence = inspect_evidence(decision, state, checkpoint.prior)
                        checkpoint.tools.append(
                            {"request": decision.model_dump(mode="json"), "evidence": evidence}
                        )
                        checkpoint.evidence_refs.append(str(evidence["evidence_ref"]))
                        checkpoint.messages.append(
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "read_only_tool_result": evidence,
                                        "iterations_remaining": settings.model_max_iterations
                                        - iteration
                                        - 1,
                                        "tool_calls_remaining": settings.model_max_tool_calls
                                        - len(checkpoint.tools),
                                    },
                                    sort_keys=True,
                                ),
                            }
                        )
                    else:
                        if not set(decision.evidence_refs) <= set(checkpoint.evidence_refs):
                            raise ValueError("UNKNOWN_EVIDENCE_REFERENCE")
                        if isinstance(decision, ProposeDecision):
                            run.intent_drafts = validated_drafts(
                                decision, goal=goal, state=state, run_id=run_id
                            )
                        checkpoint.status = "ready"
                        run.summary["model_decision"] = decision.kind
                        run.summary["model_decision_summary"] = decision.summary
                except ValueError as exc:
                    run.summary["model_planning"] = checkpoint.model_dump(mode="json")
                    return await self._stop(repo, run, str(exc))
                run.summary["model_planning"] = checkpoint.model_dump(mode="json")
                await repo.save_run(run)
                await append_trace(
                    repo,
                    run,
                    "generate_action_intents",
                    "Recorded untrusted model decision",
                    {
                        "inference_id": str(call_id),
                        "mode": "model_backed",
                        "kind": decision.kind,
                        "source": result.source,
                        "model_id": result.model_id,
                        "model_digest": result.model_digest,
                        "goal_revision": goal.revision,
                        "observation_version": checkpoint.observation_version,
                        "response_reused": reused,
                    },
                )
                if checkpoint.status == "ready":
                    return run
        async with self.database.transaction(tenant_id, write=True) as session:
            repo = ControllerRepository(session, tenant_id)
            return await self._stop(repo, await repo.get_run(run_id), "MODEL_ITERATION_LIMIT")

    @staticmethod
    async def _stop(
        repo: ControllerRepository, run: ControllerRunRecord, code: str
    ) -> ControllerRunRecord:
        if run.status in {"completed", "cancelled", "failed"}:
            return run
        checkpoint = checkpoint_for(run)
        if checkpoint is not None and checkpoint.status == "compiled":
            return run
        if checkpoint is not None:
            checkpoint.status, checkpoint.error_code = "failed", code[:100]
            run.summary["model_planning"] = checkpoint.model_dump(mode="json")
        run.status, run.completed_at = "failed", utc_now()
        run.summary["model_error"] = code[:100]
        await repo.save_run(run)
        await append_trace(
            repo,
            run,
            "summarize",
            "Model planning stopped without fallback or execution",
            {"mode": "model_backed", "error_code": code[:100]},
        )
        return run

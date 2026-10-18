"""Full comparison-path smoke stays credential-free and labels model fixtures as replay."""

import json
from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.controller.capability_evaluation import evaluate_case
from open_commerce.controller.capability_fixtures import Arm, prepare_case
from open_commerce.controller.ollama import InferenceResult, OllamaBackend
from open_commerce.persistence.runtime_db import RuntimeDatabase

from .test_capability_fixtures import CASES
from .test_model_planning import fixture_result, model_settings

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "case_id", ["acquisition_gap", "campaign_decline", "unsuccessful_prior_intervention"]
)
async def test_three_arm_rollout_records_observations_and_provenance(
    integration_settings: Settings, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    database = RuntimeDatabase(model_settings(integration_settings))
    case = next(c for c in CASES if c.id == case_id)

    async def complete(
        self: OllamaBackend, *, messages: list[dict[str, str]], schema: dict[str, object]
    ) -> InferenceResult:
        reference = json.loads(messages[1]["content"])["evidence_ref"]
        return fixture_result(
            json.dumps(
                {
                    "decision": {
                        "kind": "no_action",
                        "summary": "No new intervention proposed in this fixture.",
                        "evidence_refs": [reference],
                    }
                }
            )
        )

    monkeypatch.setattr(OllamaBackend, "complete", complete)
    arms: list[Arm] = ["no_intervention", "deterministic", "model_backed"]
    try:
        results = []
        for arm in arms:
            tenant = uuid4()
            setup = await prepare_case(database, tenant, case, 11, arm)
            result = await evaluate_case(database, tenant, case, arm, setup)
            assert result["observed_days"] == 10
            assert not result["hard_policy_violations"]
            assert not result["errors"]
            assert result["planning_failures"] == 0
            if arm == "no_intervention":
                assert result["executed"] == 0 and result["proposed"] == 0
            if arm == "model_backed":
                assert isinstance(result["inference_usage"], dict)
                assert result["inference_usage"]["sources"] == ["replay"]
            results.append(result)
        assert results[0]["objective_value"] == results[2]["objective_value"]
        assert results[0]["economics"] == results[2]["economics"]
    finally:
        await database.close()

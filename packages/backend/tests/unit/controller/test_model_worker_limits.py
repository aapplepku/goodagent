"""Model investigations fit their delivery deadline without changing no-key defaults."""

from uuid import uuid4

import pytest

from open_commerce.config import Settings
from open_commerce.persistence.runtime_db import RuntimeDatabase
from open_commerce.worker.jobs import JobRunner


@pytest.mark.parametrize("iterations,timeout", [(1, 1), (4, 60), (6, 90)])
def test_model_worker_deadline_and_lease_cover_bounded_cycle(iterations: int, timeout: int) -> None:
    settings = Settings(
        model_enabled=True, model_max_iterations=iterations, model_timeout_seconds=timeout
    )
    database = RuntimeDatabase(settings)
    runner = JobRunner(database, uuid4())
    assert settings.worker_job_timeout_seconds >= iterations * timeout + 30
    assert runner.lease_seconds >= settings.worker_job_timeout_seconds + 30


def test_offline_worker_defaults_and_explicit_recovery_test_lease_remain_unchanged() -> None:
    settings = Settings(model_enabled=False)
    database = RuntimeDatabase(settings)
    assert settings.worker_job_timeout_seconds >= settings.manager_run_active_seconds + 30
    assert JobRunner(database, uuid4()).lease_seconds == settings.worker_job_timeout_seconds + 30
    assert JobRunner(database, uuid4(), lease_seconds=1).lease_seconds == 1

"""Wait for bootstrap dependencies and apply migrations."""

import asyncio
import subprocess
import sys

from open_commerce.api.readiness import aggregate_status, run_readiness_checks
from open_commerce.config import get_settings


async def wait_for_dependencies(attempts: int = 60, delay_seconds: float = 2.0) -> None:
    """Wait until all configured dependencies report ready."""

    settings = get_settings()
    for attempt in range(1, attempts + 1):
        dependencies = await run_readiness_checks(settings)
        if aggregate_status(dependencies) == "ready":
            print("Dependencies are ready.")
            return
        summary = ", ".join(
            f"{dependency.name}={'ok' if dependency.ok else dependency.detail}"
            for dependency in dependencies
        )
        print(f"Waiting for dependencies ({attempt}/{attempts}): {summary}")
        await asyncio.sleep(delay_seconds)
    raise TimeoutError("Timed out waiting for dependencies.")


def run_migrations() -> None:
    """Apply Alembic migrations."""

    subprocess.run(["alembic", "upgrade", "head"], check=True)


def main() -> None:
    """CLI entrypoint."""

    try:
        asyncio.run(wait_for_dependencies())
        run_migrations()
    except Exception as exc:
        print(f"Dependency wait failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

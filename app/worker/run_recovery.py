"""Run Recovery: scans for non-terminal runs on Worker startup and re-queues
them for execution.

Recovery rules (plan.md §10.2):
  - Process crash: resume from latest Checkpoint.
  - Service restart: scan non-terminal runs, resume or mark retryable.
  - Interaction wait: run stays waiting_interaction, does NOT occupy worker.
  - Approval wait: approval expired → fail or cancel branch.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.persistence.engine import get_session_factory
from app.persistence.repositories import RunRepository

logger = logging.getLogger(__name__)

# Runs that are eligible for recovery on startup
_RECOVERABLE_STATUSES = ("queued", "running", "rendering")


async def scan_and_recover() -> list[dict[str, Any]]:
    """Scan for non-terminal runs and enqueue them for processing.

    Returns a list of recovered run IDs for observability.
    """
    from sqlalchemy import select

    from app.persistence.models import Run

    factory = get_session_factory()
    recovered: list[dict[str, Any]] = []

    async with factory() as session:
        repo = RunRepository(session)
        result = await session.execute(
            select(Run).where(Run.status.in_(_RECOVERABLE_STATUSES))
        )
        runs = result.scalars().all()

        for run in runs:
            run_id = run.id
            status = run.status

            # If run was running when process crashed, reset to queued for re-execution
            if status == "running":
                # Check if the run has been stuck for too long (crash vs normal)
                if run.started_at:
                    elapsed = (datetime.now(UTC) - run.started_at).total_seconds()
                    if elapsed > 3600:  # > 1 hour stuck → mark as failed
                        await repo.mark_finished(run_id, "failed", "run_stuck_worker_crash")
                        logger.warning(
                            "Run marked as failed (stuck > 1h)",
                            extra={"run_id": run_id},
                        )
                        continue

                # Reset to queued for recovery
                await repo.update_status(run_id, "queued")
                logger.info(
                    "Run reset to queued for recovery",
                    extra={"run_id": run_id, "previous_status": status},
                )

            # Enqueue for worker processing
            recovered.append({
                "run_id": run_id,
                "conversation_id": run.conversation_id,
                "previous_status": status,
                "action": "recovered" if status == "running" else "retained",
            })

        await session.commit()

    logger.info(
        "Run recovery scan complete",
        extra={"recovered_count": len(recovered)},
    )
    return recovered

"""Orchestrator Agent — Tasks.

No request tasks: the orchestrator executes its DAG (steps) directly.

Scheduled: on Cloud Run (CONTAINER_RUNTIME=cloudrun) a sweep deletes
ephemeral services left behind. An ephemeral that finishes only exits its
process (self_deregister → os._exit); its Cloud Run service stays, scaled
to zero, until this sweep removes it. Not registered with the Docker
backend, so local deployments need no apscheduler.
See .abi/specs/not-implemented/gcp-build-deploy-pipeline.md.
"""

import os

from app import agent

if os.getenv("CONTAINER_RUNTIME", "docker").strip().lower() == "cloudrun":

    @agent.task_schedule(
        "sweep_ephemeral_services",
        trigger="interval",
        trigger_args={"minutes": int(os.getenv("EPHEMERAL_SWEEP_INTERVAL_MINUTES", "15"))},
    )
    async def sweep_ephemeral_services():
        from abi_core.common.cloudrun_runtime import sweep_ephemerals

        # Never touch an ephemeral that may still be working: anything
        # younger than the longest allowed execution is left alone.
        max_age = int(float(os.getenv("EXECUTION_TIMEOUT", "3600"))) + int(
            os.getenv("EPHEMERAL_SWEEP_MARGIN_SECONDS", "600")
        )
        deleted = await sweep_ephemerals(max_age)
        return {"deleted": deleted}

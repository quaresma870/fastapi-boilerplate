"""
arq worker entry point. Run with:

    python -m arq app.worker.WorkerSettings

Requires REDIS_ENABLED=True / a reachable REDIS_URL — there's no fallback
path here, unlike core/tasks.enqueue_email's degrade-to-BackgroundTasks
behavior, because running this command at all means you've explicitly
chosen to run a worker process, not just import the app.
"""

from app.core.tasks import _build_worker_settings

WorkerSettings = _build_worker_settings()

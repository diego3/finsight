"""Gunicorn configuration.

Dev still uses `manage.py runserver` (hot reload). This runs in the production
compose override:

    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build

Sync/gthread workers load `config.wsgi:application`. For an async benchmark,
set GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker and point the command
at `config.asgi:application` — no code change needed.
"""
import os
import pathlib

_multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")

bind = "0.0.0.0:8000"
# Default to a single worker unless we're set up for multiprocess metrics, so a
# bare `docker run` of the image still gives consistent /metrics.
workers = int(os.getenv("GUNICORN_WORKERS", "4" if _multiproc_dir else "1"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
threads = int(os.getenv("GUNICORN_THREADS", "1"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"
# Must stay off: each worker registers its own runtime-metrics sampler and
# django-prometheus multiprocess files *after* the fork.
preload_app = False


def on_starting(server):
    """Wipe stale multiprocess metric files before the workers start."""
    if not _multiproc_dir:
        return
    d = pathlib.Path(_multiproc_dir)
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.db"):
        f.unlink()


def child_exit(server, worker):
    """Drop a dead worker's series from the aggregated /metrics output."""
    if not _multiproc_dir:
        return
    from prometheus_client import multiprocess

    multiprocess.mark_process_dead(worker.pid)

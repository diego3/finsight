# benchmarks/

Load-test runs comparing configurations of the API, with the raw artifacts
kept so numbers can be checked and re-run. The `benchmark` skill
(`.claude/skills/benchmark/`) is the procedure for conducting one and writing it
up.

## Pieces

| path | role |
|---|---|
| `docker-compose.bench.yml` | api + db override, fully env-driven (`API_CPUS`, `DB_CPUS`, `GUNICORN_WORKERS`, `GUNICORN_WORKER_CLASS`, `GUNICORN_APP`) |
| `run.sh <label> [scenario]` | runs k6, writes `results/<label>/{k6.txt,summary.json,metrics.json,window.json}` |
| `snapshot.py` | Prometheus → `metrics.json` (api + db containers, Django, Postgres, k6), scoped to the live container ids |

## Running one

The target stack must be up **with the observability profile** (the snapshot
reads cAdvisor / Django / Postgres / k6 metrics back out of Prometheus):

```bash
export API_CPUS=4 DB_CPUS=2 GUNICORN_WORKERS=9 GUNICORN_MAX_REQUESTS=0 \
       GUNICORN_WORKER_CLASS=sync GUNICORN_APP=config.wsgi:application
docker compose -f docker-compose.yml -f benchmarks/docker-compose.bench.yml \
  --profile observability up -d --force-recreate api db
docker compose --profile observability restart cadvisor      # drop old container series
# warm up, then:
benchmarks/run.sh sync stress
```

k6 exits `99` when a threshold is crossed — expected for `stress.js`.

## Reports

| report | comparison |
|---|---|
| [`2026-08-29-runserver-vs-gunicorn.md`](2026-08-29-runserver-vs-gunicorn.md) · [html](2026-08-29-runserver-vs-gunicorn.html) | `runserver` vs `gunicorn` (4 workers), 1 CPU / 512 MiB |
| [`2026-08-29-sync-vs-async.html`](2026-08-29-sync-vs-async.html) | WSGI/sync vs ASGI/uvicorn workers, api 4 CPU / db 2 CPU, 9 workers |

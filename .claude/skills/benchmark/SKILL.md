---
name: benchmark
description: Run a controlled load benchmark comparing API server configurations (sync vs async, worker count, CPU limit, pool size) with k6 + Prometheus, and write it up as an HTML report. Use when asked to benchmark, load-test a comparison, measure throughput/latency under load, or "see if X is faster than Y".
---

# Benchmark

Compare two or more configurations of the FinSight API under identical load and
produce a report. The tooling already exists in `benchmarks/`; this skill is the
procedure for using it and writing the result up.

## Pieces

| path | role |
|---|---|
| `benchmarks/docker-compose.bench.yml` | api override, fully env-driven (`API_CPUS`, `API_MEM`, `GUNICORN_WORKERS`, `GUNICORN_WORKER_CLASS`, `GUNICORN_APP`) |
| `benchmarks/run.sh <label> [scenario]` | runs k6, writes `results/<label>/{k6.txt,summary.json,metrics.json,window.json}` |
| `benchmarks/snapshot.py` | Prometheus → `metrics.json` (api + db containers, Django, Postgres, k6) |
| `load/scenarios/*.js` | k6 scenarios — `stress` (ramp to 400 rps), `clients-crud`, `smoke` |
| `.claude/skills/benchmark/assets/report-template.html` | the report skeleton |
| `.claude/skills/benchmark/references/methodology.md` | fair-comparison rules + how to read every metric — **read this first** |

## Procedure

1. **Read `references/methodology.md`.** It has the fair-comparison rules and the
   meaning of every metric. Then state the comparison in one line: what is the
   single variable, what is held fixed.

2. **Define each config** as a set of env vars for the bench override. Common ones:

   | comparison | config A | config B |
   |---|---|---|
   | sync vs async | `GUNICORN_WORKER_CLASS=sync GUNICORN_APP=config.wsgi:application` | `GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker GUNICORN_APP=config.asgi:application` |
   | CPU scaling | `API_CPUS=2` | `API_CPUS=4` |
   | worker count | `GUNICORN_WORKERS=4` | `GUNICORN_WORKERS=12` |

   Keep every *other* var identical across configs.

3. **For each config, in turn:**
   ```bash
   export API_CPUS=4 API_MEM=1G DB_CPUS=2 DB_MEM=1G \
          GUNICORN_WORKERS=9 GUNICORN_MAX_REQUESTS=0 \
          GUNICORN_WORKER_CLASS=<...> GUNICORN_APP=<...>
   docker compose -f docker-compose.yml -f benchmarks/docker-compose.bench.yml \
     --profile observability up -d --force-recreate api db
   until curl -sf localhost:8000/api/health/ >/dev/null; do sleep 2; done
   docker compose --profile observability restart cadvisor    # drop the old containers' series
   sleep 8
   docker compose exec -T api python manage.py shell -c \
     "from clients.models import Client; Client.objects.exclude(email__endswith='@example.com').delete()"
   docker compose exec -T api python manage.py seed
   for i in $(seq 1 20); do curl -s -o /dev/null localhost:8000/api/clients/; done && sleep 6
   # confirm: worker count, api/db CPU limits
   bash benchmarks/run.sh <label> stress          # ~5 min; run in the background
   ```
   - `run.sh` exits 99 when k6 thresholds are crossed — expected for `stress.js`.
     Check `window.json` for `k6_exit`.
   - `run.sh` records the live container ids in `window.json` and scopes the
     Prometheus queries to them, so a just-recreated container isn't confused
     with the previous one still inside Prometheus's 5-min lookback.
   - The DB is easy to make the bottleneck (`CONN_MAX_AGE=0` ⇒ a connect+auth per
     request). If `metrics.json` `db.cpu_max_cores` ≈ `db.cpu_limit_cores`, the
     DB is capping the result — raise `DB_CPUS` and note it.

4. **Collect** — each `benchmarks/results/<label>/` has `summary.json` (k6) and
   `metrics.json` (Prometheus). Pull the numbers you need from both. For k6
   percentiles that aren't in `summary.json`, read the summary block in `k6.txt`.

5. **Write the report** from `assets/report-template.html`. Copy it to
   `benchmarks/<YYYY-MM-DD>-<slug>.html`, fill in the data, keep the design
   system. Before writing, load the `artifact-design` and `dataviz` skills and
   run the palette validator. Then publish it as an Artifact and add a row to
   `benchmarks/README.md`.

6. **Restore dev mode:** `docker compose up -d --force-recreate api` (back to
   `runserver`), and confirm `/proc/1/cmdline` shows `runserver`.

## Notes

- The comparison colours are a validated warm/cool categorical pair — see the
  template. Re-validate if you change them (`dataviz` skill's
  `scripts/validate_palette.js`).
- Do not commit anything outside `benchmarks/` and this skill unless asked —
  other work may be in flight on the branch.
- `stress.js` targets 400 rps; if a config gets close, raise the scenario's
  target or it stops being a stress test.

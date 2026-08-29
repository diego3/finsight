# benchmarks/

Load-test runs comparing configurations of the API, with the raw artifacts
kept so numbers can be checked and re-run.

## Running one

The target stack must already be up **with the observability profile** (the
script reads cAdvisor / django / k6 metrics back out of Prometheus):

```bash
# dev target (runserver)
docker compose --profile observability up -d
benchmarks/run.sh dev stress

# prod target (gunicorn)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile observability up -d
benchmarks/run.sh prod stress
```

`run.sh <label> [scenario]` runs `load/scenarios/<scenario>.js`, writes
`benchmarks/results/<label>/`:

| file | what |
|---|---|
| `k6.txt` | k6 console output (trimmed to setup + error breakdown + summary) |
| `summary.json` | k6 `--summary-export` (machine-readable) |
| `prometheus.txt` | api container CPU / throttle / memory + Django p95 / rps over the run window |
| `window.json` | run start/end epoch + k6 exit code |

k6 exits `99` when a threshold is crossed — expected for `stress.js`, whose
whole point is to blow past them.

## Reports

- [`2026-08-29-runserver-vs-gunicorn.md`](2026-08-29-runserver-vs-gunicorn.md)
  — `stress.js` against `runserver` vs `gunicorn` (4 sync workers), same 1 CPU /
  512 MiB container limit.

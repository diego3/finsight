# stress.js — runserver vs gunicorn

**Date:** 2026-08-29
**Scenario:** `load/scenarios/stress.js` — `ramping-arrival-rate`, 10 → 400 req/s
over 4m30s, `maxVUs: 500`, read-only `GET /api/clients/`.
**Artifacts:** [`results/dev/`](results/dev/), [`results/prod/`](results/prod/)

## Setup

One variable changed: the WSGI server. Everything else identical, same machine,
runs ~7 min apart.

| | DEV | PROD |
|---|---|---|
| server | `manage.py runserver` (1 process, threaded) | `gunicorn` (4 sync workers) |
| compose | `docker compose up` | `-f docker-compose.yml -f docker-compose.prod.yml` |
| `DJANGO_DEBUG` | 1 | 0 |
| static | Django dev handler | whitenoise |
| api container limit | `cpus: "1.0"`, `memory: 512M` | same |
| db | postgres:16, same limits, 4 seed rows | same |

## Results

| metric | DEV (runserver) | PROD (gunicorn ×4) | |
|---|--:|--:|---|
| requests completed | 6,669 | 16,905 | **2.5×** |
| throughput | 22.5 req/s | 61.5 req/s | **2.7×** |
| failed requests | **42.1 %** | **0.0 %** | |
| checks passed | 57.9 % | 100 % | |
| dropped iterations | 32,631 | 22,394 | |
| k6 request errors | 1073 timeout · 337 dial timeout · 51 reset | **0** | |
| `http_req_duration` p50 | 25 ms | 6.68 s | |
| `http_req_duration` p95 | **60.0 s** (hit timeout) | 7.49 s | |
| `http_req_duration` max | 60.0 s | 8.68 s | |
| successful requests p95 | 2.10 s | 7.49 s | |
| `http_req_connecting` p95 | **5.11 s** | **0.45 ms** | ~11,000× |
| `http_req_connecting` max | 19.74 s | 8.05 ms | |
| `http_req_waiting` (TTFB) p95 | 60.0 s | 7.49 s | |
| **server-side** Django p95 (peak) | **75 s** | **97 ms** | ~770× |
| Django req/s (peak) | 52.6 | 82.4 | |
| api CPU avg / max (cores) | 0.75 / 1.00 | 0.72 / 1.00 | |
| api CPU throttling avg / max | 61 % / 100 % | 57 % / 100 % | |
| api memory (peak) | **512.0 MiB** (= the limit) | 220 MiB | **2.3× less** |

## Reading it

**1. runserver collapsed; gunicorn degraded.**
runserver settled at ~22 req/s with 42 % of requests failing (timeouts, dial
timeouts, connection resets). gunicorn sustained ~62 req/s with **zero**
failures — every request was answered, just slowly. `stress.js` uses an open
model (`ramping-arrival-rate`), so a slow server doesn't get a lighter load: it
gets a growing queue. runserver dropped that queue on the floor; gunicorn held
it.

**2. The connection stall is gone.**
`http_req_connecting` p95 went 5.11 s → 0.45 ms (max 19.7 s → 8 ms). That was
the symptom from the earlier `http_req_connecting` question: runserver has one
`accept()` loop and a small listen backlog, so new TCP connections waited
through the kernel's SYN-retransmit backoff (~1 s, 3 s, 7 s, 19 s — the exact
outliers seen). gunicorn's 4 workers accept in parallel behind a larger
backlog, so connection setup stays sub-millisecond even while the app is
saturated.

**3. Server-side latency: 75 s → 97 ms.**
The most telling pair. Under runserver, Django's *own* latency histogram maxed
out at 75 s — requests were queuing **inside the Python process** (GIL + single
accept loop). Under gunicorn each request is actually served in ~100 ms; the
multi-second `http_req_duration` is almost entirely time spent in the OS accept
queue waiting for one of the 4 workers to free up (`http_req_waiting` ≈
`http_req_duration`, and `http_req_connecting` is negligible). So gunicorn's
latency is honest back-pressure, not the app choking.

**4. Memory: runserver sat on the 512 MiB cap.**
`manage.py runserver` is threaded — roughly a thread per in-flight connection.
At 500 VUs that is ~500 thread stacks plus buffers, and the working set pinned
the container's memory limit (99.99 % of it — one bad moment from an OOM kill).
gunicorn's 4 sync workers have a bounded footprint no matter how many
connections are queued: 220 MiB, flat.

**5. Both are CPU-bound at the 1-core cap.**
CPU averaged ~0.75 cores with ~60 % CFS throttling in both runs — the `cpus:
"1.0"` limit is the ceiling, and neither server changes that. gunicorn's wins
here are the concurrency model, failure behaviour, connection handling and
memory — not raw compute.

**6. Neither reached 400 req/s.**
20k–33k dropped iterations in both. `GET /api/clients/` is CPU-bound
(serialization, pagination), and the container has one core. To actually serve
400 req/s the CPU limit has to go up; adding workers alone won't help on a
single core.

## Follow-ups

- Re-run at `cpus: "2"` / `"4"` to find where gunicorn scales.
- Run the async variant (ASGI + `uvicorn.workers.UvicornWorker`, see the header
  of `docker-compose.prod.yml`) and compare. Hypothesis: little throughput gain
  — this endpoint is CPU-bound, not I/O-bound. Worth measuring rather than
  assuming.
- Add `CONN_MAX_AGE` / pgbouncer and re-measure; check `pg_stat_database_numbackends`
  during the run.
- Try `worker_class=gthread` with `GUNICORN_THREADS` and a tuned `--backlog`.

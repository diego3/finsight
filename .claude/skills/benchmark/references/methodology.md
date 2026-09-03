# Benchmark methodology

## Fair comparison — the rules

1. **One variable per comparison.** Change the WSGI/ASGI server, or the worker
   count, or the CPU limit — never two at once. If you must change two, run the
   intermediate config too so each step is isolated.
2. **Same container limits** unless the limit *is* the variable. Set them
   explicitly (`API_CPUS`, `API_MEM` in `benchmarks/docker-compose.bench.yml`) —
   don't inherit whatever the base compose has.
3. **Same data.** Run `manage.py seed` before each run so the queried table has
   the same rows.
4. **Same scenario, same machine, back to back.** Note the wall-clock gap
   between runs in the report.
5. **Warm up** — fire ~15–20 requests and wait ~5 s before starting k6, so
   collectstatic/migrate/JIT/connection-pool effects aren't in the window.
6. **Disable worker recycling** for the run (`GUNICORN_MAX_REQUESTS=0`) — a
   worker restarting mid-test is noise.
7. **Record the config**, not just the result: server, worker class, worker
   count, CPU/mem limit, `DEBUG`, k6 scenario parameters.

## What each metric means

### k6 (client side) — from `summary.json` / `k6.txt`

| metric | reading |
|---|---|
| `http_reqs` (count, rate) | total work done and achieved throughput |
| `http_req_failed` | error rate. Non-2xx/3xx + transport errors |
| `dropped_iterations` | k6 could **not** issue requests at the target rate — the server is behind. High = saturated |
| `http_req_duration` | total client-observed time = `blocked` + `connecting` + `sending` + `waiting` + `receiving` (TLS too if https). p95/p99/max, not avg |
| `http_req_blocked` | waiting for a free connection slot / DNS before the request goes out |
| `http_req_connecting` | TCP handshake time. **Spikes to seconds ⇒ the server can't `accept()` fast enough** — backlog full, SYN-retransmit backoff (~1s, 3s, 7s, 15s) |
| `http_req_waiting` | TTFB. Under a saturated multi-worker server this is mostly *accept-queue wait for a free worker*, not app processing |
| `{ expected_response:true }` sub-metric | latency of the requests that actually succeeded — compare to the overall p95 to see how much the server dropped vs queued |
| `vus` / `vus_max` | with `ramping-arrival-rate`, VUs rise to hold the target rate; hitting `maxVUs` means the open model is starved |

### Django (server side) — `django_*` from `/metrics`, scraped as job `django`

| metric | reading |
|---|---|
| `histogram_quantile(0.95, sum by (le) (rate(django_http_requests_latency_seconds_by_view_method_bucket{view="..."}[1m])))` | **server-side** p95 for one endpoint. If this is tiny while `http_req_duration` p95 is huge, the latency is queueing *outside* Django (OS accept queue), not processing |
| `sum(rate(django_http_requests_total_by_method_total[1m]))` | requests/s Django actually handled |
| `count(process_resident_memory_bytes{job="django"})` | live worker count (multiprocess metrics) |

### Container — cAdvisor, `cname="finsight-api"` / `cname="postgres"`

| metric | reading |
|---|---|
| `rate(container_cpu_usage_seconds_total[1m])` | CPU in **cores**. Compare to `container_spec_cpu_quota / container_spec_cpu_period` (the limit) |
| `rate(container_cpu_cfs_throttled_periods_total[1m]) / rate(container_cpu_cfs_periods_total[1m])` | fraction of scheduler periods throttled. **> 0 ⇒ CPU-bound at the limit** |
| `container_memory_working_set_bytes` | real resident memory. Approaching `container_spec_memory_limit_bytes` ⇒ near OOM |

### Postgres — postgres-exporter, `datname="finsight"`

| metric | reading |
|---|---|
| `rate(pg_stat_database_tup_returned[1m])` / `_tup_fetched` | rows scanned / rows read per second |
| `rate(pg_stat_database_tup_inserted + _updated + _deleted)` | write rate (≈0 for a read-only test) |
| `rate(pg_stat_database_xact_commit[1m])` | transactions/s |
| `pg_stat_database_numbackends` | open server connections. With `CONN_MAX_AGE=0` Django opens one per request → this tracks concurrency; watch it against `pg_settings_max_connections` |
| `blks_hit / (blks_hit + blks_read)` | buffer cache hit ratio. Should stay ~1.0 for a small hot dataset; a dip means the working set spilled |
| `increase(pg_stat_database_deadlocks[window])` | lock contention (should be 0) |

## Reading a saturated result

`stress.js` is an **open model** (`ramping-arrival-rate`): a slow server does not
get a lighter load, it gets a growing queue. So under saturation:

- **dropped or failed** ⇒ the server shed load (small backlog, timeouts).
- **queued** ⇒ `http_req_duration` climbs but `http_req_failed` stays ~0 and
  server-side p95 stays low. The multi-second latency is accept-queue wait.
- Cross-check the timestamps: CPU throttling %, k6 error rate, and Django p95
  should all move together.

## Is more of X the answer?

- **CPU-bound** (throttling > ~20%, CPU pinned at the limit): raise the CPU limit.
  More workers alone won't help on a fixed core budget.
- **Concurrency-bound** (CPU has headroom, latency still high): more workers, or
  async workers if the work is I/O-bound.
- **I/O-bound** (workers idle-waiting on DB / external calls): async (ASGI +
  uvicorn workers) or a bigger DB connection pool.
- A **sync Django view under ASGI** still runs in a thread executor
  (`sync_to_async`), so async rarely helps a CPU-bound serializer endpoint and
  can add overhead — measure, don't assume.

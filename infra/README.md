# infra/

Local infrastructure that sits *around* the application — currently the
observability stack. Kept separate from the app so `docker compose up` stays
lean and this can grow (Loki, Tempo, alerting, etc.) without cluttering the
root compose file.

## What's here

| Component | Purpose | Port (host) |
|---|---|---|
| **Prometheus** | Time-series DB, scrapes metrics every 15s | http://localhost:9090 |
| **Grafana** | Dashboards over Prometheus | http://localhost:3000 |
| **cAdvisor** | Per-container CPU / memory / network, read from kernel cgroups | http://localhost:8081 |
| **node-exporter** | Host machine metrics (CPU, RAM, disk, net) | http://localhost:9100 |
| **postgres-exporter** | PostgreSQL internals: tuples r/w, txns, cache hit, connections, deadlocks | http://localhost:9187 |

Dashboards provisioned into Grafana:

- **FinSight — Containers & App** (`containers.json`) — per-container CPU vs
  limit, **CPU throttling**, memory vs limit, Django request rate by status,
  and **per-endpoint API latency (p95 / p50) and request rate**.
- **FinSight — PostgreSQL** (`database.json`) — reads/s, writes/s, transactions,
  cache hit ratio, connections vs `max_connections`, deadlocks, plus the DB
  container's CPU and memory.
- **FinSight — API Runtime (Python)** (`api-runtime.json`) — Django worker RSS
  vs virtual memory, process CPU, GC collections / reclaimed objects / pending
  allocations per generation, CPython allocator blocks, open FDs, and (opt-in)
  tracemalloc.

The Django API exposes its own metrics at `/metrics` via `django-prometheus`
(request counts, latency histograms, DB query stats). `prometheus_client` adds
`process_*` and `python_gc_*`; the local `observability` app adds
`python_allocated_blocks`, `python_gc_tracked_objects`, `python_gc_pending_objects`
and `python_tracemalloc_bytes`.

CPython has no fixed heap or stack size to report the way a JVM does — process
RSS is the real memory footprint, and the allocator/GC series are the
Python-level internals. Set `PYTHONTRACEMALLOC=1` on the `api` service to also
get `python_tracemalloc_bytes` (it roughly doubles memory use, so it's off by
default).

```
prometheus.yml ── scrapes ──▶ cadvisor, node-exporter, api:8000/metrics
       ▲
       │ datasource (provisioned)
       │
   grafana ── loads ──▶ grafana/dashboards/*.json (provisioned)
```

## Running

The root `docker-compose.yml` pulls this file in via `include:`. Everything is
behind the `observability` profile:

```bash
# app only
docker compose up

# app + full observability stack
docker compose --profile observability up --build
```

Grafana: anonymous access is enabled with Admin role (local only), or log in
with `admin` / `admin`. The **FinSight — Containers & App** dashboard is
provisioned automatically.

## Layout

```
infra/
├── docker-compose.observability.yml
├── prometheus/
│   └── prometheus.yml            scrape targets
└── grafana/
    ├── provisioning/
    │   ├── datasources/          auto-wires the Prometheus datasource
    │   └── dashboards/           tells Grafana to load ../dashboards
    └── dashboards/
        └── containers.json       CPU, memory-vs-limit, request rate, latency
```

## Using it with the resource-limit tests

The `deploy.resources.limits` in the root compose are visible here:

- **Memory panel** plots `container_memory_working_set_bytes` against
  `container_spec_memory_limit_bytes` — watch a container approach its ceiling
  and get OOM-killed (series drops, container restarts).
- **CPU panel** plots `rate(container_cpu_usage_seconds_total[1m])` in cores —
  lower a service to `cpus: "0.25"`, apply load, and see it flat-line at 0.25
  while the Django latency panel climbs.

## cAdvisor on snap Docker

snap Docker (v29) uses the **containerd image store**, so cAdvisor's Docker
handler can't resolve container layers and drops every container. Instead,
cAdvisor here talks to **Docker's containerd** directly:

- no Docker socket mount; mounts `/run/snap.docker/containerd/containerd.sock`
- `--containerd=... --containerd-namespace=moby`

The containerd handler labels series with `name="<64-hex id>"` and `image=...`
but no compose metadata. So `prometheus.yml` adds a `metric_relabel_configs`
that derives a readable **`cname`** label from `image`
(`finsight-api`, `finsight-web`, `postgres`, `grafana`, …). **Dashboard queries
match on `cname`, not `name`.**

## Troubleshooting empty container panels

The CPU/memory panels use cAdvisor metrics (`container_cpu_usage_seconds_total`,
`container_memory_working_set_bytes`) with the `cname` label. If they're blank:

```bash
# 1. Is cAdvisor running, or crash-looping?
docker compose --profile observability ps cadvisor
docker compose --profile observability logs --tail=50 cadvisor

# 2. Is Prometheus scraping it? Open http://localhost:9090/targets
#    and check the "cadvisor" and "postgres" jobs are UP.

# 3. Does cAdvisor emit data at all?
curl -s localhost:8081/metrics | grep -c '^container_cpu_usage_seconds_total'

# 4. What cname labels does Prometheus derive? (panels match these)
curl -s 'localhost:9090/api/v1/query?query=container_cpu_usage_seconds_total' \
  | grep -o '"cname":"[^"]*"' | sort -u
```

- If step 3 is `0` or step 1 shows restarts: cAdvisor can't reach the containerd
  socket — check `/run/snap.docker/containerd/containerd.sock` exists on the host
  and is mounted into the container.
- If `container_*` series exist but have no `cname`: the `metric_relabel_configs`
  in `prometheus.yml` isn't matching the `image` label — check the image
  references (`curl -s localhost:8081/metrics | grep -o 'image="[^"]*"' | sort -u`).

## Notes / caveats

- Docker here is installed as a **snap**, so cAdvisor's usual
  `/var/lib/docker` mount is omitted (snap stores data elsewhere). cgroup-based
  CPU/memory/network metrics still work; per-image filesystem stats won't.
- `/metrics` on the API is unauthenticated — fine locally, must be locked down
  (auth or network policy) before any deployment.
- Prometheus retention is 7 days (`--storage.tsdb.retention.time=7d`); data
  lives in the `prometheus_data` volume.

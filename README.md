# FinSight

FinSight is a simplified financial portfolio intelligence platform, built as an
incremental, didactic full-stack learning project (Python/Django, React, PostgreSQL,
async processing, cloud infrastructure, observability, and production engineering).

The project is developed feature-by-feature in a mentor-guided, phase-by-phase way — see
[`docs/PLAN.md`](docs/PLAN.md) for the full roadmap (goals, teaching approach, domain
model, tech stack, and all planned phases from project setup through production
verification and architecture review).

For the product lens — what a financial advisor actually does, the two flagship workflows,
and the MVP feature sequence — see
[`docs/product/advisor-workflows.md`](docs/product/advisor-workflows.md). Domain vocabulary
lives in [`CONTEXT.md`](CONTEXT.md).

Status: prototype in progress — first vertical slice (Client Management) being built.

## Repository layout

```
api/        Django + DRF + PostgreSQL backend
frontend/   React + TypeScript (Vite) single-page app
infra/      Observability stack (Prometheus, Grafana, cAdvisor, node-exporter)
load/       k6 load and stress tests
docker-compose.yml   db + api + web for local development
```

## Running the prototype

Requires Docker with Compose v2.

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- API (DRF browsable): http://localhost:8000/api/
- API health: http://localhost:8000/api/health/
- API metrics: http://localhost:8000/metrics

The default `api` service runs `manage.py runserver` (single process, hot
reload).

### Production-style API (gunicorn) — for benchmarking

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

Runs gunicorn with `GUNICORN_WORKERS` (default 4) sync workers, whitenoise for
static, and multi-process Prometheus metrics (`/metrics` aggregates request
counters across workers and adds a `pid` label to the per-worker runtime
series). Async variant (ASGI + uvicorn workers, no code change) is documented at
the top of `docker-compose.prod.yml`.

### With observability

```bash
docker compose --profile observability up --build
```

- Grafana: http://localhost:3000 (anonymous, or admin/admin)
- Prometheus: http://localhost:9090

See [`infra/README.md`](infra/README.md).

### Load testing

```bash
docker compose --profile load run --rm k6 run /load/scenarios/smoke.js
```

See [`load/README.md`](load/README.md).

Seed some sample clients:

```bash
docker compose exec api python manage.py seed
```

Run backend tests:

```bash
docker compose exec api pytest
```

## Quality gate

Every push runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml): `ruff`
(lint + format), `mypy` on the framework-free domain core, and the full `pytest`
suite against a real PostgreSQL service, with a coverage floor on new domain
code. Testing strategy and the reasoning behind it: [`docs/TESTING.md`](docs/TESTING.md).

```bash
pip install -r api/requirements-dev.txt          # ruff, mypy on top of the runtime deps
cd api && ruff check . && ruff format --check portfolio
mypy                                             # from the repo root
pytest                                           # needs a database; use the compose service
pytest portfolio/                                # pure-domain tests, no database
```

Environment variables live in `.env` at the repo root (copied from
`.env.example`; local-only dev values).


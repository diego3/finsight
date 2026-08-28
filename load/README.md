# load/

Load and stress tests with [k6](https://k6.io/). Scripts are plain JS; k6 runs
them from a container defined in `docker-compose.load.yml` (included by the root
compose, behind the `load` profile).

## Scenarios

| File | Shape | Use |
|---|---|---|
| `scenarios/smoke.js` | 1 VU, 30s | Sanity check — is the stack up and responding? |
| `scenarios/clients-crud.js` | 20 readers + 3 writers, ~2 min | Realistic mixed read/write load; writers self-clean |
| `scenarios/stress.js` | Rising arrival rate 10→400 rps | Find where the API breaks under a resource limit |

`lib/config.js` holds `BASE_URL` and shared thresholds; `lib/random.js` has
local UUID / name helpers (no remote module fetch).

## Running

Start the app first (`docker compose up -d`), then:

```bash
# smoke
docker compose --profile load run --rm k6 run /load/scenarios/smoke.js

# mixed CRUD load
docker compose --profile load run --rm k6 run /load/scenarios/clients-crud.js

# stress
docker compose --profile load run --rm k6 run /load/scenarios/stress.js
```

From the host instead of the container:

```bash
k6 run -e BASE_URL=http://localhost:8000 load/scenarios/smoke.js
```

## Sending results to Grafana

Start observability too, and add the Prometheus remote-write output. Prometheus
already runs with `--web.enable-remote-write-receiver`.

```bash
docker compose --profile observability up -d
docker compose --profile observability --profile load run --rm k6 \
  run -o experimental-prometheus-rw /load/scenarios/clients-crud.js
```

k6 metrics (`k6_http_req_duration`, `k6_http_reqs`, `k6_vus`, …) then land in
Prometheus. Import the official **k6 Prometheus** dashboard in Grafana
(dashboard ID `19665`) to view them next to the container CPU/memory panels.

## Pairing with the resource limits

The root compose caps each container (`deploy.resources.limits`). The intended
loop:

1. Lower `api` to e.g. `cpus: "0.5"` / `memory: 256M` in `docker-compose.yml`.
2. `docker compose --profile observability up -d --build`
3. Run `stress.js` with the Prometheus output.
4. In Grafana watch CPU flat-line at the cap while p95 latency climbs and
   `http_req_failed` starts rising — that's the knee. Note the rps at which it
   happens, raise the limit, repeat.

## Notes

- `clients-crud.js` writers create then `DELETE` each client, so repeated runs
  don't grow the DB. `stress.js` is read-only. If a run is interrupted
  mid-write, clean leftovers with:
  `docker compose exec api python manage.py shell -c "from clients.models import Client; Client.objects.filter(email__startswith='load-').delete()"`
- Thresholds are set for a laptop against localhost — adjust in each script.

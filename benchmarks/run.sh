#!/usr/bin/env bash
#
# Run one k6 scenario against whatever `api` service is currently up and capture
# k6's summary plus a Prometheus snapshot (api + db containers, Django, Postgres)
# over the run window.
#
#   benchmarks/run.sh <label> [scenario]
#
# label     : output dir under benchmarks/results/   (e.g. sync, async)
# scenario  : k6 script under load/scenarios/         (default: stress)
#
# Requires the target stack up WITH the observability profile.
# Writes benchmarks/results/<label>/{k6.txt,summary.json,metrics.json,window.json}
#
set -uo pipefail
cd "$(dirname "$0")/.."

LABEL=${1:?usage: run.sh <label> [scenario]}
SCENARIO=${2:-stress}
OUT="benchmarks/results/${LABEL}"
PROM="${PROM_URL:-http://localhost:9090}"
mkdir -p "$OUT"
chmod 777 "$OUT"

echo ">> ${LABEL}: k6 ${SCENARIO}.js"
START=$(date +%s)

# k6 exits 99 when a threshold is crossed (expected for stress.js). Run k6 as the
# host user so it can write into the mounted output dir.
docker compose --profile load run --rm -T \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/${OUT}:/out" \
  k6 run \
    --summary-export=/out/summary.json \
    -o experimental-prometheus-rw \
    "/load/scenarios/${SCENARIO}.js" | tee "${OUT}/k6.txt"
K6_RC=${PIPESTATUS[0]}
echo "k6 exit code: ${K6_RC}"

END=$(date +%s)
API_ID=$(docker inspect "$(docker compose ps -q api)" --format '{{.Id}}' 2>/dev/null || echo "")
DB_ID=$(docker inspect "$(docker compose ps -q db)" --format '{{.Id}}' 2>/dev/null || echo "")
printf '{"label":"%s","scenario":"%s","start":%s,"end":%s,"window_s":%s,"k6_exit":%s,"api_id":"%s","db_id":"%s"}\n' \
  "$LABEL" "$SCENARIO" "$START" "$END" "$(( END - START ))" "$K6_RC" "$API_ID" "$DB_ID" > "${OUT}/window.json"

python3 benchmarks/snapshot.py "$OUT" "$START" "$END" "$PROM" "$API_ID" "$DB_ID"

echo ">> wrote ${OUT}/{k6.txt,summary.json,metrics.json,window.json}"

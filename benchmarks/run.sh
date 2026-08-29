#!/usr/bin/env bash
#
# Run one k6 scenario against whatever `api` service is currently up and capture
# the result plus a Prometheus snapshot of the api container over the run window.
#
#   benchmarks/run.sh <label> [scenario]
#
# label     : output dir name under benchmarks/results/ (e.g. dev, prod)
# scenario  : k6 script name under load/scenarios/ (default: stress)
#
set -euo pipefail
cd "$(dirname "$0")/.."

LABEL=${1:?usage: run.sh <label> [scenario]}
SCENARIO=${2:-stress}
OUT="benchmarks/results/${LABEL}"
PROM="http://localhost:9090"
mkdir -p "$OUT"

echo ">> ${LABEL}: k6 ${SCENARIO}.js"
START=$(date +%s)

# k6 exits 99 when thresholds are crossed (expected for stress.js) — don't let
# that abort the snapshot. Run as the host user so it can write the summary.
chmod 777 "${OUT}"
set +e
docker compose --profile load run --rm -T \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/${OUT}:/out" \
  k6 run \
    --summary-export=/out/summary.json \
    -o experimental-prometheus-rw \
    "/load/scenarios/${SCENARIO}.js" | tee "${OUT}/k6.txt"
K6_RC=${PIPESTATUS[0]}
set -e
echo "k6 exit code: ${K6_RC}"

END=$(date +%s)
WINDOW=$(( END - START ))
printf '{"label":"%s","scenario":"%s","start":%s,"end":%s,"window_s":%s,"k6_exit":%s}\n' \
  "$LABEL" "$SCENARIO" "$START" "$END" "$WINDOW" "$K6_RC" > "${OUT}/window.json"

# --- Prometheus snapshot over the run window -------------------------------
q() { curl -sG "${PROM}/api/v1/query" --data-urlencode "query=$1" \
  | python3 -c 'import sys,json;r=json.load(sys.stdin)["data"]["result"];print(round(float(r[0]["value"][1]),4) if r else "n/a")'; }

RANGE="${WINDOW}s"
{
  echo "window            : ${WINDOW}s  (${START}..${END})"
  echo "api cpu  avg cores : $(q "avg_over_time(rate(container_cpu_usage_seconds_total{cname=\"finsight-api\"}[1m])[${RANGE}:15s])")"
  echo "api cpu  max cores : $(q "max_over_time(rate(container_cpu_usage_seconds_total{cname=\"finsight-api\"}[1m])[${RANGE}:15s])")"
  echo "api throttle avg % : $(q "100 * avg_over_time((rate(container_cpu_cfs_throttled_periods_total{cname=\"finsight-api\"}[1m]) / clamp_min(rate(container_cpu_cfs_periods_total{cname=\"finsight-api\"}[1m]),1))[${RANGE}:15s])")"
  echo "api throttle max % : $(q "100 * max_over_time((rate(container_cpu_cfs_throttled_periods_total{cname=\"finsight-api\"}[1m]) / clamp_min(rate(container_cpu_cfs_periods_total{cname=\"finsight-api\"}[1m]),1))[${RANGE}:15s])")"
  echo "api mem  max bytes : $(q "max_over_time(container_memory_working_set_bytes{cname=\"finsight-api\"}[${RANGE}])")"
  echo "django p95 max s   : $(q "max_over_time(histogram_quantile(0.95, sum by (le) (rate(django_http_requests_latency_seconds_by_view_method_bucket{view=\"client-list\"}[1m])))[${RANGE}:15s])")"
  echo "django rps max     : $(q "max_over_time(sum(rate(django_http_requests_total_by_method_total[1m]))[${RANGE}:15s])")"
} | tee "${OUT}/prometheus.txt"

echo ">> wrote ${OUT}/{k6.txt,summary.json,prometheus.txt,window.json}"

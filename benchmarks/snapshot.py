#!/usr/bin/env python3
"""Snapshot Prometheus over a benchmark run window into metrics.json.

    snapshot.py <out_dir> <start_epoch> <end_epoch> [prometheus_url]
"""
import json
import sys
import urllib.parse
import urllib.request

OUT, START, END = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
PROM = sys.argv[4] if len(sys.argv) > 4 else "http://localhost:9090"
API_ID = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
DB_ID = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None
R = f"{END - START}s"

# Prefer the exact container id (cAdvisor's `name` label) so a just-recreated
# container isn't confused with the previous one still in Prometheus lookback.
API = f'name="{API_ID}"' if API_ID else 'cname="finsight-api"'
DB = f'name="{DB_ID}"' if DB_ID else 'cname="postgres"'
PG = 'datname="finsight"'
LAT = 'django_http_requests_latency_seconds_by_view_method_bucket{view="client-list"}'
THR = (
    f'(rate(container_cpu_cfs_throttled_periods_total{{{API}}}[1m])'
    f'/clamp_min(rate(container_cpu_cfs_periods_total{{{API}}}[1m]),1))'
)


def q(expr):
    url = f"{PROM}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": END})
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            res = json.load(r)["data"]["result"]
        return round(float(res[0]["value"][1]), 6) if res else None
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {expr[:60]}... -> {exc}", file=sys.stderr)
        return None


def pctl(p):
    return q(f"max_over_time(histogram_quantile({p}, sum by (le)(rate({LAT}[1m])))[{R}:15s])")


metrics = {
    "window_s": END - START,
    "api": {
        "cpu_avg_cores": q(f"avg_over_time(sum(rate(container_cpu_usage_seconds_total{{{API}}}[1m]))[{R}:15s])"),
        "cpu_max_cores": q(f"max_over_time(sum(rate(container_cpu_usage_seconds_total{{{API}}}[1m]))[{R}:15s])"),
        "cpu_limit_cores": q(f"max(container_spec_cpu_quota{{{API}}}/container_spec_cpu_period{{{API}}})"),
        "throttle_avg_pct": q(f"100*avg_over_time(sum({THR})[{R}:15s])"),
        "throttle_max_pct": q(f"100*max_over_time(sum({THR})[{R}:15s])"),
        "mem_max_bytes": q(f"max_over_time(max(container_memory_working_set_bytes{{{API}}})[{R}:15s])"),
        "workers": q('count(process_resident_memory_bytes{job="django"})'),
    },
    "db": {
        "cpu_avg_cores": q(f"avg_over_time(sum(rate(container_cpu_usage_seconds_total{{{DB}}}[1m]))[{R}:15s])"),
        "cpu_max_cores": q(f"max_over_time(sum(rate(container_cpu_usage_seconds_total{{{DB}}}[1m]))[{R}:15s])"),
        "cpu_limit_cores": q(f"max(container_spec_cpu_quota{{{DB}}}/container_spec_cpu_period{{{DB}}})"),
        "mem_max_bytes": q(f"max_over_time(max(container_memory_working_set_bytes{{{DB}}})[{R}:15s])"),
    },
    "django": {
        "rps_max": q(f"max_over_time(sum(rate(django_http_requests_total_by_method_total[1m]))[{R}:15s])"),
        "p50_max_s": pctl(0.50),
        "p95_max_s": pctl(0.95),
        "p99_max_s": pctl(0.99),
    },
    "postgres": {
        "rows_returned_per_s_max": q(f"max_over_time(rate(pg_stat_database_tup_returned{{{PG}}}[1m])[{R}:15s])"),
        "rows_fetched_per_s_max": q(f"max_over_time(rate(pg_stat_database_tup_fetched{{{PG}}}[1m])[{R}:15s])"),
        "xact_commit_per_s_max": q(f"max_over_time(rate(pg_stat_database_xact_commit{{{PG}}}[1m])[{R}:15s])"),
        "rows_written_per_s_max": q(
            f"max_over_time((rate(pg_stat_database_tup_inserted{{{PG}}}[1m])"
            f"+rate(pg_stat_database_tup_updated{{{PG}}}[1m])"
            f"+rate(pg_stat_database_tup_deleted{{{PG}}}[1m]))[{R}:15s])"
        ),
        "connections_max": q(f"max_over_time(pg_stat_database_numbackends{{{PG}}}[{R}])"),
        "cache_hit_ratio_min": q(
            f"min_over_time((rate(pg_stat_database_blks_hit{{{PG}}}[5m])"
            f"/clamp_min(rate(pg_stat_database_blks_hit{{{PG}}}[5m])"
            f"+rate(pg_stat_database_blks_read{{{PG}}}[5m]),1))[{R}:30s])"
        ),
        "deadlocks_total": q(f"increase(pg_stat_database_deadlocks{{{PG}}}[{R}])"),
    },
    "k6": {
        "reqs_per_s_max": q(f"max_over_time(sum(rate(k6_http_reqs_total[30s]))[{R}:15s])"),
        "vus_max": q(f"max_over_time(k6_vus[{R}:15s])"),
    },
}

path = f"{OUT}/metrics.json"
json.dump(metrics, open(path, "w"), indent=2)
print(json.dumps(metrics, indent=2))
print(f"\n>> {path}", file=sys.stderr)

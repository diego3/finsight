// Stress test: push a rising request rate at the API until latency and errors
// break the thresholds. Pair it with a CPU/memory-limited api container
// (deploy.resources.limits in the root compose) and watch the knee in Grafana:
//
//   docker compose --profile observability up -d
//   docker compose --profile load run --rm k6 \
//     run -o experimental-prometheus-rw /load/scenarios/stress.js
//
// ramping-arrival-rate keeps the *request rate* on target and adds VUs as
// needed, so a slowing server does not reduce the offered load (open model).
import http from "k6/http";
import { check } from "k6";

import { BASE_URL } from "../lib/config.js";

export const options = {
  scenarios: {
    stress: {
      executor: "ramping-arrival-rate",
      startRate: 10,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { duration: "1m", target: 50 },
        { duration: "1m", target: 100 },
        { duration: "1m", target: 200 },
        { duration: "1m", target: 400 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1000"],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/api/clients/`);
  check(res, { "status 200": (r) => r.status === 200 });
}

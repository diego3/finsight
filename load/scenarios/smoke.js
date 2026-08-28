// Smoke test: 1 VU for 30s. Confirms the stack is wired and responding before
// running anything heavier. Fails fast if the API or DB is down.
import http from "k6/http";
import { check, sleep } from "k6";

import { BASE_URL } from "../lib/config.js";

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/api/health/`);
  check(health, { "health is 200": (r) => r.status === 200 });

  const list = http.get(`${BASE_URL}/api/clients/`);
  check(list, {
    "list is 200": (r) => r.status === 200,
    "list is paginated": (r) => r.json("results") !== undefined,
  });

  sleep(1);
}

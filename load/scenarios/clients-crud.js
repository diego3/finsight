// Realistic mixed load on the Clients API:
//   - "browse": many readers listing clients, ramps 0 -> 20 -> 0 VUs
//   - "write":  a few writers doing create -> retrieve -> delete
//
// The write path cleans up after itself so repeated runs don't bloat the DB.
import http from "k6/http";
import { check, sleep } from "k6";

import { BASE_URL, JSON_HEADERS } from "../lib/config.js";
import { uuidv4, randomName } from "../lib/random.js";

export const options = {
  scenarios: {
    browse: {
      executor: "ramping-vus",
      exec: "browse",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m", target: 40 },
        { duration: "30s", target: 0 },
      ],
    },
    write: {
      executor: "constant-vus",
      exec: "write",
      vus: 10,
      duration: "2m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.02"],
    "http_req_duration{scenario:browse}": ["p(95)<400"],
    "http_req_duration{scenario:write}": ["p(95)<800"],
  },
};

export function browse() {
  const res = http.get(`${BASE_URL}/api/clients/?ordering=-created_at`, {
    tags: { scenario: "browse" },
  });
  check(res, { "list 200": (r) => r.status === 200 });
  sleep(Math.random() * 2);
}

export function write() {
  const tags = { tags: { scenario: "write" } };

  const payload = JSON.stringify({
    name: randomName(),
    email: `load-${uuidv4()}@example.com`,
    risk_profile: "moderate",
  });

  const created = http.post(`${BASE_URL}/api/clients/`, payload, { ...JSON_HEADERS, ...tags });
  if (!check(created, { "create 201": (r) => r.status === 201 })) {
    return;
  }

  const id = created.json("id");

  const got = http.get(`${BASE_URL}/api/clients/${id}/`, tags);
  check(got, { "retrieve 200": (r) => r.status === 200 });

  const deleted = http.del(`${BASE_URL}/api/clients/${id}/`, null, tags);
  check(deleted, { "delete 204": (r) => r.status === 204 });

  sleep(1);
}

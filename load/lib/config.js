// Shared configuration for all scenarios.
// BASE_URL defaults to the in-network api service; override for host runs:
//   k6 run -e BASE_URL=http://localhost:8000 load/scenarios/smoke.js
export const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const JSON_HEADERS = { headers: { "Content-Type": "application/json" } };

// Default pass/fail gates. Tighten per scenario as needed.
export const baseThresholds = {
  http_req_failed: ["rate<0.01"],
  http_req_duration: ["p(95)<500"],
};
